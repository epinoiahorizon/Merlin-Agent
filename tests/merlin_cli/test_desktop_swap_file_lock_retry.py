"""Desktop stage-and-swap promotion rides out a transient Windows file lock (#112544).

A real-time scanner (AV/EDR) briefly holds ``release/win-unpacked`` right after the pack; the
promotion rename then raises PermissionError and the updater used to report "Could not install the
rebuilt desktop app" even though a retry a second later would have succeeded.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from merlin_cli import main_desktop


def _packaged_exe_rel() -> Path:
    if sys.platform == "darwin":
        return Path("mac-arm64") / "Merlin.app" / "Contents" / "MacOS" / "Merlin"
    if sys.platform == "win32":
        return Path("win-unpacked") / "Merlin.exe"
    return Path("linux-unpacked") / "merlin"


def _staged_over_live(tmp_path: Path, monkeypatch):
    desktop_dir = tmp_path / "apps" / "desktop"
    live_exe = desktop_dir / "release" / _packaged_exe_rel()
    live_exe.parent.mkdir(parents=True)
    live_exe.write_text("old", encoding="utf-8")
    staging = main_desktop._desktop_staging_dir(desktop_dir)
    staged_exe = staging / _packaged_exe_rel()
    staged_exe.parent.mkdir(parents=True)
    staged_exe.write_text("new", encoding="utf-8")
    # The swap point now passes ``also_posix=True`` (#116504); the double must accept the keyword.
    monkeypatch.setattr(main_desktop, "_stop_desktop_processes_locking_build", lambda d, **kw: [])
    slept: list[float] = []
    monkeypatch.setattr(main_desktop._time_mod, "sleep", slept.append)
    return desktop_dir, staging, live_exe, slept


def test_swap_retries_transient_permission_error_then_promotes(tmp_path, monkeypatch, caplog):
    desktop_dir, staging, live_exe, slept = _staged_over_live(tmp_path, monkeypatch)
    real_rename = os.rename
    locked = {"n": 0}

    def scanner_locked_rename(src, dst):
        if Path(dst) == live_exe.parent and locked["n"] < 2:
            locked["n"] += 1
            raise PermissionError(32, "being used by another process")
        return real_rename(src, dst)

    monkeypatch.setattr(main_desktop.os, "rename", scanner_locked_rename)
    with caplog.at_level("WARNING", logger=main_desktop.logger.name):
        promoted = main_desktop._swap_staged_desktop_app(desktop_dir, staging)

    assert promoted == live_exe
    assert live_exe.read_text(encoding="utf-8") == "new"
    assert len(slept) == 2  # two transient locks → two backoff sleeps before the promotion
    assert not staging.exists()


def test_swap_gives_up_after_bounded_retries_and_keeps_live_app(tmp_path, monkeypatch, caplog):
    """A lock that never clears: bounded attempts, real OSError surfaced in the log, live app untouched."""
    desktop_dir, staging, live_exe, slept = _staged_over_live(tmp_path, monkeypatch)
    real_rename = os.rename
    attempts = {"n": 0}

    def always_locked_rename(src, dst):
        if Path(src) == staging / _packaged_exe_rel().parts[0]:
            attempts["n"] += 1
            raise PermissionError(5, "Access is denied")
        return real_rename(src, dst)

    monkeypatch.setattr(main_desktop.os, "rename", always_locked_rename)
    with caplog.at_level("WARNING", logger=main_desktop.logger.name):
        assert main_desktop._swap_staged_desktop_app(desktop_dir, staging) is None

    assert attempts["n"] == len(main_desktop._DESKTOP_SWAP_RENAME_RETRY_DELAYS_S) + 1
    assert len(slept) == len(main_desktop._DESKTOP_SWAP_RENAME_RETRY_DELAYS_S)
    assert live_exe.read_text(encoding="utf-8") == "old"
    assert not (live_exe.parent.parent / (live_exe.parent.name + ".previous")).exists()
    assert any("Access is denied" in r.message and "live app kept" in r.message for r in caplog.records)


def test_swap_heals_an_interrupted_promotion_leftover(tmp_path, monkeypatch):
    """A killed earlier update leaves ``release/<root>`` as a resources-only shell plus a
    ``<root>.tmp`` sibling. The next promotion must clear both and land the staged app, instead
    of moving the shell aside and rolling it straight back — the shape that made every later
    update fail with "Could not publish the desktop build" (#112544 follow-up).
    """
    desktop_dir, staging, live_exe, _ = _staged_over_live(tmp_path, monkeypatch)
    root = live_exe.parent  # release/win-unpacked
    release = root.parent
    live_exe.unlink()  # the app is gone; only the shell an interrupted run left is here
    (root / "resources").mkdir()
    leftover = release / (root.name + ".tmp")
    leftover.mkdir()
    (leftover / "half-written").write_text("x", encoding="utf-8")

    promoted = main_desktop._swap_staged_desktop_app(desktop_dir, staging)

    assert promoted == live_exe
    assert live_exe.read_text(encoding="utf-8") == "new"
    assert not leftover.exists()
    assert not (release / (root.name + ".previous")).exists()


def test_desktop_root_has_app_ignores_a_shell(tmp_path):
    """The rollback slot is only worth spending on a directory that still holds an app."""
    shell = tmp_path / "win-unpacked"
    (shell / "resources").mkdir(parents=True)
    assert main_desktop._desktop_root_has_app(shell) is False

    (shell / "Merlin.exe").write_text("app", encoding="utf-8")
    assert main_desktop._desktop_root_has_app(shell) is True


def _lock_the_live_rename(live_exe: Path, monkeypatch):
    """The live tree cannot be moved aside, exactly as a running Desktop's exe lock behaves on
    Windows: ``desktop promotion rename win-unpacked -> win-unpacked.previous`` gets Access denied,
    wherever the staged pack happens to live."""
    real_rename = os.rename
    live_root = live_exe.parent

    def locked(src, dst):
        if Path(src) == live_root:
            raise PermissionError(5, "Access is denied")
        return real_rename(src, dst)

    monkeypatch.setattr(main_desktop.os, "rename", locked)


def test_locked_promotion_parks_the_verified_build_instead_of_failing_the_update(
    tmp_path, monkeypatch, capsys
):
    """A running Desktop keeps its files: the rebuild is parked, not discarded, and no update fails."""
    desktop_dir, staging, live_exe, _ = _staged_over_live(tmp_path, monkeypatch)
    _lock_the_live_rename(live_exe, monkeypatch)

    returned = main_desktop._promote_staged_desktop_app(
        desktop_dir, staging, integrity_check=lambda _p: None
    )

    # The live app is what the caller gets back: the update is not a failure.
    assert returned == live_exe
    assert live_exe.read_text(encoding="utf-8") == "old"
    parked = main_desktop._pending_deferred_desktop_app(desktop_dir)
    assert parked is not None and parked.is_dir()
    assert (parked / _packaged_exe_rel()).read_text(encoding="utf-8") == "new"
    out = capsys.readouterr().out
    assert "parked at:" in out and "promoted automatically" in out


def test_a_parked_build_is_promoted_by_the_next_launch(tmp_path, monkeypatch):
    """Once nothing holds the lock, the parked build lands — no second rebuild needed."""
    desktop_dir, staging, live_exe, _ = _staged_over_live(tmp_path, monkeypatch)
    real_rename = os.rename
    _lock_the_live_rename(live_exe, monkeypatch)
    assert main_desktop._promote_staged_desktop_app(
        desktop_dir, staging, integrity_check=lambda _p: None
    ) == live_exe

    monkeypatch.setattr(main_desktop.os, "rename", real_rename)  # the app exited
    promoted = main_desktop._promote_deferred_desktop_app(desktop_dir)

    assert promoted == live_exe
    assert live_exe.read_text(encoding="utf-8") == "new"
    assert main_desktop._pending_deferred_desktop_app(desktop_dir) is None
    assert not list(desktop_dir.glob(f"{main_desktop._DESKTOP_DEFERRED_PREFIX}*"))


def test_a_parked_build_stays_parked_while_the_lock_is_still_live(tmp_path, monkeypatch):
    desktop_dir, staging, live_exe, _ = _staged_over_live(tmp_path, monkeypatch)
    _lock_the_live_rename(live_exe, monkeypatch)
    main_desktop._promote_staged_desktop_app(desktop_dir, staging, integrity_check=lambda _p: None)
    parked = main_desktop._pending_deferred_desktop_app(desktop_dir)
    assert parked is not None

    assert main_desktop._promote_deferred_desktop_app(desktop_dir) is None
    assert live_exe.read_text(encoding="utf-8") == "old"
    assert main_desktop._pending_deferred_desktop_app(desktop_dir) == parked
