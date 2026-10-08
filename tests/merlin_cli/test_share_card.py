"""Share card contract tests — the /share primitive (session → social artifact).

The card is the first product surface of the Relic concept: agent labor made
legible. Invariants under test:

- self-contained HTML: no remote asset references (an offline render must work)
- fixed 1200x630 stage (OG standard) so a PNG capture maps 1:1
- stats render escaped; a red→green receipt renders only when failure evidence
  genuinely precedes pass evidence in the session
- message bodies NEVER appear in the card (secrets stay the caller's problem,
  and the card only ever carries counts + the caller-supplied title)
"""

import re

import pytest

from merlin_cli.share_card import (
    card_summary,
    generate_share_card_html,
    _has_verification_receipt,
)


def _session(title="Fix the update channel", messages=None, **extra):
    data = {"id": "20261008", "title": title, "messages": messages or []}
    data.update(extra)
    return data


class TestSelfContained:
    def test_no_remote_assets(self):
        html = generate_share_card_html(title="t")
        for banned in ("http://", "https://", "//cdn", "@import"):
            assert banned not in re.sub(r"<!--.*?-->", "", html, flags=re.S), banned

    def test_og_stage_dimensions(self):
        html = generate_share_card_html(title="t")
        assert "width:1200px" in html and "height:630px" in html

    def test_title_escaped(self):
        html = generate_share_card_html(title="<script>alert(1)</script>")
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html


class TestReceipt:
    def test_red_then_green_makes_receipt(self):
        msgs = [
            {"content": "pytest: 3 failed"},
            {"content": "rerun: 31 passed, 4 skipped"},
        ]
        assert _has_verification_receipt(msgs) is True

    def test_green_only_no_receipt(self):
        assert _has_verification_receipt([{"content": "all 50 passed"}]) is False

    def test_receipt_renders_in_card(self):
        html = generate_share_card_html(
            title="t", messages=[{"content": "FAILED 2 tests"}, {"content": "now: 214 passed"}])
        assert "Verified: caught its own errors" in html

    def test_pass_only_no_receipt_line(self):
        html = generate_share_card_html(title="t", messages=[{"content": "214 passed"}])
        assert "Verified: caught its own errors" not in html

    def test_out_of_order_is_not_a_receipt(self):
        # pass before fail = a regression story, not a fix story
        msgs = [
            {"content": "214 passed"},
            {"content": "FAILED 2 tests"},
        ]
        assert _has_verification_receipt(msgs) is False


class TestNoMessageLeak:
    def test_message_bodies_never_render(self):
        secret = "sk-ant-supersecret-do-not-leak"
        html = generate_share_card_html(title="t", messages=[{"content": f"token {secret} FAILED"}])
        assert secret not in html

    def test_tool_calls_counted_from_blocks(self):
        msgs = [
            {"content": "hi"},
            {"content": [{"type": "tool_use", "name": "terminal"}]},
            {"tool_calls": [{"id": "1"}, {"id": "2"}]},
        ]
        html = generate_share_card_html(title="t", messages=msgs)
        assert '<div class="v">3</div>' in html


class TestSummary:
    def test_card_summary_counts(self):
        s = card_summary(_session(messages=[{"content": "FAILED x"}, {"content": "ok passed"}]))
        assert s["message_count"] == 2
        assert s["verification_receipt"] is True
        assert s["title"] == "Fix the update channel"