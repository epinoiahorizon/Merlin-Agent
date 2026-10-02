"""CI enforcement for the improvement-loop skill (authoring hardline subset)."""
import re
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "skills" / "software-development" / "improvement-loop" / "SKILL.md"
MARKETING = re.compile(
    r"\b(powerful|comprehensive|seamless|revolutionary|cutting-edge|state-of-the-art)\b", re.I)
MACHINE_LOCAL = re.compile(r"/home/(?!runner\b)[a-z0-9_-]+/|[A-Z]:\\+Users\\")


def _frontmatter_block(text: str) -> str:
    assert text.startswith("---"), "frontmatter must start at byte 0"
    m = re.search(r"\n---\s*\n", text[3:])
    assert m, "frontmatter must close with a line of ---"
    return text[3 : m.start() + 3]


def _description(frontmatter: str) -> str:
    m = re.search(r'^description:\s*"?([^"\n]*)"?', frontmatter, re.M)
    assert m, "description missing"
    return m.group(1).strip()


def test_frontmatter_shape():
    import merlin_yaml as yaml
    text = SKILL.read_text(encoding="utf-8")
    fm = yaml.safe_load(_frontmatter_block(text))
    assert isinstance(fm, dict)
    for key in ("name", "description", "version", "author", "license", "platforms"):
        assert key in fm, f"missing {key}"
    assert fm["name"] == "improvement-loop"
    assert fm["author"].split(",")[0].strip() != "Merlin Agent", "human credited first"


def test_description_budget():
    text = SKILL.read_text(encoding="utf-8")
    desc = _description(_frontmatter_block(text))
    assert len(desc) <= 60, f"description {len(desc)} chars — hardline is 60"
    assert desc.endswith("."), "description must end with a period"
    assert not MARKETING.search(desc)


def test_no_machine_local_paths():
    text = SKILL.read_text(encoding="utf-8")
    assert not MACHINE_LOCAL.search(text), "machine-local path baked in"


def test_section_order():
    text = SKILL.read_text(encoding="utf-8")
    order = [text.find(h) for h in ("## When to Use", "## Procedure", "## Pitfalls", "## Verification")]
    assert all(x >= 0 for x in order), "missing a required section"
    assert order == sorted(order), "sections out of modern order"


def test_related_skills_exist_in_repo():
    import merlin_yaml as yaml
    repo = Path(__file__).resolve().parents[2]
    text = SKILL.read_text(encoding="utf-8")
    fm = yaml.safe_load(_frontmatter_block(text))
    for rel in (fm.get("metadata", {}).get("merlin", {}).get("related_skills") or []):
        hits = list(repo.glob(f"skills/*/{rel}/SKILL.md"))
        assert hits, f"related skill not found in repo: {rel}"


def test_core_loop_rules_present():
    text = SKILL.read_text(encoding="utf-8")
    for needle in ("same skill_manage call", "re-run", "Weekly sweep", "imperative rule"):
        assert needle in text, f"core rule missing: {needle}"