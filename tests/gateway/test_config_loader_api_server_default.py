"""A stock install answers on the documented loopback endpoint without extra setup.

`http://127.0.0.1:8642/v1` is the documented default, but `get_connected_platforms()` needs
`platforms.api_server` enabled AND a strong key, so an install that never mentioned the platform
bound no TCP port at all: every client aimed at 8642 got connection refused with no hint why.
`_default_api_server_when_unconfigured` seeds that block — and must never override an explicit one.
"""

from __future__ import annotations

import pytest

from gateway import config_loader
from gateway.platforms import _shared as platforms_shared


@pytest.fixture
def no_env_key(monkeypatch):
    """No ambient API_SERVER_KEY: the synthesized block generates its own."""
    monkeypatch.delenv("API_SERVER_KEY", raising=False)
    monkeypatch.setenv("API_SERVER_HOST", "127.0.0.1")
    monkeypatch.setenv("API_SERVER_PORT", "8642")
    monkeypatch.setattr(platforms_shared, "get_scoped_secret", lambda name, default="": "")


def test_default_loopback_api_server_is_seeded_when_unconfigured(no_env_key):
    platforms: dict = {}

    config_loader._default_api_server_when_unconfigured({}, platforms)

    block = platforms["api_server"]
    assert block["enabled"] is True
    assert block["extra"]["host"] == "127.0.0.1"
    assert block["extra"]["port"] == "8642"
    assert block["extra"]["_default_loopback"] is True
    # A generated key must satisfy the "strong key" gate get_connected_platforms applies.
    assert block["extra"]["key"].startswith("mga_")
    assert len(block["extra"]["key"]) >= 16


def test_an_explicit_block_always_wins_even_when_disabled(no_env_key):
    explicit = {"api_server": {"enabled": False, "extra": {"port": "9999"}}}
    platforms = {"api_server": dict(explicit["api_server"])}

    config_loader._default_api_server_when_unconfigured({}, platforms)

    assert platforms["api_server"] == explicit["api_server"]


@pytest.mark.parametrize(
    "yaml_cfg",
    [
        {"gateway": {"api_server": {"enabled": False}}},  # legacy nested subsection
        {"api_server": {"enabled": True, "extra": {}}},  # legacy top-level subsection
    ],
)
def test_a_legacy_subsection_counts_as_configured(no_env_key, yaml_cfg):
    platforms: dict = {}

    config_loader._default_api_server_when_unconfigured(yaml_cfg, platforms)

    assert "api_server" not in platforms


def test_a_strong_configured_key_is_reused_not_regenerated(monkeypatch):
    monkeypatch.setenv("API_SERVER_HOST", "127.0.0.1")
    monkeypatch.setenv("API_SERVER_PORT", "8642")
    configured = "mga_" + "k" * 32
    monkeypatch.setattr(platforms_shared, "get_scoped_secret", lambda name, default="": configured)
    platforms: dict = {}

    config_loader._default_api_server_when_unconfigured({}, platforms)

    assert platforms["api_server"]["extra"]["key"] == configured


def test_a_secondary_profile_never_seeds_its_own_listener(no_env_key, monkeypatch):
    """#100397: a secondary profile is served at /p/<profile>/v1 by the DEFAULT's listener.

    Seeding an enabled block under a profile scope would make every secondary try to bind the
    default's port, so the seeding is default-profile-only.
    """
    monkeypatch.setattr(platforms_shared, "profile_scoped", lambda: True)
    platforms: dict = {}

    config_loader._default_api_server_when_unconfigured({}, platforms)

    assert "api_server" not in platforms
