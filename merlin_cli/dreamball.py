"""Dreamball capsule: session labor, encapsulated for the Dreamfield.

A Dreamball is what a Relic becomes when it carries a soul. The capsule is
the portable inventory format for dreamballz.com — born in the harness, sealed
in the Forge, walked into the worlds.

Structure: the 5W1H of the work, plus SOUL and RIVERS.

    WHAT   manifest     artifact summary + content fingerprint
    WHO    provenance   human principal + agent co-maker + machine
    WHEN   epoch        timestamp + session identity
    WHY    intent       the first human words that called the work into being
    WHERE  anchor       Dreamfield coordinate (real place, star, or memory)
    HOW    receipt      verification record: red→green evidence + tool usage
    SOUL   inscription  one poem-line composed from the session's shape
    RIVERS tributaries  lineage session ids that fed this work

Privacy contract: a Dreamball never carries message bodies. It carries the
*shape* of the session (counts, evidence ordering, first intent line) and the
caller-supplied title — nothing that would not already appear on a share card.
The soul inscription is composed from structure only, never from content.
"""

from __future__ import annotations

import hashlib
import json
import platform
from typing import Any, Dict, List, Optional

CAPSULE_VERSION = 1
CAPSULE_EXTENSION = ".dreamball"

# Poem lexicon: composed from structural facts only (counts, evidence, hour).
# Never from message content — the soul is read from the shape of the work.
_OPENERS = {
    "verified": [
        "Every error died young",
        "It caught itself falling",
        "The proof walked in before the night did",
        "Red turned to green and stayed there",
        "It argued with itself and won",
    ],
    "built": [
        "Made with hands that do not tire",
        "The forge stayed warm",
        "Something crossed from thought into world",
        "Built while the stars kept watch",
        "A door opened that cannot close",
    ],
}
_CLOSERS = {
    "verified": ["and the receipts still glow.", "and nothing shipped broken.",
                 "and the record tells the truth.", "and the work holds its own weight."],
    "built": ["and the world is a little wider.", "and tomorrow inherits it.",
              "and the dream took its first breath.", "and the rivers remember."],
}


def _compose_inscription(verified: bool, facts: Dict[str, Any], salt: str) -> str:
    """One poem-line from the session's structural shape.

    Deterministic per (session, salt): the same work always sings the same line,
    so a Dreamball's soul is a fingerprint, not a random flavor.
    """
    import random
    rng = random.Random(salt)
    mood = "verified" if verified else "built"
    opener = rng.choice(_OPENERS[mood])
    closer = rng.choice(_CLOSERS[mood])
    if facts.get("tool_calls", 0) > 50:
        mid = f" {facts['tool_calls']} tools sang in one breath;"
        return f"{opener};{mid} {closer}"
    if facts.get("messages", 0) > 40:
        return f"{opener} over {facts['messages']} turns of will; {closer}"
    return f"{opener}; {closer}"


def _content_fingerprint(payload: Dict[str, Any]) -> str:
    """Stable digest of the capsule's non-soul fields — the WHAT's identity."""
    canonical = json.dumps(
        {k: payload[k] for k in sorted(payload) if k != "soul"},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _first_intent_line(messages: List[Dict[str, Any]]) -> Optional[str]:
    """The WHY: first human-authored plain line, truncated — the calling words.

    The first user message is the reason the work exists. We keep only its
    opening (title-length, 120 chars) — an epitaph of intent, not a transcript.
    """
    for msg in messages or []:
        role = (msg.get("role") or msg.get("sender") or "").lower()
        if role not in ("user", "human"):
            continue
        content = msg.get("content") or msg.get("text") or ""
        if not isinstance(content, str):
            continue
        line = content.strip()
        if not line:
            continue
        line = " ".join(line.split())  # collapse whitespace, keep it one line
        return line[:117] + ("…" if len(line) > 117 else "")
    return None


def forge_dreamball(
    session_data: Dict[str, Any],
    *,
    anchor: Optional[Dict[str, Any]] = None,
    principal: str = "the King",
    agent: str = "merlin",
    intent_override: Optional[str] = None,
    soul_salt: Optional[str] = None,
) -> Dict[str, Any]:
    """Forge one Dreamball capsule from an exported session dict.

    ``anchor`` is the WHERE: caller-supplied Dreamfield coordinate, e.g.
    ``{"kind": "place", "lat": -8.525, "lon": 115.256, "label": "Bali"}`` or
    ``{"kind": "star", "label": "Sirius"}`` or ``{"kind": "memory"}``.
    """
    msgs = session_data.get("messages") or []
    from merlin_cli.share_card import _count_status_evidence, _has_verification_receipt, _tool_call_count

    fails, passes = _count_status_evidence(msgs)
    verified = _has_verification_receipt(msgs)
    tool_calls = _tool_call_count(msgs)
    facts = {"tool_calls": tool_calls, "messages": len(msgs)}

    salt = soul_salt or str(session_data.get("id") or session_data.get("session_id") or "dreamball")
    inscription = _compose_inscription(verified, facts, salt)

    session_id = session_data.get("id") or session_data.get("session_id")
    created = session_data.get("created_at") or session_data.get("start") or session_data.get("epoch")
    title = session_data.get("title") or session_data.get("name") or "A working session"

    capsule = {
        "dreamball": CAPSULE_VERSION,
        "what": {
            "kind": "session-relic",
            "title": title,
            "summary": (session_data.get("description") or "")[:200] or None,
        },
        "who": {"principal": principal, "agent": agent,
                "machine": platform.system() + "/" + platform.machine()},
        "when": {"epoch": created, "session": session_id},
        "why": {"intent": intent_override or _first_intent_line(msgs)},
        "where": anchor or {"kind": "unanchored"},
        "how": {"verified": verified, "red": fails, "green": passes,
                "tool_calls": tool_calls},
        "rivers": list(session_data.get("lineage_session_ids") or []),
    }
    capsule["soul"] = {"inscription": inscription}
    capsule["fingerprint"] = _content_fingerprint(capsule)
    return capsule


def save_dreamball(capsule: Dict[str, Any], directory: str) -> str:
    """Write a capsule to <directory>/<session>.dreamball; returns the path."""
    from pathlib import Path
    out_dir = Path(directory).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    session = (capsule.get("when") or {}).get("session") or "session"
    safe = str(session).replace("/", "-")
    path = out_dir / (safe + CAPSULE_EXTENSION)
    path.write_text(json.dumps(capsule, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)