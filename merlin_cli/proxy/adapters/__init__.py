"""Upstream adapter registry.

Adapters are imported **lazily**, one at a time. That is what makes a slim deployment possible: a
gateway that only uses ``generic`` (config-driven upstreams) must not drag in ``merlin_cli.auth`` or
``agent.credential_pool``, which the OAuth adapters (atlas, xAI) need. Without this, running the
proxy in a small container meant installing the whole Merlin runtime.
"""

from __future__ import annotations

import importlib
from typing import Dict, Tuple, Type

from merlin_cli.proxy.adapters.base import UpstreamAdapter

# name -> (module path, class name). This table is the only place a new adapter must be declared;
# ``merlin proxy start --provider <name>`` keys off it.
ADAPTERS: Dict[str, Tuple[str, str]] = {
    "atlas": ("merlin_cli.proxy.adapters.atlas_portal", "AtlasPortalAdapter"),
    "xai": ("merlin_cli.proxy.adapters.xai", "XAIGrokAdapter"),
    "generic": ("merlin_cli.proxy.adapters.generic", "GenericUpstreamAdapter"),
}


def adapter_names() -> list[str]:
    """Adapter keys accepted by ``merlin proxy start --provider``."""
    return sorted(ADAPTERS)


def adapter_class(name: str) -> Type[UpstreamAdapter]:
    """Import and return the adapter class for ``name`` (raises ``ValueError`` when unknown)."""
    key = (name or "").strip().lower()
    if key not in ADAPTERS:
        available = ", ".join(adapter_names()) or "(none)"
        raise ValueError(f"Unknown proxy upstream provider: {name!r}. Available: {available}")
    module_path, class_name = ADAPTERS[key]
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def get_adapter(name: str) -> UpstreamAdapter:
    """Instantiate an adapter by provider name."""
    return adapter_class(name)()


__all__ = ["UpstreamAdapter", "ADAPTERS", "adapter_names", "adapter_class", "get_adapter"]
