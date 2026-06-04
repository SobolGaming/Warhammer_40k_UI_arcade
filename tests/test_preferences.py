"""Tests for shareable UI preferences."""

from __future__ import annotations

from pathlib import Path

import pytest

import warhammer40k_arcade_ui.preferences.io as preferences_io
from warhammer40k_arcade_ui.preferences import (
    PreferenceDiagnostic,
    default_preferences,
    export_preferences,
    load_preferences,
    load_preferences_from_text,
    parse_preferences_payload,
)
from warhammer40k_arcade_ui.preferences.defaults import (
    dense_debug_preferences,
    keyboard_heavy_preferences,
)
from warhammer40k_arcade_ui.preferences.io import write_preferences


def test_default_profile_exports_deterministic_json_and_yaml() -> None:
    preferences = default_preferences()

    first_json = export_preferences(preferences, "json")
    second_json = export_preferences(preferences, "json")
    first_yaml = export_preferences(preferences, "yaml")
    second_yaml = export_preferences(preferences, "yaml")

    assert first_json == second_json
    assert first_yaml == second_yaml
    assert '"schema_version": "1"' in first_json
    assert first_yaml.startswith("schema_version: '1'\nprofile_name: default\n")


def test_json_and_yaml_profiles_load_through_same_schema() -> None:
    preferences = default_preferences()

    json_result = load_preferences_from_text(
        text=export_preferences(preferences, "json"),
        preference_format="json",
    )
    yaml_result = load_preferences_from_text(
        text=export_preferences(preferences, "yaml"),
        preference_format="yaml",
    )

    assert json_result.preferences is not None
    assert yaml_result.preferences is not None
    assert json_result.preferences.to_payload() == yaml_result.preferences.to_payload()


def test_missing_explicit_file_reports_error_without_defaulting(tmp_path: Path) -> None:
    result = load_preferences(tmp_path / "missing.yaml")

    assert result.preferences is None
    assert result.has_errors is True
    assert _codes(result.diagnostics) == {"preferences_file_missing"}
    assert result.used_builtin_default is False


def test_unsupported_explicit_file_format_reports_diagnostic(tmp_path: Path) -> None:
    path = tmp_path / "ui-preferences.txt"
    path.write_text("{}", encoding="utf-8")

    result = load_preferences(path)

    assert result.preferences is None
    assert _codes(result.diagnostics) == {"preferences_file_format_error"}


def test_load_preferences_without_file_uses_builtin_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        preferences_io,
        "default_preferences_path",
        lambda: tmp_path / "ui-preferences.yaml",
    )

    result = load_preferences()

    assert result.preferences == default_preferences()
    assert result.used_builtin_default is True
    assert result.diagnostics == ()


def test_unknown_command_overlay_and_duplicate_hotkey_emit_diagnostics() -> None:
    payload = default_preferences().to_payload()
    payload["hotkeys"] = [
        {"command_id": "missing_command", "key": "q", "modifiers": []},
        {
            "command_id": "toggle_overlay",
            "key": "q",
            "modifiers": [],
            "overlay_id": "missing_overlay",
        },
    ]
    payload["overlays"] = {
        "default_on_model_selection": ["missing_overlay"],
        "default_on_unit_selection": [],
        "default_on_movement_draft": [],
        "enabled_by_default": [],
    }

    result = parse_preferences_payload(payload)

    assert result.preferences is not None
    assert {
        "unknown_command_id",
        "unknown_overlay_id",
        "duplicate_hotkey",
    }.issubset(_codes(result.diagnostics))


def test_invalid_key_and_modifier_syntax_emit_diagnostics() -> None:
    payload = default_preferences().to_payload()
    payload["hotkeys"] = [
        {"command_id": "cancel", "key": "not a key", "modifiers": ["hyper"]},
    ]

    result = parse_preferences_payload(payload)

    assert result.preferences is not None
    assert {"invalid_key_syntax", "invalid_modifier"}.issubset(_codes(result.diagnostics))


def test_future_facing_settings_round_trip_and_report_inactive() -> None:
    payload = default_preferences().to_payload()
    payload["experimental"] = {
        "planned_settings": {
            "hud.minimap_enabled": True,
            "input.keyboard_first_mode": "enabled",
        }
    }

    result = parse_preferences_payload(payload)

    assert result.preferences is not None
    assert result.preferences.experimental.planned_settings == {
        "hud.minimap_enabled": True,
        "input.keyboard_first_mode": "enabled",
    }
    assert _codes(result.diagnostics).issuperset({"inactive_planned_setting"})


def test_unknown_top_level_key_is_diagnostic_but_extensions_are_preserved() -> None:
    payload = default_preferences().to_payload()
    payload["unknown"] = True
    payload["extensions"] = {"local_notes": {"owner": "alice"}}

    result = parse_preferences_payload(payload)

    assert result.preferences is not None
    assert result.preferences.experimental.extensions == {"local_notes": {"owner": "alice"}}
    assert "unknown_key" in _codes(result.diagnostics)


def test_exported_profile_can_be_written_and_loaded(tmp_path: Path) -> None:
    path = tmp_path / "ui-preferences.yaml"
    preferences = keyboard_heavy_preferences()

    write_preferences(preferences=preferences, path=path)
    result = load_preferences(path)

    assert result.preferences is not None
    assert result.preferences.profile_name == "keyboard-heavy"
    assert result.source_path == path


def test_documented_example_profiles_load() -> None:
    docs_dir = Path(__file__).parents[1] / "docs" / "preferences"
    expected_payloads = {
        "default": default_preferences().to_payload(),
        "dense-debug": dense_debug_preferences().to_payload(),
        "keyboard-heavy": keyboard_heavy_preferences().to_payload(),
    }

    loaded_names: set[str] = set()
    for path in sorted(docs_dir.glob("*.yaml")):
        result = load_preferences(path)
        assert result.preferences is not None
        assert result.preferences.to_payload() == expected_payloads[result.preferences.profile_name]
        loaded_names.add(result.preferences.profile_name)

    assert loaded_names == {"default", "dense-debug", "keyboard-heavy"}


def test_dense_debug_profile_includes_planned_setting_diagnostics() -> None:
    result = parse_preferences_payload(dense_debug_preferences().to_payload())

    assert result.preferences is not None
    assert "inactive_planned_setting" in _codes(result.diagnostics)


def _codes(diagnostics: tuple[PreferenceDiagnostic, ...]) -> set[str]:
    return {diagnostic.code for diagnostic in diagnostics}
