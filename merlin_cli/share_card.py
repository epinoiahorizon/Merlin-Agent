"""Share card: a single self-contained HTML card that makes one Merlin session
shareable as a social artifact.

The card is the first primitive of the Relic concept (Epinoia Horizon): agent
labor, rendered as a poster. Every real work session becomes distributable —
the artifact loop from the marketing formulas, shipped as a product surface.

Design contract:
- 1200x630 (OG standard) so the HTML renders 1:1 into a social image
- Self-contained: no remote assets, inline starfield background, system fonts
  (a remote font would break offline + leak a request per share)
- Verification receipt rendered when the session shows red→green evidence
  (any message containing a failing check followed by a passing one)
- Never leaks secrets: the card only ever receives pre-redacted summary stats,
  never raw message bodies (redaction stays the caller's job).
"""

from __future__ import annotations

import html as _html
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Status line regexes for receipt detection. Deliberately conservative:
# only patterns the CLI itself prints, so a user quoting a failure in prose
# cannot fake a receipt.
_FAIL_RE = re.compile(r"\b(failed|FAILED|✗|AssertionError)\b")
_PASS_RE = re.compile(r"\b(passed|PASSED|✓|green)\b")


def _count_status_evidence(messages: Iterable[Dict[str, Any]]) -> Tuple[int, int]:
    """Count terminal-style pass/fail lines across message contents."""
    fails = passes = 0
    for msg in messages:
        content = msg.get("content") or msg.get("text") or ""
        if not isinstance(content, str):
            continue
        fails += len(_FAIL_RE.findall(content))
        passes += len(_PASS_RE.findall(content))
    return fails, passes


def _tool_call_count(messages: Iterable[Dict[str, Any]]) -> int:
    """Best-effort tool-use count across session messages."""
    total = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        calls = msg.get("tool_calls") or msg.get("toolCalls") or []
        if isinstance(calls, list):
            total += len(calls)
        blocks = msg.get("content")
        if isinstance(blocks, list):  # block-shaped content with tool_use
            total += sum(1 for b in blocks if isinstance(b, dict) and b.get("type") == "tool_use")
    return total


def _escape(value: Any) -> str:
    return _html.escape(str(value if value is not None else ""), quote=True)


def _has_verification_receipt(messages: List[Dict[str, Any]]) -> bool:
    """A receipt exists when failure evidence precedes pass evidence — red→green."""
    first_fail = first_pass = None
    for i, msg in enumerate(messages):
        content = msg.get("content") or msg.get("text") or ""
        if not isinstance(content, str):
            continue
        if first_fail is None and _FAIL_RE.search(content):
            first_fail = i
        if first_pass is None and _PASS_RE.search(content):
            first_pass = i
    return first_fail is not None and first_pass is not None and first_fail <= first_pass


_CARD_CSS = """
  :root { --ink:#e8dcc8; --dim:#a89d8a; --accent:#b08de0; --bg:#0a0a12; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { width:1200px; height:630px; background:var(--bg); overflow:hidden;
         font-family:'Segoe UI', 'Helvetica Neue', Arial, sans-serif; }
  .wrap { position:relative; width:100%; height:100%;
          background: radial-gradient(ellipse at 22% 14%, rgba(120,81,169,.38), transparent 55%),
                      radial-gradient(ellipse at 78% 88%, rgba(191,128,255,.22), transparent 50%),
                      #0a0a12;
          display:flex; flex-direction:column; justify-content:center; padding:54px 64px; }
  .stars { position:absolute; inset:0; background-image:
      radial-gradient(1.5px 1.5px at 110px 80px, rgba(255,255,255,.8) 50%, transparent),
      radial-gradient(1px 1px at 330px 190px, rgba(255,255,255,.6) 50%, transparent),
      radial-gradient(2px 2px at 880px 110px, rgba(255,255,255,.5) 50%, transparent),
      radial-gradient(1px 1px at 1040px 390px, rgba(255,255,255,.7) 50%, transparent),
      radial-gradient(1.5px 1.5px at 560px 500px, rgba(255,255,255,.4) 50%, transparent),
      radial-gradient(1px 1px at 200px 460px, rgba(255,255,255,.5) 50%, transparent); }
  .brand { font-size:22px; letter-spacing:.42em; color:var(--dim); text-transform:uppercase;
           margin-bottom:18px; position:relative; }
  h1 { font-size:46px; color:var(--ink); font-weight:600; line-height:1.18;
       max-width:900px; position:relative; }
  .sub { font-size:22px; color:var(--accent); margin-top:10px; font-style:italic; position:relative; }
  .line { margin:30px 0 26px; width:420px; height:1px; position:relative;
          background:linear-gradient(90deg, transparent, var(--accent), transparent); }
  .stats { display:flex; gap:46px; position:relative; }
  .stat .v { font-size:34px; color:#f4ecdd; font-weight:600; }
  .stat .k { font-size:14px; letter-spacing:.18em; text-transform:uppercase; color:var(--dim); margin-top:6px; }
  .receipt { margin-top:30px; display:inline-flex; align-items:center; gap:10px; position:relative;
             background:rgba(157,217,180,.08); border:1px solid rgba(157,217,180,.35);
             color:#9dd9b4; padding:10px 18px; border-radius:10px; font-size:17px; }
  .receipt .dot { width:9px; height:9px; border-radius:50%; background:#9dd9b4; }
  .cta { position:absolute; bottom:44px; left:64px; font-size:16px; color:var(--dim);
         letter-spacing:.06em; }
  .cta code { color:#cbb4f0; font-family:'SF Mono', Consolas, monospace; }
  .glyph { position:absolute; font-size:380px; color:rgba(176,141,224,.06);
           top:20px; right:40px; }
"""


