"""Price catalog tests: reference parsing, model matching, markup floor, sync, price history."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from merlin_cli.proxy import catalog as cat
from merlin_cli.proxy.adapters.generic import UpstreamSpec
from merlin_cli.proxy.metering import ModelPrice, Usage
from merlin_cli.proxy.tenants import InsufficientBalance, LedgerStore, Meter

OPENROUTER_SHAPED = {
    "data": [
        {"id": "deepseek/deepseek-v4-flash", "pricing": {"prompt": "0.00000015", "completion": "0.0000006", "input_cache_read": "0.000000003"}},
        {"id": "anthropic/claude-opus-5", "pricing": {"prompt": "0.000003", "completion": "0.000015"}},
        {"id": "some/free-model", "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "broken/no-pricing"},
    ]
}


@pytest.fixture()
def store(tmp_path):
    with LedgerStore(tmp_path / "ledger.db") as s:
        yield s


# -- reference feed ------------------------------------------------------------------------
def test_parse_reference_converts_per_token_to_micros_per_million() -> None:
    book = cat.parse_reference(OPENROUTER_SHAPED)
    flash = book["deepseek/deepseek-v4-flash"]
    assert flash.in_micros_per_m == 150_000      # $0.15 / 1M
    assert flash.out_micros_per_m == 600_000     # $0.60 / 1M
    assert flash.cache_read_micros_per_m == 3_000  # $0.003 / 1M
    assert book["anthropic/claude-opus-5"].out_micros_per_m == 15_000_000
    assert "some/free-model" not in book          # free rows carry no usable number
    assert "broken/no-pricing" not in book


def test_load_reference_reads_a_local_file(tmp_path) -> None:
    path = tmp_path / "ref.json"
    path.write_text(json.dumps(OPENROUTER_SHAPED), encoding="utf-8")
    book = cat.load_reference(path)
    assert "deepseek/deepseek-v4-flash" in book


def test_load_reference_rejects_empty_book(tmp_path) -> None:
    path = tmp_path / "ref.json"
    path.write_text(json.dumps({"data": []}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="no usable pricing"):
        cat.load_reference(path)


# -- matching ------------------------------------------------------------------------------
def test_find_price_exact_then_normalised_then_cross_namespace() -> None:
    book = cat.parse_reference(OPENROUTER_SHAPED)
    # exact
    price, ref = cat.find_price(book, "deepseek/deepseek-v4-flash")
    assert ref == "deepseek/deepseek-v4-flash" and price is not None
    # cross-namespace: the relay's id has no vendor prefix
    price, ref = cat.find_price(book, "deepseek-v4-flash")
    assert ref == "deepseek/deepseek-v4-flash" and price is not None
    # dated variant normalises onto the base id
    price, ref = cat.find_price(book, "deepseek-v4-flash-0731")
    assert ref == "deepseek/deepseek-v4-flash" and price is not None


def test_find_price_returns_none_for_unknown_model() -> None:
    book = cat.parse_reference(OPENROUTER_SHAPED)
    price, ref = cat.find_price(book, "totally-unlisted-model")
    assert price is None and ref == ""


def test_normalize_id_strips_dates_and_qualifiers() -> None:
    assert cat.normalize_id("DeepSeek-V4-Flash-0731") == "deepseek-v4-flash"
    assert cat.normalize_id("~x-model-latest") == "x-model"
    assert cat.normalize_id("kimi-k2:free") == "kimi-k2"


# -- retail pricing ------------------------------------------------------------------------
def test_retail_applies_markup() -> None:
    list_price = ModelPrice(1_000_000, 2_000_000, 100_000)
    retail = cat.retail_price(list_price, markup_bps=1500)
    assert retail.in_micros_per_m == 1_150_000
    assert retail.out_micros_per_m == 2_300_000
    assert retail.cache_read_micros_per_m == 115_000


def test_retail_never_sells_below_wholesale_plus_floor() -> None:
    tiny = ModelPrice(10_000, 20_000)  # $0.01 / 1M
    retail = cat.retail_price(tiny, markup_bps=100)
    assert retail.in_micros_per_m >= 10_000 + cat.MIN_MARGIN_MICROS_PER_M
    assert retail.out_micros_per_m >= 20_000 + cat.MIN_MARGIN_MICROS_PER_M


def test_retail_preserves_absent_cache_price() -> None:
    assert cat.retail_price(ModelPrice(1_000_000, 2_000_000)).cache_read_micros_per_m is None


# -- discovery over HTTP -------------------------------------------------------------------
class _ModelsHandler(BaseHTTPRequestHandler):
    payload = {"data": [{"id": "beta"}, {"id": "alpha"}, {"id": "alpha"}]}
    status = 200

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        body = json.dumps(self.payload).encode()
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture()
def models_server():
    server = HTTPServer(("127.0.0.1", 0), _ModelsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        server.server_close()


def test_fetch_models_sorts_and_dedupes(models_server) -> None:
    assert cat.fetch_models(models_server, "k") == ["alpha", "beta"]


def test_fetch_models_reports_http_error(models_server) -> None:
    _ModelsHandler.status = 401
    try:
        with pytest.raises(RuntimeError, match="HTTP 401"):
            cat.fetch_models(models_server, "bad")
    finally:
        _ModelsHandler.status = 200


# -- sync ----------------------------------------------------------------------------------
def _spec(name: str = "mock") -> UpstreamSpec:
    return UpstreamSpec(
        name=name,
        base_url="http://127.0.0.1:9/v1",
        keys=("k",),
        models=(),
        allowed_paths=frozenset({"/chat/completions"}),
        is_default=True,
    )


def test_sync_prices_writes_retail_prices_with_source(store, monkeypatch) -> None:
    monkeypatch.setattr(cat, "fetch_models", lambda base, key, timeout_s=20.0: ["deepseek-v4-flash", "mystery-model"])
    book = cat.parse_reference(OPENROUTER_SHAPED)

    report = cat.sync_prices(store, [_spec()], book, markup_bps=1500)

    assert report.added == 1
    assert [e.model for e in report.unpriced] == ["mystery-model"]
    stored = store.price_for("deepseek-v4-flash")
    assert stored is not None
    assert stored.in_micros_per_m == 172_500  # 150_000 × 1.15
    assert store.price_history("deepseek-v4-flash")[0]["source"] == "sync:mock"


def test_second_sync_is_a_no_op_for_history(store, monkeypatch) -> None:
    monkeypatch.setattr(cat, "fetch_models", lambda base, key, timeout_s=20.0: ["deepseek-v4-flash"])
    book = cat.parse_reference(OPENROUTER_SHAPED)

    cat.sync_prices(store, [_spec()], book)
    history_after_first = len(store.price_history("deepseek-v4-flash"))
    report = cat.sync_prices(store, [_spec()], book)

    assert report.unchanged == 1 and report.added == 0 and report.changed == 0
    assert len(store.price_history("deepseek-v4-flash")) == history_after_first


def test_reprice_records_a_change(store, monkeypatch) -> None:
    monkeypatch.setattr(cat, "fetch_models", lambda base, key, timeout_s=20.0: ["deepseek-v4-flash"])
    book = cat.parse_reference(OPENROUTER_SHAPED)
    cat.sync_prices(store, [_spec()], book, markup_bps=1500)
    report = cat.sync_prices(store, [_spec()], book, markup_bps=3000)  # wholesale doubled upstream

    assert report.changed == 1
    history = store.price_history("deepseek-v4-flash")
    assert len(history) == 2
    assert history[0]["in_micros_per_m"] == 195_000  # 150_000 × 1.30


def test_dry_run_writes_nothing(store, monkeypatch) -> None:
    monkeypatch.setattr(cat, "fetch_models", lambda base, key, timeout_s=20.0: ["deepseek-v4-flash"])
    book = cat.parse_reference(OPENROUTER_SHAPED)

    report = cat.sync_prices(store, [_spec()], book, dry_run=True)

    assert report.dry_run is True and report.added == 1
    assert store.price_for("deepseek-v4-flash") is None
    assert store.price_history() == []


def test_discovery_failure_is_reported_not_raised(store, monkeypatch) -> None:
    def boom(base, key, timeout_s=20.0):
        raise RuntimeError("HTTP 500")

    monkeypatch.setattr(cat, "fetch_models", boom)
    report = cat.sync_prices(store, [_spec("dead")], cat.parse_reference(OPENROUTER_SHAPED))
    assert report.entries[0].upstream == "dead"
    assert "discovery failed" in (report.entries[0].reason or "")


# -- fail closed ---------------------------------------------------------------------------
def test_meter_refuses_a_model_with_no_price(store) -> None:
    tenant = store.create_tenant("acme", initial_micros=100_000)
    token = store.issue_key(tenant)
    meter = Meter(store)  # no default price
    key = meter.authenticate(token)
    assert key is not None
    with pytest.raises(InsufficientBalance, match="no price configured"):
        meter.hold(key, "unpriced-model", "req_x", Usage(prompt_tokens=10, completion_tokens=10))
