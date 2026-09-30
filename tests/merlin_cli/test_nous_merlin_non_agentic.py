"""Tests for the Nous-Merlin-3/4 non-agentic warning detector.

Prior to this check, the warning fired on any model whose name contained
``"merlin"`` anywhere (case-insensitive). That false-positived on unrelated
local Modelfiles such as ``merlin-brain:qwen3-14b-ctx16k`` — a tool-capable
Qwen3 wrapper that happens to live under the "merlin" tag namespace.

``is_nous_merlin_non_agentic`` should only match the actual Nous Research
Merlin-3 / Merlin-4 chat family.
"""

from __future__ import annotations

import pytest

from merlin_cli.model_switch import (
    _MERLIN_MODEL_WARNING,
    _check_merlin_model_warning,
    is_nous_merlin_non_agentic,
)


@pytest.mark.parametrize(
    "model_name",
    [
        "NousResearch/Merlin-3-Llama-3.1-70B",
        "NousResearch/Merlin-3-Llama-3.1-405B",
        "merlin-3",
        "Merlin-3",
        "merlin-4",
        "merlin-4-405b",
        "merlin_4_70b",
        "openrouter/merlin3:70b",
        "openrouter/nousresearch/merlin-4-405b",
        "NousResearch/Merlin3",
        "merlin-3.1",
    ],
)
def test_matches_real_nous_merlin_chat_models(model_name: str) -> None:
    assert is_nous_merlin_non_agentic(model_name), (
        f"expected {model_name!r} to be flagged as Nous Merlin 3/4"
    )
    assert _check_merlin_model_warning(model_name) == _MERLIN_MODEL_WARNING


