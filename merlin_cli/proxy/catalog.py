"""Price catalog: discover what each upstream serves, price it from a reference feed, keep history.

Why a *reference* feed instead of scraping every provider: a relay needs a defensible wholesale
number for hundreds of model ids, and per-provider price pages are inconsistent, gated, or change
silently. OpenRouter publishes a machine-readable catalog at ``/api/v1/models`` with per-token
pricing for ~450 models and no auth, so it is used as the wholesale reference by default; a local
JSON file with the same shape works offline.

Retail = reference × (1 + markup), never below reference + a small floor, so an upstream that
under-reports its price can never turn into free traffic. Models that cannot be matched stay
**unpriced** and are reported — the meter then refuses them (402) instead of guessing.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional

from merlin_cli.proxy.metering import ModelPrice

REFERENCE_URL = "https://openrouter.ai/api/v1/models"
DEFAULT_MARKUP_BPS = 1500  # 15 %
MIN_MARGIN_MICROS_PER_M = 1000  # never sell closer than $0.001 / 1M to the wholesale rate
# Default UA for discovery/probing. Relay hosts behind Cloudflare can ban non-browser fingerprints
# (error 1010) before the API key is even checked, so a per-upstream ``user_agent`` overrides this.
DEFAULT_USER_AGENT = "merlin-proxy/1.0"

_SUFFIX_PATTERNS = (
    re.compile(r"[-_]?(\d{8})$"),      # -20260115 / _0605
    re.compile(r"[-_](\d{4})$"),       # -0731
    re.compile(r"[-_](preview|latest|exp|experimental)$"),
    re.compile(r":(free|online|thinking|extended)$"),
)


@dataclass(frozen=True)
class CatalogEntry:
    upstream: str
    model: str
    price: Optional[ModelPrice]
    reference_id: str = ""
    reason: str = ""


@dataclass
class SyncReport:
    entries: list[CatalogEntry] = field(default_factory=list)
    added: int = 0
    changed: int = 0
    unchanged: int = 0
    dry_run: bool = False

    @property
    def unpriced(self) -> list[CatalogEntry]:
        return [e for e in self.entries if e.price is None]

    def summary(self) -> str:
        lines = [
            f"{'[dry-run] ' if self.dry_run else ''}catalog sync: "
            f"{len(self.entries)} model(s) seen, {self.added} added, {self.changed} repriced, "
            f"{self.unchanged} unchanged, {len(self.unpriced)} unpriced"
        ]
        for entry in self.unpriced:
            lines.append(f"  UNPRICED {entry.upstream}:{entry.model} — {entry.reason}")
        return "\n".join(lines)


# -- reference feed --------------------------------------------------------------------------
def parse_reference(payload: Mapping) -> dict[str, ModelPrice]:
    """``{model_id: ModelPrice}`` from an OpenRouter-shaped catalogue payload.

    Prices there are USD **per token** as decimal strings; micros-per-million is that × 1e12.
    """
    models = payload.get("data") if isinstance(payload, Mapping) else None
    book: dict[str, ModelPrice] = {}
    for entry in models or []:
        if not isinstance(entry, Mapping):
            continue
        model_id = str(entry.get("id") or "").strip()
        pricing = entry.get("pricing")
        if not model_id or not isinstance(pricing, Mapping):
            continue
        try:
            prompt = float(pricing.get("prompt") or 0)
            completion = float(pricing.get("completion") or 0)
        except (TypeError, ValueError):
            continue
        if prompt <= 0 and completion <= 0:
            continue  # free or variable-priced rows carry no usable number
        cache = pricing.get("input_cache_read")
        try:
            cache_micros = round(float(cache) * 1e12) if cache not in (None, "") else None
        except (TypeError, ValueError):
            cache_micros = None
        book[model_id] = ModelPrice(
            in_micros_per_m=round(prompt * 1e12),
            out_micros_per_m=round(completion * 1e12),
            cache_read_micros_per_m=cache_micros,
        )
    return book


def load_reference(source: str | Path | None = None, timeout_s: float = 25.0) -> dict[str, ModelPrice]:
    """Load the reference price book from a URL or a local file (JSON)."""
    target = str(source or REFERENCE_URL)
    if target.startswith(("http://", "https://")):
        request = urllib.request.Request(
            target, headers={"User-Agent": "merlin-proxy-catalog/1.0", "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 - operator-supplied
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise RuntimeError(f"cannot load price reference {target}: {exc}") from exc
    else:
        path = Path(target)
        if not path.exists():
            raise RuntimeError(f"price reference file not found: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise RuntimeError(f"price reference {path} is not valid JSON: {exc}") from exc
    book = parse_reference(payload)
    if not book:
        raise RuntimeError(f"price reference {target} contained no usable pricing rows")
    return book


# -- discovery -------------------------------------------------------------------------------
def fetch_models(base_url: str, api_key: str = "", timeout_s: float = 20.0, user_agent: str = "") -> list[str]:
    """Model ids served by an OpenAI-compatible upstream (``GET {base}/models``)."""
    url = f"{base_url.rstrip('/')}/models"
    headers = {"Accept": "application/json", "User-Agent": user_agent or DEFAULT_USER_AGENT}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 - operator-supplied
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{url} returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(f"cannot list models from {url}: {exc}") from exc
    rows = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        raise RuntimeError(f"{url} did not return an OpenAI-shaped {{'data': [...]}} list")
    ids: list[str] = []
    for row in rows:
        if isinstance(row, Mapping):
            model_id = str(row.get("id") or "").strip()
        else:
            model_id = str(row).strip()
        if model_id:
            ids.append(model_id)
    return sorted(set(ids))


# -- pricing ---------------------------------------------------------------------------------
def normalize_id(model: str) -> str:
    """Strip vendor dates/qualifiers so ``x-flash-0731`` and ``x-flash`` can meet."""
    value = model.strip().lower().lstrip("~")
    for _ in range(3):  # a model can carry more than one suffix
        before = value
        for pattern in _SUFFIX_PATTERNS:
            value = pattern.sub("", value)
        if value == before:
            break
    return value


def find_price(book: Mapping[str, ModelPrice], model: str) -> tuple[Optional[ModelPrice], str]:
    """Best-effort match: exact → normalised → same trailing segment. Returns (price, reference id)."""
    if model in book:
        return book[model], model
    normalized = normalize_id(model)
    if normalized in book:
        return book[normalized], normalized
    # Cross-namespace match: "deepseek-v4-flash" ~ "deepseek/deepseek-v4-flash".
    tail = normalized.rsplit("/", 1)[-1]
    candidates = [
        (ref, price) for ref, price in book.items() if normalize_id(ref).rsplit("/", 1)[-1] == tail
    ]
    if len(candidates) == 1:
        return candidates[0][1], candidates[0][0]
    if candidates:  # ambiguous: prefer the shortest id (least decorated)
        ref, price = min(candidates, key=lambda item: len(item[0]))
        return price, ref
    return None, ""


def retail_price(
    list_price: ModelPrice,
    markup_bps: int = DEFAULT_MARKUP_BPS,
    floor_micros: int = MIN_MARGIN_MICROS_PER_M,
) -> ModelPrice:
    """Apply markup with a hard floor so no model is ever sold at or below wholesale."""
    markup_bps = max(0, int(markup_bps))

    def apply(amount: int) -> int:
        marked = amount * (10_000 + markup_bps) // 10_000
        floored = amount + floor_micros if amount > 0 else floor_micros
        return max(marked, floored)

    cache = list_price.cache_read_micros_per_m
    return ModelPrice(
        in_micros_per_m=apply(list_price.in_micros_per_m),
        out_micros_per_m=apply(list_price.out_micros_per_m),
        cache_read_micros_per_m=None if cache is None else apply(cache),
    )


def sync_prices(
    store,
    specs: Iterable,
    book: Mapping[str, ModelPrice],
    markup_bps: int = DEFAULT_MARKUP_BPS,
    dry_run: bool = False,
) -> SyncReport:
    """Price every model each upstream advertises; report what could not be matched.

    ``specs`` are objects with ``name``, ``base_url`` and ``keys`` (see ``UpstreamSpec``).
    Unchanged prices are not rewritten, so ``price_history`` stays a history of *changes*.
    """
    report = SyncReport(dry_run=dry_run)
    for spec in specs:
        api_key = spec.keys[0] if getattr(spec, "keys", ()) else ""
        try:
            models = fetch_models(
                spec.base_url, api_key, user_agent=getattr(spec, "user_agent", "") or ""
            )
        except RuntimeError as exc:
            report.entries.append(CatalogEntry(spec.name, "*", None, reason=f"discovery failed: {exc}"))
            continue
        for model in models:
            list_price, reference_id = find_price(book, model)
            if list_price is None:
                report.entries.append(
                    CatalogEntry(spec.name, model, None, reason="no reference price (add it manually)")
                )
                continue
            price = retail_price(list_price, markup_bps)
            current = store.price_for(model)
            if current == price:
                report.unchanged += 1
            elif current is None:
                report.added += 1
            else:
                report.changed += 1
            if not dry_run:
                store.set_price(
                    model,
                    price.in_micros_per_m,
                    price.out_micros_per_m,
                    price.cache_read_micros_per_m,
                    source=f"sync:{spec.name}",
                )
            report.entries.append(CatalogEntry(spec.name, model, price, reference_id))
    return report


def reference_id_for_model(model: str) -> str:
    """Convenience for logging: the reference id a model would be matched against."""
    return normalize_id(model)


__all__ = [
    "CatalogEntry",
    "SyncReport",
    "REFERENCE_URL",
    "DEFAULT_MARKUP_BPS",
    "MIN_MARGIN_MICROS_PER_M",
    "parse_reference",
    "load_reference",
    "fetch_models",
    "normalize_id",
    "find_price",
    "retail_price",
    "sync_prices",
    "reference_id_for_model",
]
