"""HTTP server that forwards OpenAI-compatible requests to a configured upstream.

A credential-attaching forwarder: request/response bodies are never mediated, logged, or rewritten.
The one shim: after a *clean* upstream EOF, a ``text/event-stream`` response that carried a terminal
``finish_reason`` or ``lastOne: true`` but omitted ``data: [DONE]`` gets a single ``[DONE]`` frame.

With a ``Meter`` attached the same relay additionally *reads* (never rewrites) the bodies to bill the
caller: ``stream_options.include_usage`` is set on metered chat paths so streams report token counts,
an SSE scanner picks the last usage frame out of the passing chunks, and a hold reserved up front is
settled from that report. Bodies are still relayed byte-for-byte.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import uuid
from typing import Optional

try:
    import aiohttp
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    aiohttp = None  # type: ignore[assignment]
    web = None  # type: ignore[assignment]
    AIOHTTP_AVAILABLE = False

from merlin_cli.proxy.adapters.base import UpstreamAdapter, UpstreamCredential
from merlin_cli.proxy.metering import SseUsageScanner, Usage, ensure_include_usage, estimate_usage, parse_json_usage
from merlin_cli.proxy.sse_done import DONE_SSE_FRAME, SseDoneTracker, content_type_is_sse
from merlin_cli.proxy.tenants import Hold, InsufficientBalance, Meter

logger = logging.getLogger(__name__)

# Paths whose request body may carry a ``model`` and whose response carries ``usage``. Metering
# rewrites ``stream_options`` only here: ``/v1/messages`` (Anthropic wire) rejects unknown fields.
_METERED_PATHS = frozenset({"/chat/completions", "/completions"})


# Stripped when forwarding upstream: ``host``/``content-length`` are recomputed by aiohttp,
# ``authorization`` is replaced with our bearer; everything else passes through.
_HOP_BY_HOP_HEADERS = frozenset({
    "host", "content-length", "connection", "keep-alive", "proxy-authenticate",
    "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade", "authorization",
})
# aiohttp recomputes Content-Encoding/Content-Length on stream — let it.
_RESPONSE_DROP_HEADERS = _HOP_BY_HOP_HEADERS | {"content-encoding", "content-length"}

DEFAULT_PORT = 8645
DEFAULT_HOST = "127.0.0.1"
# Mirrors api_server's MAX_REQUEST_BYTES (10 MB); client_max_size bounds every read path,
# including chunked bodies.
MAX_REQUEST_BYTES = 10_000_000


def _require_aiohttp() -> None:
    if not AIOHTTP_AVAILABLE:
        raise RuntimeError("aiohttp is required for `merlin proxy`. Run `merlin setup` to install it.")


def _json_error(status: int, message: str, code: str = "proxy_error") -> "web.Response":
    """OpenAI-style error JSON response."""
    body = {"error": {"message": message, "type": code, "code": code}}
    return web.json_response(body, status=status)


def _filter_headers(headers, drop: frozenset = _HOP_BY_HOP_HEADERS) -> dict:
    """Strip hop-by-hop (+ auth) headers; ``drop`` widens the set for upstream responses."""
    return {key: value for key, value in headers.items() if key.lower() not in drop}


def _bearer_token(request: "web.Request") -> str:
    """Client credential presented to *this* proxy (``Authorization: Bearer mk_…``)."""
    prefix, _, token = request.headers.get("Authorization", "").partition(" ")
    return token.strip() if prefix.lower() == "bearer" else ""


def _request_id(request: "web.Request") -> str:
    """Billing key for this call: client-supplied (retry-safe) or generated."""
    supplied = (request.headers.get("X-Merlin-Request-Id") or "").strip()
    return supplied or "req_" + uuid.uuid4().hex[:24]


def _model_from_body(body: bytes) -> str:
    """Model id used for pricing, read from the request payload."""
    try:
        payload = json.loads(body) if body else {}
    except (ValueError, UnicodeDecodeError):
        return "unknown"
    model = payload.get("model") if isinstance(payload, dict) else None
    return str(model) if model else "unknown"


def _settle_hold(
    meter: "Meter",
    hold: "Hold",
    status: int,
    scanner: Optional[SseUsageScanner],
    buffered: Optional[bytearray],
    request_body: bytes,
    generated_bytes: int,
) -> None:
    """Charge or release the hold once the relay ends. Never raises into the response path."""
    try:
        if status >= 400:
            meter.release(hold)  # upstream refused: nothing was served, nothing is billed
            return
        usage: Optional[Usage] = None
        if scanner is not None:
            usage = scanner.usage
        elif buffered:
            usage = parse_json_usage(bytes(buffered))
        if usage is None:
            # Upstream reported nothing (or the stream died before its usage frame): charge a
            # conservative estimate rather than serve free tokens.
            usage = estimate_usage(request_body, generated_bytes)
        meter.settle(hold, usage, status="estimated" if usage.estimated else "ok")
    except Exception as exc:  # pragma: no cover - defensive: billing must not break responses
        logger.warning("proxy: settlement failed for %s: %s", hold.request_id, exc)


async def _open_upstream(
    request: "web.Request",
    rel_path: str,
    body: bytes,
    cred: UpstreamCredential,
    overrides: Optional[dict] = None,
):
    """Send the request upstream with ``cred``; returns ``(session, response)`` or
    ``(error_response, None)``."""
    upstream_url = f"{cred.base_url.rstrip('/')}{rel_path}"
    if request.query_string:  # preserved verbatim
        upstream_url = f"{upstream_url}?{request.query_string}"
    fwd_headers = _filter_headers(request.headers)
    fwd_headers["Authorization"] = f"{cred.token_type} {cred.bearer}"
    # Ask for an uncompressed body. We drop content-encoding on the way back (otherwise the client
    # receives raw brotli/gzip bytes with no header saying so), and aiohttp cannot decode `br`
    # without the optional Brotli package — Cloudflare-fronted relays do return it. Removing the
    # header is not enough: aiohttp then injects its own "gzip, deflate, zstd" default.
    fwd_headers["Accept-Encoding"] = "identity"
    if overrides:
        fwd_headers.update(overrides)
    logger.debug("proxy: forwarding %s %s -> %s (body=%d bytes)", request.method, rel_path, upstream_url, len(body))
    try:
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=300))
    except Exception as exc:  # pragma: no cover - aiohttp setup issue
        return _json_error(500, f"proxy session init failed: {exc}"), None
    try:
        upstream_resp = await session.request(
            request.method, upstream_url, data=body if body else None, headers=fwd_headers, allow_redirects=False
        )
    except RuntimeError as exc:
        await session.close()
        return _json_error(500, str(exc)), None
    except aiohttp.ClientError as exc:
        await session.close()
        logger.warning("proxy: upstream connection failed: %s", exc)
        return _json_error(502, f"upstream connection failed: {exc}", code="upstream_unreachable"), None
    except asyncio.TimeoutError:
        await session.close()
        return _json_error(504, "upstream request timed out", code="upstream_timeout"), None
    except Exception:
        await session.close()
        raise
    return session, upstream_resp


async def _stream_back(
    request: "web.Request",
    session,
    upstream_resp,
    *,
    meter: Optional["Meter"] = None,
    hold: Optional["Hold"] = None,
    request_id: str = "",
    request_body: bytes = b"",
) -> "web.StreamResponse":
    """Relay status + filtered headers, then the body chunk-by-chunk, appending a missing SSE
    ``[DONE]`` only after a clean EOF.

    With ``meter`` set the same bytes are also inspected — in-flight for SSE, buffered for JSON —
    so the upstream's ``usage`` report can settle the hold. Inspection never mutates what is sent.
    """
    resp_headers = _filter_headers(upstream_resp.headers, _RESPONSE_DROP_HEADERS)
    if request_id:
        resp_headers["X-Merlin-Request-Id"] = request_id
    resp = web.StreamResponse(status=upstream_resp.status, headers=resp_headers)
    await resp.prepare(request)
    done_tracker: Optional[SseDoneTracker] = None
    is_sse = content_type_is_sse(upstream_resp.headers)
    if is_sse:
        done_tracker = SseDoneTracker()
    scanner: Optional[SseUsageScanner] = SseUsageScanner() if (meter is not None and is_sse) else None
    buffered: Optional[bytearray] = bytearray() if (meter is not None and not is_sse) else None
    generated = 0
    try:
        async for chunk in upstream_resp.content.iter_any():
            if chunk:
                if done_tracker is not None:
                    done_tracker.feed(chunk)
                if scanner is not None:
                    scanner.feed(chunk)
                if buffered is not None:
                    buffered.extend(chunk)
                generated += len(chunk)
                await resp.write(chunk)
        if done_tracker is not None and done_tracker.should_append_done():
            try:
                await resp.write(DONE_SSE_FRAME)
            except Exception as exc:  # client hung up at EOF — harmless
                logger.debug("proxy: DONE append skipped: %s", exc)
    except (aiohttp.ClientError, asyncio.CancelledError, OSError) as exc:
        if done_tracker is not None:
            done_tracker.mark_interrupted()
        if scanner is not None:
            scanner.mark_interrupted()
        logger.warning("proxy: streaming interrupted: %s", exc)
    finally:
        upstream_resp.release()
        await session.close()
        if meter is not None and hold is not None:
            _settle_hold(meter, hold, upstream_resp.status, scanner, buffered, request_body, generated)
    await _safe_write_eof(resp)
    return resp


async def _safe_write_eof(resp) -> None:
    """Finish the response, tolerating a client that hung up first.

    Cloudflare (or any impatient client) can reset the connection while we are still writing. The
    old code let aiohttp raise ``ClientConnectionResetError`` out of the handler, producing a
    traceback per aborted request instead of a clean finish.
    """
    try:
        await resp.write_eof()
    except (ConnectionResetError, asyncio.CancelledError, OSError) as exc:
        logger.debug("proxy: client hung up before EOF: %s", exc)
    except Exception as exc:  # pragma: no cover - aiohttp internals; never break the loop
        logger.debug("proxy: write_eof failed: %s", exc)


def create_app(adapter: UpstreamAdapter, meter: Optional["Meter"] = None) -> "web.Application":
    """Build the aiohttp application bound to a specific upstream adapter.

    Every adapter method is synchronous and blocking (the Atlas adapter takes the 15s cross-process
    ``_auth_store_lock()`` and may POST a token refresh; xAI rotates its key pool under a lock),
    so all three are run via ``asyncio.to_thread`` — a contended lock or refresh must never freeze
    the single loop and every other in-flight streaming completion.

    ``meter`` turns the forwarder into a billing gateway: client keys are verified against the
    tenant ledger, a hold is reserved per request, and the upstream's usage report settles it. With
    ``meter=None`` behaviour is byte-for-byte the previous credential-attaching forwarder.
    """
    _require_aiohttp()
    app = web.Application(client_max_size=MAX_REQUEST_BYTES)
    # AppKey: forward-compat with aiohttp versions that strip bare-string keys.
    adapter_key = web.AppKey("adapter", UpstreamAdapter)
    meter_key = web.AppKey("meter", object)
    app[adapter_key] = adapter
    app[meter_key] = meter

    async def handle_health(request: "web.Request") -> "web.Response":
        authenticated = await asyncio.to_thread(adapter.is_authenticated)
        return web.json_response({"status": "ok", "upstream": adapter.display_name, "authenticated": authenticated})

    async def handle_models(request: "web.Request") -> "web.Response":
        """Serve the catalog we actually sell.

        GET /v1/models carries no body, so the metering path priced it as model 'unknown' and
        answered 402 "model 'unknown' has no price configured" — verified against production. A
        model listing is free and must never be forwarded/priced; SDKs call it before their first
        completion. Prices are the gateway's own rate card, which is exactly what a caller needs.
        """
        active_meter = app.get(meter_key)
        if not isinstance(active_meter, Meter):
            return _json_error(404, "model listing is only available on a metered gateway", code="not_supported")
        key = await asyncio.to_thread(active_meter.authenticate, _bearer_token(request))
        if key is None:
            return _json_error(401, "invalid or revoked Merlin API key", code="invalid_api_key")
        rows = await asyncio.to_thread(active_meter.store.models)
        data = [
            {
                "id": row["model"],
                "object": "model",
                "owned_by": "merlin-gateway",
                "pricing": {
                    "input_micros_per_million": row["in_micros_per_m"],
                    "output_micros_per_million": row["out_micros_per_m"],
                    "cache_read_micros_per_million": row["cache_read_micros_per_m"],
                },
            }
            for row in rows
        ]
        return web.json_response({"object": "list", "data": data})

    async def handle_proxy(request: "web.Request") -> "web.StreamResponse":
        rel_path = "/" + request.match_info.get("tail", "").lstrip("/")
        if rel_path not in adapter.allowed_paths:
            allowed = ", ".join(sorted(adapter.allowed_paths))
            return _json_error(
                404, f"Path /v1{rel_path} is not forwarded by this proxy. Allowed: {allowed}", code="path_not_allowed"
            )
        active_meter = app.get(meter_key)
        if not isinstance(active_meter, Meter):
            active_meter = None
        key = None
        if active_meter is not None:
            key = await asyncio.to_thread(active_meter.authenticate, _bearer_token(request))
            if key is None:
                return _json_error(401, "invalid or revoked Merlin API key", code="invalid_api_key")
        body = await request.read()
        model = _model_from_body(body)
        request_id = _request_id(request)
        try:
            cred = await asyncio.to_thread(adapter.get_credential_for, model)
        except Exception as exc:
            logger.warning("proxy: credential resolution failed: %s", exc)
            return _json_error(401, str(exc), code="upstream_auth_failed")
        overrides = adapter.request_overrides(model)
        hold = None
        if active_meter is not None and key is not None:
            if rel_path in _METERED_PATHS:
                # Ask OpenAI-compatible upstreams to report usage inside the stream; without it a
                # streamed response carries no token counts at all.
                body, _ = ensure_include_usage(body)
            try:
                hold = await asyncio.to_thread(active_meter.hold, key, model, request_id, estimate_usage(body))
            except InsufficientBalance as exc:
                return _json_error(402, str(exc), code="insufficient_balance")
            if hold is None:
                return _json_error(402, "insufficient balance for this request", code="insufficient_balance")
        session, upstream_resp = await _open_upstream(request, rel_path, body, cred, overrides)
        if upstream_resp is None:
            if active_meter is not None and hold is not None:
                await asyncio.to_thread(active_meter.release, hold)
            return session
        if upstream_resp.status in {401, 429}:
            # One-shot retry with a refreshed/rotated credential (Atlas: unconditional refresh
            # POST under the auth lock; xAI: pool rotation).
            try:
                retry_cred = await asyncio.to_thread(
                    adapter.get_retry_credential, failed_credential=cred, status_code=upstream_resp.status
                )
            except Exception as exc:
                logger.warning("proxy: retry credential resolution failed: %s", exc)
                retry_cred = None
            if retry_cred is not None:
                upstream_resp.release()
                await session.close()
                session, upstream_resp = await _open_upstream(request, rel_path, body, retry_cred, overrides)
                if upstream_resp is None:
                    if active_meter is not None and hold is not None:
                        await asyncio.to_thread(active_meter.release, hold)
                    return session
        return await _stream_back(
            request,
            session,
            upstream_resp,
            meter=active_meter,
            hold=hold,
            request_id=request_id,
            request_body=body,
        )

    app.router.add_get("/health", handle_health)  # never goes upstream
    # Registered before the catch-all so a body-less GET is answered from our rate card instead of
    # being forwarded and priced as model 'unknown'.
    app.router.add_get("/v1/models", handle_models)
    app.router.add_route("*", "/v1/{tail:.*}", handle_proxy)  # forwards if the path is allowed
    return app


async def run_server(
    adapter: UpstreamAdapter,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    shutdown_event: Optional[asyncio.Event] = None,
    meter: Optional["Meter"] = None,
) -> None:
    """Run the proxy in the current event loop until shutdown_event is set."""
    _require_aiohttp()
    app = create_app(adapter, meter=meter)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    logger.info("proxy: listening on http://%s:%d/v1 -> %s", host, port, adapter.display_name)
    stop_event = shutdown_event or asyncio.Event()
    if shutdown_event is None:  # we own the loop's lifetime → wire signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop_event.set)  # windows-footgun: ok
            except NotImplementedError:
                pass  # Windows / restricted envs — Ctrl+C still raises KeyboardInterrupt
    try:
        await stop_event.wait()
    finally:
        logger.info("proxy: shutting down")
        await runner.cleanup()


__all__ = ["create_app", "run_server", "DEFAULT_HOST", "DEFAULT_PORT", "AIOHTTP_AVAILABLE"]
