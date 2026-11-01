"""The slim-deployment contract: importing the gateway entry must not drag in the Merlin runtime.

This is a packaging guarantee, not a style preference — the Docker image installs only aiohttp and
segno, so any adapter that starts importing ``merlin_cli.auth`` at module scope silently breaks the
container build. Run in a subprocess so the assertion reflects a fresh interpreter.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_PROBE = """
import sys
import merlin_cli.proxy.entry  # noqa: F401
from merlin_cli.proxy.adapters import get_adapter, adapter_names
assert adapter_names() == ["atlas", "generic", "xai"], adapter_names()
get_adapter("generic")  # the only adapter a slim image ships with
heavy = [m for m in ("merlin_cli.auth", "agent.credential_pool", "rich", "textual", "typer")
         if m in sys.modules]
print(",".join(heavy))
"""


def test_entry_imports_no_heavy_modules() -> None:
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"gateway entry pulled in: {result.stdout.strip()}"


def test_unknown_adapter_lists_alternatives() -> None:
    from merlin_cli.proxy.adapters import get_adapter

    try:
        get_adapter("does-not-exist")
    except ValueError as exc:
        message = str(exc)
        assert "atlas" in message and "generic" in message
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for an unknown adapter")
