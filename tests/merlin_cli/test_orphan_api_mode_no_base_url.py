"""A persisted ``model.api_mode`` with no ``model.base_url`` must not leak across providers.

Regression: a removed custom relay left ``api_mode: codex_responses`` behind in the ``model:``
block (its ``base_url``/``api_key`` were scrubbed, the mode was not). The ladder honoured that
orphan for every provider picked afterwards, so z.ai/GLM turns were posted to
``https://api.z.ai/api/paas/v4/responses`` and 404'd on all three retries — the route's own
derivation said ``chat_completions`` all along.
"""

import pytest

from merlin_cli.runtime_provider import (
    _configured_api_mode,
    _configured_or_fallback_api_mode,
    _fallback_api_mode,
)

ZAI_BASE = "https://api.z.ai/api/paas/v4"
DEEPSEEK_BASE = "https://api.deepseek.com/v1"
OPENAI_BASE = "https://api.openai.com/v1"


@pytest.mark.parametrize(
    "provider, base_url, model",
    [
        ("zai", ZAI_BASE, "glm-5.3-flash"),
        ("zai", "https://api.z.ai/api/coding/paas/v4", "glm-5.3-flash"),
        ("deepseek", DEEPSEEK_BASE, "deepseek-flash"),
        ("openrouter", "https://openrouter.ai/api/v1", "deepseek/deepseek-v4-pro"),
    ],
)
def test_orphan_codex_responses_is_ignored(provider, base_url, model):
    """``codex_responses`` without a base_url is residue — the route decides the wire."""
    model_cfg = {"default": "gemini-2.5-pro", "api_mode": "codex_responses"}

    assert _configured_api_mode(provider, model_cfg) is None
    assert _configured_or_fallback_api_mode(
        provider, model_cfg, base_url, model, opencode_by_model=True
    ) == "chat_completions"


def test_orphan_mode_still_resolves_responses_for_openai_route():
    """Dropping the orphan must not lose Responses where the endpoint actually mandates it."""
    model_cfg = {"default": "gpt-5.5", "api_mode": "codex_responses"}

    assert _configured_api_mode("openai", model_cfg) is None
    assert _configured_or_fallback_api_mode(
        "openai", model_cfg, OPENAI_BASE, "gpt-5.5", opencode_by_model=True
    ) == "codex_responses"


def test_attributable_codex_responses_is_kept():
    """A mode that says WHERE the wire belongs stays authoritative (custom relay behind base_url)."""
    model_cfg = {
        "default": "clario/gpt-6-sol",
        "provider": "clario",
        "base_url": "https://clariohub.id/v1",
        "api_mode": "codex_responses",
    }

    assert _configured_api_mode("clario", model_cfg) == "codex_responses"
    assert _configured_or_fallback_api_mode(
        "clario", model_cfg, "https://clariohub.id/v1", "clario/gpt-6-sol", opencode_by_model=True
    ) == "codex_responses"


def test_chat_completions_without_base_url_is_unaffected():
    """Only the Responses-mode orphan is rejected; other persisted modes keep working."""
    model_cfg = {"default": "some-model", "api_mode": "chat_completions"}

    assert _configured_api_mode("zai", model_cfg) == "chat_completions"


def test_fallback_is_chat_completions_for_zai_hosts():
    """Ground truth: z.ai serves /chat/completions only (a /responses POST is 404 there)."""
    assert _fallback_api_mode("zai", ZAI_BASE, "glm-5.3-flash") == "chat_completions"
