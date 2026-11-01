"""Generic (config-driven) upstream adapter: routing, key resolution/rotation, and a live e2e run."""

from __future__ import annotations

import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from merlin_cli.proxy.adapters.generic import (
    DEFAULT_ALLOWED_PATHS,
    GenericUpstreamAdapter,
    UpstreamConfigError,
    parse_specs,
)
from merlin_cli.proxy.server import create_app
from merlin_cli.proxy.tenants import LedgerStore, Meter


def _cfg(tmp_path, payload: dict, name: str = "proxy_upstreams.json"):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


TWO_UPSTREAMS = {
    "default": "first",
    "upstreams": [
        {
            "name": "first",
            "base_url": "https://first.example/v1",
            "api_key": "k-first",
            "models": ["alpha-exact", "alpha/*"],
        },
        {
            "name": "second",
            "base_url": "https://second.example/v1/",
            "api_key_env": "DEMO_UPSTREAM_VALUE",
            "models": ["beta-*"],
            "allowed_paths": ["/chat/completions"],
        },
    ],
}


# -- config parsing ------------------------------------------------------------------------
def test_parse_specs_reads_entries_and_default(tmp_path) -> None:
    specs, default = parse_specs(TWO_UPSTREAMS, tmp_path / "x.json")
    assert [s.name for s in specs] == ["first", "second"]
    assert default == "first"
    assert specs[1].base_url == "https://second.example/v1"  # trailing slash normalised
    assert specs[1].allowed_paths == frozenset({"/chat/completions"})


def test_duplicate_names_rejected(tmp_path) -> None:
    payload = {"upstreams": [{"name": "a", "base_url": "https://x/v1"}, {"name": "a", "base_url": "https://y/v1"}]}
    with pytest.raises(UpstreamConfigError, match="duplicate"):
        parse_specs(payload, tmp_path / "x.json")


def test_default_must_exist(tmp_path) -> None:
    payload = {"default": "ghost", "upstreams": [{"name": "a", "base_url": "https://x/v1"}]}
    with pytest.raises(UpstreamConfigError, match="ghost"):
        parse_specs(payload, tmp_path / "x.json")


def test_base_url_is_required(tmp_path) -> None:
    with pytest.raises(UpstreamConfigError, match="base_url"):
        parse_specs({"upstreams": [{"name": "a"}]}, tmp_path / "x.json")


def test_missing_file_names_the_path_and_shows_a_template(tmp_path) -> None:
    adapter = GenericUpstreamAdapter(tmp_path / "nope.yaml")
    with pytest.raises(UpstreamConfigError) as excinfo:
        adapter.route("any-model")
    message = str(excinfo.value)
    assert str(tmp_path / "nope.yaml") in message
    assert '"upstreams"' in message  # actionable JSON template, not a bare error


# -- routing -------------------------------------------------------------------------------
def test_exact_match_beats_glob(tmp_path) -> None:
    adapter = GenericUpstreamAdapter(_cfg(tmp_path, TWO_UPSTREAMS))
    assert adapter.route("alpha-exact").name == "first"
    assert adapter.route("alpha/whatever").name == "first"
    assert adapter.route("beta-mini").name == "second"


def test_unmatched_model_falls_back_to_default(tmp_path) -> None:
    adapter = GenericUpstreamAdapter(_cfg(tmp_path, TWO_UPSTREAMS))
    assert adapter.route("something-unlisted").name == "first"


def test_empty_models_means_catch_all(tmp_path) -> None:
    cfg = {"upstreams": [{"name": "solo", "base_url": "https://solo/v1", "api_key": "k"}]}
    adapter = GenericUpstreamAdapter(_cfg(tmp_path, cfg))
    assert adapter.route("anything-at-all").name == "solo"


def test_entry_level_default_flag_wins_over_position(tmp_path) -> None:
    cfg = {
        "upstreams": [
            {"name": "pos-first", "base_url": "https://a/v1", "api_key": "k1", "models": ["x-1"]},
            {"name": "flagged", "base_url": "https://b/v1", "api_key": "k2", "default": True},
        ]
    }
    adapter = GenericUpstreamAdapter(_cfg(tmp_path, cfg))
    assert adapter.route("unknown-model").name == "flagged"


def test_env_overrides_the_default_upstream(tmp_path, monkeypatch) -> None:
    adapter = GenericUpstreamAdapter(_cfg(tmp_path, TWO_UPSTREAMS))
    monkeypatch.setenv("MERLIN_PROXY_UPSTREAM", "second")
    assert adapter.route("unlisted-model").name == "second"


def test_user_agent_is_per_upstream(tmp_path) -> None:
    cfg = {
        "upstreams": [
            {"name": "waf", "base_url": "https://waf/v1", "api_key": "k", "models": ["waf-*"],
             "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/141.0.0.0"},
            {"name": "plain", "base_url": "https://plain/v1", "api_key": "k", "models": ["plain-*"]},
        ]
    }
    adapter = GenericUpstreamAdapter(_cfg(tmp_path, cfg))
    assert adapter.request_overrides("waf-model") == {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/141.0.0.0"
    }
    assert adapter.request_overrides("plain-model") == {}


def test_allowed_paths_are_the_union(tmp_path) -> None:
    adapter = GenericUpstreamAdapter(_cfg(tmp_path, TWO_UPSTREAMS))
    assert adapter.allowed_paths == frozenset({"/chat/completions", "/models", "/completions", "/embeddings", "/responses"})


def test_unconfigured_adapter_reports_no_paths_and_no_auth(tmp_path) -> None:
    adapter = GenericUpstreamAdapter(tmp_path / "absent.json")
    assert adapter.allowed_paths == DEFAULT_ALLOWED_PATHS
    assert adapter.is_authenticated() is False


