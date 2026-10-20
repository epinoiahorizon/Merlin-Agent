"""install.sh: a clone that only an IPv4 pin or HTTP/1.1 can reach is retried.

Same failure class as the PowerShell sibling: git's libcurl takes the first
address the resolver returns, so a host with no usable IPv6 route hangs until
the connect timeout and prints

    fatal: unable to access 'https://github.com/...': Failed to connect to
        github.com port 443 after 21xxx ms: Could not connect to server

while every other HTTPS fetch from that machine works. ``stage_repository``
used to repeat the identical command three times plus a fourth deferred
checkout. It now probes the address families once (curl is already a
prerequisite), retries with the remedy the probe justifies, and keeps the
setting that worked in the checkout so ``merlin update`` inherits it.
"""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent

STUB = r"""
source {install_sh} --manifest
sleep() {{ :; }}
{curl_stub}
{getent_stub}
git() {{
    case "$1" in
        clone) _clone "$@" ;;
        -c)    if [ "${{3:-}}" = clone ]; then _clone "$@"; else command git "$@"; fi ;;
        -C)    if [ "${{3:-}}" = config ]; then _config "$4" "$5"; else command git "$@"; fi ;;
        *)     command git "$@" ;;
    esac
}}
_clone() {{
    printf '%s\n' "$*" >> {attempts}
    if [ "$(wc -l < {attempts})" -le {fail_limit} ]; then
        printf '%s\n' "fatal: unable to access '{repo}/': Failed to connect to {repo_host} port 443 after 21067 ms: Could not connect to server" >&2
        return 128
    fi
    for last; do :; done
    mkdir -p "$last/.git"
    return 0
}}
_config() {{ printf '%s=%s\n' "$1" "$2" >> {config}; }}
stage_repository
"""


def _run(tmp_path: Path, curl_stub: str, getent_stub: str = "  :", fail_limit: int = 2) -> subprocess.CompletedProcess:
    attempts = tmp_path / "attempts"
    config = tmp_path / "config"
    repo = "https://github.com/epinoiahorizon/Merlin-Agent.git"
    script = STUB.format(
        install_sh=shlex.quote((ROOT / "scripts/install.sh").as_posix()),
        curl_stub=curl_stub,
        getent_stub=getent_stub,
        attempts=shlex.quote(attempts.as_posix()),
        config=shlex.quote(config.as_posix()),
        fail_limit=fail_limit,
        repo=repo,
        repo_host="github.com",
    )
    env = dict(
        os.environ,
        HOME=tmp_path.as_posix(),
        MERLIN_HOME=(tmp_path / "home").as_posix(),
        MERLIN_INSTALL_DIR=(tmp_path / "install").as_posix(),
        MERLIN_REPO_URL=repo,
    )
    env.pop("CI", None)
    return subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=60)


@pytest.mark.skipif(
    __import__("shutil").which("bash") is None or __import__("shutil").which("git") is None,
    reason="needs bash and git",
)
def test_ipv6_dead_route_retries_pinned_to_ipv4(tmp_path):
    # IPv4 answers, IPv6 does not: the probe must pin the host to its A record.
    curl = 'curl() { for a in "$@"; do [ "$a" = -6 ] && return 7; done; return 0; }'
    getent = 'getent() { printf "%s\n" "140.82.121.4  STREAM github.com"; }'
    result = _run(tmp_path, curl, getent)

    assert result.returncode == 0, result.stdout + result.stderr
    calls = (tmp_path / "attempts").read_text().splitlines()
    assert len(calls) == 3, calls
    assert "-c http.curloptResolve=github.com:443:140.82.121.4" in calls[2], calls[2]
    assert "--filter=tree:0" in calls[2]
    # The pin reaches the checkout so the next fetch does not fail the same way.
    assert "http.curloptResolve=github.com:443:140.82.121.4" in (tmp_path / "config").read_text()
    assert "IPv4 answers and IPv6 does not" in result.stdout + result.stderr


@pytest.mark.skipif(
    __import__("shutil").which("bash") is None or __import__("shutil").which("git") is None,
    reason="needs bash and git",
)
def test_undiagnosed_failure_retries_over_http1(tmp_path):
    # Both families answer yet the clone still died: a middlebox breaking HTTP/2
    # is the remaining explanation, so the next attempt asks for HTTP/1.1.
    curl = "curl() { return 0; }"
    result = _run(tmp_path, curl)

    assert result.returncode == 0, result.stdout + result.stderr
    calls = (tmp_path / "attempts").read_text().splitlines()
    assert len(calls) == 3, calls
    assert "-c http.version=HTTP/1.1" in calls[2], calls[2]
    assert "http.version=HTTP/1.1" in (tmp_path / "config").read_text()
    assert "retrying over HTTP/1.1" in result.stdout + result.stderr


@pytest.mark.skipif(
    __import__("shutil").which("bash") is None or __import__("shutil").which("git") is None,
    reason="needs bash and git",
)
def test_healthy_clone_never_probes(tmp_path):
    result = _run(tmp_path, "curl() { return 0; }", fail_limit=0)

    assert result.returncode == 0, result.stdout + result.stderr
    calls = (tmp_path / "attempts").read_text().splitlines()
    assert len(calls) == 1, calls
    assert "-c " not in calls[0]
    assert not (tmp_path / "config").exists()
    assert "IPv4" not in (result.stdout + result.stderr)
