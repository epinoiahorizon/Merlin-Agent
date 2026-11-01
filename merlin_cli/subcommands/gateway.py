"""``merlin gateway`` and ``merlin proxy`` subcommand parsers."""

from __future__ import annotations

import argparse
from typing import Callable

from merlin_cli.subcommands._shared import add_accept_hooks_flag


# `start`/`restart` on a named profile refuse while the default multiplexer serves it (a second gateway
# would double-bind its platforms); `gateway run` carries its own broader --force text.
_FORCE_SERVED_PROFILE_HELP = (
    "Start a separate gateway for this profile even when the default multiplexer already serves it "
    "(not recommended: two pollers on one bot token, port conflicts)")


def _flag(parser, *names, help, **kw):
    parser.add_argument(*names, action="store_true", help=help, **kw)


def _add_compat_platform_flag(parser: argparse.ArgumentParser) -> None:
    """Accept stale `gateway <verb> --platform X` docs without advertising it.

    Lifecycle commands operate on the gateway process, not one adapter; Photon briefly
    printed a per-platform start command during setup, so keep it parseable.
    """
    parser.add_argument("--platform", dest="platform", help=argparse.SUPPRESS)


def _add_system_flag(parser: argparse.ArgumentParser) -> None:
    _flag(parser, "--system", help="Target the Linux system-level gateway service")


