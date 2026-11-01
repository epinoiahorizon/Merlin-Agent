"""Minimal entry point for container deployments.

``merlin proxy …`` lives inside the full Merlin CLI, which pulls rich/typer/textual and the whole
agent runtime. A gateway container needs none of that: this entry wires only the proxy, its
adapters and the dashboard, so the image can stay small (aiohttp + segno + the proxy package).

    python -m merlin_cli.proxy.entry serve --provider generic --host 0.0.0.0 --port 8645
    python -m merlin_cli.proxy.entry dashboard --host 0.0.0.0 --port 8680 --qris /etc/gateway/qris.txt
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Optional


def _serve(args: argparse.Namespace) -> int:
    from merlin_cli.proxy.adapters import get_adapter
    from merlin_cli.proxy.server import run_server
    from merlin_cli.proxy.tenants import LedgerStore, Meter, meter_from_env

    try:
        adapter = get_adapter(args.provider)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    meter = meter_from_env()
    if meter is None and args.metered:
        meter = Meter(LedgerStore())
    print(
        f"gateway: provider={adapter.name} listen={args.host}:{args.port} "
        f"metering={'on' if meter is not None else 'off'}",
        file=sys.stderr,
    )
    asyncio.run(run_server(adapter, host=args.host, port=args.port, meter=meter))
    return 0


def _dashboard(args: argparse.Namespace) -> int:
    from aiohttp import web

    from merlin_cli.proxy import qris
    from merlin_cli.proxy.dashboard import create_dashboard_app
    from merlin_cli.proxy.probe import ProbeStore
    from merlin_cli.proxy.tenants import LedgerStore

    source: Optional[str] = (
        args.qris
        or os.environ.get("MERLIN_PROXY_QRIS_FILE", "")
        or os.environ.get("MERLIN_PROXY_QRIS", "")
    )
    if not source:
        print("error: no QRIS payload (use --qris, MERLIN_PROXY_QRIS_FILE or MERLIN_PROXY_QRIS)", file=sys.stderr)
        return 2
    try:
        payload = qris.load_static(source)
    except qris.QrisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    ledger = LedgerStore(os.environ.get("MERLIN_PROXY_LEDGER") or None)
    probes = ProbeStore(os.environ.get("MERLIN_PROXY_PROBES") or None)
    app = create_dashboard_app(
        ledger,
        probes,
        payload,
        admin_token=os.environ.get("MERLIN_PROXY_ADMIN_TOKEN", ""),
        webhook_secret=os.environ.get("MERLIN_PROXY_WEBHOOK_SECRET", ""),
        invoice_ttl_s=int(os.environ.get("MERLIN_PROXY_INVOICE_TTL", "1800")),
    )
    if not os.environ.get("MERLIN_PROXY_ADMIN_TOKEN"):
        token = getattr(app, "admin_token", "")
        print(f"dashboard: generated admin token = {token}", file=sys.stderr)
    info = qris.describe(payload)
    print(f"dashboard: merchant={info['merchant']} currency={info['currency']} port={args.port}", file=sys.stderr)
    web.run_app(app, host=args.host, port=args.port, print=None)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="merlin-proxy", description="Gateway container entry")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the OpenAI-compatible gateway")
    serve.add_argument("--provider", default="generic", help="Upstream adapter (default: generic)")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8645)
    serve.add_argument("--metered", action="store_true", help="Force metering even without the env flag")
    serve.set_defaults(handler=_serve)

    dashboard = sub.add_parser("dashboard", help="Run the status + top-up dashboard")
    dashboard.add_argument("--host", default="0.0.0.0")
    dashboard.add_argument("--port", type=int, default=8680)
    dashboard.add_argument("--qris", default=None, help="QRIS payload file (image or text)")
    dashboard.set_defaults(handler=_dashboard)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
