"""Dashboard tests: status page, QRIS invoice flow, crediting, idempotent payment."""

from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

from merlin_cli.proxy import qris
from merlin_cli.proxy.dashboard import _new_invoice, create_dashboard_app
from merlin_cli.proxy.probe import ProbeResult, ProbeStore
from merlin_cli.proxy.tenants import MICROS_PER_UNIT, LedgerStore

pytestmark = pytest.mark.asyncio

STATIC = qris.build_from_parts(
    [qris.Tlv("26", "0016ID.CO.EXAMPLE.WWW01189360000000000000000215ID1024000000001")],
    merchant_name_value="EPINOIA HORIZON, Komputer",
    city="Tangerang Selat",
    postal_code="15315",
)


class Harness:
    def __init__(self, ledger, probes, client):
        self.ledger, self.probes, self.client = ledger, probes, client


async def _harness(tmp_path, admin_token: str = ""):
    ledger = LedgerStore(tmp_path / "ledger.db")
    ledger.set_price("deepseek/deepseek-v4-flash", 104_650, 209_300, 20_930)
    probes = ProbeStore(tmp_path / "probes.db")
    probes.record(ProbeResult("mock", "deepseek/deepseek-v4-flash", True, 200, 41.0, 40, 4, "deepseek-v4-flash", "deepseek"))
    client = TestClient(TestServer(create_dashboard_app(ledger, probes, STATIC, admin_token=admin_token)))
    await client.start_server()
    return Harness(ledger, probes, client)


async def _close(harness: Harness) -> None:
    await harness.client.close()
    harness.ledger.close()
    harness.probes.close()


# -- page & api ----------------------------------------------------------------------------
async def test_status_page_renders_measured_data(tmp_path) -> None:
    h = await _harness(tmp_path)
    try:
        response = await h.client.get("/")
        assert response.status == 200
        assert response.content_type == "text/html"
        body = await response.text()
        assert "EPINOIA HORIZON" in body          # merchant from the QRIS payload
        assert "deepseek/deepseek-v4-flash" in body  # price book row
        assert "41 ms" in body                     # measured p50
        assert "100.0%" in body                     # uptime from the probe sample
    finally:
        await _close(h)


async def test_status_api_is_json(tmp_path) -> None:
    h = await _harness(tmp_path)
    try:
        payload = await (await h.client.get("/api/status")).json()
        assert payload["currency"] == "IDR"
        assert payload["merchant"] == "EPINOIA HORIZON, Komputer"
        assert payload["models"][0]["model"] == "deepseek/deepseek-v4-flash"
        assert payload["prices"][0]["in_micros_per_m"] == 104_650
        assert payload["pending_invoices"] == 0
    finally:
        await _close(h)


# -- top up --------------------------------------------------------------------------------
async def test_topup_creates_a_unique_nominal_invoice_and_redirects(tmp_path) -> None:
    h = await _harness(tmp_path)
    try:
        response = await h.client.post(
            "/topup", data={"tenant": "acme", "amount": "25000"}, allow_redirects=False
        )
        assert response.status == 303
        location = response.headers["Location"]
        assert location.startswith("/?invoice=inv_")

        invoice_id = location.rsplit("=", 1)[1]
        invoice = h.ledger.invoice(invoice_id)
        assert invoice is not None and invoice["status"] == "pending"
        assert 25_001 <= invoice["amount_idr"] <= 25_999          # unique nominal inside the band
        assert qris.amount_of(invoice["payload"]) == str(invoice["amount_idr"])
        assert qris.validate(invoice["payload"]) is True

        # The invoice page shows the QR for that invoice.
        page = await (await h.client.get(location)).text()
        assert invoice_id in page and "Rp " in page
    finally:
        await _close(h)


async def test_two_invoices_for_the_same_base_amount_differ(tmp_path) -> None:
    ledger = LedgerStore(tmp_path / "ledger.db")
    tenant = ledger.create_tenant("acme")
    first = _new_invoice(ledger, tenant, 25_000, STATIC)
    second = _new_invoice(ledger, tenant, 25_000, STATIC)
    assert first["amount_idr"] != second["amount_idr"]
    assert first["payload"] != second["payload"]
    ledger.close()


async def test_qr_png_is_served_for_a_pending_invoice(tmp_path) -> None:
    h = await _harness(tmp_path)
    try:
        tenant = h.ledger.create_tenant("acme")
        invoice = _new_invoice(h.ledger, tenant, 10_000, STATIC)
        response = await h.client.get(f"/qr/{invoice['id']}.png")
        assert response.status == 200
        assert response.content_type == "image/png"
        body = await response.read()
        assert body.startswith(b"\x89PNG") and len(body) > 200
    finally:
        await _close(h)


async def test_qr_for_unknown_invoice_is_404(tmp_path) -> None:
    h = await _harness(tmp_path)
    try:
        assert (await h.client.get("/qr/inv_missing.png")).status == 404
    finally:
        await _close(h)


async def test_topup_rejects_bad_input(tmp_path) -> None:
    h = await _harness(tmp_path)
    try:
        assert (await h.client.post("/topup", data={"tenant": "", "amount": "100"})).status == 400
        assert (await h.client.post("/topup", data={"tenant": "x", "amount": "abc"})).status == 400
    finally:
        await _close(h)


# -- payment -------------------------------------------------------------------------------
async def test_pay_credits_the_ledger_exactly_once(tmp_path) -> None:
    h = await _harness(tmp_path)
    try:
        tenant = h.ledger.create_tenant("acme", initial_micros=0)
        invoice = _new_invoice(h.ledger, tenant, 20_000, STATIC)

        response = await h.client.post(f"/api/invoices/{invoice['id']}/pay", allow_redirects=False)
        assert response.status == 303
        assert h.ledger.balance(tenant) == invoice["amount_idr"] * MICROS_PER_UNIT
        entries = h.ledger.entries(tenant)
        assert entries[0]["reason"] == f"topup:{invoice['id']}"

        # A second notification must not credit twice.
        again = await h.client.post(
            f"/api/invoices/{invoice['id']}/pay",
            headers={"Accept": "application/json"},
        )
        assert (await again.json())["credited_micros"] == 0
        assert h.ledger.balance(tenant) == invoice["amount_idr"] * MICROS_PER_UNIT
        assert h.ledger.invoice(invoice["id"])["status"] == "paid"
    finally:
        await _close(h)


async def test_pay_requires_the_admin_token_when_configured(tmp_path) -> None:
    h = await _harness(tmp_path, admin_token="s3cret")
    try:
        tenant = h.ledger.create_tenant("acme")
        invoice = _new_invoice(h.ledger, tenant, 5_000, STATIC)
        denied = await h.client.post(
            f"/api/invoices/{invoice['id']}/pay", headers={"Accept": "application/json"}
        )
        assert denied.status == 403
        assert h.ledger.balance(tenant) == 0

        allowed = await h.client.post(
            f"/api/invoices/{invoice['id']}/pay",
            headers={"Accept": "application/json", "X-Admin-Token": "s3cret"},
        )
        assert (await allowed.json())["credited_micros"] == invoice["amount_idr"] * MICROS_PER_UNIT
    finally:
        await _close(h)
