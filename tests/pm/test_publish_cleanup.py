"""Cleanup after a swap must never be what fails the swap.

Both paths here end with a directory whose bytes are *no longer authoritative* —
the displaced copy after a rollback restored the previous version, and the
`.previous-*` entry after a publication verified. On Windows those directories
are hardlinked to the live toolchain, so a DLL inside them (libcrypto, for one)
cannot be deleted while this very process is running from it.

That is disk waste. Reporting it as a failed update is what strands a client:
`Source update preparation failed: [WinError 5] ... .displaced-...\\DLLs\\libcrypto-3-x64.dll`
after the install itself had already succeeded.
"""
from pathlib import Path

import pytest

import pm.install as install
from pm.install import _publish_entry, _restore_previous_entry
from pm.store import Store


class _Package:
    name = "git"

    def verify(self, entry: Path, target: str):
        return None


def _entry(store: Store, name: str, marker: str) -> Path:
    path = store.entry(name)
    path.mkdir()
    (path / "VERSION").write_text(marker, encoding="utf-8")
    return path


def _held(store_arg, name):
    raise PermissionError(5, "Access is denied")


def test_locked_displaced_directory_does_not_fail_the_rollback(tmp_path, monkeypatch):
    """The restore succeeded; the leftover could not be deleted. Not an error."""
    store = Store(tmp_path)
    entry = _entry(store, "python-3.14.7", "new")
    previous = _entry(store, ".previous-python-3.14.7", "old")

    monkeypatch.setattr(install, "_remove_entry", _held)

    _restore_previous_entry(store, entry, previous, "python")

    assert (entry / "VERSION").read_text(encoding="utf-8") == "old", (
        "the previous version must be back in place"
    )
    assert not previous.exists(), "the restore point is consumed by the rename"


def test_locked_previous_entry_does_not_fail_a_verified_publish(tmp_path, monkeypatch):
    """Publication verified; the old copy is debris the OS still has open."""
    store = Store(tmp_path)
    staged = tmp_path / "staged"
    staged.mkdir()
    (staged / "VERSION").write_text("new", encoding="utf-8")
    entry = store.entry("git-2.53.0+3")
    previous = _entry(store, ".previous-git-2.53.0+3", "old")

    monkeypatch.setattr(install, "_remove_entry", _held)

    with _publish_entry(_Package(), store, staged, entry, previous, "win32-x64"):
        pass  # verification passed, caller committed

    assert entry.exists(), "the published entry must survive"
    assert previous.exists(), "the undeletable leftover stays as debris"


def test_a_failed_publish_still_rolls_back(tmp_path, monkeypatch):
    """Tolerating cleanup must not swallow the rollback it protects."""
    store = Store(tmp_path)
    staged = tmp_path / "staged"
    staged.mkdir()
    (staged / "VERSION").write_text("new", encoding="utf-8")
    entry = store.entry("git-2.53.0+3")
    previous = _entry(store, ".previous-git-2.53.0+3", "old")

    class _Failing(_Package):
        def verify(self, entry: Path, target: str):
            return "published entry failed verification"

    monkeypatch.setattr(install, "_remove_entry", _held)

    with pytest.raises(install.InstallError):
        with _publish_entry(_Failing(), store, staged, entry, previous, "win32-x64"):
            pass

    assert (entry / "VERSION").read_text(encoding="utf-8") == "old", (
        "the previous bytes must be restored before the error surfaces"
    )
