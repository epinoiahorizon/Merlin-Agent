"""Resolve MERLIN_HOME for standalone skill scripts.

Skill scripts may run outside the Merlin process (e.g. system Python,
nix env, CI) where ``merlin_constants`` is not importable.  This module
provides the same ``get_merlin_home()`` and ``display_merlin_home()``
contracts as ``merlin_constants`` without requiring it on ``sys.path``.

When ``merlin_constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``merlin_constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``MERLIN_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from merlin_constants import display_merlin_home as display_merlin_home
    from merlin_constants import get_merlin_home as get_merlin_home
except (ModuleNotFoundError, ImportError):

    def get_merlin_home() -> Path:
        """Return the Merlin home directory (default: ~/.merlin).

        Mirrors ``merlin_constants.get_merlin_home()``."""
        val = os.environ.get("MERLIN_HOME", "").strip()
        return Path(val) if val else Path.home() / ".merlin"

    def display_merlin_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``merlin_constants.display_merlin_home()``."""
        home = get_merlin_home()
        try:
            return "~/" + home.relative_to(Path.home()).as_posix()
        except ValueError:
            return str(home)
