"""Codex device login fails actionably, not silently.

Field report: a ChatGPT account with "device code sign-in" disabled never approves the
device grant, so the poll loop just spins for the full 15 minutes and the user sees a bare
"Login timed out after 15 minutes." with no way forward. The loop now says what usually
blocks it after ``_POLL_PENDING_HINT_AFTER_S`` seconds (once) and the timeout error names
the browser-PKCE alternative.
"""

import pytest

from merlin_cli import auth_codex
from merlin_cli.auth import AuthError


class _AdvancingClock:
    """``time`` stand-in: every ``monotonic()`` call jumps ``step`` seconds, ``sleep`` is free
    so the 15-minute loop finishes in milliseconds."""

    def __init__(self, step=30.0):
        self.now = 0.0
        self.step = step
        self.sleeps = 0

    def monotonic(self):
        self.now += self.step
        return self.now

    def sleep(self, _seconds):
        self.sleeps += 1


class _Response:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _PendingClient:
    """``403`` until ``approve_after`` polls, then the approval payload."""

    def __init__(self, approve_after=None):
        self.calls = 0
        self.approve_after = approve_after

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def post(self, url, **kwargs):
        self.calls += 1
        if self.approve_after is not None and self.calls >= self.approve_after:
            return _Response(200, {"authorization_code": "ac", "code_verifier": "cv"})
        return _Response(403)


def _poll():
    return auth_codex._codex_poll_authorization_code(
        "https://auth.openai.com", device_auth_id="da", user_code="uc", poll_interval=0)


def test_pending_forever_prints_one_hint_and_names_the_browser_retry(monkeypatch, capsys):
    clock = _AdvancingClock()
    client = _PendingClient()
    monkeypatch.setattr(auth_codex, "time", clock)
    monkeypatch.setattr(auth_codex, "_codex_http_client", lambda **kw: client)

    with pytest.raises(AuthError) as excinfo:
        _poll()

    err = excinfo.value
    assert err.code == "device_code_timeout"
    assert "--browser" in str(err)
    assert "device code sign-in" in str(err)
    out = capsys.readouterr().out
    assert out.count(auth_codex._POLL_PENDING_HINT) == 1  # said once, not once per poll
    assert client.calls > 1  # it really did poll before giving up


def test_approval_after_the_hint_still_completes_without_the_error(monkeypatch, capsys):
    clock = _AdvancingClock()
    monkeypatch.setattr(auth_codex, "time", clock)
    monkeypatch.setattr(auth_codex, "_codex_http_client",
                        lambda **kw: _PendingClient(approve_after=6))

    assert _poll() == {"authorization_code": "ac", "code_verifier": "cv"}
    assert capsys.readouterr().out.count(auth_codex._POLL_PENDING_HINT) == 1
