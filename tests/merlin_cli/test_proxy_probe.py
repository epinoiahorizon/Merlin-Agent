"""Probe tests: liveness/latency capture, fingerprint stability, swap detection, aggregates."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from merlin_cli.proxy.adapters.generic import UpstreamSpec
from merlin_cli.proxy.probe import (
    IDENTITY_CHANGED,
    OK,
    ProbeResult,
    ProbeStore,
    detect_vendor,
    probe_specs,
    run_probe,
)


class _Handler(BaseHTTPRequestHandler):
    """Canned OpenAI-shaped reply; per-model knobs simulate an upstream swapping models."""

    replies: dict[str, dict] = {}
    status = 200

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        model = body.get("model", "")
        if self.status != 200:
            payload = {"error": {"message": "boom"}}
            self._send(payload, self.status)
            return
        spec = self.replies.get(model, {"prompt_tokens": 40, "content": "deepseek", "echo": model})
        self._send(
            {
                "id": "probe",
                "model": spec.get("echo", model),
                "choices": [{"index": 0, "message": {"role": "assistant", "content": spec["content"]}}],
                "usage": {"prompt_tokens": spec["prompt_tokens"], "completion_tokens": 4},
            }
        )

    def _send(self, payload: dict, status: int = 200) -> None:
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture()
def upstream():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _Handler.replies = {}
    _Handler.status = 200
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture()
def store(tmp_path):
    with ProbeStore(tmp_path / "probes.db") as s:
        yield s


# -- single probe --------------------------------------------------------------------------
def test_probe_captures_latency_usage_and_identity(upstream) -> None:
    result = run_probe(upstream, "k", "deepseek-v4-flash", upstream="mock")
    assert result.ok is True and result.status == 200
    assert result.latency_ms > 0
    assert result.prompt_tokens == 40
    assert result.model_echo == "deepseek-v4-flash"
    assert result.vendor == "deepseek"  # detected from the constrained reply


def test_probe_records_http_failure_without_raising(upstream) -> None:
    _Handler.status = 500
    result = run_probe(upstream, "k", "m", upstream="mock")
    assert result.ok is False
    assert result.status == 500
    assert "HTTP 500" in result.note
    assert result.fingerprint == ""  # nothing to fingerprint


def test_probe_records_connection_failure() -> None:
    result = run_probe("http://127.0.0.1:9/v1", "k", "m", upstream="dead", timeout_s=2)
    assert result.ok is False and result.status == 0
    assert result.note


def test_vendor_detection_prefers_reply_then_model_id() -> None:
    assert detect_vendor("GLM-5.3", "") == "zhipu"
    assert detect_vendor("", "claude-opus-5") == "anthropic"
    assert detect_vendor("mystery", "mystery-model") == ""


# -- fingerprint ---------------------------------------------------------------------------
def _result(prompt_tokens: int = 40, echo: str = "deepseek-v4-flash", vendor: str = "deepseek") -> ProbeResult:
    return ProbeResult("mock", "deepseek-v4-flash", True, 200, 12.0, prompt_tokens, 4, echo, vendor)


def test_fingerprint_is_stable_for_identical_signals() -> None:
    assert _result().fingerprint == _result().fingerprint


def test_fingerprint_changes_when_the_tokenizer_signature_changes() -> None:
    assert _result().fingerprint != _result(prompt_tokens=41).fingerprint


def test_fingerprint_changes_when_the_model_self_id_changes() -> None:
    assert _result().fingerprint != _result(vendor="openai").fingerprint


# -- store: baselines and swaps ------------------------------------------------------------
def test_first_probe_sets_baseline_then_repeat_is_ok(store) -> None:
    assert store.record(_result()) == OK
    baseline = store.baseline("mock", "deepseek-v4-flash")
    assert baseline is not None and baseline["vendor"] == "deepseek"
    assert store.record(_result()) == OK


def test_changed_signature_is_flagged_as_identity_change(store) -> None:
    store.record(_result())
    verdict = store.record(_result(prompt_tokens=77, vendor="openai"))
    assert verdict == IDENTITY_CHANGED


def test_baseline_reset_allows_relearning(store) -> None:
    store.record(_result())
    assert store.reset_baseline("mock", "deepseek-v4-flash") == 1
    assert store.record(_result(prompt_tokens=77, vendor="openai")) == OK


def test_failures_do_not_touch_the_baseline(store) -> None:
    store.record(_result())
    failed = ProbeResult("mock", "deepseek-v4-flash", False, 503, 5.0, note="HTTP 503")
    assert store.record(failed) == "HTTP 503"
    assert store.baseline("mock", "deepseek-v4-flash") is not None


# -- aggregates ----------------------------------------------------------------------------
def test_summary_reports_uptime_and_percentiles(store) -> None:
    for latency in (10.0, 20.0, 30.0, 40.0):
        store.record(
            ProbeResult("mock", "m", True, 200, latency, 40, 4, "m", "deepseek")
        )
    store.record(ProbeResult("mock", "m", False, 500, 5.0, note="HTTP 500"))

    row = store.summary(hours=1)[0]
    assert row["probes"] == 5 and row["ok"] == 4
    assert row["uptime_pct"] == 80.0
    assert row["p50_ms"] == 25.0 and row["p95_ms"] == 38.5
    assert row["identity"] == OK


def test_summary_flags_mixed_fingerprints(store) -> None:
    store.record(_result())
    store.record(_result(prompt_tokens=99))
    assert store.summary(hours=1)[0]["identity"] == IDENTITY_CHANGED


def test_summary_respects_the_window(store) -> None:
    store.record(_result())
    assert store.summary(hours=1)
    with store._lock:  # age the row past the window
        store._conn.execute("UPDATE probes SET ts = ts - 7200")
    assert store.summary(hours=1) == []


# -- batch ---------------------------------------------------------------------------------
def test_probe_specs_runs_each_declared_model(upstream, store) -> None:
    spec = UpstreamSpec(
        name="mock",
        base_url=upstream,
        keys=("k",),
        models=("alpha", "beta"),
        allowed_paths=frozenset({"/chat/completions"}),
        is_default=True,
    )
    results = probe_specs(store, [spec])
    assert [r.model for r, _ in results] == ["alpha", "beta"]
    assert all(verdict == OK for _, verdict in results)
    assert {row["model"] for row in store.summary(hours=1)} == {"alpha", "beta"}


def test_probe_specs_honours_limit(upstream, store) -> None:
    spec = UpstreamSpec(
        name="mock",
        base_url=upstream,
        keys=("k",),
        models=("a", "b", "c"),
        allowed_paths=frozenset({"/chat/completions"}),
        is_default=True,
    )
    assert len(probe_specs(store, [spec], limit=2)) == 2
    time.sleep(0)  # keep linters honest about the import
