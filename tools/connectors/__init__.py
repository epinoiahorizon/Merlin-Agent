"""Connector integration boundary for managed gateway accounts and local MCP servers.

Only the names below are cross-package surface; imports beyond it need a design decision.
Siblings: ``contract`` (states, actors, transition table), ``operation`` (the record),
``live`` (open operation per session), ``run`` (the lifecycle loop), ``managed`` / ``mcp``
(per-kind hooks), ``targets``, ``search``, ``dispatch``, ``gateway/`` (HTTP wire + client).

Exports resolve on first access (PEP 562), never at package-import time. Eagerly
re-exporting ``tools.connectors.tool`` here made the package lock and the ``tool`` module
lock invertible: ``tools/registry.py`` discovery imports ``tools.connectors.tool`` (parent
package lock, then module) while another thread importing the package ran this ``__init__``,
which asked for ``tool`` again — an ABBA on ``_ModuleLock`` that CPython reports as
``_DeadlockError: deadlock detected by _ModuleLock('tools.connectors.tool')`` and that
leaves the ``connections`` tool unregistered for the life of the process. Keep this file
free of sibling imports: same surface, resolved later.
"""

from importlib import import_module
from typing import Any

# name -> module that owns it. The indirection is what keeps the import graph acyclic:
# importing the package touches no sibling, so there is no second lock order to invert.
_LAZY_EXPORTS = {
    "CONNECTOR_BATCH_SENTINEL": "tools.connectors.gateway.names",
    "MANAGE_CONNECTIONS_SCHEMA": "tools.connectors.tool",
    "connector_describe": "tools.connectors.gateway.bridge",
    "connector_search_hits": "tools.connectors.gateway.bridge",
    "connectors_available": "tools.connectors.gateway.config",
    "dispatch_connector_batch": "tools.connectors.dispatch",
    "dispatch_connector_call": "tools.connectors.dispatch",
    "is_connector_name": "tools.connectors.gateway.names",
    "manage_connections": "tools.connectors.tool",
}

__all__ = [
    "CONNECTOR_BATCH_SENTINEL",
    "MANAGE_CONNECTIONS_SCHEMA",
    "connector_describe",
    "connector_search_hits",
    "connectors_available",
    "dispatch_connector_batch",
    "dispatch_connector_call",
    "is_connector_name",
    "manage_connections",
]


def __getattr__(name: str) -> Any:
    """Resolve one public name on first access, then cache it on the module."""
    try:
        module_name = _LAZY_EXPORTS[name]
    except KeyError:
        # AttributeError (not ImportError) is what lets ``from tools.connectors import
        # <sibling>`` fall through to the ordinary submodule import.
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(import_module(module_name), name)
    globals()[name] = value  # later accesses skip this hook entirely
    return value


def __dir__() -> list:
    return sorted(__all__)
