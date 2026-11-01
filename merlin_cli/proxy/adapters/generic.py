"""Config-driven upstream adapter: many OpenAI-compatible hosts behind one proxy.

This is the half a relay needs that the OAuth adapters (atlas, xAI) cannot provide — arbitrary
upstreams, chosen per requested model:

.. code-block:: yaml

    # ~/.merlin/proxy_upstreams.yaml  (or MERLIN_PROXY_UPSTREAMS=/path/file.yaml)
    default: deepseek
    upstreams:
      - name: deepseek
        base_url: https://api.deepseek.com/v1
        api_key_env: DEEPSEEK_API_KEY        # or api_key: sk-… / api_keys: [k1, k2]
        models: [deepseek-v4-flash, deepseek-v4-pro]
      - name: relay
        base_url: https://api.thirtystore.com/v1
        api_key: ${THIRTY_KEY}               # ${ENV} is expanded at load time
        models: ["thirty/*"]
        allowed_paths: ["/chat/completions", "/models"]

Routing precedence for a request model: exact match → glob match (``thirty/*``) → the entry marked
``default: true`` → the file-level ``default:`` → the first entry. ``models`` omitted means "match
anything" for that entry, which makes a single-upstream config work with no routing at all.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet, Optional

from merlin_cli.proxy.adapters.base import UpstreamAdapter, UpstreamCredential
from merlin_cli.proxy.tenants import default_ledger_path

logger = logging.getLogger(__name__)

# Union of what OpenAI-compatible hosts commonly serve; per-entry ``allowed_paths`` narrows it.
DEFAULT_ALLOWED_PATHS: FrozenSet[str] = frozenset(
    {"/responses", "/chat/completions", "/completions", "/embeddings", "/models"}
)

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

CONFIG_TEMPLATE = """\
{
  "default": "primary",
  "upstreams": [
    {
      "name": "primary",
      "base_url": "https://api.example.com/v1",
      "api_key_env": "EXAMPLE_API_KEY",
      "models": ["example/*"]
    }
  ]
}
"""


class UpstreamConfigError(RuntimeError):
    """Raised when the upstream config is missing or unusable (message is user-facing)."""


@dataclass(frozen=True)
class UpstreamSpec:
    name: str
    base_url: str
    keys: tuple[str, ...]
    models: tuple[str, ...]
    allowed_paths: FrozenSet[str]
    is_default: bool
    user_agent: str = ""

    @property
    def has_key(self) -> bool:
        return bool(self.keys)

    def matches(self, model: str) -> bool:
        if not model or not self.models:
            return not self.models  # empty models = catch-all
        for pattern in self.models:
            if pattern.endswith("*"):
                if fnmatch.fnmatchcase(model, pattern):
                    return True
            elif model == pattern:
                return True
        return False

    @property
    def specificity(self) -> int:
        """Exact patterns beat globs (used to break ties between catch-all entries)."""
        return sum(0 if pattern.endswith("*") else 1 for pattern in self.models)


def config_path() -> Path:
    """``MERLIN_PROXY_UPSTREAMS`` wins; otherwise the same Merlin home the ledger uses.

    JSON is the default because it needs no optional dependency; YAML is picked up when present and
    PyYAML is importable.
    """
    override = os.environ.get("MERLIN_PROXY_UPSTREAMS", "").strip()
    if override:
        return Path(override)
    home = default_ledger_path().parent
    for name in ("proxy_upstreams.json", "proxy_upstreams.yaml", "proxy_upstreams.yml"):
        candidate = home / name
        if candidate.exists():
            return candidate
    return home / "proxy_upstreams.json"


def _expand_env(value: str) -> str:
    return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value).strip()


def _read_config(path: Path) -> dict:
    if not path.exists():
        raise UpstreamConfigError(
            f"No upstream config at {path}.\nCreate it (or point MERLIN_PROXY_UPSTREAMS at one):\n\n"
            f"{CONFIG_TEMPLATE}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise UpstreamConfigError(f"Cannot read upstream config {path}: {exc}") from exc
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # local import: the proxy works without PyYAML when JSON is used
        except ImportError as exc:  # pragma: no cover - PyYAML ships with Merlin
            raise UpstreamConfigError(
                f"{path} is YAML but PyYAML is unavailable; use JSON instead."
            ) from exc
        try:
            parsed = yaml.safe_load(text) or {}
        except Exception as exc:
            raise UpstreamConfigError(f"{path} is not valid YAML: {exc}") from exc
    else:
        try:
            parsed = json.loads(text or "{}")
        except ValueError as exc:
            raise UpstreamConfigError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise UpstreamConfigError(f"{path} must contain a mapping with an 'upstreams' list.")
    return parsed


def parse_specs(raw: dict, source: Path) -> tuple[list[UpstreamSpec], str]:
    """Validate the parsed config into specs + the default upstream name."""
    entries = raw.get("upstreams")
    if not isinstance(entries, list) or not entries:
        raise UpstreamConfigError(f"{source}: 'upstreams' must be a non-empty list.\n\n{CONFIG_TEMPLATE}")
    specs: list[UpstreamSpec] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise UpstreamConfigError(f"{source}: upstreams[{index}] must be a mapping.")
        name = str(entry.get("name") or f"upstream-{index + 1}").strip()
        if name in seen:
            raise UpstreamConfigError(f"{source}: duplicate upstream name {name!r}.")
        seen.add(name)
        base_url = _expand_env(str(entry.get("base_url") or "")).rstrip("/")
        if not base_url.lower().startswith(("http://", "https://")):
            raise UpstreamConfigError(f"{source}: upstream {name!r} needs an http(s) base_url.")
        specs.append(
            UpstreamSpec(
                name=name,
                base_url=base_url,
                keys=_spec_keys(entry),
                models=tuple(str(m) for m in (entry.get("models") or [])),
                allowed_paths=frozenset(entry.get("allowed_paths") or DEFAULT_ALLOWED_PATHS),
                is_default=bool(entry.get("default")),
                user_agent=_expand_env(str(entry.get("user_agent") or "")).strip(),
            )
        )
    default_name = str(raw.get("default") or "").strip()
    if default_name and default_name not in seen:
        raise UpstreamConfigError(f"{source}: default upstream {default_name!r} is not in 'upstreams'.")
    return specs, default_name


def _spec_keys(entry: dict) -> tuple[str, ...]:
    keys: list[str] = []
    for candidate in entry.get("api_keys") or []:
        expanded = _expand_env(str(candidate))
        if expanded:
            keys.append(expanded)
    inline = _expand_env(str(entry.get("api_key") or ""))
    if inline:
        keys.append(inline)
    env_name = str(entry.get("api_key_env") or "").strip()
    if env_name:
        from_env = os.environ.get(env_name, "").strip()
        if from_env:
            keys.append(from_env)
    # Preserve order, drop duplicates (a key listed inline and in the env is one key).
    return tuple(dict.fromkeys(keys))


class GenericUpstreamAdapter(UpstreamAdapter):
    """One proxy, many configured OpenAI-compatible upstreams, routed by model id."""

    auth_hint = "create ~/.merlin/proxy_upstreams.yaml (base_url + api_key_env per upstream)"
    setup_instructions = (
        "Create an upstream config (MERLIN_PROXY_UPSTREAMS overrides the default path):\n\n" + CONFIG_TEMPLATE
    )

    def __init__(self, path: Optional[str | os.PathLike] = None) -> None:
        self._path = Path(path) if path else None
        self._lock = threading.Lock()
        self._specs: Optional[list[UpstreamSpec]] = None
        self._default_name = ""
        self._rotation: dict[str, int] = {}

    # -- config -------------------------------------------------------------------------------
    @property
    def path(self) -> Path:
        return self._path or config_path()

    def reload(self) -> None:
        with self._lock:
            self._specs = None
            self._rotation.clear()

    def config_error(self) -> str:
        """The reason the config is unusable (empty string when it loads fine)."""
        try:
            self._load()
            return ""
        except UpstreamConfigError as exc:
            return str(exc)

    def specs(self) -> list[UpstreamSpec]:
        """Configured upstreams (raises ``UpstreamConfigError`` when the config is unusable)."""
        return list(self._load())

    def _load(self) -> list[UpstreamSpec]:
        with self._lock:
            if self._specs is None:
                specs, default_name = parse_specs(_read_config(self.path), self.path)
                self._specs, self._default_name = specs, default_name
            return self._specs

    # -- adapter contract ---------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "generic"

    @property
    def display_name(self) -> str:
        try:
            count = len(self._load())
        except UpstreamConfigError:
            return "Generic upstreams (unconfigured)"
        return f"Generic upstreams ({count} configured)"

    @property
    def allowed_paths(self) -> FrozenSet[str]:
        try:
            specs = self._load()
        except UpstreamConfigError:
            return DEFAULT_ALLOWED_PATHS
        union: set[str] = set()
        for spec in specs:
            union |= set(spec.allowed_paths)
        return frozenset(union) or DEFAULT_ALLOWED_PATHS

    def is_authenticated(self) -> bool:
        try:
            return any(spec.has_key for spec in self._load())
        except UpstreamConfigError:
            return False

    def get_credential(self) -> UpstreamCredential:
        return self.get_credential_for("")

    def request_overrides(self, model: str = "") -> dict:
        """Apply this upstream's ``user_agent`` to forwarded requests (WAF-safe UA)."""
        try:
            spec = self.route(model)
        except UpstreamConfigError:
            return {}
        return {"User-Agent": spec.user_agent} if spec.user_agent else {}

    def get_credential_for(self, model: str = "") -> UpstreamCredential:
        spec = self.route(model)
        if not spec.has_key:
            raise RuntimeError(
                f"Upstream {spec.name!r} has no API key: set api_key_env (currently unset) or api_key "
                f"in {self.path}."
            )
        key = self._current_key(spec)
        logger.debug("proxy: routing model %r -> upstream %s", model or "(default)", spec.name)
        return UpstreamCredential(bearer=key, base_url=spec.base_url)

    def get_retry_credential(
        self, *, failed_credential: UpstreamCredential, status_code: int
    ) -> Optional[UpstreamCredential]:
        """Rotate to the next configured key for the same upstream (401/429 only)."""
        if status_code not in {401, 429}:
            return None
        try:
            specs = self._load()
        except UpstreamConfigError:
            return None
        failed_base = failed_credential.base_url.rstrip("/")
        for spec in specs:
            if spec.base_url.rstrip("/") != failed_base or len(spec.keys) < 2:
                continue
            with self._lock:
                index = (self._rotation.get(spec.name, 0) + 1) % len(spec.keys)
                self._rotation[spec.name] = index
            rotated = spec.keys[index]
            if rotated == failed_credential.bearer:
                return None
            logger.info("proxy: upstream %s returned %s; retrying with rotated key", spec.name, status_code)
            return UpstreamCredential(bearer=rotated, base_url=spec.base_url)
        return None

    def describe(self) -> str:
        try:
            specs = self._load()
        except UpstreamConfigError as exc:
            return f"generic: {exc}".splitlines()[0]
        lines = [f"generic: {len(specs)} upstream(s) from {self.path}"]
        for spec in specs:
            state = f"{len(spec.keys)} key(s)" if spec.has_key else "NO KEY"
            models = ", ".join(spec.models) or "(catch-all)"
            lines.append(f"  - {spec.name}: {spec.base_url} [{state}] models={models}")
        return "\n".join(lines)

    # -- routing ------------------------------------------------------------------------------
    def route(self, model: str) -> UpstreamSpec:
        """Pick the upstream for ``model`` (see module docstring for precedence)."""
        specs = self._load()
        model = (model or "").strip()
        if model:
            exact = [s for s in specs if s.matches(model) and s.specificity > 0]
            if exact:
                return max(exact, key=lambda s: s.specificity)
            globbed = [s for s in specs if s.matches(model)]
            if globbed:
                return globbed[0]
        override = os.environ.get("MERLIN_PROXY_UPSTREAM", "").strip()
        for candidate in (override, self._default_name):
            if candidate:
                for spec in specs:
                    if spec.name == candidate:
                        return spec
        for spec in specs:
            if spec.is_default:
                return spec
        return specs[0]

    def _current_key(self, spec: UpstreamSpec) -> str:
        with self._lock:
            index = self._rotation.get(spec.name, 0) % len(spec.keys)
        return spec.keys[index]


__all__ = [
    "GenericUpstreamAdapter",
    "UpstreamSpec",
    "UpstreamConfigError",
    "config_path",
    "parse_specs",
    "DEFAULT_ALLOWED_PATHS",
    "CONFIG_TEMPLATE",
]
