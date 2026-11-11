"""Regression test: an empty answer caused by `finish_reason=length` must raise the retry ceiling.

Why this exists: a reasoning model can spend the whole output budget thinking and return
empty content with HTTP 200. The empty-response ladder then retried with the SAME ceiling,
which walks into the same wall. The retry now doubles `agent.max_tokens` (capped) for the
rest of the turn, and the next turn restores the configured value.

Real evidence this happens: a benchmark run recorded 4/20 with empty content on two
provider calls; re-running with a doubled budget produced a full 20/20.
"""
from types import SimpleNamespace

import pytest

from agent import turn_empty_response as ter


class _FakeAgent(SimpleNamespace):
    def _buffer_diagnostic_status(self, *a, **k):
        pass

    def _flush_status_buffer(self):
        pass


@pytest.fixture()
def agent(monkeypatch):
    a = _FakeAgent(max_tokens=4096, _empty_content_retries=0, model="deepseek-v4.1-flash:1017",
                   _max_tokens_before_length_retry=None)
    monkeypatch.setattr(ter._empty_guard, "record_empty_attempt", lambda *a, **k: None)
    monkeypatch.setattr(ter._empty_guard, "empty_retry_budget", lambda *a, **k: 3)
    monkeypatch.setattr(ter._empty_guard, "deterministic_empty", lambda *a, **k: False)
    monkeypatch.setattr(ter, "interruptible_backoff_sleep", lambda *a, **k: None)
    return a


def _retry(agent, finish_reason):
    return ter._retry_empty(
        agent, response={}, finish_reason=finish_reason, empty_candidate=True,
        messages=[], conversation_history=[], api_call_count=1,
    )


def test_length_stop_raises_ceiling_for_the_retry(agent):
    action, interrupt, _ = _retry(agent, "length")
    assert action == "continue" and interrupt is None
    assert agent.max_tokens == 8192
    assert agent._max_tokens_before_length_retry == 4096


def test_bump_is_idempotent_within_a_turn(agent):
    _retry(agent, "length")
    _retry(agent, "length")
    assert agent.max_tokens == 8192, "repeated empty retries must not compound the ceiling"


def test_other_finish_reasons_do_not_touch_the_ceiling(agent):
    _retry(agent, "stop")
    assert agent.max_tokens == 4096
    assert agent._max_tokens_before_length_retry is None


def test_ceiling_is_capped(agent):
    agent.max_tokens = 40000
    _retry(agent, "length")
    assert agent.max_tokens == 40000, "values already above the cap are left alone"


def test_restore_returns_the_configured_budget(agent):
    _retry(agent, "length")
    ter.restore_turn_max_tokens(agent)
    assert agent.max_tokens == 4096
    assert agent._max_tokens_before_length_retry is None


def test_unset_budget_uses_a_concrete_floor(agent):
    agent.max_tokens = None
    _retry(agent, "length")
    assert agent.max_tokens == ter._LENGTH_RETRY_FLOOR * 2
    ter.restore_turn_max_tokens(agent)
    assert agent.max_tokens is None, "an unset budget must stay unset after the turn"
