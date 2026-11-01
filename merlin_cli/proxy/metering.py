"""Token metering for the proxy: usage extraction, cache-aware cost math, SSE scanning.

The forwarder is credential-attaching and body-agnostic by design (see ``server.py``). Metering is
therefore opt-in and bolted on at the edges only:

* non-stream responses — ``parse_json_usage(body)`` reads the ``usage`` object once at EOF;
* stream responses — ``SseUsageScanner`` feeds on chunks as they pass through and keeps the last
  usage frame (OpenAI only reports it when ``stream_options.include_usage`` is set, hence
  ``ensure_include_usage``);
* upstream sent nothing — ``estimate_usage`` gives a conservative fallback so usage is never free.

Money is integer **micros** (1e-6 USD). Floats are never used for balances: a relay that drifts by
a fraction of a cent per request loses real money over a month.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

# Prices are expressed per 1M tokens in micros, matching how providers publish them.
PRICE_SCALE = 1_000_000
# Rough bytes-per-token for the fallback estimate (JSON overhead included on purpose: a hold may
# over-reserve slightly, it must never under-reserve).
CHARS_PER_TOKEN = 4
DEFAULT_ESTIMATED_OUTPUT = 1024
MAX_ESTIMATED_OUTPUT = 8192


@dataclass(frozen=True)
class Usage:
    """Normalised token counts. ``estimated`` marks a heuristic count, never an upstream report."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_read_tokens: int = 0
    estimated: bool = False

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @classmethod
    def from_payload(cls, payload: Any) -> Optional["Usage"]:
        """Parse an OpenAI *or* Anthropic usage object; ``None`` when the payload carries none.

        OpenAI: ``prompt_tokens`` / ``completion_tokens`` (+ ``prompt_tokens_details.cached_tokens``).
        Anthropic: ``input_tokens`` / ``output_tokens`` (+ ``cache_read_input_tokens``). Anthropic
        ``input_tokens`` excludes cache reads, so cached tokens are added back into the prompt total
        to keep costing consistent across wires.
        """
        if not isinstance(payload, dict):
            return None
        usage = payload.get("usage")
        if isinstance(usage, dict):
            parsed = cls._from_flat(usage)
            if parsed is not None:
                return parsed
        return cls._from_flat(payload)

    @classmethod
    def _from_flat(cls, obj: dict) -> Optional["Usage"]:
        if "prompt_tokens" in obj or "completion_tokens" in obj:
            details = obj.get("prompt_tokens_details")
            cached = 0
            if isinstance(details, dict):
                cached = _as_int(details.get("cached_tokens"))
            prompt = _as_int(obj.get("prompt_tokens"))
            return cls(prompt_tokens=prompt, completion_tokens=_as_int(obj.get("completion_tokens")), cache_read_tokens=cached)
        if "input_tokens" in obj or "output_tokens" in obj:
            cached = _as_int(obj.get("cache_read_input_tokens"))
            return cls(
                prompt_tokens=_as_int(obj.get("input_tokens")) + cached,
                completion_tokens=_as_int(obj.get("output_tokens")),
                cache_read_tokens=cached,
            )
        return None


def _as_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True)
class ModelPrice:
    """Per-million-token price in micros. ``cache_read`` defaults to the input rate (no discount)."""

    in_micros_per_m: int
    out_micros_per_m: int
    cache_read_micros_per_m: Optional[int] = None

    @property
    def cache_micros(self) -> int:
        return self.in_micros_per_m if self.cache_read_micros_per_m is None else self.cache_read_micros_per_m


def cost_micros(usage: Usage, price: ModelPrice) -> int:
    """Integer micro-USD cost. Rounds down (favours the customer by <1 micro per request)."""
    cached = min(usage.cache_read_tokens, usage.prompt_tokens)
    uncached = max(0, usage.prompt_tokens - cached)
    total = (
        uncached * price.in_micros_per_m
        + cached * price.cache_micros
        + usage.completion_tokens * price.out_micros_per_m
    )
    return total // PRICE_SCALE


def parse_json_usage(body: bytes) -> Optional[Usage]:
    """Usage from a complete non-stream response body (``None`` if absent/unparseable)."""
    if not body:
        return None
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None
    return Usage.from_payload(payload)


