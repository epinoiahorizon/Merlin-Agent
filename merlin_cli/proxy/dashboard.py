"""Public status + top-up dashboard for the metered proxy.

One small aiohttp app that answers the two questions a paying customer actually asks:

* "is the model I am paying for actually up, fast, and the model it claims to be?" — answered from
  :class:`~merlin_cli.proxy.probe.ProbeStore` (measured samples, not marketing copy);
* "how do I put money in?" — a QRIS invoice whose nominal is unique per customer, built by stamping
  the amount into the static merchant payload (see :mod:`merlin_cli.proxy.qris`).

It is deliberately separate from the OpenAI-compatible proxy: the billing plane must be able to say
"this upstream is down" even when the proxy is the thing that is down.
"""

from __future__ import annotations

import html
import random
import secrets
import time
from typing import Optional

from merlin_cli.proxy import qris, topup
from merlin_cli.proxy.tenants import DuplicateInvoiceAmount, LedgerStore

try:
    from aiohttp import web

    AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    web = None  # type: ignore[assignment]
    AIOHTTP_AVAILABLE = False

_CSS = """
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:#0b0d10;color:#e6e8eb;font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
main{max-width:1080px;margin:0 auto;padding:32px 20px 64px}
h1{font-size:20px;letter-spacing:.14em;text-transform:uppercase;margin:0 0 4px;font-weight:600}
h2{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:#8b949e;margin:36px 0 10px;font-weight:600}
.sub{color:#8b949e;margin:0 0 28px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.card{border:1px solid #1f242c;border-radius:10px;padding:14px 16px;background:#0f1216}
.k{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8b949e}
.v{font-size:26px;font-weight:600;margin-top:6px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #1b2027}
th{color:#8b949e;font-weight:500;font-size:11px;letter-spacing:.1em;text-transform:uppercase}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.ok{color:#3fb950}.bad{color:#f85149}.warn{color:#d29922}
form{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin:14px 0 0}
label{display:block;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#8b949e;margin-bottom:4px}
input{background:#0f1216;border:1px solid #2a3038;color:#e6e8eb;border-radius:8px;padding:9px 11px;font:inherit;min-width:180px}
button{background:#1f6feb;border:0;color:#fff;border-radius:8px;padding:10px 16px;font:inherit;cursor:pointer}
button.ghost{background:#21262d}
.qr{background:#fff;padding:12px;border-radius:12px;display:inline-block;margin-top:12px}
.note{color:#8b949e;font-size:12px;margin-top:10px}
a{color:#58a6ff}
"""


def _fmt(value: int | float) -> str:
    return f"{value:,}".replace(",", ".")


def _ident_class(identity: str) -> str:
    return "ok" if identity == "ok" else "bad"


def _resolve_tenant(ledger: LedgerStore, name: str) -> str:
    """Tenant id for ``name``, creating the tenant on first top-up."""
    existing = ledger.find_tenant_by_name(name)
    if existing:
        return existing
    return ledger.create_tenant(name)


def _new_invoice(
    ledger: LedgerStore, tenant_id: str, base_amount: int, static_payload: str, ttl_s: int = 1800
) -> dict:
    """Invoice with a unique nominal so a QRIS notification maps to exactly one customer.

    Up to 999 distinct pendings can share a base amount; past that the caller gets the last error
    instead of an invoice that two customers could pay into.
    """
    last_error: Optional[Exception] = None
    candidates = random.sample(range(1, 1000), k=min(999, 64))
    for offset in candidates:
        amount = int(base_amount) + offset
        try:
            payload = qris.with_amount(static_payload, amount)
        except qris.QrisError:
            payload = ""
        try:
            return ledger.create_invoice(tenant_id, amount, payload, ttl_s=ttl_s)
        except DuplicateInvoiceAmount as exc:
            last_error = exc
            continue
    raise DuplicateInvoiceAmount(str(last_error) if last_error else "could not allocate a unique amount")


