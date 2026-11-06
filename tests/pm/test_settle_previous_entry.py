"""Settling a restore point left by an aborted swap.

Two Windows failures meet here and must not be confused:

* a leftover whose published bytes **still verify** is debris — dropping it is
  all that is left, and a store that hardlinks entries may refuse the delete
  while the toolchain executes from those files;
* a leftover whose canonical entry **fails** verification is a real rollback —
  restoring it is mandatory, and a refused rename must surface.

Getting the first case wrong costs disk. Getting the second wrong throws away
the only good copy, so the unverified paths keep their tests.
"""
from pathlib import Path

import pytest

import pm.install as install
from pm.install import _settle_previous_entry
from pm.store import Store, tree_digest
from pm.package import InstallError


class _Package:
    """Minimal stand-in: ``verify`` returns None when the entry looks intact."""

    name = "git"

    def __init__(self, healthy: bool = True):
        self.healthy = healthy

    def verify(self, entry: Path, target: str):
        if not (entry / "VERSION").exists():
            return "missing VERSION"
        return None if self.healthy else "corrupt payload"


def _entry(store: Store, name: str, marker: str) -> Path:
    path = store.entry(name)
    path.mkdir()
    (path / "VERSION").write_text(marker, encoding="utf-8")
    return path


def _record(entry: Path) -> dict:
    return {"entry": entry.name, "digest": tree_digest(entry)}


def test_verified_entry_drops_the_leftover(tmp_path):
    """Published bytes verify: the leftover is debris, not a rollback."""
    store = Store(tmp_path)
    entry = _entry(store, "git-2.53.0+3", "live")
    previous = _entry(store, ".previous-git-2.53.0+3", "stale")

    _settle_previous_entry(_Package(), store, entry, previous, _record(entry), "win32-x64")

    assert not previous.exists(), "the leftover must be dropped"
    assert (entry / "VERSION").read_text(encoding="utf-8") == "live"


def test_undeletable_leftover_does_not_fail_the_update(tmp_path, monkeypatch):
    """Hardlinked entries cannot be deleted while the toolchain runs from them.

    That is disk waste, not a reason to fail an otherwise healthy update.
    """
    store = Store(tmp_path)
    entry = _entry(store, "node-26.12.1", "live")
    previous = _entry(store, ".previous-node-26.12.1", "stale")

    def held(store_arg, name):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(install, "_remove_entry", held)

    _settle_previous_entry(_Package(), store, entry, previous, _record(entry), "win32-x64")

    assert entry.exists(), "the live entry must survive"
    assert (entry / "VERSION").read_text(encoding="utf-8") == "live", (
        "debris must not be restored over a verified entry"
    )


def test_unverified_entry_still_restores(tmp_path):
    """A tampered entry beside a usable leftover is a rollback, not debris.

    Guards against deciding 'healthy' from a shallow structural check: the
    recorded digest is what proves the published bytes are the intended ones.
    """
    store = Store(tmp_path)
    entry = _entry(store, "git-2.53.0+3", "tampered")
    previous = _entry(store, ".previous-git-2.53.0+3", "old")

    stale = {"entry": entry.name, "digest": "0" * 64}   # record does not match

    _settle_previous_entry(_Package(), store, entry, previous, stale, "win32-x64")

    assert (entry / "VERSION").read_text(encoding="utf-8") == "old", (
        "the recorded-good copy must be restored over a tampered entry"
    )


def test_missing_canonical_restores_the_previous_entry(tmp_path):
    """Nothing published: the old bytes come back."""
    store = Store(tmp_path)
    entry = store.entry("git-2.53.0+3")
    previous = _entry(store, ".previous-git-2.53.0+3", "old")

    _settle_previous_entry(_Package(), store, entry, previous, None, "win32-x64")

    assert entry.exists()
    assert (entry / "VERSION").read_text(encoding="utf-8") == "old"
    assert not previous.exists(), "the restore point is consumed by the rename"


def test_broken_canonical_still_restores(tmp_path):
    """A structurally broken entry is not trustworthy — restore."""
    store = Store(tmp_path)
    entry = _entry(store, "git-2.53.0+3", "broken")
    previous = _entry(store, ".previous-git-2.53.0+3", "old")

    _settle_previous_entry(_Package(healthy=False), store, entry, previous, None, "win32-x64")

    assert (entry / "VERSION").read_text(encoding="utf-8") == "old"


def test_refused_restore_names_the_remedy(tmp_path, monkeypatch):
    """A permanent Windows hold must not surface as a bare PermissionError."""
    store = Store(tmp_path)
    entry = store.entry("git-2.53.0+3")          # absent: restore is required
    previous = _entry(store, ".previous-git-2.53.0+3", "old")

    real_rename = Path.rename

    def refused(self, destination):
        if self.name.startswith(".previous-"):
            raise PermissionError(5, "Access is denied")
        return real_rename(self, destination)

    monkeypatch.setattr(Path, "rename", refused)

    with pytest.raises(InstallError) as caught:
        _settle_previous_entry(_Package(), store, entry, previous, None, "win32-x64")

    message = str(caught.value)
    assert "still running" in message and "close Merlin" in message
