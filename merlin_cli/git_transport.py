"""Retry a git network operation with the proxy or address family this host needs.

A machine can reach GitHub in the browser while ``git`` cannot: ``Invoke-WebRequest`` (and the
browser) follow the Windows proxy and fall through to the next address when one does not answer,
while git's libcurl reads neither the WinINET proxy nor a ProxyAutoConfig script and prefers the
first address the resolver returns. The failure is always the same shape::

    fatal: unable to access 'https://github.com/...': Failed to connect to
        github.com port 443 after 21xxx ms: Could not connect to server

``merlin update`` fetches through exactly that path, so it died the same way -- with no probe and
no remedy -- while the installer (``scripts/install.ps1`` / ``scripts/install.sh``) learned to
recover. This module is that ladder for the Python side: only a connect-level failure reaches it,
so authentication errors, missing refs and the pack-objects crash keep their existing handling.

Remedies, in the order tried by :func:`plan_transport`:

* the proxy this PC already uses, from ``http(s)_proxy``/``ALL_PROXY`` or the Windows Internet
  Settings registry (only if something is actually listening on its port);
* an IPv4 pin when IPv4 answers on 443 and IPv6 does not -- ``http.curloptResolve``.

Whatever made the fetch work is written into the checkout's local git config, so later fetches do
not pay for the failed attempt and the probe again.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import socket
import subprocess
from typing import Iterable, Sequence

# Only these mean "the connection never happened". A rejected credential, a
# missing ref or a pack-objects crash must keep the caller's own handling.
_CONNECT_FAILURE_MARKERS = (
    "could not connect to server",
    "failed to connect to",
    "connection timed out",
    "connection reset by peer",
    "could not resolve host",
    "network is unreachable",
)

_PROXY_ENV_NAMES = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy")

_HOST_RE = re.compile(r"^(?:https?://)(\[[^]]+\]|[^/:]+)", re.IGNORECASE)
_SCP_RE = re.compile(r"^[^@/]+@([^:/]+):")


def is_connect_failure(stderr: str | bytes | None) -> bool:
    """True when git never reached the server (as opposed to being told no)."""
    if not stderr:
        return False
    text = stderr.decode("utf-8", "replace") if isinstance(stderr, bytes) else str(stderr)
    lowered = text.lower()
    return any(marker in lowered for marker in _CONNECT_FAILURE_MARKERS)


def _host_from_url(url: str) -> str | None:
    """Host of a git remote URL; None for SSH URLs and local paths (nothing to proxy or pin)."""
    match = _HOST_RE.match(url)
    if match:
        return match.group(1).strip("[]")
    match = _SCP_RE.match(url)
    if match:
        return match.group(1)
    return None


def remote_host(git_cmd: Sequence[str], repo_root: Path, remote: str = "origin") -> str | None:
    """Host of ``remote``'s URL, or None for an SSH/local remote (no proxy/pin to reason about)."""
    try:
        result = subprocess.run(
            [*git_cmd, "-C", str(repo_root), "config", "--get", f"remote.{remote}.url"],
            capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    url = (result.stdout or "").strip()
    if not url:
        return None
    return _host_from_url(url)


def _proxy_from_environment() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for name in _PROXY_ENV_NAMES:
        value = os.environ.get(name)
        if value and value.strip():
            found.append((value.strip(), f"${name}"))
    return found


def _proxy_from_windows_registry() -> list[tuple[str, str]]:
    """The proxy the browser uses. git reads no registry key, so this is often the whole bug."""
    try:
        import winreg  # noqa: PLC0415 -- Windows only
    except ImportError:
        return []
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        ) as key:
            enabled = winreg.QueryValueEx(key, "ProxyEnable")[0]
            server = winreg.QueryValueEx(key, "ProxyServer")[0]
    except OSError:
        return []
    if not enabled or not server:
        return []
    text = str(server).strip()
    if "=" in text:
        # "http=h:80;https=h:443" -- git needs the https entry.
        by_scheme = {}
        for part in text.split(";"):
            scheme, _, value = part.partition("=")
            if value:
                by_scheme[scheme.strip().lower()] = value.strip()
        text = by_scheme.get("https") or by_scheme.get("http") or ""
    if not text:
        return []
    if not re.match(r"^[a-z][a-z0-9+.-]*://", text, re.IGNORECASE):
        text = f"http://{text}"
    return [(text, "Windows Internet Settings")]


