"""Migration 50→51: display.compact flips to true and display.skin to solarized.

Contract: a saved value still equal to the OLD default (compact: false, skin: default) is the
template seeder copied, not a choice — the key is dropped so config.yaml follows the new default.
Any OTHER saved value is a user choice and survives untouched. Driven through ``run_migrations``
against a temp home; the end-to-end path (``migrate_config`` including the version re-stamp) gets
its own test because that is the path ``merlin update`` actually takes.
"""

import os
from unittest.mock import patch

import merlin_yaml as yaml


def _write_config(tmp_path, config: dict) -> None:
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")


def _run_migrations(tmp_path, current_ver: int) -> dict:
    from merlin_cli.config_migrations import run_migrations

    results = {"env_added": [], "config_added": [], "warnings": []}
    with patch.dict(os.environ, {"MERLIN_HOME": str(tmp_path)}, clear=False):
        run_migrations(current_ver, results, quiet=True)
    return results


def _raw_display(tmp_path) -> dict:
    return yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8")).get("display", {})


def _merged_display(tmp_path) -> dict:
    from merlin_cli.config import load_config

    with patch.dict(os.environ, {"MERLIN_HOME": str(tmp_path)}):
        merged = load_config()
    return merged["display"]


def test_old_default_pins_are_dropped_and_follow_the_new_default(tmp_path):
    _write_config(tmp_path, {"_config_version": 50, "display": {"skin": "default", "compact": False}})
    _run_migrations(tmp_path, 50)

    raw = _raw_display(tmp_path)
    assert "compact" not in raw, "the old default is the template copied, not a choice"
    assert "skin" not in raw

    merged = _merged_display(tmp_path)
    assert merged["compact"] is True
    assert merged["skin"] == "solarized"


def test_user_choices_are_never_rewritten(tmp_path):
    _write_config(tmp_path, {"_config_version": 50, "display": {"skin": "grimoire", "compact": True, "language": "ja"}})
    _run_migrations(tmp_path, 50)

    raw = _raw_display(tmp_path)
    assert raw["skin"] == "grimoire"
    assert raw["compact"] is True
    assert raw["language"] == "ja"


def test_missing_display_section_is_a_no_op(tmp_path):
    _write_config(tmp_path, {"_config_version": 50})
    _run_migrations(tmp_path, 50)

    raw = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert "display" not in raw or not raw["display"], "a missing section must NOT be created"


def test_end_to_end_migrate_config_re_stamps_and_resolves_new_defaults(tmp_path):
    """The `merlin update` path: full migrate_config on a stamped v50 file with old-default pins."""
    from merlin_cli.config import migrate_config

    _write_config(tmp_path, {"_config_version": 50, "display": {"skin": "default", "compact": False}})
    with patch.dict(os.environ, {"MERLIN_HOME": str(tmp_path)}, clear=False):
        migrate_config(interactive=False, quiet=True)

    stamp = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))["_config_version"]
    assert stamp == 51, "the update path re-stamps the config to the latest schema version"

    merged = _merged_display(tmp_path)
    assert merged["skin"] == "solarized" and merged["compact"] is True


def test_cli_config_defaults_table_follows_default_config(tmp_path):
    """The CLI/TUI runtime reads cli._cli_config_defaults(), a SECOND defaults table; its
    display section must derive from DEFAULT_CONFIG, not diverge (634a2e66 flipped only the
    merlin_cli.config table and `merlin --tui` kept the old FULL banner while `merlin config`
    reported the new one)."""
    os.environ["MERLIN_IGNORE_USER_CONFIG"] = "1"
    try:
        from merlin_cli.cli_config_load import load_cli_config
        from merlin_cli.config_defaults import DEFAULT_CONFIG

        cfg = load_cli_config()
        assert cfg["display"]["compact"] == DEFAULT_CONFIG["display"]["compact"]
        assert cfg["display"]["skin"] == DEFAULT_CONFIG["display"]["skin"]
    finally:
        os.environ.pop("MERLIN_IGNORE_USER_CONFIG", None)


def test_solarized_is_a_builtin_skin():
    """The global default skin must resolve on machines WITHOUT ~/.merlin/skins/solarized.yaml."""
    import merlin_cli.skin_engine as se

    assert "solarized" in se._BUILTIN_SKINS
    skin = se.load_skin("solarized")
    assert skin.branding.get("prompt_symbol") == "ᛟ cast"


def test_already_current_config_survives_byte_identical(tmp_path):
    """A v51 config (post-flip machines) must not be touched by re-running the ladder."""
    _write_config(tmp_path, {"_config_version": 51, "display": {"skin": "default", "compact": False}})
    before = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    _run_migrations(tmp_path, 51)
    after = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert before == after