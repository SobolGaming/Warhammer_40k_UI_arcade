"""Stable command, overlay, and planned-setting registries for UI preferences."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type RegistryStatus = Literal["active", "planned"]


@dataclass(frozen=True, slots=True)
class CommandDefinition:
    """A UI-local command that preferences may bind to input."""

    command_id: str
    label: str
    status: RegistryStatus


@dataclass(frozen=True, slots=True)
class OverlayDefinition:
    """A viewer-scoped advisory overlay that preferences may enable or toggle."""

    overlay_id: str
    label: str
    status: RegistryStatus


@dataclass(frozen=True, slots=True)
class PlannedSettingDefinition:
    """Recognized future-facing setting accepted for round-trip preservation."""

    setting_id: str
    label: str
    status: RegistryStatus = "planned"


def command_registry() -> dict[str, CommandDefinition]:
    """Return known UI command IDs."""

    return {
        "toggle_overlay": CommandDefinition(
            command_id="toggle_overlay",
            label="Toggle selected overlay",
            status="active",
        ),
        "open_selected_unit_actions": CommandDefinition(
            command_id="open_selected_unit_actions",
            label="Open selected-unit action menu",
            status="active",
        ),
        "toggle_measure_mode": CommandDefinition(
            command_id="toggle_measure_mode",
            label="Toggle measure mode",
            status="active",
        ),
        "confirm": CommandDefinition(
            command_id="confirm",
            label="Confirm local UI action",
            status="active",
        ),
        "cancel": CommandDefinition(
            command_id="cancel",
            label="Cancel local UI state",
            status="active",
        ),
        "cycle_selection": CommandDefinition(
            command_id="cycle_selection",
            label="Cycle selectable units or models",
            status="active",
        ),
        "add_entity_selection": CommandDefinition(
            command_id="add_entity_selection",
            label="Add entity to request selection",
            status="active",
        ),
        "subtract_entity_selection": CommandDefinition(
            command_id="subtract_entity_selection",
            label="Remove entity from request selection",
            status="active",
        ),
        "toggle_entity_selection": CommandDefinition(
            command_id="toggle_entity_selection",
            label="Toggle request-scoped entity selection",
            status="active",
        ),
        "cycle_entity_layer": CommandDefinition(
            command_id="cycle_entity_layer",
            label="Cycle active request-selection layer",
            status="active",
        ),
        "select_current_entity_group": CommandDefinition(
            command_id="select_current_entity_group",
            label="Select current entity group",
            status="active",
        ),
        "toggle_action_summary": CommandDefinition(
            command_id="toggle_action_summary",
            label="Toggle current action visual summary",
            status="active",
        ),
        "review_action_summary": CommandDefinition(
            command_id="review_action_summary",
            label="Toggle bright review mode for the current action summary",
            status="active",
        ),
    }


def overlay_registry() -> dict[str, OverlayDefinition]:
    """Return known advisory overlay IDs."""

    return {
        "selected_model": OverlayDefinition(
            overlay_id="selected_model",
            label="Selected model highlight",
            status="active",
        ),
        "selected_unit": OverlayDefinition(
            overlay_id="selected_unit",
            label="Selected unit highlight",
            status="active",
        ),
        "debug_coordinates": OverlayDefinition(
            overlay_id="debug_coordinates",
            label="Debug coordinate display",
            status="active",
        ),
        "movement_budget": OverlayDefinition(
            overlay_id="movement_budget",
            label="Movement budget overlay",
            status="active",
        ),
        "movement_path_draft": OverlayDefinition(
            overlay_id="movement_path_draft",
            label="Movement path draft overlay",
            status="active",
        ),
        "objective_control_context": OverlayDefinition(
            overlay_id="objective_control_context",
            label="Objective control context overlay",
            status="planned",
        ),
        "engagement_range": OverlayDefinition(
            overlay_id="engagement_range",
            label="Engagement range overlay",
            status="planned",
        ),
        "coherency": OverlayDefinition(
            overlay_id="coherency",
            label="Unit coherency overlay",
            status="planned",
        ),
        "line_of_sight": OverlayDefinition(
            overlay_id="line_of_sight",
            label="Line-of-sight overlay",
            status="planned",
        ),
        "cover": OverlayDefinition(
            overlay_id="cover",
            label="Cover overlay",
            status="planned",
        ),
    }


def planned_setting_registry() -> dict[str, PlannedSettingDefinition]:
    """Return recognized future-facing preference properties."""

    return {
        "hud.minimap_enabled": PlannedSettingDefinition(
            setting_id="hud.minimap_enabled",
            label="HUD minimap toggle",
        ),
        "input.keyboard_first_mode": PlannedSettingDefinition(
            setting_id="input.keyboard_first_mode",
            label="Keyboard-first workflow mode",
        ),
        "movement.auto_path_preview": PlannedSettingDefinition(
            setting_id="movement.auto_path_preview",
            label="Automatic movement path preview",
        ),
        "render.cached_text_objects": PlannedSettingDefinition(
            setting_id="render.cached_text_objects",
            label="Cached Arcade text objects",
        ),
        "selection.history_limit": PlannedSettingDefinition(
            setting_id="selection.history_limit",
            label="Selection history limit",
        ),
    }