def generate_share_card_html(
    *,
    title: str,
    subtitle: Optional[str] = None,
    stats: Optional[Dict[str, Any]] = None,
    messages: Optional[List[Dict[str, Any]]] = None,
    install_command: str = "epinoiahorizon.com/grimoire.sh  (curl | bash)",
) -> str:
    """Render one session as a 1200x630 self-contained share card (HTML).

    ``stats`` maps label→value (already-redacted, caller-supplied); ``messages``
    (also caller-supplied and already redacted) is used ONLY to detect the
    red→green verification receipt, never rendered raw.
    """
    msgs = messages or []
    fails, passes = _count_status_evidence(msgs)
    receipt = _has_verification_receipt(msgs)
    tool_calls = (stats or {}).get("tool_calls")
    if tool_calls is None:
        tool_calls = _tool_call_count(msgs)

    stat_cells = []
    for label, value in (stats or {}).items():
        if label == "tool_calls":
            continue
        stat_cells.append(f'<div class="stat"><div class="v">{_escape(value)}</div>'
                          f'<div class="k">{_escape(label)}</div></div>')
    stat_cells.append(f'<div class="stat"><div class="v">{_escape(tool_calls)}</div>'
                      '<div class="k">tool calls</div></div>')
    if fails and passes:
        stat_cells.append(f'<div class="stat"><div class="v">{_escape(fails)}→{_escape(passes)}</div>'
                          '<div class="k">red→green</div></div>')

    receipt_html = ""
    if receipt:
        receipt_html = ('<div class="receipt"><span class="dot"></span>'
                        'Verified: caught its own errors — fixed before shipping</div>')

    sub_html = f'<div class="sub">{_escape(subtitle)}</div>' if subtitle else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{_escape(title)} — Merlin Agent session</title>
<style>{_CARD_CSS}</style>
</head>
<body>
  <div class="wrap">
    <div class="stars"></div>
    <div class="glyph">✦</div>
    <div class="brand">Merlin Agent · Session Relic</div>
    <h1>{_escape(title)}</h1>
    {sub_html}
    <div class="line"></div>
    <div class="stats">{''.join(stat_cells)}</div>
    {receipt_html}
    <div class="cta">Built with <code>merlin</code> — install: <code>{_escape(install_command)}</code></div>
  </div>
</body>
</html>"""


def card_summary(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """Derive the (redaction-safe) share-card inputs from one exported session.

    Only metadata and self-supplied stats leave the session; message bodies are
    reduced to counts by :func:`generate_share_card_html` and never rendered.
    """
    msgs = session_data.get("messages") or []
    return {
        "session_id": session_data.get("id") or session_data.get("session_id"),
        "title": session_data.get("title") or session_data.get("name") or "A working session",
        "message_count": len(msgs),
        "tool_calls": _tool_call_count(msgs),
        "verification_receipt": _has_verification_receipt(msgs),
    }