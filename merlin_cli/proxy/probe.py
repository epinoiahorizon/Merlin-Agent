"""Upstream probing: liveness, latency, and an identity fingerprint that catches model swaps.

A relay's whole claim is "the model you asked for is the model you got". Two cheap, deterministic
signals make that checkable without trusting the vendor:

1. **Tokenizer signature** — for one fixed probe prompt, ``usage.prompt_tokens`` is a property of
   the model's tokenizer, not of the wording. A silent swap to a different model changes it.
2. **Echo + self-ID** — the ``model`` field the upstream returns, plus the vendor string the model
   names itself in a constrained reply (``<vendor>/<model>`` and nothing else).

Together they form a fingerprint stored per ``(upstream, model)``. The first successful probe sets
the baseline; later probes that disagree are flagged as ``IDENTITY_CHANGED`` — the same failure
mode BazaarLink's public probe caught on ``api.thirtystore.com`` (29% of runs swapped).

Latency is recorded on every probe so uptime and p50/p95 come from measurements, not claims.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from merlin_cli.proxy.tenants import default_ledger_path

# One fixed prompt: any change to it invalidates the tokenizer baseline for every model, so it is
# versioned in the fingerprint ("p1") instead of being edited in place.
PROBE_PROMPT = (
    "Answer with only the vendor and model that produced this message, in the form "
    "vendor/model, lowercase, no punctuation and no explanation."
)
PROBE_PROMPT_VERSION = "p1"
PROBE_MAX_TOKENS = 16

VENDOR_HINTS = {
    "deepseek": "deepseek",
    "claude": "anthropic",
    "anthropic": "anthropic",
    "gpt": "openai",
    "openai": "openai",
    "gemini": "google",
    "gemma": "google",
    "qwen": "alibaba",
    "glm": "zhipu",
    "kimi": "moonshot",
    "moonshot": "moonshot",
    "minimax": "minimax",
    "llama": "meta",
    "mistral": "mistral",
    "grok": "xai",
    "hunyuan": "tencent",
    "ernie": "baidu",
}

PROBE_SCHEMA = """
CREATE TABLE IF NOT EXISTS probes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                INTEGER NOT NULL,
    upstream          TEXT NOT NULL,
    model             TEXT NOT NULL,
    ok                INTEGER NOT NULL,
    status            INTEGER NOT NULL,
    latency_ms        REAL NOT NULL,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    model_echo        TEXT NOT NULL DEFAULT '',
    vendor            TEXT NOT NULL DEFAULT '',
    fingerprint       TEXT NOT NULL DEFAULT '',
    note              TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS probe_baselines (
    upstream    TEXT NOT NULL,
    model       TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    vendor      TEXT NOT NULL DEFAULT '',
    set_at      INTEGER NOT NULL,
    PRIMARY KEY (upstream, model)
);
CREATE INDEX IF NOT EXISTS idx_probes_lookup ON probes (upstream, model, ts DESC);
"""

OK = "ok"
IDENTITY_CHANGED = "IDENTITY_CHANGED"


@dataclass(frozen=True)
class ProbeResult:
    upstream: str
    model: str
    ok: bool
    status: int
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model_echo: str = ""
    vendor: str = ""
    reply: str = ""
    note: str = ""

    @property
    def fingerprint(self) -> str:
        """Stable identity digest: tokenizer signature + echo + self-ID."""
        if not self.ok:
            return ""
        material = f"{PROBE_PROMPT_VERSION}|{self.prompt_tokens}|{self.model_echo}|{self.vendor}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def detect_vendor(text: str, model: str = "") -> str:
    """Vendor guessed from the reply (falling back to the model id)."""
    haystack = f"{text} {model}".lower()
    for hint, vendor in VENDOR_HINTS.items():
        if hint in haystack:
            return vendor
    return ""


def _normalise_reply(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:120]


def run_probe(
    base_url: str,
    api_key: str,
    model: str,
    upstream: str = "",
    timeout_s: float = 20.0,
    user_agent: str = "",
) -> ProbeResult:
    """One cheap completion against ``model``; never raises for upstream-level failures."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROBE_PROMPT}],
        "max_tokens": PROBE_MAX_TOKENS,
        "temperature": 0,
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": user_agent or "merlin-proxy/1.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 - operator-supplied
            body = json.loads(response.read().decode("utf-8"))
            status = int(getattr(response, "status", 200))
    except urllib.error.HTTPError as exc:
        elapsed = (time.perf_counter() - started) * 1000
        return ProbeResult(upstream, model, False, int(exc.code), elapsed, note=f"HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        elapsed = (time.perf_counter() - started) * 1000
        return ProbeResult(upstream, model, False, 0, elapsed, note=str(exc)[:160])
    elapsed = (time.perf_counter() - started) * 1000

    payload_obj = body if isinstance(body, dict) else {}
    usage_obj = payload_obj.get("usage")
    usage = usage_obj if isinstance(usage_obj, dict) else {}
    choices = payload_obj.get("choices")
    reply = ""
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first.get("message"), dict) else {}
        reply = _normalise_reply(str(message.get("content") or first.get("text") or ""))
    model_echo = str(payload_obj.get("model") or "")
    return ProbeResult(
        upstream=upstream,
        model=model,
        ok=True,
        status=status,
        latency_ms=elapsed,
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        model_echo=model_echo,
        vendor=detect_vendor(reply, model_echo or model),
        reply=reply,
    )


