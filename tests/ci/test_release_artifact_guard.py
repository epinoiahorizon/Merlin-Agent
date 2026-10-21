"""A shipped portable pack must carry exactly one app executable and no rename leftovers.

`Merlin-Agent-win-x64.zip` shipped `Merlin.pre-rebrand.exe` — a 214 MB duplicate of the app kept
back by hand during the rebrand, swept into the zip by whoever packed the directory. Every
downloader paid for it and a "pre-rebrand" binary in a brand-clean release is confusing at best.
`scripts/check_release_artifact.py` is the gate: this file proves it rejects the shape that shipped
and accepts the shape that should.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_release_artifact.py"


@pytest.fixture(scope="module")
def guard():
    spec = importlib.util.spec_from_file_location("check_release_artifact", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pack(tmp_path: Path, root_exes: dict[str, str]) -> Path:
    """A minimal unpacked-app directory: resources/app.asar plus the given root executables."""
    pack = tmp_path / "Merlin-Agent-win-x64"
    (pack / "resources").mkdir(parents=True)
    (pack / "resources" / "app.asar").write_text("asar", encoding="utf-8")
    for name, body in root_exes.items():
        (pack / name).write_text(body, encoding="utf-8")
    return pack


def test_a_clean_pack_passes(guard, tmp_path):
    pack = _pack(tmp_path, {"Merlin.exe": "app"})
    assert guard.check(pack) == []
    assert guard.main([str(pack)]) == 0


def test_a_pre_rebrand_leftover_is_refused(guard, tmp_path, capsys):
    pack = _pack(tmp_path, {"Merlin.exe": "app", "Merlin.pre-rebrand.exe": "duplicate"})
    findings = guard.check(pack)

    assert [(f.name, f.reason) for f in findings] == [
        ("Merlin.pre-rebrand.exe", "stray/pre-rebrand binary must not ship")
    ]
    assert guard.main([str(pack)]) == 1
    out = capsys.readouterr().out
    assert "must not be published" in out and "Merlin.pre-rebrand.exe" in out


@pytest.mark.parametrize("stray", ["hermes.exe", "Hermes.pre-rebrand.exe", "Merlin.exe.bak", "Merlin copy.exe"])
def test_an_upstream_or_backup_binary_is_refused(guard, tmp_path, stray):
    pack = _pack(tmp_path, {"Merlin.exe": "app", stray: "x"})
    findings = guard.check(pack)
    assert [f.name for f in findings] == [stray]


def test_a_second_unexplained_executable_is_refused(guard, tmp_path):
    pack = _pack(tmp_path, {"Merlin.exe": "app", "helper32.exe": "x"})
    findings = guard.check(pack)
    assert [(f.name, f.reason) for f in findings] == [
        ("helper32.exe", "unexpected executable in the pack root (expected merlin.exe)")
    ]


def test_a_pack_without_the_asar_is_refused(guard, tmp_path):
    pack = tmp_path / "broken"
    pack.mkdir()
    (pack / "Merlin.exe").write_text("app", encoding="utf-8")
    reasons = {f.reason for f in guard.check(pack)}
    assert any("app.asar" in r for r in reasons)


def test_a_zip_is_scanned_the_same_way(guard, tmp_path):
    zip_path = tmp_path / "Merlin-Agent-win-x64.zip"
    import zipfile

    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("Merlin-Agent-win-x64/Merlin.exe", "app")
        z.writestr("Merlin-Agent-win-x64/resources/app.asar", "asar")
        z.writestr("Merlin-Agent-win-x64/Merlin.pre-rebrand.exe", "duplicate")

    findings = guard.check(zip_path)
    assert [f.name for f in findings] == ["Merlin-Agent-win-x64/Merlin.pre-rebrand.exe"]
    assert guard.main([str(zip_path)]) == 1
