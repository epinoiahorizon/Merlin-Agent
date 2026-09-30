"""The Atlas picker row never starts a pricing fetch: the picker only uses the ids the Portal
unions append, and a cold pricing cache must not hold the picker open (salvage of #102099)."""

import merlin_cli.models_pricing as mp
from merlin_cli import model_switch_providers as msp


def test_atlas_picker_model_ids_reads_pricing_cache_only(monkeypatch):
    seen: list[bool] = []

    def fake_pricing(provider, *, force_refresh=False, cached_only=False):
        seen.append(cached_only)
        return {}

    monkeypatch.setattr(mp, "get_pricing_for_provider", fake_pricing)
    # Keep the sibling Portal calls off the network; only the pricing call shape is under test.
    monkeypatch.setattr("merlin_cli.models.check_atlas_free_tier", lambda **kw: False)
    monkeypatch.setattr("merlin_cli.models.fetch_atlas_recommended_models", lambda *a, **kw: None)
    monkeypatch.setattr(mp, "atlas_policy_allowed_ids", lambda **kw: None)

    assert msp._atlas_picker_model_ids({"atlas": ["atlas/a"]}, False) == ["atlas/a"]
    assert seen == [True]