class ProbeStore:
    """Probe history + baselines, kept in the same SQLite file as the ledger by default."""

    def __init__(self, path: Optional[os.PathLike | str] = None) -> None:
        if path is None:
            path = os.environ.get("MERLIN_PROXY_PROBES") or default_ledger_path()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), isolation_level=None, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(PROBE_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "ProbeStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- writes ------------------------------------------------------------------------------
    def record(self, result: ProbeResult) -> str:
        """Persist a probe. Returns ``ok`` / ``IDENTITY_CHANGED`` / the failure kind."""
        now = int(time.time())
        verdict = OK if result.ok else (result.note or "failed")
        fingerprint = result.fingerprint
        with self._lock:
            self._conn.execute(
                "INSERT INTO probes (ts, upstream, model, ok, status, latency_ms, prompt_tokens,"
                " completion_tokens, model_echo, vendor, fingerprint, note)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    now,
                    result.upstream,
                    result.model,
                    1 if result.ok else 0,
                    result.status,
                    result.latency_ms,
                    result.prompt_tokens,
                    result.completion_tokens,
                    result.model_echo,
                    result.vendor,
                    fingerprint,
                    result.note,
                ),
            )
            if not result.ok:
                return verdict
            baseline = self._conn.execute(
                "SELECT fingerprint FROM probe_baselines WHERE upstream = ? AND model = ?",
                (result.upstream, result.model),
            ).fetchone()
            if baseline is None:
                self._conn.execute(
                    "INSERT OR REPLACE INTO probe_baselines (upstream, model, fingerprint, vendor, set_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (result.upstream, result.model, fingerprint, result.vendor, now),
                )
                return OK
            if baseline["fingerprint"] != fingerprint:
                return IDENTITY_CHANGED
        return OK

    def reset_baseline(self, upstream: str = "", model: str = "") -> int:
        with self._lock:
            if upstream and model:
                cursor = self._conn.execute(
                    "DELETE FROM probe_baselines WHERE upstream = ? AND model = ?", (upstream, model)
                )
            else:
                cursor = self._conn.execute("DELETE FROM probe_baselines")
        return cursor.rowcount

    # -- reads -------------------------------------------------------------------------------
    def baseline(self, upstream: str, model: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM probe_baselines WHERE upstream = ? AND model = ?", (upstream, model)
        ).fetchone()
        return dict(row) if row else None

    def summary(self, hours: int = 24) -> list[dict]:
        """Per ``(upstream, model)``: uptime %, p50/p95 latency, last probe, swap flag."""
        since = int(time.time()) - max(1, hours) * 3600
        rows = self._conn.execute(
            "SELECT upstream, model, ok, status, latency_ms, ts, fingerprint, note FROM probes WHERE ts >= ?"
            " ORDER BY ts ASC",
            (since,),
        ).fetchall()
        buckets: dict[tuple[str, str], dict] = {}
        for row in rows:
            key = (row["upstream"], row["model"])
            bucket = buckets.setdefault(
                key,
                {"upstream": key[0], "model": key[1], "probes": 0, "ok": 0, "latencies": [], "last_ts": 0,
                 "last_note": "", "identity": OK, "fingerprints": set()},
            )
            bucket["probes"] += 1
            if row["ok"]:
                bucket["ok"] += 1
                bucket["latencies"].append(float(row["latency_ms"]))
                bucket["fingerprints"].add(row["fingerprint"])
            bucket["last_ts"] = int(row["ts"])
            bucket["last_note"] = row["note"] or ""
            if row["note"] == IDENTITY_CHANGED:
                bucket["identity"] = IDENTITY_CHANGED
        out: list[dict] = []
        for bucket in buckets.values():
            latencies = sorted(bucket.pop("latencies"))
            fingerprints = bucket.pop("fingerprints")
            if len(fingerprints) > 1:
                bucket["identity"] = IDENTITY_CHANGED
            bucket["uptime_pct"] = round(100.0 * bucket["ok"] / bucket["probes"], 1) if bucket["probes"] else 0.0
            bucket["p50_ms"] = _percentile(latencies, 50)
            bucket["p95_ms"] = _percentile(latencies, 95)
            out.append(bucket)
        return sorted(out, key=lambda item: (item["upstream"], item["model"]))


def _percentile(values: list[float], pct: float) -> float:
    """Linear-interpolated percentile (same convention as numpy), rounded to 0.1 ms."""
    if not values:
        return 0.0
    if len(values) == 1:
        return round(values[0], 1)
    rank = (pct / 100.0) * (len(values) - 1)
    lower = int(rank)
    upper = min(len(values) - 1, lower + 1)
    fraction = rank - lower
    return round(values[lower] + (values[upper] - values[lower]) * fraction, 1)


def probe_specs(
    store: ProbeStore,
    specs: Iterable,
    models_by_upstream: Optional[dict[str, list[str]]] = None,
    limit: int = 0,
    timeout_s: float = 20.0,
) -> list[tuple[ProbeResult, str]]:
    """Probe every model of every configured upstream; returns ``(result, verdict)`` pairs."""
    out: list[tuple[ProbeResult, str]] = []
    for spec in specs:
        models = (models_by_upstream or {}).get(spec.name) or list(getattr(spec, "models", ()) or [])
        if limit:
            models = models[:limit]
        api_key = spec.keys[0] if getattr(spec, "keys", ()) else ""
        for model in models:
            result = run_probe(
                spec.base_url,
                api_key,
                model,
                upstream=spec.name,
                timeout_s=timeout_s,
                user_agent=getattr(spec, "user_agent", "") or "",
            )
            verdict = store.record(result)
            out.append((result, verdict))
    return out


__all__ = [
    "PROBE_PROMPT",
    "PROBE_PROMPT_VERSION",
    "OK",
    "IDENTITY_CHANGED",
    "ProbeResult",
    "ProbeStore",
    "run_probe",
    "probe_specs",
    "detect_vendor",
]