def system_proxy_candidates() -> list[tuple[str, str]]:
    """``(url, where-it-came-from)`` for every proxy this session could use, deduplicated."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for url, source in [*_proxy_from_environment(), *_proxy_from_windows_registry()]:
        if url in seen:
            continue
        seen.add(url)
        out.append((url, source))
    return out


def _tcp_ok(host: str, port: int, timeout: float = 2.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _listening(proxy_url: str) -> bool:
    match = re.match(r"^[a-z][a-z0-9+.-]*://(?:[^@/]*@)?(\[[^]]+\]|[^:/]+)(?::(\d+))?", proxy_url, re.IGNORECASE)
    if not match:
        return False
    host = match.group(1).strip("[]")
    port = int(match.group(2) or 8080)
    return _tcp_ok(host, port, timeout=1.2)


def _addresses(host: str) -> tuple[list[str], list[str]]:
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return [], []
    v4: list[str] = []
    v6: list[str] = []
    for info in infos:
        address = str(info[4][0])
        if info[0] == socket.AF_INET and address not in v4:
            v4.append(address)
        elif info[0] == socket.AF_INET6:
            bare = address.split("%")[0]
            if bare not in v6 and bare != "::1":
                v6.append(bare)
    return v4, v6


def plan_transport(host: str) -> list[str]:
    """Git settings that could fix a connect failure to ``host``; prints why, in one line each."""
    v4, v6 = _addresses(host)
    if not v4 and not v6:
        print(f"  (cannot resolve {host} from this PC)")
        return []
    v4_ok = any(_tcp_ok(address, 443) for address in v4[:2])
    v6_ok = any(_tcp_ok(address, 443) for address in v6[:2])
    print(
        f"  {host} answers: IPv4 {'ok' if v4_ok else 'no'}"
        f" ({', '.join(v4[:2]) or 'none'}); IPv6 {'ok' if v6_ok else 'no'}"
        f" ({', '.join(v6[:2]) or 'none'})"
    )
    settings: list[str] = []
    for url, source in system_proxy_candidates():
        if _listening(url):
            print(f"  using the proxy this PC already uses ({source}): {url}")
            settings.extend([f"http.proxy={url}", f"https.proxy={url}"])
            break
    if v4_ok and not v6_ok and v4:
        print(f"  IPv4 answers and IPv6 does not; pinning {host} to {v4[0]}")
        settings.append(f"http.curloptResolve={host}:443:{v4[0]}")
    return settings


def _applied(git_cmd: Sequence[str], repo_root: Path, settings: Iterable[str]) -> list[str]:
    """Drop settings the checkout already carries: retrying them would just fail again."""
    pending: list[str] = []
    for setting in settings:
        key, _, value = setting.partition("=")
        try:
            result = subprocess.run(
                [*git_cmd, "-C", str(repo_root), "config", "--local", "--get", key],
                capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError):
            result = None
        if result is not None and result.returncode == 0 and result.stdout.strip() == value:
            continue
        pending.append(setting)
    return pending


def _persist(git_cmd: Sequence[str], repo_root: Path, settings: Iterable[str]) -> None:
    for setting in settings:
        key, _, value = setting.partition("=")
        try:
            subprocess.run(
                [*git_cmd, "-C", str(repo_root), "config", "--local", key, value],
                capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError):
            continue


def recover_fetch_transport(runner, git_cmd, fetch_args, repo_root, failed):
    """Retry ``runner(git_cmd, fetch_args)`` with the remedy the probe justifies.

    ``runner`` is the caller's ``(git_cmd, args) -> CompletedProcess`` hook, so this stays out of
    the way of how each caller runs git. Returns the retry's result when it worked, else the
    caller's original failure -- the message the user already knows.
    """
    stderr = getattr(failed, "stderr", "")
    if not is_connect_failure(stderr):
        return failed
    host = remote_host(git_cmd, repo_root)
    if not host:
        return failed
    settings = plan_transport(host)
    pending = _applied(git_cmd, repo_root, settings)
    if not pending:
        if settings:
            return failed  # already configured and still failing: the network, not the settings
        print(f"  no proxy or address-family remedy applies; {host}:443 is unreachable from this PC")
        return failed
    args = []
    for setting in pending:
        args.extend(["-c", setting])
    print(f"⚠ {host} refused the connection; retrying with {' '.join(pending)}")
    result = runner(git_cmd, [*args, *fetch_args])
    if result.returncode == 0:
        _persist(git_cmd, repo_root, pending)
        print("✓ Fetch reached the remote; those git settings are saved in this checkout")
        return result
    return failed
