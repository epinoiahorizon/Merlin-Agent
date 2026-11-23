"""A live pid is not proof that the update behind it is still running.

Windows recycles pids fast. When a failed update leaves its marker behind and the
pid is later handed to an unrelated process, the marker looks owned forever: every
launch raises "an update is still running" and `merlin debug share` refuses, until
the 20-minute ceiling expires.

The owner writes its own start time, so its create time is at or before that value.
A process created *after* the marker was written cannot be the owner.
"""
import os
import time

import pytest

from merlin_cli.update_lock import UPDATE_MARKER_MAX_AGE_SECONDS, read_live_update


def _write(marker, pid: int, started_at: float) -> None:
    marker.write_text(f"{pid}\n{int(started_at)}\n", encoding="utf-8")


def test_recycled_pid_does_not_hold_the_lock(tmp_path):
    """Marker older than this process, naming its pid: the owner is gone.

    The marker is dated *before this process existed*, which no real owner can
    do — it writes its own start time. Kept well inside the 20-minute ceiling so
    the age rule cannot be what clears it.
    """
    psutil = pytest.importorskip("psutil")
    born = psutil.Process().create_time()
    started_at = born - 60
    if time.time() - started_at >= UPDATE_MARKER_MAX_AGE_SECONDS:
        pytest.skip("test process has been alive too long to isolate this rule")

    marker = tmp_path / ".merlin-update-in-progress"
    _write(marker, os.getpid(), started_at)

    assert read_live_update(path=marker) is None
    assert not marker.exists(), "the stale marker is cleared so it cannot strand the next run"


def test_a_fresh_marker_from_a_live_process_still_blocks(tmp_path):
    """The real case must keep working: an update that started just now."""
    marker = tmp_path / ".merlin-update-in-progress"
    _write(marker, os.getpid(), time.time())

    holder = read_live_update(path=marker)

    assert holder is not None, "a genuinely live update must still refuse a second one"
    assert holder.pid == os.getpid()
    assert marker.exists()


def test_dead_pid_still_expires(tmp_path):
    marker = tmp_path / ".merlin-update-in-progress"
    _write(marker, 0, time.time())

    assert read_live_update(path=marker) is None
    assert not marker.exists()
