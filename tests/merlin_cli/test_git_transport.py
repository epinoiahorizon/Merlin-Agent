"""git fetch recovers from a proxy git cannot see, and from a dead IPv6 route.

Live failure this pins down (2026-10-20, a Chinese-locale laptop behind a
proxy client): ``install.ps1`` downloaded its pinned Git artifact from
github.com, then every ``git clone`` timed out with

    fatal: unable to access 'https://github.com/epinoiahorizon/Merlin-Agent.git/':
        Failed to connect to github.com port 443 after 21067 ms

because .NET follows the Windows system proxy and git's libcurl does not.
``merlin update`` fetches through the same libcurl, so it must retry with the
proxy (or an IPv4 pin when IPv6 is the dead half) instead of reporting a
connect failure the user cannot act on.
"""
from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from merlin_cli import git_transport
from merlin_cli.gitlock import fetch_with_partial_clone_recovery

LIVE_STDERR = (
    "fatal: unable to access 'https://github.com/epinoiahorizon/Merlin-Agent.git/': "
    "Failed to connect to github.com port 443 after 21067 ms: Could not connect to server\n"
)


def _failed():
    return CompletedProcess(["git"], 128, stdout="", stderr=LIVE_STDERR)


def _ok():
    return CompletedProcess(["git"], 0, stdout="", stderr="")


# --- classification ---------------------------------------------------------


def test_live_connect_failure_is_recognised():
    assert git_transport.is_connect_failure(LIVE_STDERR) is True
    # The Windows/git 2.53 partial-clone crash and refusals must keep their own handling.
    assert git_transport.is_connect_failure("fatal: should_include_obj failed") is False
    assert git_transport.is_connect_failure("fatal: couldn't find remote ref main") is False
    assert git_transport.is_connect_failure("remote: Permission denied (publickey).") is False
    assert git_transport.is_connect_failure("") is False
    assert git_transport.is_connect_failure(None) is False


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/epinoiahorizon/Merlin-Agent.git", "github.com"),
        ("http://127.0.0.1:8080/repo.git", "127.0.0.1"),
        ("git@github.com:epinoiahorizon/Merlin-Agent.git", "github.com"),
        ("ssh://git@github.com/epinoiahorizon/Merlin-Agent.git", None),
        ("/srv/git/Merlin-Agent.git", None),
    ],
)
def test_remote_host(url, expected):
    assert git_transport._host_from_url(url) == expected  # noqa: SLF001 -- parser under test


# --- the remedy ladder ------------------------------------------------------


def _probe(monkeypatch, *, v4_ok, v6_ok, proxies=(), listening=True):
    monkeypatch.setattr(git_transport, "_addresses", lambda host: (["140.82.121.4"], ["2606:50c0::153"]))
    monkeypatch.setattr(
        git_transport, "_tcp_ok", lambda host, port, timeout=2.5: v4_ok if host == "140.82.121.4" else v6_ok
    )
    monkeypatch.setattr(git_transport, "system_proxy_candidates", lambda: list(proxies))
    monkeypatch.setattr(git_transport, "_listening", lambda url: listening)


def test_dead_ipv6_route_is_pinned_to_ipv4(monkeypatch):
    _probe(monkeypatch, v4_ok=True, v6_ok=False)
    assert git_transport.plan_transport("github.com") == ["http.curloptResolve=github.com:443:140.82.121.4"]


def test_browser_proxy_is_used_before_any_address_pin(monkeypatch):
    _probe(monkeypatch, v4_ok=True, v6_ok=False, proxies=[("http://127.0.0.1:7890", "Windows Internet Settings")])
    assert git_transport.plan_transport("github.com") == [
        "http.proxy=http://127.0.0.1:7890",
        "https.proxy=http://127.0.0.1:7890",
        "http.curloptResolve=github.com:443:140.82.121.4",
    ]


def test_a_proxy_that_is_not_running_is_not_offered(monkeypatch):
    _probe(monkeypatch, v4_ok=True, v6_ok=False, proxies=[("http://127.0.0.1:7890", "registry")], listening=False)
    assert git_transport.plan_transport("github.com") == ["http.curloptResolve=github.com:443:140.82.121.4"]


def test_nothing_to_offer_when_both_families_answer(monkeypatch):
    _probe(monkeypatch, v4_ok=True, v6_ok=True)
    assert git_transport.plan_transport("github.com") == []


# --- wiring -----------------------------------------------------------------


def test_fetch_retries_with_the_proxy_and_keeps_it(monkeypatch):
    calls = []
    persisted = []

    def runner(git_cmd, args):
        # The failed attempt already happened in the caller; every call this
        # runner sees is a retry.
        calls.append(list(args))
        return _ok()

    monkeypatch.setattr(git_transport, "remote_host", lambda *a, **k: "github.com")
    monkeypatch.setattr(
        git_transport, "plan_transport", lambda host: ["http.proxy=http://127.0.0.1:7890"]
    )
    monkeypatch.setattr(git_transport, "_applied", lambda git_cmd, root, settings: list(settings))
    monkeypatch.setattr(git_transport, "_persist", lambda git_cmd, root, settings: persisted.extend(settings))

    result = git_transport.recover_fetch_transport(
        runner, ["git"], ["fetch", "origin", "main"], Path("."), _failed()
    )

    assert result.returncode == 0
    assert calls == [["-c", "http.proxy=http://127.0.0.1:7890", "fetch", "origin", "main"]]
    assert persisted == ["http.proxy=http://127.0.0.1:7890"]


def test_a_rejected_fetch_is_not_retried(monkeypatch):
    calls = []

    def runner(git_cmd, args):
        calls.append(list(args))
        return CompletedProcess(["git"], 1, stdout="", stderr="fatal: couldn't find remote ref main\n")

    result = git_transport.recover_fetch_transport(runner, ["git"], ["fetch"], Path("."), 
                                                   CompletedProcess(["git"], 1, stderr="fatal: couldn't find remote ref main"))
    assert calls == []
    assert result.returncode == 1


def test_gitlock_fetch_hook_uses_the_transport_retry(monkeypatch):
    """The update paths call fetch_with_partial_clone_recovery; it must carry the remedy."""
    calls = []

    def runner(git_cmd, args):
        calls.append(list(args))
        return _failed() if len(calls) == 1 else _ok()

    monkeypatch.setattr(git_transport, "remote_host", lambda *a, **k: "github.com")
    monkeypatch.setattr(git_transport, "plan_transport", lambda host: ["http.curloptResolve=github.com:443:140.82.121.4"])
    monkeypatch.setattr(git_transport, "_applied", lambda git_cmd, root, settings: list(settings))
    monkeypatch.setattr(git_transport, "_persist", lambda *a, **k: None)

    result = fetch_with_partial_clone_recovery(runner, ["git"], ["fetch", "origin", "+refs/heads/main:refs/remotes/origin/main"], Path("."))

    assert result.returncode == 0
    assert calls[1][:2] == ["-c", "http.curloptResolve=github.com:443:140.82.121.4"]
    assert calls[1][2:] == ["fetch", "origin", "+refs/heads/main:refs/remotes/origin/main"]


def test_gitlock_fetch_hook_leaves_other_failures_alone(monkeypatch):
    calls = []

    def runner(git_cmd, args):
        calls.append(list(args))
        return CompletedProcess(["git"], 1, stdout="", stderr="fatal: couldn't find remote ref main\n")

    result = fetch_with_partial_clone_recovery(runner, ["git"], ["fetch", "origin", "main"], Path("."))
    assert result.returncode == 1
    assert calls == [["fetch", "origin", "main"]], "a refused fetch must not be retried"