def ensure_include_usage(body: bytes) -> tuple[bytes, bool]:
    """Set ``stream_options.include_usage`` on a streaming chat request.

    Returns ``(body, injected)``; the body is returned untouched (same object) when nothing was
    needed, and untouched on any parse error — the proxy must never corrupt a payload it cannot
    understand. Callers must scope this to OpenAI-compatible paths only: ``/v1/messages``
    (Anthropic) rejects unknown fields.
    """
    if not body:
        return body, False
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return body, False
    if not isinstance(payload, dict) or not payload.get("stream"):
        return body, False
    options = payload.get("stream_options")
    if isinstance(options, dict):
        if options.get("include_usage"):
            return body, False
        options["include_usage"] = True
    else:
        payload["stream_options"] = {"include_usage": True}
    try:
        return json.dumps(payload).encode("utf-8"), True
    except (TypeError, ValueError):  # pragma: no cover - json.loads already validated
        return body, False


class SseUsageScanner:
    """Incremental ``text/event-stream`` reader: keeps the last usage frame and the stream state.

    Chunk boundaries are arbitrary, so lines are buffered until a newline arrives. Both
    ``data: {...}`` and bare ``{...}`` lines are accepted (a few upstreams drop the prefix).
    """

    def __init__(self) -> None:
        self._buf = b""
        self.usage: Optional[Usage] = None
        self.finish_reason: Optional[str] = None
        self.saw_done = False
        self.interrupted = False

    def feed(self, chunk: bytes) -> None:
        if not chunk:
            return
        self._buf += chunk
        while True:
            idx = self._buf.find(b"\n")
            if idx < 0:
                return
            line, self._buf = self._buf[:idx], self._buf[idx + 1 :]
            self._consume_line(line.rstrip(b"\r"))

    def mark_interrupted(self) -> None:
        self.interrupted = True

    def _consume_line(self, line: bytes) -> None:
        stripped = line.strip()
        if not stripped:
            return
        if stripped in (b"data: [DONE]", b"[DONE]"):
            self.saw_done = True
            return
        if stripped.startswith(b"data:"):
            payload = stripped[5:].strip()
        elif stripped.startswith(b"{"):
            payload = stripped
        else:
            return
        try:
            obj = json.loads(payload)
        except (ValueError, UnicodeDecodeError):
            return
        parsed = Usage.from_payload(obj)
        if parsed is not None:
            self.usage = parsed
        if isinstance(obj, dict):
            for choice in obj.get("choices") or ():
                if isinstance(choice, dict) and choice.get("finish_reason"):
                    self.finish_reason = str(choice["finish_reason"])


def estimate_usage(body: bytes, generated_bytes: int = 0) -> Usage:
    """Conservative fallback when the upstream reported no usage at all.

    Prompt tokens come from the request size, completion tokens from what actually flowed back
    (or the requested ``max_tokens`` when nothing did). The result is flagged ``estimated`` so the
    ledger can label the entry instead of silently presenting it as an upstream report.
    """
    estimated_in = max(1, len(body) // CHARS_PER_TOKEN) if body else 1
    requested = _requested_max_tokens(body)
    if generated_bytes:
        estimated_out = max(1, generated_bytes // CHARS_PER_TOKEN)
    else:
        estimated_out = requested or DEFAULT_ESTIMATED_OUTPUT
    estimated_out = min(estimated_out, MAX_ESTIMATED_OUTPUT)
    return Usage(prompt_tokens=estimated_in, completion_tokens=estimated_out, estimated=True)


def _requested_max_tokens(body: bytes) -> int:
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return 0
    if not isinstance(payload, dict):
        return 0
    for key in ("max_completion_tokens", "max_tokens"):
        value = payload.get(key)
        try:
            if value:
                return max(0, int(value))
        except (TypeError, ValueError):
            continue
    return 0


__all__ = [
    "Usage",
    "ModelPrice",
    "SseUsageScanner",
    "cost_micros",
    "parse_json_usage",
    "ensure_include_usage",
    "estimate_usage",
    "PRICE_SCALE",
]
