"""Downloaded archives are debris once the package is published.

A freshly written archive can still be open on Windows (a virus scanner reading it,
the search indexer) and the delete then fails. That is a disk-space problem, never a
reason to report a finished install as failed — and the next install sweeps whatever
could not be reclaimed.
"""
from pathlib import Path

import pm.install as install
from pm.install import _remove_downloads
from pm.store import Store


def _fetch(store: Store, sha: str) -> Path:
    path = store.entry(f"fetch-{sha}")
    path.mkdir()
    (path / "archive.tar.gz").write_text("payload", encoding="utf-8")
    return path


def _held(store_arg, name):
    raise PermissionError(2, "The system cannot find the file specified")


def test_locked_archive_does_not_fail_a_published_install(tmp_path, monkeypatch):
    store = Store(tmp_path)
    _fetch(store, "a" * 64)

    monkeypatch.setattr(install, "_remove_entry", _held)

    _remove_downloads(store, [{"sha256": "a" * 64}])  # must not raise


def test_free_archive_is_still_removed(tmp_path):
    store = Store(tmp_path)
    archive = _fetch(store, "b" * 64)

    _remove_downloads(store, [{"sha256": "b" * 64}])

    assert not archive.exists(), "the archive is released once it is publishable"