def _page(
    ledger: LedgerStore,
    probes,
    static_payload: str,
    invoice_id: str = "",
    currency: str = "IDR",
    show_pay_button: bool = False,
) -> str:
    merchant = qris.merchant_name(static_payload) or "merchant"
    rows_status = probes.summary(hours=24) if probes is not None else []
    prices = ledger.models()
    pending = ledger.pending_invoices()
    tenants = ledger.conn.execute("SELECT COUNT(*) AS n FROM tenants").fetchone()["n"]
    probes_24h = sum(row["probes"] for row in rows_status)
    swapped = [row for row in rows_status if row["identity"] != "ok"]

    parts: list[str] = []
    parts.append(_CSS.join(["<style>", "</style>"]))
    parts.append(
        "<main><h1>Merlin Gateway</h1>"
        f'<p class="sub">Status terukur &amp; top-up QRIS · merchant <strong>{html.escape(merchant)}</strong>'
        f" · {html.escape(currency)}</p>"
    )
    parts.append('<div class="grid">')
    for label, value in (
        ("model terpantau", len(rows_status)),
        ("probe 24 jam", probes_24h),
        ("model berharga", len(prices)),
        ("tenant", tenants),
    ):
        parts.append(f'<div class="card"><div class="k">{label}</div><div class="v">{_fmt(value)}</div></div>')
    identity_value = "aman" if not swapped else f"{len(swapped)} anomali"
    identity_class = "ok" if not swapped else "bad"
    parts.append(
        f'<div class="card"><div class="k">identitas model</div>'
        f'<div class="v {identity_class}">{html.escape(identity_value)}</div></div>'
    )
    parts.append("</div>")

    # -- status table
    parts.append("<h2>Uptime &amp; latency (24 jam, sampel nyata)</h2>")
    if rows_status:
        parts.append(
            "<table><tr><th>upstream</th><th>model</th><th class=num>uptime</th>"
            "<th class=num>p50</th><th class=num>p95</th><th>identitas</th></tr>"
        )
        for row in rows_status:
            parts.append(
                f"<tr><td>{html.escape(row['upstream'])}</td><td>{html.escape(row['model'])}</td>"
                f"<td class=num>{row['uptime_pct']:.1f}%</td>"
                f"<td class=num>{row['p50_ms']:.0f} ms</td><td class=num>{row['p95_ms']:.0f} ms</td>"
                f"<td class={_ident_class(row['identity'])}>{html.escape(row['identity'])}</td></tr>"
            )
        parts.append("</table>")
    else:
        parts.append('<p class="note">Belum ada probe. Jalankan <code>merlin proxy probe run</code>.</p>')

    # -- price book
    parts.append("<h2>Harga per 1 juta token (micro, sebelum PPN)</h2>")
    if prices:
        parts.append(
            "<table><tr><th>model</th><th class=num>input</th><th class=num>output</th>"
            "<th class=num>cache-read</th></tr>"
        )
        for row in prices:
            cache = row["cache_read_micros_per_m"]
            parts.append(
                f"<tr><td>{html.escape(row['model'])}</td>"
                f"<td class=num>{_fmt(row['in_micros_per_m'])}</td>"
                f"<td class=num>{_fmt(row['out_micros_per_m'])}</td>"
                f"<td class=num>{'-' if cache is None else _fmt(cache)}</td></tr>"
            )
        parts.append("</table>")
    else:
        parts.append('<p class="note">Belum ada harga. Jalankan <code>merlin proxy catalog sync</code>.</p>')

    # -- top up
    parts.append("<h2>Top up via QRIS</h2>")
    parts.append(
        '<form method="post" action="/topup">'
        '<div><label for="tenant">nama tenant</label>'
        '<input id="tenant" name="tenant" required placeholder="acme"></div>'
        '<div><label for="amount">nominal (Rp)</label>'
        '<input id="amount" name="amount" required inputmode="numeric" placeholder="25000"></div>'
        '<button type="submit">Buat invoice</button></form>'
    )
    parts.append(
        '<p class="note">Nominal akhirnya ditambah 1–999 rupiah secara acak supaya tiap pembayaran '
        "bisa dicocokkan ke satu invoice tanpa kode referensi.</p>"
    )
    if invoice_id:
        invoice = ledger.invoice(invoice_id)
        if invoice and invoice["status"] == "pending":
            parts.append(
                '<div class="card" style="margin-top:16px">'
                f'<div class="k">invoice {html.escape(invoice["id"])}</div>'
                f'<div class="v">Rp {_fmt(invoice["amount_idr"])}</div>'
                f'<div class="qr"><img alt="QRIS" width="260" src="/qr/{html.escape(invoice["id"])}.png"></div>'
                '<p class="note">Scan dengan aplikasi bank / e-wallet apa pun yang mendukung QRIS, '
                "lalu bayar <strong>tepat</strong> sejumlah nominal di atas.</p>"
            )
            if show_pay_button:
                parts.append(
                    f'<form method="post" action="/api/invoices/{html.escape(invoice["id"])}/pay">'
                    '<button class="ghost" type="submit">Tandai sudah dibayar</button></form>'
                )
            else:
                parts.append(
                    '<p class="note">Konfirmasi dilakukan operator: <code>merlin proxy payments '
                    "--claim &lt;payment&gt; --invoice &lt;id&gt;</code> atau impor mutasi.</p>"
                )
            parts.append("</div>")
        elif invoice:
            parts.append(f'<p class="note">Invoice {html.escape(invoice_id)} sudah {html.escape(invoice["status"])}.</p>')

    # -- pending invoices
    if pending:
        parts.append("<h2>Invoice menunggu pembayaran</h2>")
        parts.append("<table><tr><th>invoice</th><th>tenant</th><th class=num>nominal</th><th>dibuat</th></tr>")
        for invoice in pending[:20]:
            created = time.strftime("%Y-%m-%d %H:%M", time.localtime(invoice["created_at"]))
            parts.append(
                f'<tr><td><a href="/?invoice={html.escape(invoice["id"])}">{html.escape(invoice["id"])}</a></td>'
                f'<td>{html.escape(invoice["tenant_id"])}</td>'
                f'<td class=num>Rp {_fmt(invoice["amount_idr"])}</td><td>{created}</td></tr>'
            )
        parts.append("</table>")

    parts.append(
        '<p class="note" style="margin-top:40px">Data di halaman ini berasal dari database billing '
        "yang sama dengan yang dipakai gateway untuk menagih — bukan laporan terpisah.</p></main>"
    )
    return "<!doctype html><html lang=id><head><meta charset=utf-8>" \
        '<meta name=viewport content="width=device-width,initial-scale=1">' \
        "<title>Merlin Gateway — status &amp; top up</title>" + "".join(parts) + "</html>"


