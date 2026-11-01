"""Inbound top-up payments: webhook intake, matching, and manual reconciliation.

The hard part of taking money by QRIS without an acquirer is that nothing calls you back. With an
acquirer (Midtrans, Xendit, DOKU, Pakasir, …) something eventually does, and every one of them sends
a different shape. This module is the adapter seam:

* :func:`extract_amount` finds the paid amount across the field names those providers use;
* :func:`effective_status` maps their transaction states onto "count this" / "ignore this";
* :func:`apply_payment` matches the amount against a pending invoice (unique nominal — see
  :meth:`~merlin_cli.proxy.tenants.LedgerStore.create_invoice`) and records everything it sees,
  including payments it could not match, so money never vanishes silently;
* :func:`verify_signature` checks an HMAC-SHA256 signature when the provider supports one.

Anything unmatched lands in ``payments`` with ``status='unmatched'`` and can be claimed later with
:meth:`~merlin_cli.proxy.tenants.LedgerStore.claim_payment`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Mapping, Optional

AMOUNT_KEYS = (
    "amount_idr",
    "gross_amount",
    "amount",
    "nominal",
    "total",
    "paid_amount",
    "transaction_amount",
    "payment_amount",
)
NESTED_KEYS = ("transaction_details", "transaction", "data", "payment", "payload")

PAID_STATES = {"settlement", "capture", "success", "paid", "completed", "succeeded", "settled"}
IGNORED_STATES = {
    "pending",
    "deny",
    "denied",
    "expire",
    "expired",
    "cancel",
    "canceled",
    "cancelled",
    "failure",
    "failed",
    "refund",
    "refunded",
}
STATUS_KEYS = ("transaction_status", "payment_status", "transaction_state", "status", "state")

_AMOUNT_PATTERN = re.compile(r"^(\d+)(?:[.,](\d{1,2}))?$")


def to_idr(value: object) -> Optional[int]:
    """Best-effort integer rupiah from the ways providers express money.

    ``25889``, ``"25889"``, ``"25889.00"``, ``"25.889"`` (Indonesian thousand separator) and
    ``"Rp 25.889"`` all resolve to ``25889``; anything else returns ``None`` rather than a guess.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    text = str(value or "").strip().lower().replace("rp", "").replace(" ", "")
    if not text:
        return None
    text = text.replace("_", "")
    match = _AMOUNT_PATTERN.match(text)
    if match:
        return int(match.group(1))
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", text):  # 25.889 / 25,889
        return int(re.sub(r"[.,]", "", text))
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def extract_amount(payload: object) -> Optional[int]:
    """First plausible amount found at the top level or one level down."""
    if not isinstance(payload, Mapping):
        return None
    for key in AMOUNT_KEYS:
        if key in payload:
            amount = to_idr(payload.get(key))
            if amount:
                return amount
    for nested in NESTED_KEYS:
        child = payload.get(nested)
        if isinstance(child, Mapping):
            for key in AMOUNT_KEYS:
                if key in child:
                    amount = to_idr(child.get(key))
                    if amount:
                        return amount
    return None


def effective_status(payload: object) -> str:
    """``paid`` when the notification should credit, ``ignored`` when it is noise."""
    if not isinstance(payload, Mapping):
        return "paid"
    for key in STATUS_KEYS:
        value = payload.get(key)
        if isinstance(value, str):
            state = value.strip().lower()
            if state in IGNORED_STATES:
                return "ignored"
            if state in PAID_STATES:
                return "paid"
    # No recognisable state (plain {"amount": …}): treat as a settlement notification.
    return "paid"


def verify_signature(secret: str, raw_body: bytes, signature: str) -> bool:
    """HMAC-SHA256 of the raw body, hex, constant-time compared."""
    if not secret:
        return True
    if not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    provided = signature.strip().lower().removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


def apply_payment(ledger, payload: object, *, provider: str = "", raw: str = "") -> dict:
    """Credit the invoice whose unique nominal matches, else record an unmatched payment."""
    amount = extract_amount(payload)
    if amount is None:
        payment = ledger.record_payment(0, status="unmatched", provider=provider, raw=raw)
        return {
            "result": "no_amount",
            "payment": payment["id"],
            "credited_micros": 0,
            "invoice": None,
        }

    state = effective_status(payload)
    if state == "ignored":
        payment = ledger.record_payment(amount, status="ignored", provider=provider, raw=raw)
        return {"result": "ignored", "payment": payment["id"], "credited_micros": 0, "invoice": None}

    invoice = ledger.find_pending_by_amount(amount)
    if invoice is None:
        payment = ledger.record_payment(amount, status="unmatched", provider=provider, raw=raw)
        return {
            "result": "unmatched",
            "payment": payment["id"],
            "credited_micros": 0,
            "invoice": None,
            "amount_idr": amount,
        }

    credited = ledger.pay_invoice(invoice["id"])
    payment = ledger.record_payment(
        amount,
        invoice_id=invoice["id"],
        status="matched" if credited else "duplicate",
        provider=provider,
        raw=raw,
    )
    return {
        "result": "matched" if credited else "duplicate",
        "payment": payment["id"],
        "credited_micros": credited,
        "invoice": invoice["id"],
        "amount_idr": amount,
    }


def parse_body(raw: bytes) -> Optional[dict]:
    """JSON object from a webhook body, or ``None`` when it is not usable JSON."""
    try:
        parsed = json.loads(raw.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


__all__ = [
    "to_idr",
    "extract_amount",
    "effective_status",
    "verify_signature",
    "apply_payment",
    "parse_body",
    "AMOUNT_KEYS",
    "PAID_STATES",
    "IGNORED_STATES",
]
