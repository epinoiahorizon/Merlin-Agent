"""Top-up intake tests: amount parsing, status mapping, signature, matching, expiry, claiming."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from aiohttp.test_utils import TestClient, TestServer

from merlin_cli.proxy import qris, topup
from merlin_cli.proxy.dashboard import _new_invoice, create_dashboard_app
from merlin_cli.proxy.tenants import MICROS_PER_UNIT, LedgerStore

STATIC = qris.build_from_parts(
    [qris.Tlv("26", "0016ID.CO.EXAMPLE.WWW01189360000000000000000215ID1024000000001")],
    merchant_name_value="EPINOIA HORIZON, Komputer",
    city="Tangerang Selat",
)


@pytest.fixture()
def ledger(tmp_path):
    with LedgerStore(tmp_path / "ledger.db") as store:
        yield store


# -- amount parsing ------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        (25889, 25889),
        ("25889", 25889),
        ("25889.00", 25889),
        ("25.889", 25889),
        ("25,889", 25889),
        ("Rp 25.889", 25889),
        (25889.0, 25889),
        ("", None),
        ("not money", None),
        (None, None),
        (True, None),
    ],
)
def test_to_idr_handles_provider_formats(raw, expected) -> None:
    assert topup.to_idr(raw) == expected


def test_extract_amount_reads_top_level_and_nested() -> None:
    assert topup.extract_amount({"amount": "10000"}) == 10000
    assert topup.extract_amount({"gross_amount": "50000.00"}) == 50000
    assert topup.extract_amount({"transaction_details": {"gross_amount": "25000"}}) == 25000
    assert topup.extract_amount({"order_id": "x"}) is None


def test_effective_status_maps_provider_states() -> None:
    assert topup.effective_status({"transaction_status": "settlement"}) == "paid"
    assert topup.effective_status({"transaction_status": "capture"}) == "paid"
    assert topup.effective_status({"status": "PENDING"}) == "ignored"
    assert topup.effective_status({"status": "expire"}) == "ignored"
    assert topup.effective_status({"amount": 1000}) == "paid"  # plain payload: assume settlement


def test_verify_signature_round_trip() -> None:
    body = b'{"amount": 1000}'
    signature = hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert topup.verify_signature("s3cret", body, signature) is True
    assert topup.verify_signature("s3cret", body, signature.upper()) is True
    assert topup.verify_signature("s3cret", body, "sha256=" + signature) is True
    assert topup.verify_signature("s3cret", body, "deadbeef") is False
    assert topup.verify_signature("s3cret", body, "") is False
    assert topup.verify_signature("", body, "") is True  # no secret configured


# -- matching ------------------------------------------------------------------------------
def test_apply_payment_matches_the_invoice_with_that_nominal(ledger) -> None:
    tenant = ledger.create_tenant("acme")
    invoice = ledger.create_invoice(tenant, 25_889)
    result = topup.apply_payment(ledger, {"amount": "25889"})
    assert result["result"] == "matched"
    assert result["invoice"] == invoice["id"]
    assert result["credited_micros"] == 25_889 * MICROS_PER_UNIT
    assert ledger.balance(tenant) == 25_889 * MICROS_PER_UNIT


def test_duplicate_webhook_does_not_credit_twice(ledger) -> None:
    tenant = ledger.create_tenant("acme")
    ledger.create_invoice(tenant, 10_000)
    first = topup.apply_payment(ledger, {"amount": 10_000})
    second = topup.apply_payment(ledger, {"amount": 10_000})
    assert first["result"] == "matched"
    assert second["result"] == "unmatched"  # the invoice is no longer pending
    assert ledger.balance(tenant) == 10_000 * MICROS_PER_UNIT


def test_unknown_amount_is_recorded_not_dropped(ledger) -> None:
    result = topup.apply_payment(ledger, {"amount": "77777"}, provider="xendit")
    assert result["result"] == "unmatched"
    stored = ledger.payment(result["payment"])
    assert stored is not None and stored["status"] == "unmatched"
    assert stored["amount_idr"] == 77_777 and stored["provider"] == "xendit"
    assert ledger.payments(status="unmatched")


def test_ignored_status_is_logged_without_crediting(ledger) -> None:
    tenant = ledger.create_tenant("acme")
    ledger.create_invoice(tenant, 10_000)
    result = topup.apply_payment(ledger, {"amount": 10_000, "transaction_status": "pending"})
    assert result["result"] == "ignored"
    assert ledger.balance(tenant) == 0
    assert ledger.invoice(ledger.pending_invoices()[0]["id"])["status"] == "pending"


def test_payload_without_amount_is_logged(ledger) -> None:
    result = topup.apply_payment(ledger, {"order_id": "abc"})
    assert result["result"] == "no_amount"
    assert ledger.payment(result["payment"])["amount_idr"] == 0


# -- expiry & claiming ---------------------------------------------------------------------
def test_invoice_expiry_frees_the_nominal(ledger) -> None:
    tenant = ledger.create_tenant("acme")
    invoice = ledger.create_invoice(tenant, 5_000, ttl_s=60)
    assert ledger.expire_invoices(now=int(time.time()) + 61) == 1
    assert ledger.invoice(invoice["id"])["status"] == "expired"
    assert ledger.pay_invoice(invoice["id"]) == 0  # expired invoices cannot be paid
    # The nominal is reusable for a new customer.
    fresh = ledger.create_invoice(tenant, 5_000, ttl_s=60)
    assert fresh["id"] != invoice["id"]


def test_claim_attaches_an_unmatched_payment_to_an_invoice(ledger) -> None:
    tenant = ledger.create_tenant("acme")
    invoice = ledger.create_invoice(tenant, 12_345)
    unmatched = ledger.record_payment(12_345, status="unmatched", provider="manual")
    credited = ledger.claim_payment(unmatched["id"], invoice["id"])
    assert credited == 12_345 * MICROS_PER_UNIT
    assert ledger.payment(unmatched["id"])["status"] == "matched"
    assert ledger.claim_payment(unmatched["id"], invoice["id"]) == 0  # already claimed


# -- webhook endpoint ----------------------------------------------------------------------
pytestmark_async = pytest.mark.asyncio


class _H:
    def __init__(self, client, ledger):
        self.client, self.ledger = client, ledger


async def _harness(tmp_path, secret: str = ""):
    ledger = LedgerStore(tmp_path / "ledger.db")
    client = TestClient(TestServer(create_dashboard_app(ledger, None, STATIC, webhook_secret=secret)))
    await client.start_server()
    return _H(client, ledger)


@pytest.mark.asyncio
async def test_webhook_matches_and_credits(tmp_path) -> None:
    h = await _harness(tmp_path)
    try:
        tenant = h.ledger.create_tenant("acme")
        invoice = _new_invoice(h.ledger, tenant, 30_000, STATIC)
        response = await h.client.post(
            "/api/webhooks/qris",
            data=json.dumps({"gross_amount": f"{invoice['amount_idr']}.00", "transaction_status": "settlement"}),
            headers={"Content-Type": "application/json"},
        )
        payload = await response.json()
        assert response.status == 200
        assert payload["result"] == "matched" and payload["invoice"] == invoice["id"]
        assert h.ledger.balance(tenant) == invoice["amount_idr"] * MICROS_PER_UNIT
    finally:
        await h.client.close()
        h.ledger.close()


@pytest.mark.asyncio
async def test_webhook_rejects_a_bad_signature(tmp_path) -> None:
    h = await _harness(tmp_path, secret="s3cret")
    try:
        tenant = h.ledger.create_tenant("acme")
        invoice = _new_invoice(h.ledger, tenant, 10_000, STATIC)
        body = json.dumps({"amount": invoice["amount_idr"]})
        bad = await h.client.post(
            "/api/webhooks/qris", data=body,
            headers={"Content-Type": "application/json", "X-Signature": "nope"},
        )
        assert bad.status == 401
        assert h.ledger.balance(tenant) == 0

        good_sig = hmac.new(b"s3cret", body.encode(), hashlib.sha256).hexdigest()
        good = await h.client.post(
            "/api/webhooks/qris", data=body,
            headers={"Content-Type": "application/json", "X-Signature": good_sig},
        )
        assert good.status == 200 and (await good.json())["result"] == "matched"
    finally:
        await h.client.close()
        h.ledger.close()


@pytest.mark.asyncio
async def test_webhook_rejects_non_json(tmp_path) -> None:
    h = await _harness(tmp_path)
    try:
        response = await h.client.post(
            "/api/webhooks/qris", data="amount=1000", headers={"Content-Type": "text/plain"}
        )
        assert response.status == 400
    finally:
        await h.client.close()
        h.ledger.close()