# -- credentials ---------------------------------------------------------------------------
def test_credential_carries_the_routed_base_url_and_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_UPSTREAM_VALUE", "k-second")
    adapter = GenericUpstreamAdapter(_cfg(tmp_path, TWO_UPSTREAMS))
    assert adapter.is_authenticated() is True

    first = adapter.get_credential_for("alpha-exact")
    assert (first.base_url, first.bearer) == ("https://first.example/v1", "k-first")

    second = adapter.get_credential_for("beta-mini")
    assert (second.base_url, second.bearer) == ("https://second.example/v1", "k-second")


def test_env_expansion_inside_api_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_UPSTREAM_VALUE", "expanded-key")
    cfg = {"upstreams": [{"name": "a", "base_url": "https://a/v1", "api_key": "${DEMO_UPSTREAM_VALUE}"}]}
    adapter = GenericUpstreamAdapter(_cfg(tmp_path, cfg))
    assert adapter.get_credential_for("m").bearer == "expanded-key"


def test_missing_key_raises_actionable_error(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DEMO_UPSTREAM_VALUE", raising=False)
    adapter = GenericUpstreamAdapter(_cfg(tmp_path, TWO_UPSTREAMS))
    assert adapter.is_authenticated() is True  # "first" still has an inline key
    with pytest.raises(RuntimeError, match="DEMO_UPSTREAM_VALUE|api_key"):
        adapter.get_credential_for("beta-mini")


def test_retry_rotates_to_the_next_key(tmp_path) -> None:
    cfg = {
        "upstreams": [
            {"name": "pool", "base_url": "https://pool/v1", "api_keys": ["k1", "k2"], "models": ["m"]},
        ]
    }
    adapter = GenericUpstreamAdapter(_cfg(tmp_path, cfg))
    primary = adapter.get_credential_for("m")
    assert primary.bearer == "k1"

    retried = adapter.get_retry_credential(failed_credential=primary, status_code=429)
    assert retried is not None and retried.bearer == "k2"
    # Rotates back around the pool.
    again = adapter.get_retry_credential(failed_credential=retried, status_code=401)
    assert again is not None and again.bearer == "k1"


def test_no_rotation_for_non_auth_status_or_single_key(tmp_path) -> None:
    cfg = {"upstreams": [{"name": "solo", "base_url": "https://solo/v1", "api_key": "k1", "models": ["m"]}]}
    adapter = GenericUpstreamAdapter(_cfg(tmp_path, cfg))
    cred = adapter.get_credential_for("m")
    assert adapter.get_retry_credential(failed_credential=cred, status_code=500) is None
    assert adapter.get_retry_credential(failed_credential=cred, status_code=401) is None


def test_describe_lists_upstreams_and_flags_missing_keys(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DEMO_UPSTREAM_VALUE", raising=False)
    adapter = GenericUpstreamAdapter(_cfg(tmp_path, TWO_UPSTREAMS))
    text = adapter.describe()
    assert "first" in text and "second" in text
    assert "NO KEY" in text


# -- end to end: routing + billing together -------------------------------------------------
class _Echo:
    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.seen: list[str] = []
        self.app = web.Application()
        self.app.router.add_route("*", "/{tail:.*}", self.handle)

    async def handle(self, request: web.Request) -> web.StreamResponse:
        body = await request.read()
        self.seen.append(json.loads(body).get("model", ""))
        return web.json_response(
            {
                "id": f"{self.tag}-1",
                "choices": [{"message": {"content": self.tag}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
        )


@pytest.mark.asyncio
async def test_two_upstreams_are_routed_and_billed_independently(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_UPSTREAM_VALUE", "k-second")

    alpha, beta = _Echo("alpha"), _Echo("beta")
    alpha_server, beta_server = TestServer(alpha.app), TestServer(beta.app)
    await alpha_server.start_server()
    await beta_server.start_server()

    cfg = {
        "default": "alpha",
        "upstreams": [
            {"name": "alpha", "base_url": str(alpha_server.make_url("/v1")), "api_key": "k-a", "models": ["alpha-*"]},
            {"name": "beta", "base_url": str(beta_server.make_url("/v1")), "api_key_env": "DEMO_UPSTREAM_VALUE", "models": ["beta-*"]},
        ],
    }
    store = LedgerStore(tmp_path / "ledger.db")
    store.set_price("alpha-model", 1_000_000, 2_000_000)
    store.set_price("beta-model", 3_000_000, 4_000_000)
    tenant = store.create_tenant("acme", initial_micros=100_000)
    token = store.issue_key(tenant)

    adapter = GenericUpstreamAdapter(_cfg(tmp_path, cfg))
    client = TestClient(TestServer(create_app(adapter, meter=Meter(store))))
    await client.start_server()
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r1 = await client.post("/v1/chat/completions", json={"model": "alpha-model", "messages": []}, headers=headers)
        r2 = await client.post("/v1/chat/completions", json={"model": "beta-model", "messages": []}, headers=headers)
        assert r1.status == 200 and r2.status == 200
        assert (await r1.json())["choices"][0]["message"]["content"] == "alpha"
        assert (await r2.json())["choices"][0]["message"]["content"] == "beta"

        # Each host saw only its own model.
        assert alpha.seen == ["alpha-model"]
        assert beta.seen == ["beta-model"]

        # Each request was priced by its own model's rate card.
        events = {e["model"]: e for e in store.recent_usage(tenant)}
        assert events["alpha-model"]["cost_micros"] == 10 * 1 + 5 * 2       # 20
        assert events["beta-model"]["cost_micros"] == 10 * 3 + 5 * 4        # 50
        assert store.balance(tenant) == 100_000 - 70
    finally:
        await client.close()
        await alpha_server.close()
        await beta_server.close()
        store.close()
