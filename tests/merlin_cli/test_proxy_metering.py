"""Unit tests for the proxy metering primitives: usage parsing, SSE scanning, cost math."""

from __future__ import annotations

import json

import pytest

from merlin_cli.proxy.metering import (
    ModelPrice,
    SseUsageScanner,
    Usage,
    cost_micros,
    ensure_include_usage,
    estimate_usage,
    parse_json_usage,
)


# -- usage parsing -------------------------------------------------------------------------
def test_openai_usage_with_cache_details() -> None:
    body = json.dumps(
        {
            "id": "chatcmpl-1",
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 200,
                "prompt_tokens_details": {"cached_tokens": 800},
            },
        }
    ).encode()
    usage = parse_json_usage(body)
    assert usage is not None
    assert (usage.prompt_tokens, usage.completion_tokens, usage.cache_read_tokens) == (1000, 200, 800)
    assert usage.estimated is False


def test_anthropic_usage_adds_cache_reads_to_prompt_total() -> None:
    body = json.dumps(
        {"usage": {"input_tokens": 50, "output_tokens": 10, "cache_read_input_tokens": 950}}
    ).encode()
    usage = parse_json_usage(body)
    assert usage is not None
    # Anthropic's input_tokens excludes cache reads; the normalised total must include them.
    assert usage.prompt_tokens == 1000
    assert usage.cache_read_tokens == 950
    assert usage.completion_tokens == 10


def test_missing_usage_is_none() -> None:
    assert parse_json_usage(b'{"id": "x", "choices": []}') is None
    assert parse_json_usage(b"not json") is None
    assert parse_json_usage(b"") is None


# -- stream_options injection --------------------------------------------------------------
def test_include_usage_injected_for_stream() -> None:
    body = json.dumps({"model": "m", "stream": True, "messages": []}).encode()
    patched, injected = ensure_include_usage(body)
    assert injected is True
    assert json.loads(patched)["stream_options"] == {"include_usage": True}
    assert json.loads(patched)["model"] == "m"  # nothing else touched


def test_include_usage_preserves_existing_options() -> None:
    body = json.dumps({"stream": True, "stream_options": {"include_usage": True}}).encode()
    patched, injected = ensure_include_usage(body)
    assert injected is False
    assert patched == body


def test_include_usage_skips_non_stream_and_garbage() -> None:
    plain = json.dumps({"model": "m", "messages": []}).encode()
    assert ensure_include_usage(plain) == (plain, False)
    assert ensure_include_usage(b"{not json") == (b"{not json", False)
    assert ensure_include_usage(b"") == (b"", False)


# -- SSE scanning --------------------------------------------------------------------------
def _frame(payload: dict) -> bytes:
    return b"data: " + json.dumps(payload).encode() + b"\n\n"


def test_sse_scanner_reads_usage_split_across_chunks() -> None:
    usage_frame = _frame({"choices": [], "usage": {"prompt_tokens": 321, "completion_tokens": 45}})
    stream = (
        _frame({"choices": [{"delta": {"content": "hi"}}]})
        + _frame({"choices": [{"delta": {}, "finish_reason": "stop"}]})
        + usage_frame
        + b"data: [DONE]\n\n"
    )
    scanner = SseUsageScanner()
    # Feed in 7-byte slices: every frame lands mid-line at least once.
    for i in range(0, len(stream), 7):
        scanner.feed(stream[i : i + 7])
    assert scanner.usage is not None
    assert (scanner.usage.prompt_tokens, scanner.usage.completion_tokens) == (321, 45)
    assert scanner.finish_reason == "stop"
    assert scanner.saw_done is True


def test_sse_scanner_keeps_last_usage_and_tolerates_bare_json() -> None:
    scanner = SseUsageScanner()
    scanner.feed(_frame({"usage": {"prompt_tokens": 1, "completion_tokens": 1}}))
    scanner.feed(b'{"usage": {"prompt_tokens": 9, "completion_tokens": 3}}\n\n')
    assert scanner.usage is not None
    assert scanner.usage.prompt_tokens == 9


def test_sse_scanner_without_usage_reports_none() -> None:
    scanner = SseUsageScanner()
    scanner.feed(_frame({"choices": [{"delta": {"content": "x"}}]}))
    assert scanner.usage is None
    scanner.mark_interrupted()
    assert scanner.interrupted is True


# -- cost math -----------------------------------------------------------------------------
def test_cost_splits_cached_and_uncached_input() -> None:
    price = ModelPrice(in_micros_per_m=1_000_000, out_micros_per_m=2_000_000, cache_read_micros_per_m=100_000)
    usage = Usage(prompt_tokens=1000, completion_tokens=500, cache_read_tokens=800)
    # uncached 200 @ $1/M = 200 micros; cached 800 @ $0.10/M = 80 micros; output 500 @ $2/M = 1000
    assert cost_micros(usage, price) == 1280


def test_cost_falls_back_to_input_rate_when_cache_price_unset() -> None:
    price = ModelPrice(in_micros_per_m=1_000_000, out_micros_per_m=0, cache_read_micros_per_m=None)
    assert cost_micros(Usage(prompt_tokens=1000, cache_read_tokens=1000), price) == 1000


def test_cost_is_integer_micros_never_float() -> None:
    price = ModelPrice(in_micros_per_m=333_333, out_micros_per_m=777_777)
    cost = cost_micros(Usage(prompt_tokens=7, completion_tokens=3), price)
    assert isinstance(cost, int)
    assert cost == (7 * 333_333 + 3 * 777_777) // 1_000_000


def test_estimate_marks_itself_and_respects_max_tokens() -> None:
    body = json.dumps({"model": "m", "max_tokens": 256, "messages": [{"content": "x" * 400}]}).encode()
    usage = estimate_usage(body)
    assert usage.estimated is True
    assert usage.completion_tokens == 256
    assert usage.prompt_tokens == max(1, len(body) // 4)


def test_estimate_caps_runaway_output() -> None:
    body = json.dumps({"max_tokens": 10**9}).encode()
    assert estimate_usage(body).completion_tokens == 8192


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
