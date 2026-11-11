"""CLI handlers for the ``merlin proxy`` subcommand."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from typing import Any

from merlin_cli.proxy.adapters import ADAPTERS, get_adapter
from merlin_cli.proxy.server import (
    AIOHTTP_AVAILABLE, DEFAULT_HOST, DEFAULT_PORT, run_server
)
from merlin_cli.proxy.tenants import meter_from_env

logger = logging.getLogger(__name__)


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def cmd_proxy_start(args: Any) -> int:
    """Run the proxy server in the foreground."""
    if not AIOHTTP_AVAILABLE:
        _err("merlin proxy requires aiohttp. Run `merlin setup` to install it.")
        return 1
    provider = getattr(args, "provider", None) or "atlas"
    try:
        adapter = get_adapter(provider)
    except ValueError as exc:
        _err(f"Error: {exc}")
        return 2
    if not adapter.is_authenticated():
        config_error = getattr(adapter, "config_error", lambda: "")()
        if config_error:
            _err(f"{adapter.display_name} is not usable.\n\n{config_error}")
        else:
            setup = getattr(adapter, "setup_instructions", "")
            if setup:
                _err(f"{adapter.display_name} is not configured.\n\n{setup}")
            else:
                auth_hint = getattr(adapter, "auth_hint", f"merlin auth add {adapter.name}")
                _err(f"Not logged into {adapter.display_name}. Run `{auth_hint}` first.")
        return 2
    host = getattr(args, "host", None) or DEFAULT_HOST
    port = getattr(args, "port", None) or DEFAULT_PORT
    meter = meter_from_env()
    if meter is not None:
        _err(
            f"Starting Merlin proxy for {adapter.display_name}  [METERED]\n"
            f"  Listening on:  http://{host}:{port}/v1\n"
            f"  Billing DB:    {meter.store.path}\n"
            f"  Clients must send: Authorization: Bearer mk_… (tenant key)\n"
            f"  Send X-Merlin-Request-Id on retries to avoid double billing.\n"
            f"\n"
            f"Press Ctrl+C to stop."
        )
    else:
        _err(
            f"Starting Merlin proxy for {adapter.display_name}\n"
            f"  Listening on:  http://{host}:{port}/v1\n"
            f"  Forwarding to: (resolved per-request from your subscription)\n"
            f"  Use any bearer token in the client — the proxy attaches your real credential.\n"
            f"\n"
            f"Press Ctrl+C to stop."
        )
    try:
        asyncio.run(run_server(adapter, host=host, port=port, meter=meter))
    except KeyboardInterrupt:
        _err("\nproxy: stopped")
    except OSError as exc:
        _err(f"proxy: failed to bind {host}:{port}: {exc}")
        return 1
    return 0


def cmd_proxy_status(args: Any) -> int:
    """Print the status of each configured upstream adapter."""
    print("Merlin proxy upstream adapters\n")
    for name in sorted(ADAPTERS):
        adapter = get_adapter(name)
        if not adapter.is_authenticated():
            print(f"  [{name:8s}] {adapter.display_name} — not logged in")
            continue
        try:
            cred = adapter.get_credential()
        except Exception as exc:
            print(f"  [{name:8s}] {adapter.display_name} — credentials need attention ({exc})")
            continue
        expires = f" (bearer expires {cred.expires_at})" if cred.expires_at else ""
        print(f"  [{name:8s}] {adapter.display_name} — ready{expires}")
    print("\nStart the proxy with: merlin proxy start [--provider <name>]")
    return 0


def cmd_proxy_list_providers(args: Any) -> int:
    """List available proxy upstream providers."""
    print("Available proxy upstream providers:")
    for name in sorted(ADAPTERS):
        adapter = get_adapter(name)
        print(f"  {name}  — {adapter.display_name}")
    return 0


def cmd_proxy_catalog(args: Any) -> int:
    """``merlin proxy catalog <sync|list>`` — price book maintenance."""
    from merlin_cli.proxy import catalog as cat
    from merlin_cli.proxy.adapters.generic import GenericUpstreamAdapter
    from merlin_cli.proxy.tenants import LedgerStore

    action = getattr(args, "catalog_command", None) or "list"
    store = LedgerStore(os.environ.get("MERLIN_PROXY_LEDGER") or None)
    try:
        if action == "list":
            rows = store.models()
            if not rows:
                _err("No prices yet. Run `merlin proxy catalog sync`.")
                return 0
            print(f"{'model':38} {'in':>12} {'out':>12} {'cache':>12}  (micros / 1M tokens)")
            for row in rows:
                cache = row["cache_read_micros_per_m"]
                print(
                    f"{row['model'][:38]:38} {row['in_micros_per_m']:>12,} {row['out_micros_per_m']:>12,}"
                    f" {('-' if cache is None else format(cache, ',')):>12}"
                )
            changes = store.price_history(limit=5)
            if changes:
                print("\nlast price changes:")
                for change in changes:
                    print(
                        f"  {change['model']}: in={change['in_micros_per_m']:,}"
                        f" out={change['out_micros_per_m']:,} [{change['source']}]"
                    )
            return 0

        adapter = GenericUpstreamAdapter(getattr(args, "config", None))
        config_error = adapter.config_error()
        if config_error:
            _err(config_error)
            return 2
        specs = adapter.specs()
        markup_bps = getattr(args, "markup_bps", None)
        book = cat.load_reference(getattr(args, "reference", None))
        report = cat.sync_prices(
            store,
            specs,
            book,
            markup_bps=cat.DEFAULT_MARKUP_BPS if markup_bps is None else int(markup_bps),
            dry_run=bool(getattr(args, "dry_run", False)),
        )
        print(report.summary())
        priced = [e for e in report.entries if e.price is not None]
        for entry in priced[:40]:
            price = entry.price
            if price is None:  # narrowed by the filter above; keeps type checkers honest
                continue
            ref = f" <- {entry.reference_id}" if entry.reference_id != entry.model else ""
            print(
                f"  {entry.model[:34]:34} in={price.in_micros_per_m:>10,}"
                f" out={price.out_micros_per_m:>10,}{ref}"
            )
        if len(priced) > 40:
            print(f"  … {len(priced) - 40} more")
        return 0 if not report.unpriced else 1
    finally:
        store.close()


def cmd_proxy_probe(args: Any) -> int:
    """``merlin proxy probe <run|status>`` — liveness, latency and model-identity checks."""
    from merlin_cli.proxy import probe as pr
    from merlin_cli.proxy.adapters.generic import GenericUpstreamAdapter

    action = getattr(args, "probe_command", None) or "status"
    store = pr.ProbeStore()
    try:
        if action == "status":
            rows = store.summary(hours=int(getattr(args, "hours", 24) or 24))
            if not rows:
                _err("No probes recorded yet. Run `merlin proxy probe run`.")
                return 0
            print(f"{'upstream':14} {'model':36} {'up%':>5} {'p50':>9} {'p95':>9}  identity")
            for row in rows:
                print(
                    f"{row['upstream'][:14]:14} {row['model'][:36]:36} {row['uptime_pct']:>5.1f}"
                    f" {row['p50_ms']:>7.0f}ms {row['p95_ms']:>7.0f}ms  {row['identity']}"
                )
            return 0

        adapter = GenericUpstreamAdapter(getattr(args, "config", None))
        config_error = adapter.config_error()
        if config_error:
            _err(config_error)
            return 2
        if getattr(args, "reset_baseline", False):
            cleared = store.reset_baseline()
            _err(f"cleared {cleared} stored fingerprint baseline(s)")
        specs = adapter.specs()
        models_by_upstream: dict[str, list[str]] = {}
        explicit = list(getattr(args, "model", None) or [])
        if explicit:
            models_by_upstream = {spec.name: explicit for spec in specs}
        elif getattr(args, "discover", False):
            from merlin_cli.proxy import catalog as cat

            for spec in specs:
                try:
                    models_by_upstream[spec.name] = cat.fetch_models(
                        spec.base_url, spec.keys[0] if spec.keys else ""
                    )
                except RuntimeError as exc:
                    _err(f"discovery failed for {spec.name}: {exc}")
        results = pr.probe_specs(
            store,
            specs,
            models_by_upstream,
            limit=int(getattr(args, "limit", 0) or 0),
            timeout_s=float(getattr(args, "timeout", 20) or 20),
        )
        if not results:
            _err("Nothing to probe: no models declared for these upstreams (use --model or --discover).")
            return 2
        for result, verdict in results:
            print(
                f"{result.upstream[:14]:14} {result.model[:36]:36} status={result.status:<4}"
                f" {result.latency_ms:>8.0f}ms  {verdict}"
            )
        return 1 if any(verdict == pr.IDENTITY_CHANGED for _, verdict in results) else 0
    finally:
        store.close()


def cmd_proxy_dashboard(args: Any) -> int:
    """``merlin proxy dashboard`` — public status page + QRIS top-up."""
    from merlin_cli.proxy import qris
    from merlin_cli.proxy.dashboard import AIOHTTP_AVAILABLE, create_dashboard_app
    from merlin_cli.proxy.probe import ProbeStore
    from merlin_cli.proxy.tenants import LedgerStore

    if not AIOHTTP_AVAILABLE:
        _err("dashboard membutuhkan aiohttp. Jalankan `merlin setup` untuk memasangnya.")
        return 1
    source = (
        getattr(args, "qris", None)
        or os.environ.get("MERLIN_PROXY_QRIS_FILE", "")
        or os.environ.get("MERLIN_PROXY_QRIS", "")
    )
    if not source:
        _err("QRIS belum diset. Pakai `--qris <file|payload>` atau MERLIN_PROXY_QRIS_FILE.")
        return 2
    try:
        payload = qris.load_static(source)
    except qris.QrisError as exc:
        _err(f"QRIS tidak valid: {exc}")
        return 2

    ledger = LedgerStore(os.environ.get("MERLIN_PROXY_LEDGER") or None)
    probes = ProbeStore(os.environ.get("MERLIN_PROXY_PROBES") or None)
    host = getattr(args, "host", None) or "127.0.0.1"
    port = int(getattr(args, "port", None) or 8680)
    info = qris.describe(payload)
    _err(
        f"Merlin dashboard  -> http://{host}:{port}\n"
        f"  merchant:   {info['merchant']} ({info['city']})\n"
        f"  currency:   {info['currency']}   static: {info['static']}\n"
        f"  billing DB: {ledger.path}\n"
        f"  probes DB:  {probes.path}"
    )
    from aiohttp import web

    app = create_dashboard_app(
        ledger,
        probes,
        payload,
        admin_token=os.environ.get("MERLIN_PROXY_ADMIN_TOKEN", ""),
        webhook_secret=os.environ.get("MERLIN_PROXY_WEBHOOK_SECRET", ""),
        invoice_ttl_s=int(getattr(args, "ttl", 1800) or 1800),
    )
    if not os.environ.get("MERLIN_PROXY_ADMIN_TOKEN"):
        token = getattr(app, "admin_token", "")
        _err(f"  admin token:   {token}  (generated — simpan; dipakai untuk konfirmasi bayar)")
    web.run_app(app, host=host, port=port, print=None)
    return 0


def cmd_proxy_payments(args: Any) -> int:
    """Reconcile money-in: expire stale invoices, import a statement, list/claim unmatched payments."""
    from merlin_cli.proxy.tenants import LedgerStore

    store = LedgerStore(os.environ.get("MERLIN_PROXY_LEDGER") or None)
    try:
        ingest_file = getattr(args, "ingest", None)
        if ingest_file:
            from pathlib import Path

            from merlin_cli.proxy import statement

            path = Path(ingest_file)
            if not path.exists():
                _err(f"file tidak ditemukan: {path}")
                return 2
            rows = statement.parse(
                path.read_text(encoding="utf-8-sig", errors="replace"), getattr(args, "format", "auto") or "auto"
            )
            if not rows:
                _err("tidak ada baris transaksi yang terbaca — cek format/kolom nominal")
                return 2
            report = statement.ingest(
                store,
                rows,
                provider=getattr(args, "provider", "dana") or "dana",
                dry_run=bool(getattr(args, "dry_run", False)),
            )
            print(report.summary())
            for item in report.items[:25]:
                extra = f" -> {item.get('invoice')}" if item.get("invoice") else ""
                print(f"  Rp {item['amount']:>10,}  {item['result']}{extra}")
            if len(report.items) > 25:
                print(f"  … {len(report.items) - 25} more")
            return 0 if report.unmatched == 0 else 1

        claim_id = getattr(args, "claim", None)
        if claim_id:
            invoice_id = getattr(args, "invoice", None)
            if not invoice_id:
                _err("--claim butuh --invoice <invoice_id>")
                return 2
            credited = store.claim_payment(claim_id, invoice_id)
            print(f"claimed {claim_id} -> {invoice_id}: credited {credited:,} micros")
            return 0 if credited else 1
        if getattr(args, "expire", False):
            print(f"expired {store.expire_invoices()} invoice(s)")
        rows = store.payments(status="unmatched", limit=int(getattr(args, "limit", 50) or 50))
        if not rows:
            print("no unmatched payments")
            return 0
        print(f"{'payment':26} {'amount':>12} {'provider':12} received")
        for row in rows:
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(row["received_at"]))
            print(f"{row['id']:26} {row['amount_idr']:>12,} {row['provider'][:12]:12} {when}")
        print("\nclaim one with: merlin proxy payments --claim <payment> --invoice <invoice>")
        return 0
    finally:
        store.close()


def cmd_proxy_maintenance(args: Any) -> int:
    """One cron-friendly pass: expire invoices, re-price models, probe identity/latency."""
    from merlin_cli.proxy import catalog as cat
    from merlin_cli.proxy import probe as pr
    from merlin_cli.proxy.adapters.generic import GenericUpstreamAdapter
    from merlin_cli.proxy.tenants import LedgerStore

    ledger = LedgerStore(os.environ.get("MERLIN_PROXY_LEDGER") or None)
    probes = pr.ProbeStore(os.environ.get("MERLIN_PROXY_PROBES") or None)
    rc = 0
    try:
        print(f"invoices expired : {ledger.expire_invoices()}")

        adapter = GenericUpstreamAdapter(getattr(args, "config", None))
        config_error = adapter.config_error()
        if config_error:
            _err(config_error)
            return 2
        specs = adapter.specs()
        if not specs:
            _err("no upstreams configured")
            return 2

        if not getattr(args, "skip_catalog", False):
            book = cat.load_reference(getattr(args, "reference", None))
            report = cat.sync_prices(
                ledger,
                specs,
                book,
                markup_bps=int(getattr(args, "markup_bps", None) or cat.DEFAULT_MARKUP_BPS),
            )
            print(report.summary())
            if report.unpriced:
                rc = 1
        else:
            print("catalog sync     : skipped")

        if not getattr(args, "skip_probe", False):
            models: dict[str, list[str]] = {}
            for spec in specs:
                try:
                    models[spec.name] = cat.fetch_models(spec.base_url, spec.keys[0] if spec.keys else "")
                except RuntimeError as exc:
                    _err(f"discovery failed for {spec.name}: {exc}")
            results = pr.probe_specs(
                probes,
                specs,
                models,
                limit=int(getattr(args, "limit", 0) or 0),
                timeout_s=float(getattr(args, "timeout", 20) or 20),
            )
            changed = [result for result, verdict in results if verdict == pr.IDENTITY_CHANGED]
            down = [result for result, verdict in results if not result.ok]
            print(
                f"probes           : {len(results)} model(s), "
                f"{len(changed)} identity changed, {len(down)} failed"
            )
            for result in changed:
                print(f"  IDENTITY_CHANGED {result.upstream}:{result.model}")
            for result in down:
                print(f"  DOWN {result.upstream}:{result.model} ({result.note or result.status})")
            if changed or down:
                rc = 1
        else:
            print("probes           : skipped")
        return rc
    finally:
        ledger.close()
        probes.close()


_SUBCOMMANDS = {
    "start": cmd_proxy_start,
    "status": cmd_proxy_status,
    "providers": cmd_proxy_list_providers,
    "list": cmd_proxy_list_providers,
    "catalog": cmd_proxy_catalog,
    "probe": cmd_proxy_probe,
    "dashboard": cmd_proxy_dashboard,
    "payments": cmd_proxy_payments,
    "maintenance": cmd_proxy_maintenance,
}


def cmd_proxy(args: Any) -> int:
    """Dispatch ``merlin proxy <subcommand>``; no/unknown subcommand prints the short help."""
    handler = _SUBCOMMANDS.get(getattr(args, "proxy_command", None))
    if handler is not None:
        return handler(args)
    _err(
        "merlin proxy — local OpenAI-compatible proxy that attaches your\n"
        "OAuth-authenticated provider credentials to outbound requests.\n"
        "\n"
        "Subcommands:\n"
        "  merlin proxy start [--provider atlas|xai] [--host 127.0.0.1] [--port 8645]\n"
        "      Run the proxy in the foreground.\n"
        "  merlin proxy status\n"
        "      Show which upstream adapters are ready.\n"
        "  merlin proxy providers\n"
        "      List available upstream providers.\n"
    )
    return 0


__all__ = ["cmd_proxy", "cmd_proxy_start", "cmd_proxy_status", "cmd_proxy_list_providers"]
