"""A host that mirrors the served profile into MERLIN_HOME must not flip launch-home identity.

Merlin WebUI serves several profiles from one process and, for legacy readers, mirrors the active
turn's profile into ``os.environ["MERLIN_HOME"]`` while also installing the context-local override.
Every "is this task routed / is this the launch home" decision that compared the override with the
live env var then saw the served home as the launch home: MCP connections were keyed by bare name
(shared across profiles), the launch residue was never stripped from the served profile's child env,
the launch profile's bridged allow-all grant was seeded into the served profile's secret scope, and
the served profile's ``terminal.*`` config was bridged into the shared process env.
``merlin_constants.pin_process_merlin_home`` gives such hosts one stable anchor for all of them.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import merlin_constants
from agent.secret_scope import _is_process_home, serves_routed_profile
from merlin_cli.env_loader import _process_merlin_home
from tools.environments.local import _is_routed_home
from tools.mcp_tool_scope import _server_key


def _under(home, fn):
    """Run *fn* with *home* installed as the task's Merlin-home override."""
    token = merlin_constants.set_merlin_home_override(home)
    try:
        return fn()
    finally:
        merlin_constants.reset_merlin_home_override(token)


# name -> "does this decision treat *home* as a routed (non-launch) profile?"
ROUTED = {
    "secret_scope.serves_routed_profile": lambda home: _under(home, serves_routed_profile),
    "secret_scope._is_process_home": lambda home: not _is_process_home(home),
    "environments.local._is_routed_home": lambda home: _is_routed_home(home),
    "env_loader._process_merlin_home": lambda home: _process_merlin_home().resolve() != Path(home).resolve(),
    "mcp_tool_scope._server_key": lambda home: _under(home, lambda: _server_key("atlassian")) != "atlassian",
}


@pytest.fixture
def homes(tmp_path, monkeypatch):
    launch = tmp_path / "launch"
    served = tmp_path / "profiles" / "served"
    launch.mkdir()
    served.mkdir(parents=True)
    monkeypatch.setenv("MERLIN_HOME", str(launch))
    monkeypatch.setattr(merlin_constants, "_PINNED_PROCESS_MERLIN_HOME", None)
    return launch, served


@pytest.mark.parametrize("decision", sorted(ROUTED))
def test_pinned_launch_home_survives_a_mirrored_merlin_home(homes, monkeypatch, decision):
    launch, served = homes
    routed = ROUTED[decision]
    merlin_constants.pin_process_merlin_home(launch)
    monkeypatch.setenv("MERLIN_HOME", str(served))  # the host's per-turn mirror

    assert routed(served) is True
    assert routed(launch) is False
    # The served profile's MCP connection is its own, keyed by its home, not a bare shared name.
    assert _under(served, lambda: _server_key("atlassian")) == (merlin_constants.merlin_home_key(served), "atlassian")
    # Process-asset readers keep following the env var: only routing decisions use the pin.
    assert merlin_constants.get_process_merlin_home() == served
    assert merlin_constants.get_routing_process_merlin_home() == launch


@pytest.mark.parametrize("decision", sorted(ROUTED))
def test_unpinned_or_cleared_pin_keeps_merlin_home_semantics(homes, monkeypatch, decision):
    launch, served = homes
    routed = ROUTED[decision]
    for _ in ("never pinned", "pinned then cleared"):
        monkeypatch.setenv("MERLIN_HOME", str(launch))
        assert routed(served) is True
        assert routed(launch) is False
        monkeypatch.setenv("MERLIN_HOME", str(served))  # mirrored: the env var IS the launch home
        assert routed(served) is False
        merlin_constants.pin_process_merlin_home(launch)
        merlin_constants.pin_process_merlin_home(None)
