"""End-to-end: metered proxy in front of a mock OpenAI-compatible upstream.

These tests are the deliverable's proof: a streamed completion is relayed byte-for-byte, the
upstream's usage report lands in the ledger, the tenant balance moves by the exact cost, a retry
with the same ``X-Merlin-Request-Id`` does not double-charge, and an upstream failure refunds the
hold instead of billing the caller.
"""

from __future__ import annotations

import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from merlin_cli.proxy.adapters.base import UpstreamAdapter, UpstreamCredential
from merlin_cli.proxy.server import create_app
from merlin_cli.proxy.tenants import LedgerStore, Meter

pytestmark = pytest.mark.asyncio

PRICE_IN = 1_000_000  # $1.00 / 1M tokens
PRICE_OUT = 2_000_000  # $2.00 / 1M tokens
MODEL = "test-model"


class MockUpstream:
    """OpenAI-compatible upstream that echoes a canned SSE stream or JSON completion."""

    def __init__(self, mode: str = "stream", status: int = 200) -> None:
        self.mode, self.status = mode, status
        self.bodies: list[bytes] = []
        self.user_agents: list[str] = []
        self.accept_encodings: list[str] = []
        self.app = web.Application()
        self.app.router.add_route("*", "/{tail:.*}", self.handle)

    async def handle(self, request: web.Request) -> web.StreamResponse:
        self.bodies.append(await request.read())
        self.user_agents.append(request.headers.get("User-Agent", ""))
        self.accept_encodings.append(request.headers.get("Accept-Encoding", ""))
        if self.status >= 400:
            return web.json_response({"error": {"message": "upstream exploded"}}, status=self.status)
        if self.mode == "json_no_usage":
            return web.json_response({"id": "chatcmpl-no-usage", "choices": [{"message": {"content": "hi"}}]})
        if self.mode == "stream":
            resp = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
            await resp.prepare(request)
            for frame in (
                b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n',
                b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n',
                b'data: {"choices":[],"usage":{"prompt_tokens":100,"completion_tokens":50}}\n\n',
            ):
                await resp.write(frame)
            return resp  # deliberately no [DONE]: the proxy must append it
        return web.json_response(
            {
                "id": "chatcmpl-1",
                "choices": [{"message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 30},
            }
        )


class StubAdapter(UpstreamAdapter):
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    @property
    def name(self) -> str:
        return "stub"

    @property
    def display_name(self) -> str:
        return "Stub Upstream"

    @property
    def allowed_paths(self):
        return frozenset({"/chat/completions", "/completions", "/models"})

    def is_authenticated(self) -> bool:
        return True

    def get_credential(self) -> UpstreamCredential:
        return UpstreamCredential(bearer="upstream-secret", base_url=self._base)


class Harness:
    def __init__(self, store: LedgerStore, meter: Meter, client: TestClient, upstream: MockUpstream, server):
        self.store, self.meter = store, meter
        self.client, self.upstream, self.server = client, upstream, server
        self.tenant_id = ""
        self.key = ""

    async def aclose(self) -> None:
        await self.client.close()
        await self.server.close()
        self.store.close()


async def _harness(tmp_path, *, mode: str = "stream", status: int = 200, balance: int = 10_000) -> Harness:
    upstream = MockUpstream(mode=mode, status=status)
    up_server = TestServer(upstream.app)
    await up_server.start_server()

    store = LedgerStore(tmp_path / "ledger.db")
    store.set_price(MODEL, PRICE_IN, PRICE_OUT)
    tenant_id = store.create_tenant("acme", initial_micros=balance)
    token = store.issue_key(tenant_id, label="test")
    meter = Meter(store)

    proxy_client = TestClient(TestServer(create_app(StubAdapter(str(up_server.make_url("/v1"))), meter=meter)))
    await proxy_client.start_server()

    harness = Harness(store, meter, proxy_client, upstream, up_server)
    harness.tenant_id, harness.key = tenant_id, token
    return harness


def _payload(stream: bool = True) -> dict:
    return {
        "model": MODEL,
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 64,
        "stream": stream,
    }


async def _close(harness: Harness) -> None:
    await harness.aclose()


# -- auth ----------------------------------------------------------------------------------
async def test_request_without_key_is_rejected_before_forwarding(tmp_path) -> None:
    h = await _harness(tmp_path)
    try:
        resp = await h.client.post("/v1/chat/completions", json=_payload())
        assert resp.status == 401
        assert (await resp.json())["error"]["code"] == "invalid_api_key"
        assert h.upstream.bodies == []  # never reached the upstream
    finally:
        await _close(h)


async def test_revoked_key_is_rejected(tmp_path) -> None:
    h = await _harness(tmp_path)
    try:
        assert h.store.revoke_key(h.key) is True
        resp = await h.client.post(
            "/v1/chat/completions", json=_payload(), headers={"Authorization": f"Bearer {h.key}"}
        )
        assert resp.status == 401
    finally:
        await _close(h)


# -- billing a stream ----------------------------------------------------------------------
async def test_streamed_completion_is_relayed_and_billed(tmp_path) -> None:
    h = await _harness(tmp_path)
    try:
        resp = await h.client.post(
            "/v1/chat/completions", json=_payload(), headers={"Authorization": f"Bearer {h.key}"}
        )
        assert resp.status == 200
        body = await resp.text()

        # Relay fidelity: payload untouched, missing [DONE] appended, request id exposed.
        assert "Hello" in body
        assert '"finish_reason":"stop"' in body
        assert body.rstrip().endswith("data: [DONE]")
        assert resp.headers.get("X-Merlin-Request-Id", "").startswith("req_")

        # The proxy asked the upstream for usage inside the stream.
        sent = json.loads(h.upstream.bodies[0])
        assert sent["stream_options"] == {"include_usage": True}

        # Ledger: exactly one event, exact cost, hold released.
        events = h.store.recent_usage(h.tenant_id)
        assert len(events) == 1
        event = events[0]
        assert (event["prompt_tokens"], event["completion_tokens"]) == (100, 50)
        assert event["status"] == "ok"
        assert event["cost_micros"] == 100 * 1 + 50 * 2
        assert h.store.balance(h.tenant_id) == 10_000 - 200
        assert h.store.available(h.tenant_id) == 10_000 - 200  # nothing left reserved
    finally:
        await _close(h)


async def test_retry_with_same_request_id_is_charged_once(tmp_path) -> None:
    h = await _harness(tmp_path)
    try:
        headers = {"Authorization": f"Bearer {h.key}", "X-Merlin-Request-Id": "req_client_retry_1"}
        first = await h.client.post("/v1/chat/completions", json=_payload(), headers=headers)
        assert first.status == 200
        await first.text()
        balance_after_first = h.store.balance(h.tenant_id)

        second = await h.client.post("/v1/chat/completions", json=_payload(), headers=headers)
        assert second.status == 200
        await second.text()

        assert h.store.balance(h.tenant_id) == balance_after_first
        assert len(h.store.recent_usage(h.tenant_id)) == 1
        assert h.store.available(h.tenant_id) == balance_after_first
    finally:
        await _close(h)


# -- non-stream ----------------------------------------------------------------------------
async def test_json_completion_uses_reported_usage(tmp_path) -> None:
    h = await _harness(tmp_path, mode="json")
    try:
        resp = await h.client.post(
            "/v1/chat/completions",
            json=_payload(stream=False),
            headers={"Authorization": f"Bearer {h.key}"},
        )
        assert resp.status == 200
        payload = await resp.json()
        assert payload["usage"]["prompt_tokens"] == 120  # body passed through unchanged

        event = h.store.recent_usage(h.tenant_id)[0]
        assert (event["prompt_tokens"], event["completion_tokens"]) == (120, 30)
        assert event["cost_micros"] == 120 * 1 + 30 * 2
        assert h.store.balance(h.tenant_id) == 10_000 - 180
    finally:
        await _close(h)


# -- failure and refusal paths -------------------------------------------------------------
async def test_insufficient_balance_returns_402_and_does_not_forward(tmp_path) -> None:
    h = await _harness(tmp_path, balance=5)  # below any plausible hold
    try:
        resp = await h.client.post(
            "/v1/chat/completions", json=_payload(), headers={"Authorization": f"Bearer {h.key}"}
        )
        assert resp.status == 402
        assert (await resp.json())["error"]["code"] == "insufficient_balance"
        assert h.upstream.bodies == []
        assert h.store.balance(h.tenant_id) == 5
    finally:
        await _close(h)


async def test_upstream_error_releases_the_hold(tmp_path) -> None:
    h = await _harness(tmp_path, status=500)
    try:
        resp = await h.client.post(
            "/v1/chat/completions", json=_payload(), headers={"Authorization": f"Bearer {h.key}"}
        )
        assert resp.status == 500
        await resp.read()

        assert h.store.recent_usage(h.tenant_id) == []
        assert h.store.balance(h.tenant_id) == 10_000
        assert h.store.available(h.tenant_id) == 10_000
    finally:
        await _close(h)


async def test_unmetered_proxy_keeps_previous_behaviour(tmp_path) -> None:
    """With ``meter=None`` any client bearer is accepted and nothing is billed (back-compat)."""
    upstream = MockUpstream(mode="stream")
    up_server = TestServer(upstream.app)
    await up_server.start_server()
    client = TestClient(TestServer(create_app(StubAdapter(str(up_server.make_url("/v1"))))))
    await client.start_server()
    try:
        resp = await client.post(
            "/v1/chat/completions", json=_payload(), headers={"Authorization": "Bearer any-client-token"}
        )
        assert resp.status == 200
        assert "Hello" in await resp.text()
    finally:
        await client.close()
        await up_server.close()


async def test_upstream_user_agent_override_reaches_the_upstream(tmp_path) -> None:
    """A WAF-fronted relay bans unknown fingerprints; the adapter's UA must replace the client's."""
    browser_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/141.0.0.0 Safari/537.36"

    class UaAdapter(StubAdapter):
        def request_overrides(self, model: str = "") -> dict:
            return {"User-Agent": browser_ua}

    upstream = MockUpstream(mode="json")
    up_server = TestServer(upstream.app)
    await up_server.start_server()
    store = LedgerStore(tmp_path / "ledger.db")
    store.set_price(MODEL, PRICE_IN, PRICE_OUT)
    tenant = store.create_tenant("acme", initial_micros=10_000)
    token = store.issue_key(tenant)
    client = TestClient(TestServer(create_app(UaAdapter(str(up_server.make_url("/v1"))), meter=Meter(store))))
    await client.start_server()
    try:
        response = await client.post(
            "/v1/chat/completions",
            json=_payload(stream=False),
            headers={"Authorization": f"Bearer {token}", "User-Agent": "curl/8.5.0"},
        )
        assert response.status == 200
        await response.read()
        assert upstream.user_agents == [browser_ua]
    finally:
        await client.close()
        await up_server.close()
        store.close()


async def test_upstream_is_never_asked_for_a_compressed_body(tmp_path) -> None:
    """We drop content-encoding on the way back, so we must not request br/gzip upstream.

    A Cloudflare-fronted relay happily answers `Accept-Encoding: br`; aiohttp without the Brotli
    package then fails with "Can not decode content-encoding: brotli", surfacing as a 502 to the
    client. Requesting identity removes the whole class of failure.
    """
    h = await _harness(tmp_path, mode="json")
    try:
        response = await h.client.post(
            "/v1/chat/completions",
            json=_payload(stream=False),
            headers={"Authorization": f"Bearer {h.key}", "Accept-Encoding": "gzip, br"},
        )
        assert response.status == 200
        await response.read()
        assert h.upstream.accept_encodings == ["identity"]
    finally:
        await _close(h)


async def test_upstream_without_usage_is_billed_as_estimated(tmp_path) -> None:
    """No usage frame and no JSON usage: the ledger records an explicitly estimated charge."""
    h = await _harness(tmp_path, mode="json")
    try:
        h.upstream.mode = "json_no_usage"
        resp = await h.client.post(
            "/v1/chat/completions", json=_payload(stream=False), headers={"Authorization": f"Bearer {h.key}"}
        )
        assert resp.status == 200
        await resp.read()

        event = h.store.recent_usage(h.tenant_id)[0]
        assert event["status"] == "estimated"
        assert event["estimated"] == 1
        assert event["cost_micros"] > 0
        assert h.store.available(h.tenant_id) < 10_000
    finally:
        await _close(h)


# -- model listing -------------------------------------------------------------------------
async def test_model_listing_is_free_and_never_forwarded(tmp_path) -> None:
    """GET /v1/models must answer from our rate card.

    Regression: it used to fall through to the metered forwarder, which has no body to read a model
    from, priced the request as model 'unknown' and returned 402 — verified against the live
    gateway. SDKs call this endpoint before their first completion.
    """
    h = await _harness(tmp_path)
    try:
        resp = await h.client.get("/v1/models", headers={"Authorization": f"Bearer {h.key}"})
        assert resp.status == 200
        payload = await resp.json()
        assert payload["object"] == "list"
        ids = [entry["id"] for entry in payload["data"]]
        assert MODEL in ids
        entry = next(e for e in payload["data"] if e["id"] == MODEL)
        assert entry["pricing"]["input_micros_per_million"] == PRICE_IN
        assert entry["pricing"]["output_micros_per_million"] == PRICE_OUT
        assert h.upstream.bodies == []  # listing is served locally, never forwarded
        # Listing must not move money either.
        assert h.store.balance(h.tenant_id) == 10_000
    finally:
        await _close(h)


async def test_model_listing_requires_a_valid_key(tmp_path) -> None:
    h = await _harness(tmp_path)
    try:
        assert (await h.client.get("/v1/models")).status == 401
        assert (await h.client.get("/v1/models", headers={"Authorization": "Bearer mk_nope"})).status == 401
    finally:
        await _close(h)
