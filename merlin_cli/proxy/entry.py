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


def _load_env_file(path: str) -> None:
    """Apply ``KEY=VALUE`` lines to ``os.environ``.

    Container/Task-Scheduler deployments must not depend on inherited environment variables: a
    scheduled task can start a child with a different environment than the shell that configured it
    (found in production — PYTHONPATH never reached the process and Python died on import). Passing
    an env file explicitly makes the launch self-contained.
    """
    from pathlib import Path

    target = Path(path)
    if not target.exists():
        raise SystemExit(f"error: env file not found: {target}")
    for line in target.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _serve(args: argparse.Namespace) -> int:
    from merlin_cli.proxy.adapters import get_adapter
    from merlin_cli.proxy.server import run_server
    from merlin_cli.proxy.tenants import LedgerStore, Meter, meter_from_env

    if getattr(args, "upstreams", None):
        os.environ["MERLIN_PROXY_UPSTREAMS"] = args.upstreams
    if getattr(args, "ledger", None):
        os.environ["MERLIN_PROXY_LEDGER"] = args.ledger
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

    for attribute, env_name in (
        ("ledger", "MERLIN_PROXY_LEDGER"),
        ("probes", "MERLIN_PROXY_PROBES"),
        ("admin_token", "MERLIN_PROXY_ADMIN_TOKEN"),
    ):
        value = getattr(args, attribute, None)
        if value:
            os.environ[env_name] = value
    if getattr(args, "ttl", None):
        os.environ["MERLIN_PROXY_INVOICE_TTL"] = str(args.ttl)

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
    serve.add_argument("--upstreams", default=None, help="Path to proxy_upstreams.json")
    serve.add_argument("--ledger", default=None, help="Path to the billing SQLite file")
    serve.add_argument("--env-file", dest="env_file", default=None, help="KEY=VALUE file applied first")
    serve.set_defaults(handler=_serve)

    dashboard = sub.add_parser("dashboard", help="Run the status + top-up dashboard")
    dashboard.add_argument("--host", default="0.0.0.0")
    dashboard.add_argument("--port", type=int, default=8680)
    dashboard.add_argument("--qris", default=None, help="QRIS payload file (image or text)")
    dashboard.add_argument("--ledger", default=None)
    dashboard.add_argument("--probes", default=None)
    dashboard.add_argument("--admin-token", dest="admin_token", default=None)
    dashboard.add_argument("--ttl", type=int, default=None, help="Invoice lifetime in seconds")
    dashboard.add_argument("--env-file", dest="env_file", default=None, help="KEY=VALUE file applied first")
    dashboard.set_defaults(handler=_dashboard)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "env_file", None):
        _load_env_file(args.env_file)
    return int(args.handler(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
