"""Per-file context manifest (``agent/context_file_sources.py``) behind the ``/context`` Rules figure.

The manifest and ``build_context_files_prompt`` share one discovery walk. Under the MERLIN_OS SEAL
(Vector #6) project context auto-loading is disabled: the builder never loads project context files,
so the invariants under test are (a) the manifest stays honest about what discovery WOULD load, and
(b) the built prompt only ever carries SOUL.md — no project file content, whatever the manifest says.
"""

from pathlib import Path

import pytest

from agent.context_file_sources import list_context_file_sources, render_context_file_lines
from agent.prompt_builder import build_context_files_prompt


@pytest.fixture()
def project(tmp_path):
    (tmp_path / ".git").mkdir()
    return tmp_path


def _by_label(sources):
    return {s["label"]: s for s in sources}


def test_manifest_stays_honest_while_the_sealed_builder_loads_only_soul(project, tmp_path_factory):
    """Discovery still reports the ladder winner; the sealed builder must not load any project file."""
    (project / ".merlin.md").write_text("merlin rules")
    (project / "AGENTS.md").write_text("root agents rules")
    sub = project / "pkg"
    sub.mkdir()
    (sub / "AGENTS.override.md").write_text("")  # empty: falls through to AGENTS.md in the same directory
    (sub / "AGENTS.md").write_text("pkg agents rules")
    (sub / "CLAUDE.md").write_text("claude rules")
    (sub / ".cursorrules").write_text("cursor rules")
    (sub / ".cursor" / "rules").mkdir(parents=True)
    (sub / ".cursor" / "rules" / "a.mdc").write_text("mdc rule a")
    home = tmp_path_factory.mktemp("home")
    (home / "SOUL.md").write_text("identity text")

    sources = list_context_file_sources(cwd=str(sub), home_override=home)
    prompt = build_context_files_prompt(cwd=str(sub), home_override=home)

    statuses = {s["label"]: s["status"] for s in sources}
    assert statuses == {
        ".merlin.md": "loaded", "../AGENTS.md": "shadowed", "AGENTS.override.md": "empty", "AGENTS.md": "shadowed",
        "CLAUDE.md": "shadowed", ".cursorrules": "shadowed", ".cursor/rules/a.mdc": "shadowed", "SOUL.md": "loaded",
    }
    # SEAL contract: SOUL rides along, project file content never enters the prompt.
    assert "identity text" in prompt
    for banned in ("merlin rules", "root agents rules", "pkg agents rules", "claude rules", "cursor rules", "mdc rule a"):
        assert banned not in prompt, banned
    assert all(s["est_tokens"] > 0 for s in sources if s["chars"])

    # Empty-seal edge: with SOUL disabled too, the prompt is empty even though discovery finds files.
    assert build_context_files_prompt(cwd=str(sub), skip_soul=True) == ""


def test_sealed_builder_suppresses_even_threat_marked_project_files(project, monkeypatch, tmp_path_factory):
    """The SEAL outranks the injection scanner too: blocked markers never render because project files never load."""
    import agent.prompt_builder as pb

    monkeypatch.setattr(pb, "_get_context_file_max_chars", lambda *_a: 10_000)
    monkeypatch.setattr(pb, "_scan_for_threats", lambda content, scope: ["fake-pattern"] if "evil" in content else [])
    (project / "AGENTS.md").write_text("evil")
    home = tmp_path_factory.mktemp("home")
    (home / "SOUL.md").write_text("identity text")

    # The manifest still reports the would-be load honestly (blocked + not loaded).
    entry = _by_label(list_context_file_sources(cwd=str(project), home_override=home))["AGENTS.md"]
    assert entry["status"] == "blocked" and entry["loaded"] is False

    # The sealed builder neither loads the file nor renders a BLOCKED marker for it.
    prompt = build_context_files_prompt(cwd=str(project), home_override=home)
    assert "evil" not in prompt and "[BLOCKED: AGENTS.md" not in prompt
    assert "identity text" in prompt

    # SOUL itself is still scanned: a flagged SOUL is loaded but the manifest says so.
    (home / "SOUL.md").write_text("evil identity text")
    entries = _by_label(list_context_file_sources(cwd=str(project), home_override=home))
    assert entries["SOUL.md"]["status"] == "flagged" and entries["SOUL.md"]["loaded"] is True
    prompt = build_context_files_prompt(cwd=str(project), home_override=home)
    assert "evil identity text" in prompt and "[BLOCKED: SOUL.md" not in prompt
    assert any("SOUL.md" in line and "review the file" in line
               for line in render_context_file_lines(list(entries.values())))