def create_dashboard_app(
    ledger: LedgerStore,
    probes=None,
    static_payload: str = "",
    admin_token: str = "",
    currency: str = "IDR",
    webhook_secret: str = "",
    invoice_ttl_s: int = 1800,
):
    """Build the aiohttp dashboard app."""
    if not AIOHTTP_AVAILABLE:
        raise RuntimeError("aiohttp is required for the dashboard")
    app = web.Application()
    # Money-confirming endpoints always require a token. When the operator did not supply one we
    # generate it and print it at startup, so a public page can never credit anyone by accident.
    effective_admin_token = admin_token or secrets.token_urlsafe(18)
    app.admin_token = effective_admin_token  # read by the CLI banner; attribute avoids AppKey churn
    show_pay_button = bool(admin_token)

    def _admin_ok(request: "web.Request") -> bool:
        provided = request.headers.get("X-Admin-Token", "") or request.query.get("token", "")
        return secrets.compare_digest(provided, effective_admin_token)

    async def handle_index(request: "web.Request") -> "web.Response":
        invoice_id = request.query.get("invoice", "")
        body = _page(
            ledger,
            probes,
            static_payload,
            invoice_id=invoice_id,
            currency=currency,
            show_pay_button=show_pay_button,
        )
        return web.Response(text=body, content_type="text/html")

    async def handle_status(request: "web.Request") -> "web.Response":
        summaries = probes.summary(hours=24) if probes is not None else []
        return web.json_response(
            {
                "generated_at": int(time.time()),
                "currency": currency,
                "merchant": qris.merchant_name(static_payload),
                "models": summaries,
                "prices": ledger.models(),
                "pending_invoices": len(ledger.pending_invoices()),
            }
        )

    async def handle_topup(request: "web.Request") -> "web.Response":
        form = await request.post()
        tenant_name = str(form.get("tenant") or "").strip()
        raw_amount = str(form.get("amount") or "").strip().replace(".", "").replace(",", "")
        if not tenant_name or not raw_amount.isdigit() or int(raw_amount) <= 0:
            return web.Response(text="tenant dan nominal (angka) wajib diisi", status=400)
        tenant_id = _resolve_tenant(ledger, tenant_name)
        invoice = _new_invoice(ledger, tenant_id, int(raw_amount), static_payload, ttl_s=invoice_ttl_s)
        raise web.HTTPSeeOther(location=f"/?invoice={invoice['id']}")

    async def handle_qr(request: "web.Request") -> "web.Response":
        invoice = ledger.invoice(request.match_info.get("invoice_id", ""))
        if invoice is None:
            return web.Response(text="invoice tidak ditemukan", status=404)
        payload = invoice["payload"] or static_payload
        if not payload:
            return web.Response(text="QRIS belum dikonfigurasi", status=503)
        try:
            png = qris.render_png(payload)
        except qris.QrisError:
            return web.Response(text="render PNG butuh paket 'segno'", status=503)
        return web.Response(body=png, content_type="image/png", headers={"Cache-Control": "no-store"})

    async def handle_pay(request: "web.Request") -> "web.Response":
        if not _admin_ok(request):
            return web.json_response({"error": "admin token required"}, status=403)
        invoice_id = request.match_info.get("invoice_id", "")
        credited = ledger.pay_invoice(invoice_id)
        if request.headers.get("Accept", "").startswith("application/json"):
            return web.json_response({"invoice": invoice_id, "credited_micros": credited})
        raise web.HTTPSeeOther(location=f"/?invoice={invoice_id}")

    async def handle_webhook(request: "web.Request") -> "web.Response":
        """Acquirer callback: verify, match by unique nominal, never lose an event."""
        raw = await request.read()
        signature = request.headers.get("X-Signature") or request.headers.get("X-Callback-Signature", "")
        if not topup.verify_signature(webhook_secret, raw, signature):
            return web.json_response({"error": "bad signature"}, status=401)
        payload = topup.parse_body(raw)
        if payload is None:
            return web.json_response({"error": "body must be a JSON object"}, status=400)
        result = topup.apply_payment(
            ledger, payload, provider=str(request.headers.get("X-Provider", "")), raw=raw.decode("utf-8", "replace")
        )
        return web.json_response(result)

    async def handle_payments(request: "web.Request") -> "web.Response":
        if not _admin_ok(request):
            return web.json_response({"error": "admin token required"}, status=403)
        rows = ledger.payments(status=request.query.get("status", ""), limit=int(request.query.get("limit", 50)))
        return web.json_response({"payments": rows, "unmatched": len(ledger.payments(status="unmatched", limit=500))})

    async def handle_claim(request: "web.Request") -> "web.Response":
        if not _admin_ok(request):
            return web.json_response({"error": "admin token required"}, status=403)
        try:
            body = await request.json()
        except ValueError:
            body = {}
        invoice_id = str((body or {}).get("invoice") or "")
        if not invoice_id:
            return web.json_response({"error": "invoice is required"}, status=400)
        credited = ledger.claim_payment(request.match_info.get("payment_id", ""), invoice_id)
        return web.json_response({"invoice": invoice_id, "credited_micros": credited})

    app.router.add_get("/", handle_index)
    app.router.add_get("/api/status", handle_status)
    app.router.add_post("/topup", handle_topup)
    app.router.add_post("/api/invoices/{invoice_id}/pay", handle_pay)
    app.router.add_post("/api/webhooks/qris", handle_webhook)
    app.router.add_get("/api/payments", handle_payments)
    app.router.add_post("/api/payments/{payment_id}/claim", handle_claim)
    app.router.add_get("/qr/{invoice_id}.png", handle_qr)
    return app


__all__ = ["create_dashboard_app", "_new_invoice", "_page"]
