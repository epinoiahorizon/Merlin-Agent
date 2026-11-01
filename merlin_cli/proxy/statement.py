"""Import a merchant statement and match it against pending invoices.

A DANA Bisnis (or any) merchant QRIS gives you a *statement*, not a webhook: money lands, and the
only record is the transaction list in the app (exportable as CSV) or the notification text. This
module turns either into the same :class:`StatementRow` list and feeds it to the ledger, so top-ups
can be confirmed without an acquirer account.

Deliberate rules:

* rows with a **discriminating identifier** (a date or a reference) are fingerprinted and de-duped,
  so re-importing yesterday's export never double-credits;
* rows with neither are kept (two identical amounts on the same day are real, distinct payments)
  and can only be reconciled once — a second identical row with no identifier is recorded as
  unmatched rather than silently merged;
* a negative amount is recorded as ``ignored`` (a refund is not a top-up);
* nothing is ever deleted: unmatched rows stay in ``payments`` for manual claiming.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from typing import Iterable, Optional

from merlin_cli.proxy.topup import to_idr

AMOUNT_HINTS = ("nominal", "amount", "jumlah", "kredit", "credit", "masuk", "total", "gross", "nilai")
DATE_HINTS = ("tanggal", "date", "waktu", "time", "jam", "timestamp")
REF_HINTS = ("reference", "ref", "kode", "order", "trx", "transaksi", "id", "no")

_DATE_PATTERN = re.compile(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})")
_RP_PATTERN = re.compile(r"rp\.?\s*([0-9][0-9.,]*)", re.IGNORECASE)
_REF_PATTERN = re.compile(r"(?:ref|no|id|kode)[:.\s]*([A-Za-z0-9\-_]{5,})", re.IGNORECASE)


@dataclass(frozen=True)
class StatementRow:
    amount_idr: int
    when: str = ""
    reference: str = ""
    description: str = ""

    @property
    def ignorable(self) -> bool:
        return self.amount_idr <= 0


@dataclass
class IngestReport:
    matched: int = 0
    unmatched: int = 0
    ignored: int = 0
    skipped: int = 0
    credited_micros: int = 0
    dry_run: bool = False
    items: list[dict] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.items is None:
            self.items = []

    def summary(self) -> str:
        prefix = "[dry-run] " if self.dry_run else ""
        return (
            f"{prefix}statement ingest: {self.matched} matched, {self.unmatched} unmatched, "
            f"{self.ignored} ignored, {self.skipped} already imported, "
            f"credited {self.credited_micros:,} micros"
        )


def _pick(headers: Iterable[str], hints: tuple[str, ...]) -> Optional[str]:
    lowered = {header.lower().strip(): header for header in headers}
    for hint in hints:
        for low, original in lowered.items():
            if hint in low:
                return original
    return None


def _signed_amount(value: object) -> Optional[int]:
    """Amount with its sign preserved — ``to_idr`` strips ``-``, which would turn a refund into a
    top-up (caught by a live statement import: ``-3.000`` came back as ``+3000``)."""
    text = str(value or "").strip()
    negative = text.startswith("-") or text.startswith("(") or "rp -" in text.lower()
    amount = to_idr(text.replace("(", "").replace(")", "").replace("rp -", "rp "))
    if amount is None:
        return None
    return -amount if negative else amount


def parse_csv(text: str) -> list[StatementRow]:
    """Rows from a CSV/TSV export; column names are matched by keyword, not by position."""
    text = (text or "").strip()
    if not text:
        return []
    try:
        dialect = csv.Sniffer().sniff(text[:2000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        return []
    amount_column = _pick(reader.fieldnames, AMOUNT_HINTS)
    if amount_column is None:
        return []
    date_column = _pick(reader.fieldnames, DATE_HINTS)
    ref_column = _pick(reader.fieldnames, REF_HINTS)
    rows: list[StatementRow] = []
    for record in reader:
        amount = _signed_amount(record.get(amount_column))
        if amount is None:
            continue
        rows.append(
            StatementRow(
                amount_idr=amount,
                when=str(record.get(date_column) or "") if date_column else "",
                reference=str(record.get(ref_column) or "") if ref_column else "",
                description=" ".join(str(value) for value in record.values() if value)[:300],
            )
        )
    return rows


def parse_text(text: str) -> list[StatementRow]:
    """Rows from notification lines / pasted email bodies: every line with an ``Rp`` amount."""
    rows: list[StatementRow] = []
    for line in (text or "").splitlines():
        match = _RP_PATTERN.search(line)
        if not match:
            continue
        amount = to_idr(match.group(1))
        if amount is None:
            continue
        negative = "-" in line[: match.start() + 1][-3:] or "refund" in line.lower()
        date_match = _DATE_PATTERN.search(line)
        ref_match = _REF_PATTERN.search(line)
        rows.append(
            StatementRow(
                amount_idr=-amount if negative else amount,
                when=date_match.group(1) if date_match else "",
                reference=ref_match.group(1) if ref_match else "",
                description=line.strip()[:300],
            )
        )
    return rows


def parse(text: str, fmt: str = "auto") -> list[StatementRow]:
    """``fmt`` is ``csv``, ``text`` or ``auto`` (CSV when a delimiter is detected)."""
    fmt = (fmt or "auto").lower()
    if fmt == "csv":
        return parse_csv(text)
    if fmt == "text":
        return parse_text(text)
    csv_rows = parse_csv(text)
    return csv_rows if csv_rows else parse_text(text)


def fingerprint(row: StatementRow, provider: str = "") -> str:
    """Dedupe key, or ``""`` when the row carries no discriminating identifier."""
    if not row.when and not row.reference:
        return ""
    material = f"{provider}|{row.amount_idr}|{row.when}|{row.reference}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def ingest(ledger, rows: Iterable[StatementRow], *, provider: str = "dana", dry_run: bool = False) -> IngestReport:
    """Match each row against a pending invoice and record everything seen."""
    report = IngestReport(dry_run=dry_run)
    for row in rows:
        key = fingerprint(row, provider)
        if key and ledger.payment_by_fingerprint(key) is not None:
            report.skipped += 1
            continue
        if row.ignorable:
            if not dry_run:
                ledger.record_payment(
                    row.amount_idr, status="ignored", provider=provider, raw=row.description, fingerprint=key
                )
            report.ignored += 1
            report.items.append({"amount": row.amount_idr, "result": "ignored"})
            continue

        invoice = ledger.find_pending_by_amount(row.amount_idr)
        if invoice is None:
            if not dry_run:
                ledger.record_payment(
                    row.amount_idr, status="unmatched", provider=provider, raw=row.description, fingerprint=key
                )
            report.unmatched += 1
            report.items.append({"amount": row.amount_idr, "result": "unmatched"})
            continue

        if dry_run:
            report.matched += 1
            report.items.append({"amount": row.amount_idr, "result": "would-match", "invoice": invoice["id"]})
            continue

        credited = ledger.pay_invoice(invoice["id"])
        ledger.record_payment(
            row.amount_idr,
            invoice_id=invoice["id"],
            status="matched" if credited else "duplicate",
            provider=provider,
            raw=row.description,
            fingerprint=key,
        )
        report.matched += 1
        report.credited_micros += credited
        report.items.append({"amount": row.amount_idr, "result": "matched", "invoice": invoice["id"]})
    return report


__all__ = [
    "StatementRow",
    "IngestReport",
    "parse_csv",
    "parse_text",
    "parse",
    "fingerprint",
    "ingest",
]
