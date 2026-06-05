"""Typed schemas and validation for shareable UI preferences."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast

from warhammer40k_arcade_ui.preferences.diagnostics import PreferenceDiagnostic, Severity
from warhammer40k_arcade_ui.preferences.registries import (
    command_registry,
    overlay_registry,
    planned_setting_registry,
)

SCHEMA_VERSION = "1"

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]
type AssignmentHudMode = Literal["compact", "detailed"]

_VALID_MODIFIERS = frozenset(("ctrl", "alt", "shift", "meta"))
_VALID_MOUSE_BUTTONS = frozenset(("left", "right", "middle"))
_VALID_ASSIGNMENT_HUD_MODES: frozenset[AssignmentHudMode] = frozenset(("compact", "detailed"))
_VALID_NAMED_KEYS = frozenset(
    (
        "escape",
        "enter",
        "tab",
        "space",
        "backspace",
        "delete",
        "up",
        "down",
        "left",
        "right",
        "pageup",
        "pagedown",
        "home",
        "end",
    )
)
_TOP_LEVEL_KEYS = frozenset(
    (
        "schema_version",
        "profile_name",
        "overlays",
        "hotkeys",
        "selection",
        "hud",
        "experimental",
        "extensions",
    )
)


@dataclass(frozen=True, slots=True)
class OverlayPreferences:
    """Overlay defaults controlled by a preference profile."""

    default_on_model_selection: tuple[str, ...]
    default_on_unit_selection: tuple[str, ...]
    default_on_movement_draft: tuple[str, ...]
    enabled_by_default: tuple[str, ...]

    def to_payload(self) -> JsonObject:
        """Convert to deterministic JSON-safe payload."""

        return {
            "default_on_model_selection": list(self.default_on_model_selection),
            "default_on_unit_selection": list(self.default_on_unit_selection),
            "default_on_movement_draft": list(self.default_on_movement_draft),
            "enabled_by_default": list(self.enabled_by_default),
        }


@dataclass(frozen=True, slots=True)
class HotkeyBinding:
    """A local input binding for a registered UI command."""

    command_id: str
    key: str
    modifiers: tuple[str, ...] = ()
    overlay_id: str | None = None

    @property
    def normalized_input(self) -> tuple[tuple[str, ...], str]:
        """Return a stable input identity for duplicate detection."""

        return (tuple(sorted(self.modifiers)), self.key.lower())

    def to_payload(self) -> JsonObject:
        """Convert to deterministic JSON-safe payload."""

        payload: JsonObject = {
            "command_id": self.command_id,
            "key": self.key,
            "modifiers": list(self.modifiers),
        }
        if self.overlay_id is not None:
            payload["overlay_id"] = self.overlay_id
        return payload


@dataclass(frozen=True, slots=True)
class SelectionBehaviorPreferences:
    """Local selection behavior defaults."""

    default_mouse_button: str
    cycle_overlapping_bases: bool
    show_debug_inspector: bool

    def to_payload(self) -> JsonObject:
        """Convert to deterministic JSON-safe payload."""

        return {
            "default_mouse_button": self.default_mouse_button,
            "cycle_overlapping_bases": self.cycle_overlapping_bases,
            "show_debug_inspector": self.show_debug_inspector,
        }


@dataclass(frozen=True, slots=True)
class HudPreferences:
    """HUD display defaults."""

    show_phase: bool
    show_active_player: bool
    show_event_log: bool
    show_config_diagnostics: bool
    show_selected_model_panel: bool
    show_selected_unit_panel: bool
    show_assignment_hud: bool
    assignment_hud_mode: AssignmentHudMode
    show_assignment_warning_markers: bool
    show_chain_breadcrumbs: bool
    text_scale: float
    high_contrast: bool

    def to_payload(self) -> JsonObject:
        """Convert to deterministic JSON-safe payload."""

        return {
            "show_phase": self.show_phase,
            "show_active_player": self.show_active_player,
            "show_event_log": self.show_event_log,
            "show_config_diagnostics": self.show_config_diagnostics,
            "show_selected_model_panel": self.show_selected_model_panel,
            "show_selected_unit_panel": self.show_selected_unit_panel,
            "show_assignment_hud": self.show_assignment_hud,
            "assignment_hud_mode": self.assignment_hud_mode,
            "show_assignment_warning_markers": self.show_assignment_warning_markers,
            "show_chain_breadcrumbs": self.show_chain_breadcrumbs,
            "text_scale": self.text_scale,
            "high_contrast": self.high_contrast,
        }


@dataclass(frozen=True, slots=True)
class ExperimentalPreferenceFlags:
    """Recognized future-facing settings and explicit extension payloads."""

    planned_settings: JsonObject
    extensions: JsonObject

    def to_payload(self) -> JsonObject:
        """Convert to deterministic JSON-safe payload."""

        return {
            "planned_settings": _copy_json_object(self.planned_settings),
        }


@dataclass(frozen=True, slots=True)
class UiPreferences:
    """Complete shareable UI preferences profile."""

    schema_version: str
    profile_name: str
    overlays: OverlayPreferences
    hotkeys: tuple[HotkeyBinding, ...]
    selection: SelectionBehaviorPreferences
    hud: HudPreferences
    experimental: ExperimentalPreferenceFlags

    def to_payload(self) -> JsonObject:
        """Convert to deterministic JSON-safe payload with stable field order."""

        return {
            "schema_version": self.schema_version,
            "profile_name": self.profile_name,
            "overlays": self.overlays.to_payload(),
            "hotkeys": [binding.to_payload() for binding in self.hotkeys],
            "selection": self.selection.to_payload(),
            "hud": self.hud.to_payload(),
            "experimental": self.experimental.to_payload(),
            "extensions": _copy_json_object(self.experimental.extensions),
        }


@dataclass(frozen=True, slots=True)
class PreferencesValidationResult:
    """Validated preferences plus typed diagnostics."""

    preferences: UiPreferences | None
    diagnostics: tuple[PreferenceDiagnostic, ...]

    @property
    def has_errors(self) -> bool:
        """Return whether validation produced any error diagnostics."""

        return any(diagnostic.severity == "error" for diagnostic in self.diagnostics)


def parse_preferences_payload(payload: object) -> PreferencesValidationResult:
    """Parse a JSON/YAML payload into typed preferences and diagnostics."""

    diagnostics: list[PreferenceDiagnostic] = []
    if type(payload) is not dict:
        return PreferencesValidationResult(
            preferences=None,
            diagnostics=(
                _diagnostic(
                    severity="error",
                    code="invalid_document",
                    field="$",
                    message="Preference document must be an object.",
                ),
            ),
        )
    document = cast(dict[str, object], payload)
    _diagnose_unknown_keys(document, _TOP_LEVEL_KEYS, "$", diagnostics)
    schema_version = _required_string(document, "schema_version", diagnostics)
    if schema_version != SCHEMA_VERSION:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="unsupported_schema_version",
                field="schema_version",
                message=f"Unsupported preference schema version: {schema_version!r}.",
                value=schema_version,
            )
        )
    profile_name = _required_string(document, "profile_name", diagnostics)
    overlays = _parse_overlays(document.get("overlays"), diagnostics)
    hotkeys = _parse_hotkeys(document.get("hotkeys"), diagnostics)
    selection = _parse_selection(document.get("selection"), diagnostics)
    hud = _parse_hud(document.get("hud"), diagnostics)
    experimental = _parse_experimental(
        payload=document.get("experimental"),
        extensions=document.get("extensions"),
        diagnostics=diagnostics,
    )
    if schema_version != SCHEMA_VERSION:
        preferences = None
    else:
        preferences = UiPreferences(
            schema_version=schema_version,
            profile_name=profile_name,
            overlays=overlays,
            hotkeys=hotkeys,
            selection=selection,
            hud=hud,
            experimental=experimental,
        )
    return PreferencesValidationResult(
        preferences=preferences,
        diagnostics=tuple(diagnostics),
    )


def _parse_overlays(payload: object, diagnostics: list[PreferenceDiagnostic]) -> OverlayPreferences:
    section = _object_section(payload, "overlays", diagnostics)
    _diagnose_unknown_keys(
        section,
        frozenset(
            (
                "default_on_model_selection",
                "default_on_unit_selection",
                "default_on_movement_draft",
                "enabled_by_default",
            )
        ),
        "overlays",
        diagnostics,
    )
    return OverlayPreferences(
        default_on_model_selection=_overlay_id_list(
            section,
            "default_on_model_selection",
            "overlays.default_on_model_selection",
            diagnostics,
        ),
        default_on_unit_selection=_overlay_id_list(
            section,
            "default_on_unit_selection",
            "overlays.default_on_unit_selection",
            diagnostics,
        ),
        default_on_movement_draft=_overlay_id_list(
            section,
            "default_on_movement_draft",
            "overlays.default_on_movement_draft",
            diagnostics,
        ),
        enabled_by_default=_overlay_id_list(
            section,
            "enabled_by_default",
            "overlays.enabled_by_default",
            diagnostics,
        ),
    )


def _parse_hotkeys(
    payload: object, diagnostics: list[PreferenceDiagnostic]
) -> tuple[HotkeyBinding, ...]:
    if type(payload) is not list:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_hotkeys",
                field="hotkeys",
                message="hotkeys must be a list.",
            )
        )
        return ()
    bindings: list[HotkeyBinding] = []
    seen_inputs: dict[tuple[tuple[str, ...], str], str] = {}
    commands = command_registry()
    overlays = overlay_registry()
    for index, raw_binding in enumerate(cast(list[object], payload)):
        field = f"hotkeys[{index}]"
        if type(raw_binding) is not dict:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="invalid_hotkey",
                    field=field,
                    message="Hotkey binding must be an object.",
                )
            )
            continue
        binding_payload = cast(dict[str, object], raw_binding)
        _diagnose_unknown_keys(
            binding_payload,
            frozenset(("command_id", "key", "modifiers", "overlay_id")),
            field,
            diagnostics,
        )
        command_id = _required_string(binding_payload, "command_id", diagnostics, field)
        key = _normalize_key(
            _required_string(binding_payload, "key", diagnostics, field), field, diagnostics
        )
        modifiers = _modifier_list(
            binding_payload.get("modifiers"), f"{field}.modifiers", diagnostics
        )
        overlay_id = _optional_string(binding_payload, "overlay_id", diagnostics, field)
        command = commands.get(command_id)
        if command is None:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="unknown_command_id",
                    field=f"{field}.command_id",
                    message=f"Unknown command id: {command_id}.",
                    value=command_id,
                )
            )
        elif command.status == "planned":
            diagnostics.append(_inactive_diagnostic(f"{field}.command_id", command_id))
        if overlay_id is not None:
            overlay = overlays.get(overlay_id)
            if overlay is None:
                diagnostics.append(
                    _diagnostic(
                        severity="error",
                        code="unknown_overlay_id",
                        field=f"{field}.overlay_id",
                        message=f"Unknown overlay id: {overlay_id}.",
                        value=overlay_id,
                    )
                )
            elif overlay.status == "planned":
                diagnostics.append(_inactive_diagnostic(f"{field}.overlay_id", overlay_id))
        binding = HotkeyBinding(
            command_id=command_id,
            key=key,
            modifiers=modifiers,
            overlay_id=overlay_id,
        )
        input_identity = binding.normalized_input
        existing_command = seen_inputs.get(input_identity)
        if existing_command is not None:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="duplicate_hotkey",
                    field=field,
                    message=(
                        f"Hotkey {binding.key} with modifiers {list(binding.modifiers)} "
                        f"is already bound to {existing_command}."
                    ),
                    value=binding.key,
                )
            )
        else:
            seen_inputs[input_identity] = command_id
        bindings.append(binding)
    return tuple(bindings)


def _parse_selection(
    payload: object,
    diagnostics: list[PreferenceDiagnostic],
) -> SelectionBehaviorPreferences:
    section = _object_section(payload, "selection", diagnostics)
    _diagnose_unknown_keys(
        section,
        frozenset(("default_mouse_button", "cycle_overlapping_bases", "show_debug_inspector")),
        "selection",
        diagnostics,
    )
    default_mouse_button = _required_string(
        section, "default_mouse_button", diagnostics, "selection"
    )
    if default_mouse_button not in _VALID_MOUSE_BUTTONS:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_mouse_button",
                field="selection.default_mouse_button",
                message=f"Invalid mouse button: {default_mouse_button}.",
                value=default_mouse_button,
            )
        )
    return SelectionBehaviorPreferences(
        default_mouse_button=default_mouse_button,
        cycle_overlapping_bases=_required_bool(
            section,
            "cycle_overlapping_bases",
            diagnostics,
            "selection",
        ),
        show_debug_inspector=_required_bool(
            section,
            "show_debug_inspector",
            diagnostics,
            "selection",
        ),
    )


def _parse_hud(payload: object, diagnostics: list[PreferenceDiagnostic]) -> HudPreferences:
    section = _object_section(payload, "hud", diagnostics)
    _diagnose_unknown_keys(
        section,
        frozenset(
            (
                "show_phase",
                "show_active_player",
                "show_event_log",
                "show_config_diagnostics",
                "show_selected_model_panel",
                "show_selected_unit_panel",
                "show_assignment_hud",
                "assignment_hud_mode",
                "show_assignment_warning_markers",
                "show_chain_breadcrumbs",
                "text_scale",
                "high_contrast",
            )
        ),
        "hud",
        diagnostics,
    )
    text_scale = _required_float(section, "text_scale", diagnostics, "hud")
    if text_scale < 0.5 or text_scale > 2.0:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_text_scale",
                field="hud.text_scale",
                message="HUD text_scale must be between 0.5 and 2.0.",
                value=str(text_scale),
            )
        )
    return HudPreferences(
        show_phase=_required_bool(section, "show_phase", diagnostics, "hud"),
        show_active_player=_required_bool(section, "show_active_player", diagnostics, "hud"),
        show_event_log=_required_bool(section, "show_event_log", diagnostics, "hud"),
        show_config_diagnostics=_required_bool(
            section,
            "show_config_diagnostics",
            diagnostics,
            "hud",
        ),
        show_selected_model_panel=_required_bool(
            section,
            "show_selected_model_panel",
            diagnostics,
            "hud",
        ),
        show_selected_unit_panel=_required_bool(
            section,
            "show_selected_unit_panel",
            diagnostics,
            "hud",
        ),
        show_assignment_hud=_required_bool(
            section,
            "show_assignment_hud",
            diagnostics,
            "hud",
        ),
        assignment_hud_mode=_assignment_hud_mode(
            section,
            "assignment_hud_mode",
            diagnostics,
            "hud",
        ),
        show_assignment_warning_markers=_required_bool(
            section,
            "show_assignment_warning_markers",
            diagnostics,
            "hud",
        ),
        show_chain_breadcrumbs=_required_bool(
            section,
            "show_chain_breadcrumbs",
            diagnostics,
            "hud",
        ),
        text_scale=text_scale,
        high_contrast=_required_bool(section, "high_contrast", diagnostics, "hud"),
    )


def _parse_experimental(
    *,
    payload: object,
    extensions: object,
    diagnostics: list[PreferenceDiagnostic],
) -> ExperimentalPreferenceFlags:
    section = _object_section(payload, "experimental", diagnostics)
    _diagnose_unknown_keys(section, frozenset(("planned_settings",)), "experimental", diagnostics)
    planned_settings = _json_object_section(
        section.get("planned_settings"),
        "experimental.planned_settings",
        diagnostics,
    )
    planned_registry = planned_setting_registry()
    for setting_id in planned_settings:
        setting = planned_registry.get(setting_id)
        if setting is None:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="unknown_planned_setting",
                    field=f"experimental.planned_settings.{setting_id}",
                    message=f"Unknown planned setting: {setting_id}.",
                    value=setting_id,
                )
            )
        else:
            diagnostics.append(
                _inactive_diagnostic(f"experimental.planned_settings.{setting_id}", setting_id)
            )
    return ExperimentalPreferenceFlags(
        planned_settings=planned_settings,
        extensions=_json_object_section(extensions, "extensions", diagnostics),
    )


def _overlay_id_list(
    section: dict[str, object],
    key: str,
    field: str,
    diagnostics: list[PreferenceDiagnostic],
) -> tuple[str, ...]:
    ids = _string_list(section.get(key), field, diagnostics)
    overlays = overlay_registry()
    for overlay_id in ids:
        overlay = overlays.get(overlay_id)
        if overlay is None:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="unknown_overlay_id",
                    field=field,
                    message=f"Unknown overlay id: {overlay_id}.",
                    value=overlay_id,
                )
            )
        elif overlay.status == "planned":
            diagnostics.append(_inactive_diagnostic(field, overlay_id))
    return ids


def _object_section(
    payload: object,
    field: str,
    diagnostics: list[PreferenceDiagnostic],
) -> dict[str, object]:
    if type(payload) is not dict:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_section",
                field=field,
                message=f"{field} must be an object.",
            )
        )
        return {}
    return cast(dict[str, object], payload)


def _json_object_section(
    payload: object,
    field: str,
    diagnostics: list[PreferenceDiagnostic],
) -> JsonObject:
    if payload is None:
        return {}
    if type(payload) is not dict:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_section",
                field=field,
                message=f"{field} must be an object.",
            )
        )
        return {}
    result: JsonObject = {}
    for key, value in cast(dict[object, object], payload).items():
        if type(key) is not str or not key:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="invalid_key",
                    field=field,
                    message=f"{field} keys must be non-empty strings.",
                )
            )
            continue
        result[key] = _json_safe_value(value, f"{field}.{key}", diagnostics)
    return result


def _required_string(
    payload: dict[str, object],
    key: str,
    diagnostics: list[PreferenceDiagnostic],
    prefix: str = "",
) -> str:
    field = f"{prefix}.{key}" if prefix else key
    value = payload.get(key)
    if type(value) is not str or not value:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_string",
                field=field,
                message=f"{field} must be a non-empty string.",
            )
        )
        return ""
    return value


def _optional_string(
    payload: dict[str, object],
    key: str,
    diagnostics: list[PreferenceDiagnostic],
    prefix: str,
) -> str | None:
    if key not in payload:
        return None
    value = payload[key]
    field = f"{prefix}.{key}"
    if value is None:
        return None
    if type(value) is not str or not value:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_string",
                field=field,
                message=f"{field} must be a non-empty string when present.",
            )
        )
        return None
    return value


def _required_bool(
    payload: dict[str, object],
    key: str,
    diagnostics: list[PreferenceDiagnostic],
    prefix: str,
) -> bool:
    field = f"{prefix}.{key}"
    value = payload.get(key)
    if type(value) is not bool:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_bool",
                field=field,
                message=f"{field} must be a bool.",
            )
        )
        return False
    return value


def _required_float(
    payload: dict[str, object],
    key: str,
    diagnostics: list[PreferenceDiagnostic],
    prefix: str,
) -> float:
    field = f"{prefix}.{key}"
    value = payload.get(key)
    if type(value) is int:
        return float(value)
    if type(value) is float:
        return value
    diagnostics.append(
        _diagnostic(
            severity="error",
            code="invalid_number",
            field=field,
            message=f"{field} must be numeric.",
        )
    )
    return 0.0


def _assignment_hud_mode(
    payload: dict[str, object],
    key: str,
    diagnostics: list[PreferenceDiagnostic],
    prefix: str,
) -> AssignmentHudMode:
    field = f"{prefix}.{key}"
    value = payload.get(key)
    if type(value) is str and value in _VALID_ASSIGNMENT_HUD_MODES:
        return value
    diagnostics.append(
        _diagnostic(
            severity="error",
            code="invalid_assignment_hud_mode",
            field=field,
            message="hud.assignment_hud_mode must be compact or detailed.",
            value=str(value),
        )
    )
    return "compact"


def _string_list(
    payload: object,
    field: str,
    diagnostics: list[PreferenceDiagnostic],
) -> tuple[str, ...]:
    if type(payload) is not list:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_list",
                field=field,
                message=f"{field} must be a list.",
            )
        )
        return ()
    values: list[str] = []
    for index, raw_value in enumerate(cast(list[object], payload)):
        if type(raw_value) is not str or not raw_value:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="invalid_string",
                    field=f"{field}[{index}]",
                    message=f"{field}[{index}] must be a non-empty string.",
                )
            )
            continue
        values.append(raw_value)
    return tuple(values)


def _modifier_list(
    payload: object,
    field: str,
    diagnostics: list[PreferenceDiagnostic],
) -> tuple[str, ...]:
    modifiers = _string_list(payload, field, diagnostics)
    normalized: list[str] = []
    for modifier in modifiers:
        normalized_modifier = modifier.lower()
        if normalized_modifier not in _VALID_MODIFIERS:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="invalid_modifier",
                    field=field,
                    message=f"Invalid modifier: {modifier}.",
                    value=modifier,
                )
            )
            continue
        if normalized_modifier not in normalized:
            normalized.append(normalized_modifier)
    return tuple(normalized)


def _normalize_key(
    key: str,
    field: str,
    diagnostics: list[PreferenceDiagnostic],
) -> str:
    normalized = key.lower()
    if _valid_key(normalized):
        return normalized
    diagnostics.append(
        _diagnostic(
            severity="error",
            code="invalid_key_syntax",
            field=f"{field}.key",
            message=f"Invalid key syntax: {key}.",
            value=key,
        )
    )
    return normalized


def _valid_key(key: str) -> bool:
    return (
        bool(re.fullmatch(r"[a-z0-9]", key))
        or bool(re.fullmatch(r"f(?:[1-9]|1[0-2])", key))
        or key in _VALID_NAMED_KEYS
    )


def _diagnose_unknown_keys(
    payload: Mapping[str, object] | Mapping[object, object],
    known_keys: frozenset[str],
    field: str,
    diagnostics: list[PreferenceDiagnostic],
) -> None:
    for key in payload:
        if type(key) is not str or not key:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="invalid_key",
                    field=field,
                    message=f"{field} keys must be non-empty strings.",
                    value=repr(key),
                )
            )
            continue
        if key not in known_keys:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="unknown_key",
                    field=f"{field}.{key}",
                    message=f"Unknown preference field: {field}.{key}.",
                    value=key,
                )
            )


def _json_safe_value(
    value: object,
    field: str,
    diagnostics: list[PreferenceDiagnostic],
) -> JsonValue:
    if value is None or type(value) in (bool, int, float, str):
        return cast(JsonValue, value)
    if type(value) is list:
        return [_json_safe_value(item, field, diagnostics) for item in cast(list[object], value)]
    if type(value) is dict:
        return _json_object_section(cast(dict[object, object], value), field, diagnostics)
    diagnostics.append(
        _diagnostic(
            severity="error",
            code="invalid_json_value",
            field=field,
            message=f"{field} must be JSON-safe.",
        )
    )
    return None


def _copy_json_object(value: JsonObject) -> JsonObject:
    return {key: _copy_json_value(item) for key, item in value.items()}


def _copy_json_value(value: JsonValue) -> JsonValue:
    if type(value) is list:
        return [_copy_json_value(item) for item in value]
    if type(value) is dict:
        return {key: _copy_json_value(item) for key, item in value.items()}
    return value


def _inactive_diagnostic(field: str, value: str) -> PreferenceDiagnostic:
    return _diagnostic(
        severity="warning",
        code="inactive_planned_setting",
        field=field,
        message=f"{value} is recognized but not active in this build.",
        value=value,
    )


def _diagnostic(
    *,
    severity: Severity,
    code: str,
    field: str,
    message: str,
    value: str | None = None,
) -> PreferenceDiagnostic:
    return PreferenceDiagnostic(
        severity=severity,
        code=code,
        field=field,
        message=message,
        value=value,
    )
