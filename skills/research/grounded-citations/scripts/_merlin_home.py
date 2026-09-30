"""Resolve MERLIN_HOME for standalone skill scripts.

Skill scripts may run outside the Merlin process (system Python, nix env,
CI) where ``merlin_constants`` is not importable.  This module provides the
same ``get_merlin_home()`` contract without requiring it on ``sys.path``.

When ``merlin_constants`` IS available it is used directly so profile
resolution and any future enhancements are picked up automatically.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from merlin_constants import get_merlin_home as get_merlin_home
except (ModuleNotFoundError, ImportError):

    def get_merlin_home() -> Path:
        """Return the Merlin home directory (default: ``~/.merlin``)."""
        val = os.environ.get("MERLIN_HOME", "").strip()
        return Path(val) if val else Path.home() / ".merlin"
