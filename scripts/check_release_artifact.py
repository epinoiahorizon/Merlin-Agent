#!/usr/bin/env python3
"""Refuse a release artifact that ships stray or pre-rebrand executables.

A portable pack is a directory (or zip) a user extracts and runs. Anything else in its root that
looks runnable is either a leftover from a rename (``Merlin.pre-rebrand.exe``, ~214 MB of duplicate
app), a copy of an earlier product's binary, or a half-made backup — all of them are shipped to
every downloader and none of them belong in a release. The check is deliberately name-based and
cheap so it can run on the artifact right before upload:

    python scripts/check_release_artifact.py Merlin-Agent-win-x64.zip

Exit code 0 = the artifact is clean, 1 = it must not be published (each finding is printed with the
bytes it wastes). Runs on a directory too, which is what the pack step produces before zipping.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable, NamedTuple

# The one executable a pack may launch. Everything else at the root is suspicious.
APP_EXE = "merlin.exe"
# Installer/helper executables that legitimately sit next to the app in an NSIS-style pack.
ALLOWED_HELPERS = ("uninstall merlin.exe", "uninstall.exe", "elevate.exe")
# Name fragments that mean "this is not this product's current binary".
FORBIDDEN_FRAGMENTS = (
    "pre-rebrand", "prerebrand", "hermes", "openclaw", "clawd",
    ".bak", ".old", ".orig", " copy", "-copy", "backup",
)


class Finding(NamedTuple):
    name: str
    size: int
    reason: str


def _at_pack_root(name: str) -> bool:
    """True for a file in the pack root — including one wrapping folder, which is how zips ship."""
    return len(PurePosixPath(name.replace("\\", "/")).parts) <= 2


def _is_executable(name: str) -> bool:
    return PurePosixPath(name.replace("\\", "/")).suffix.lower() in {".exe", ".com", ".bat", ".cmd", ".ps1"}


def _check(name: str, size: int) -> Finding | None:
    lowered = PurePosixPath(name.replace("\\", "/")).name.lower()
    if any(f in lowered for f in FORBIDDEN_FRAGMENTS):
        return Finding(name, size, "stray/pre-rebrand binary must not ship")
    if not _is_executable(lowered):
        return None
    if lowered != APP_EXE and lowered not in ALLOWED_HELPERS:
        return Finding(name, size, f"unexpected executable in the pack root (expected {APP_EXE})")
    return None


def scan_zip(path: Path) -> tuple[list[Finding], int, int]:
    findings: list[Finding] = []
    app_exe_count = 0
    has_asar = False
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            name = info.filename
            if name.endswith("/"):
                continue
            if _at_pack_root(name) and name.rsplit("/", 1)[-1].lower() == APP_EXE:
                app_exe_count += 1
            if name.endswith("resources/app.asar"):
                has_asar = True
            if _at_pack_root(name):
                found = _check(name, info.file_size)
                if found:
                    findings.append(found)
    return findings, app_exe_count, int(has_asar)


def scan_dir(path: Path) -> tuple[list[Finding], int, int]:
    findings: list[Finding] = []
    # Only the pack root's own app exe counts: a bundled pack legitimately carries more copies
    # (tools/, bin/) deeper in the tree.
    app_exe_count = sum(
        1 for p in path.rglob("*")
        if p.is_file() and p.name.lower() == APP_EXE and len(p.relative_to(path).parts) <= 2
    )
    has_asar = any(p.is_file() for p in path.rglob("resources/app.asar"))
    for entry in sorted(path.iterdir()):
        if entry.is_file() and _at_pack_root(entry.name):
            found = _check(entry.name, entry.stat().st_size)
            if found:
                findings.append(found)
    return findings, app_exe_count, int(has_asar)


def check(target: Path) -> list[Finding]:
    """Every reason *target* must not be published; empty means clean."""
    if target.is_dir():
        findings, app_exes, has_asar = scan_dir(target)
    else:
        findings, app_exes, has_asar = scan_zip(target)
    findings = list(findings)
    if app_exes != 1:
        findings.append(Finding(str(target.name), 0, f"expected exactly one {APP_EXE}, found {app_exes}"))
    if not has_asar:
        findings.append(Finding(str(target.name), 0, "no resources/app.asar — this is not a complete pack"))
    return findings


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refuse a release artifact that ships stray or pre-rebrand executables."
    )
    parser.add_argument("target", type=Path, help="pack directory or portable .zip")
    args = parser.parse_args(list(argv) if argv is not None else None)
    target: Path = args.target
    if not target.exists():
        print(f"✗ {target}: not found")
        return 1
    findings = check(target)
    if not findings:
        print(f"✓ {target.name}: clean (one app executable, no pre-rebrand leftovers)")
        return 0
    wasted = sum(f.size for f in findings)
    print(f"✗ {target.name}: must not be published — {len(findings)} finding(s)")
    for finding in findings:
        size = f" ({finding.size / 1_000_000:.0f} MB)" if finding.size else ""
        print(f"    - {finding.name}{size}: {finding.reason}")
    if wasted:
        print(f"  Removing these would shrink the artifact by ~{wasted / 1_000_000:.0f} MB.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