def build_gateway_parser(
    subparsers, *, cmd_gateway: Callable, cmd_proxy: Callable, cmd_gateway_enroll: Callable
) -> None:
    """Attach the ``gateway`` and ``proxy`` subcommands to ``subparsers``."""
    gateway_parser = subparsers.add_parser("gateway", help="Messaging gateway management",
        description="Manage the messaging gateway (Telegram, Discord, WhatsApp, Weixin, and more)")
    gateway_subparsers = gateway_parser.add_subparsers(dest="gateway_command")

    gateway_run = gateway_subparsers.add_parser(
        "run", help="Run gateway in foreground (recommended for WSL and Docker)"
    )
    gateway_run.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase stderr log verbosity (-v=INFO, -vv=DEBUG)",
    )
    gateway_run.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress all stderr log output"
    )
    gateway_run.add_argument(
        "--replace",
        action="store_true",
        help="Replace any existing gateway instance (useful for systemd)",
    )
    gateway_run.add_argument(
        "--force",
        action="store_true",
        help=(
            "Start a foreground gateway even when a systemd/launchd/s6 service "
            "already supervises this profile. Without --force, the command "
            "refuses because a second dispatcher escapes the service and can "
            "corrupt shared gateway state."
        ),
    )
    gateway_run.add_argument(
        "--no-supervise",
        action="store_true",
        help=(
            "Inside the s6-overlay Docker image, normally `gateway run` is "
            "automatically redirected to the supervised s6 service (so the "
            "gateway gets auto-restart on crash, plus a supervised dashboard "
            "if MERLIN_DASHBOARD is set). Pass --no-supervise to opt out and "
            "get the historical pre-s6 foreground behavior: the gateway is "
            "the container's main process and the container exits with the "
            "gateway's exit code. No effect outside an s6 container."),
    )
    _flag(gateway_run, "--external-supervisor",
        help="Declare that an external process manager owns this foreground "
            "gateway. In-chat restarts and updates exit back to that manager "
            "instead of spawning a detached replacement. Use this when a "
            "launchd/systemd wrapper strips its native environment markers.")
    add_accept_hooks_flag(gateway_run)
    add_accept_hooks_flag(gateway_parser)

    gateway_start = gateway_subparsers.add_parser(
        "start", help="Start the installed systemd/launchd background service")
    _add_system_flag(gateway_start)
    _flag(gateway_start, "--all",
        help="Kill ALL stale gateway processes across all profiles before starting")
    _flag(gateway_start, "--force", help=_FORCE_SERVED_PROFILE_HELP)
    _add_compat_platform_flag(gateway_start)

    gateway_stop = gateway_subparsers.add_parser("stop", help="Stop gateway service")
    _add_system_flag(gateway_stop)
    _flag(gateway_stop, "--all", help="Stop ALL gateway processes across all profiles")

    gateway_restart = gateway_subparsers.add_parser("restart", help="Restart gateway service")
    _add_system_flag(gateway_restart)
    _flag(gateway_restart, "--all",
        help="Kill ALL gateway processes across all profiles before restarting")
    _flag(gateway_restart, "--force", help=_FORCE_SERVED_PROFILE_HELP)
    _add_compat_platform_flag(gateway_restart)

    gateway_status = gateway_subparsers.add_parser("status", help="Show gateway status")
    _flag(gateway_status, "--deep", help="Deep status check")
    _flag(gateway_status, "-l", "--full",
        help="Show full, untruncated service/log output where supported")
    _add_system_flag(gateway_status)
    _add_compat_platform_flag(gateway_status)

    # gateway install
    gateway_install = gateway_subparsers.add_parser(
        "install", help="Install gateway as a systemd/launchd background service")
    _flag(gateway_install, "--force",
        help="Force reinstall, and install even when the default multiplexer already serves this profile")
    _flag(gateway_install, "--system",
        help="Install as a Linux system-level service (starts at boot)")
    gateway_install.add_argument("--run-as-user", dest="run_as_user",
        help="User account the Linux system service should run as")
    _flag(gateway_install, "--start-now", dest="start_now", default=None,
        help="Start the gateway service immediately after installing")
    gateway_install.add_argument("--no-start-now", dest="start_now", action="store_false",
        help="Do not start the gateway service after installing")
    _flag(gateway_install, "--start-on-login", dest="start_on_login", default=None,
        help="Enable the service to start automatically on login/boot")
    gateway_install.add_argument("--no-start-on-login", dest="start_on_login", action="store_false",
        help="Do not enable the service to start on login/boot")
    _flag(gateway_install, "--if-missing", dest="if_missing",
        help="Do nothing when a gateway service is already installed")
    _flag(gateway_install, "--elevated-handoff", dest="elevated_handoff", help=argparse.SUPPRESS)

    gateway_uninstall = gateway_subparsers.add_parser("uninstall", help="Uninstall gateway service")
    _add_system_flag(gateway_uninstall)

    gateway_subparsers.add_parser("list", help="List all profiles and their gateway status")

    gateway_subparsers.add_parser("setup", help="Configure messaging platforms")

    gateway_migrate_legacy = gateway_subparsers.add_parser(
        "migrate-legacy", help="Remove legacy merlin.service units from pre-rename installs",
        description="Stop, disable, and remove legacy Merlin gateway unit files "
            "(e.g. merlin.service) left over from older installs. Profile "
            "units (merlin-gateway-<profile>.service) and unrelated "
            "third-party services are never touched.")
    _flag(gateway_migrate_legacy, "--dry-run", dest="dry_run",
        help="List what would be removed without doing it")
    _flag(gateway_migrate_legacy, "-y", "--yes", dest="yes", help="Skip the confirmation prompt")

    gateway_migrate = gateway_subparsers.add_parser(
        "migrate", help="Converge every per-profile gateway onto the ONE host gateway",
        description="Converge this host onto the one-gateway-per-host model: stop and uninstall "
            "each secondary profile's gateway and its supervisor unit (systemd, launchd, Windows "
            "Scheduled Task), then restart the default profile's gateway so it serves every "
            "profile. Runs a preflight first (duplicate bot tokens, port-binding platforms "
            "without a /p/<profile>/ ingress) and changes nothing when blocked. Safe to re-run: a "
            "half-migrated host converges on the next run. Per-profile gateways are not a "
            "supported topology any more, so there is no rollback command.")
    _flag(gateway_migrate, "--multiplex", dest="multiplex", help="Converge onto the one host gateway (default)")
    _flag(gateway_migrate, "--dry-run", dest="dry_run", help="Print the plan and blockers without changing anything")
    _flag(gateway_migrate, "-y", "--yes", dest="yes", help="Apply without confirmation")

    # enroll: redeem a single-use connector token for the per-gateway secret + per-tenant
    # delivery key, written to .env. See website/docs/developer-guide/relay-connector-contract.md. EXPERIMENTAL.
    gateway_enroll = gateway_subparsers.add_parser("enroll",
        help="Enroll this gateway with a relay connector (writes relay auth creds to .env)",
        description="Redeem a single-use enrollment token with a relay connector. "
            "Authenticates as your Atlas Portal account (the connector derives the "
            "authoritative tenant from it), mints this gateway's per-gateway secret "
            "and per-tenant delivery key, and writes GATEWAY_RELAY_ID / "
            "GATEWAY_RELAY_SECRET / GATEWAY_RELAY_DELIVERY_KEY into ~/.merlin/.env. "
            "Requires being logged in (merlin setup). Not available in managed installs.")
    gateway_enroll.add_argument("--token", default=None,
        help="The single-use enrollment token from the connector (delivered with "
            "your gateway config). Also settable via GATEWAY_RELAY_ENROLL_TOKEN.")
    gateway_enroll.add_argument("--connector-url", dest="connector_url", default=None,
        help="The connector base/relay URL, e.g. wss://connector.example.com/relay "
            "or https://connector.example.com. Also settable via GATEWAY_RELAY_URL "
            "/ gateway.relay_url in config.yaml.")
    gateway_enroll.add_argument("--gateway-id", dest="gateway_id", default=None,
        help="A stable id for this gateway instance (kill-switch granularity). "
            "Defaults to gw-<hostname>.")
    gateway_enroll.add_argument("--wake-url", dest="wake_url", default=None,
        help="Phase 5 §5.2 wake URL: a reachable URL the connector pokes "
            "(payload-free GET) to wake this gateway when buffered work arrives "
            "while it's idle/suspended, so it reconnects and drains. Persisted as "
            "GATEWAY_RELAY_WAKE_URL in ~/.merlin/.env and forwarded at provision. "
            "Optional — without it the gateway still drains whenever it next "
            "reconnects on its own.")
    gateway_enroll.set_defaults(func=cmd_gateway_enroll)

    # proxy: local OpenAI-compatible proxy attaching the user's OAuth provider credentials,
    # so external apps (Open WebUI, Karakeep, ...) ride a logged-in subscription.
    proxy_parser = subparsers.add_parser(
        "proxy", help="Local OpenAI-compatible proxy to OAuth providers",
        description="Run a local HTTP server that forwards OpenAI-compatible requests "
            "to an OAuth-authenticated provider (e.g. Atlas Portal). External "
            "apps can point at the proxy with any bearer token; the proxy "
            "attaches your real credentials.")
    proxy_subparsers = proxy_parser.add_subparsers(dest="proxy_command")

    proxy_start = proxy_subparsers.add_parser("start", help="Run the proxy in the foreground")
    proxy_start.add_argument("--provider", default="atlas",
        help="Upstream provider: atlas or xai (default: atlas). See `merlin proxy providers`.")
    proxy_start.add_argument("--host", default=None,
        help="Bind address (default: 127.0.0.1). Use 0.0.0.0 to expose on LAN.")
    proxy_start.add_argument("--port", type=int, default=None, help="Bind port (default: 8645)")

    proxy_subparsers.add_parser("status", help="Show which proxy upstreams are ready")
    proxy_subparsers.add_parser("providers", help="List available proxy upstream providers")

    proxy_catalog = proxy_subparsers.add_parser(
        "catalog", help="Price book: sync from a reference feed, list current prices")
    proxy_catalog_sub = proxy_catalog.add_subparsers(dest="catalog_command")
    proxy_catalog_sync = proxy_catalog_sub.add_parser(
        "sync", help="Discover each upstream's models and price them from the reference feed")
    proxy_catalog_sync.add_argument("--config", default=None,
        help="Path to proxy_upstreams.json (default: MERLIN_PROXY_UPSTREAMS or the Merlin home)")
    proxy_catalog_sync.add_argument("--reference", default=None,
        help="Price reference: URL or local JSON (default: OpenRouter /api/v1/models)")
    proxy_catalog_sync.add_argument("--markup-bps", dest="markup_bps", type=int, default=None,
        help="Markup over the reference in basis points (default 1500 = 15%%)")
    proxy_catalog_sync.add_argument("--dry-run", dest="dry_run", action="store_true",
        help="Report what would change without writing to the ledger")
    proxy_catalog_sub.add_parser("list", help="Show the current price book and last changes")
    proxy_catalog.set_defaults(catalog_command="list")

    proxy_probe = proxy_subparsers.add_parser(
        "probe", help="Probe upstreams: liveness, latency, and model-identity fingerprint")
    proxy_probe_sub = proxy_probe.add_subparsers(dest="probe_command")
    probe_run = proxy_probe_sub.add_parser("run", help="Probe each upstream's models once")
    probe_run.add_argument("--config", default=None, help="Path to proxy_upstreams.json")
    probe_run.add_argument("--model", action="append", default=None,
        help="Model id to probe (repeatable; default: the models declared per upstream)")
    probe_run.add_argument("--discover", action="store_true",
        help="Ask the upstream for its model list instead of using the declared models")
    probe_run.add_argument("--limit", type=int, default=0, help="Probe at most N models per upstream")
    probe_run.add_argument("--timeout", type=float, default=20.0, help="Per-probe timeout in seconds")
    probe_run.add_argument("--reset-baseline", dest="reset_baseline", action="store_true",
        help="Forget stored fingerprints first (use after an intentional model/version change)")
    probe_status = proxy_probe_sub.add_parser("status", help="Show uptime, p50/p95 and identity verdicts")
    probe_status.add_argument("--hours", type=int, default=24, help="Window in hours (default 24)")
    proxy_probe.set_defaults(probe_command="status")

    proxy_dash = proxy_subparsers.add_parser(
        "dashboard", help="Serve the public status page and QRIS top-up flow")
    proxy_dash.add_argument("--host", default=None, help="Bind address (default: 127.0.0.1)")
    proxy_dash.add_argument("--port", type=int, default=None, help="Bind port (default: 8680)")
    proxy_dash.add_argument("--qris", default=None,
        help="Static QRIS: image path (.png/.jpg), text file with the payload, or the raw payload")
    proxy_dash.add_argument("--ttl", type=int, default=1800,
        help="Invoice lifetime in seconds (default 1800); expired invoices free their nominal")

    proxy_payments = proxy_subparsers.add_parser(
        "payments", help="Reconcile top-ups: expire stale invoices, list/claim unmatched payments")
    proxy_payments.add_argument("--expire", action="store_true", help="Expire invoices past their TTL first")
    proxy_payments.add_argument("--claim", default=None, help="Payment id to attach to an invoice")
    proxy_payments.add_argument("--invoice", default=None, help="Invoice id for --claim")
    proxy_payments.add_argument("--limit", type=int, default=50, help="Max rows to list")
    proxy_payments.add_argument("--ingest", default=None,
        help="Statement file to import (DANA Bisnis CSV export, or pasted notification text)")
    proxy_payments.add_argument("--format", default="auto", choices=["auto", "csv", "text"],
        help="Statement format (default: auto-detect)")
    proxy_payments.add_argument("--provider", default="dana", help="Provider label recorded on payments")
    proxy_payments.add_argument("--dry-run", dest="dry_run", action="store_true",
        help="Show what would match without writing or crediting")

    proxy_maint = proxy_subparsers.add_parser(
        "maintenance", help="Cron pass: expire invoices, re-price models, probe upstreams")
    proxy_maint.add_argument("--config", default=None, help="Path to proxy_upstreams.json")
    proxy_maint.add_argument("--reference", default=None, help="Price reference URL or JSON file")
    proxy_maint.add_argument("--markup-bps", dest="markup_bps", type=int, default=None)
    proxy_maint.add_argument("--skip-catalog", dest="skip_catalog", action="store_true")
    proxy_maint.add_argument("--skip-probe", dest="skip_probe", action="store_true")
    proxy_maint.add_argument("--limit", type=int, default=0, help="Probe at most N models per upstream")
    proxy_maint.add_argument("--timeout", type=float, default=20.0)
    proxy_parser.set_defaults(func=cmd_proxy)
    gateway_parser.set_defaults(func=cmd_gateway)
