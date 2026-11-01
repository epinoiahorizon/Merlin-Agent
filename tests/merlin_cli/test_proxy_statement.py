"""Statement import tests: parsing DANA-style exports/notifications, dedupe, matching."""

from __future__ import annotations

import pytest

from merlin_cli.proxy import statement
from merlin_cli.proxy.tenants import MICROS_PER_UNIT, LedgerStore


@pytest.fixture()
def ledger(tmp_path):
    with LedgerStore(tmp_path / "ledger.db") as store:
        yield store


# -- parsing -------------------------------------------------------------------------------
def test_parse_csv_with_indonesian_headers() -> None:
    text = "Tanggal,Nominal,Keterangan\n2026-11-01,15.928,QRIS masuk\n2026-11-01,25.000,QRIS masuk\n"
    rows = statement.parse_csv(text)
    assert [row.amount_idr for row in rows] == [15_928, 25_000]
    assert rows[0].when == "2026-11-01"


def test_parse_csv_with_english_headers_and_decimals() -> None:
    text = "Date,Amount,Reference\n2026-11-01,15928.00,TRX-99881\n"
    rows = statement.parse_csv(text)
    assert rows[0].amount_idr == 15_928
    assert rows[0].reference == "TRX-99881"


def test_parse_csv_handles_tab_delimiters() -> None:
    text = "tanggal\tnominal\n2026-11-01\t7.500\n"
    rows = statement.parse_csv(text)
    assert rows[0].amount_idr == 7_500


def test_parse_csv_keeps_refund_sign() -> None:
    """Regression: ``-3.000`` in a statement is a refund, not a 3 000 top-up."""
    rows = statement.parse_csv("Tanggal,Nominal\n2026-11-01,-3.000\n")
    assert rows[0].amount_idr == -3_000
    assert rows[0].ignorable is True


def test_parse_csv_without_amount_column_yields_nothing() -> None:
    assert statement.parse_csv("foo,bar\n1,2\n") == []


def test_parse_text_reads_notification_lines() -> None:
    text = (
        "DANA Bisnis: Pembayaran masuk Rp 15.928 pada 01/11/2026 ref 88776655 dari BUDI\n"
        "Saldo Anda Rp 250.000\n"
        "Promo: cashback Rp 5.000\n"
    )
    rows = statement.parse_text(text)
    amounts = [row.amount_idr for row in rows]
    assert 15_928 in amounts and 250_000 in amounts  # balance lines are parsed too — hence --dry-run
    first = rows[0]
    assert first.when == "01/11/2026"
    assert first.reference == "88776655"


def test_parse_text_marks_refunds_negative() -> None:
    rows = statement.parse_text("Refund transaksi Rp 10.000 ke pelanggan\n")
    assert rows[0].amount_idr == -10_000
    assert rows[0].ignorable is True


def test_parse_auto_prefers_csv_when_delimited() -> None:
    rows = statement.parse("Tanggal,Nominal\n2026-11-01,15.928\n")
    assert rows and rows[0].amount_idr == 15_928


# -- fingerprints --------------------------------------------------------------------------
def test_fingerprint_requires_an_identifier() -> None:
    bare = statement.StatementRow(amount_idr=15_928)
    assert statement.fingerprint(bare, "dana") == ""
    dated = statement.StatementRow(amount_idr=15_928, when="2026-11-01")
    assert statement.fingerprint(dated, "dana") != ""
    assert statement.fingerprint(dated, "dana") == statement.fingerprint(dated, "dana")
    assert statement.fingerprint(dated, "dana") != statement.fingerprint(dated, "xendit")


# -- ingest --------------------------------------------------------------------------------
def test_ingest_matches_pending_invoice_and_credits(ledger) -> None:
    tenant = ledger.create_tenant("acme")
    invoice = ledger.create_invoice(tenant, 15_928)
    rows = [statement.StatementRow(amount_idr=15_928, when="2026-11-01", reference="TRX1")]
    report = statement.ingest(ledger, rows, provider="dana")
    assert report.matched == 1
    assert report.credited_micros == 15_928 * MICROS_PER_UNIT
    assert ledger.invoice(invoice["id"])["status"] == "paid"


def test_reingesting_the_same_statement_credits_nothing_twice(ledger) -> None:
    tenant = ledger.create_tenant("acme")
    ledger.create_invoice(tenant, 15_928)
    rows = [statement.StatementRow(amount_idr=15_928, when="2026-11-01", reference="TRX1")]
    first = statement.ingest(ledger, rows, provider="dana")
    second = statement.ingest(ledger, rows, provider="dana")
    assert first.matched == 1
    assert second.skipped == 1 and second.matched == 0
    assert ledger.balance(tenant) == 15_928 * MICROS_PER_UNIT


def test_ingest_records_unmatched_amounts(ledger) -> None:
    rows = [statement.StatementRow(amount_idr=99_999, when="2026-11-01", reference="X")]
    report = statement.ingest(ledger, rows, provider="dana")
    assert report.unmatched == 1
    assert ledger.payments(status="unmatched")


def test_ingest_logs_refunds_as_ignored(ledger) -> None:
    rows = [statement.StatementRow(amount_idr=-5_000, when="2026-11-01")]
    report = statement.ingest(ledger, rows, provider="dana")
    assert report.ignored == 1
    stored = ledger.payments(limit=1)[0]
    assert stored["status"] == "ignored" and stored["amount_idr"] == -5_000


def test_dry_run_writes_nothing(ledger) -> None:
    tenant = ledger.create_tenant("acme")
    ledger.create_invoice(tenant, 12_000)
    rows = [statement.StatementRow(amount_idr=12_000, when="2026-11-01")]
    report = statement.ingest(ledger, rows, dry_run=True)
    assert report.matched == 1 and report.dry_run is True
    assert ledger.balance(tenant) == 0
    assert ledger.payments(limit=5) == []


def test_two_undated_rows_with_the_same_amount_are_both_kept(ledger) -> None:
    """No identifier means no dedupe: two identical payments are real, the second is unmatched."""
    tenant = ledger.create_tenant("acme")
    ledger.create_invoice(tenant, 8_000)
    rows = [statement.StatementRow(amount_idr=8_000), statement.StatementRow(amount_idr=8_000)]
    report = statement.ingest(ledger, rows, provider="dana")
    assert report.matched == 1 and report.unmatched == 1
    assert ledger.balance(tenant) == 8_000 * MICROS_PER_UNIT
