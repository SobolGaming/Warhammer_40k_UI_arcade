"""Shareable UI preferences framework."""

from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.preferences.diagnostics import PreferenceDiagnostic, Severity
from warhammer40k_arcade_ui.preferences.io import (
    PreferenceFormat,
    PreferencesLoadResult,
    default_preferences_path,
    export_preferences,
    load_preferences,
    load_preferences_from_text,
    write_preferences,
)
from warhammer40k_arcade_ui.preferences.registries import (
    CommandDefinition,
    OverlayDefinition,
    PlannedSettingDefinition,
    command_registry,
    overlay_registry,
    planned_setting_registry,
)
from warhammer40k_arcade_ui.preferences.schema import (
    ExperimentalPreferenceFlags,
    HotkeyBinding,
    HudPreferences,
    OverlayPreferences,
    SelectionBehaviorPreferences,
    UiPreferences,
    parse_preferences_payload,
)

__all__ = [
    "CommandDefinition",
    "ExperimentalPreferenceFlags",
    "HotkeyBinding",
    "HudPreferences",
    "OverlayDefinition",
    "OverlayPreferences",
    "PlannedSettingDefinition",
    "PreferenceDiagnostic",
    "PreferenceFormat",
    "PreferencesLoadResult",
    "SelectionBehaviorPreferences",
    "Severity",
    "UiPreferences",
    "command_registry",
    "default_preferences",
    "default_preferences_path",
    "export_preferences",
    "load_preferences",
    "load_preferences_from_text",
    "overlay_registry",
    "parse_preferences_payload",
    "planned_setting_registry",
    "write_preferences",
]
