"""Dreamball capsule contract tests — Phase 1.5 of the Dreamfield sequence.

Invariants under test:

- 5W1H structure: what/who/when/why/where/how keys all present in a capsule
- SOUL: deterministic per session (same ball, same line), composed from
  structure only — never from message content
- RIVERS: lineage session ids pass through to the capsule
- Privacy: message bodies never appear in the capsule; the WHY keeps only the
  first user line, truncated
- Fingerprint: changes when any field changes, stable across re-forges
- Verified sessions carry receipt data (red before green) in HOW
"""

import json

import pytest

from merlin_cli.dreamball import (
    CAPSULE_EXTENSION,
    forge_dreamball,
    save_dreamball,
    _first_intent_line,
)


def _session(title="The Night the Repository Healed", messages=None, sid="20261008", **extra):
    data = {"id": sid, "title": title, "messages": messages or []}
    data.update(extra)
    return data


class TestStructure5W1H:
    def test_all_six_keys_present(self):
        ball = forge_dreamball(_session())
        for key in ("what", "who", "when", "why", "where", "how"):
            assert key in ball, key

    def test_soul_and_rivers(self):
        ball = forge_dreamball(_session(), anchor={"kind": "place", "label": "Bali"})
        assert "soul" in ball and ball["soul"]["inscription"].strip()
        assert ball["where"]["label"] == "Bali"
        assert ball["rivers"] == []

    def test_rivers_carry_lineage(self):
        ball = forge_dreamball(_session(lineage_session_ids=["aaa", "bbb"]))
        assert ball["rivers"] == ["aaa", "bbb"]

    def test_version_and_fingerprint(self):
        ball = forge_dreamball(_session())
        assert ball["dreamball"] == 1
        assert len(ball["fingerprint"]) == 64  # sha256 hex


class TestSoul:
    def test_inscription_deterministic(self):
        s = _session(messages=[{"role": "user", "content": "gas"}, {"role": "assistant", "content": "FAILED x"}])
        a = forge_dreamball(s)
        b = forge_dreamball(s)
        assert a["soul"]["inscription"] == b["soul"]["inscription"]

    def test_soul_never_contains_message_content(self):
        secret = "sk-supersecret-never-in-soul"
        s = _session(messages=[
            {"role": "user", "content": "forge the ball"},
            {"role": "assistant", "content": f"transcript {secret} full body"},
            {"role": "user", "content": f"another {secret} later line"},
        ])
        ball = forge_dreamball(s)
        # only the FIRST user line survives (as the WHY epitaph); later
        # messages and assistant bodies never appear anywhere in the capsule
        assert "transcript" not in json.dumps(ball)
        assert ball["why"]["intent"] == "forge the ball"

    def test_verified_mood_distinct_from_built(self):
        verified = forge_dreamball(_session(messages=[
            {"role": "assistant", "content": "3 failed"}, {"role": "assistant", "content": "214 passed"}]))
        built = forge_dreamball(_session())
        # both have souls; verified ball records the receipt in HOW
        assert verified["how"]["verified"] is True
        assert built["how"]["verified"] is False


class TestPrivacy:
    def test_message_bodies_not_in_capsule(self):
        s = _session(messages=[
            {"role": "user", "content": "fix the update channel please"},
            {"role": "assistant", "content": "long transcript body that must never appear"},
        ])
        ball = forge_dreamball(s)
        blob = json.dumps(ball)
        assert "long transcript body" not in blob
        # the WHY keeps only the truncated first intent line
        assert ball["why"]["intent"] == "fix the update channel please"

    def test_intent_truncated_to_epitaph(self):
        s = _session(messages=[{"role": "user", "content": "x" * 400}])
        ball = forge_dreamball(s)
        assert len(ball["why"]["intent"]) <= 120
        assert ball["why"]["intent"].endswith("…")


class TestFingerprint:
    def test_stable_across_reforge(self):
        s = _session()
        assert forge_dreamball(s)["fingerprint"] == forge_dreamball(s)["fingerprint"]

    def test_changes_when_anchor_changes(self):
        s = _session()
        a = forge_dreamball(s)
        b = forge_dreamball(s, anchor={"kind": "place", "label": "Jakarta"})
        assert a["fingerprint"] != b["fingerprint"]


class TestSave:
    def test_save_writes_dreamball_file(self, tmp_path):
        ball = forge_dreamball(_session(sid="night-01"))
        path = save_dreamball(ball, str(tmp_path))
        assert path.endswith("night-01" + CAPSULE_EXTENSION)
        loaded = json.loads((tmp_path / ("night-01" + CAPSULE_EXTENSION)).read_text())
        assert loaded["soul"] == ball["soul"]

    def test_intent_helper_first_user_line(self):
        msgs = [{"role": "assistant", "content": "hi"}, {"role": "user", "content": "  the\nreal\nintent  "}]
        assert _first_intent_line(msgs) == "the real intent"


class TestLiveSession:
    def test_forge_this_night_session_shape(self):
        """Shape check with the session that built the feature itself."""
        msgs = [
            {"role": "user", "content": "ok go"},
            {"role": "assistant", "content": "pytest 3 failed"},
            {"role": "assistant", "content": "rerun: 31 passed, 4 skipped"},
            {"content": [{"type": "tool_use", "name": "terminal"}]},
        ]
        ball = forge_dreamball(_session(messages=msgs, lineage_session_ids=["20261005_192656_a3a15a"]),
                               anchor={"kind": "place", "lat": -6.2, "lon": 106.8, "label": "Jakarta"})
        assert ball["how"]["verified"] is True
        assert ball["how"]["red"] >= 1 and ball["how"]["green"] >= 1
        assert ball["how"]["tool_calls"] == 1
        assert ball["rivers"] == ["20261005_192656_a3a15a"]