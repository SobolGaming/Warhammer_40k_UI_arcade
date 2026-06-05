"""Built-in shareable UI preference profiles."""

from __future__ import annotations

from warhammer40k_arcade_ui.preferences.schema import (
    SCHEMA_VERSION,
    ExperimentalPreferenceFlags,
    HotkeyBinding,
    HudPreferences,
    OverlayPreferences,
    SelectionBehaviorPreferences,
    UiPreferences,
)


def default_preferences() -> UiPreferences:
    """Return the complete built-in default preference profile."""

    return UiPreferences(
        schema_version=SCHEMA_VERSION,
        profile_name="default",
        overlays=OverlayPreferences(
            default_on_model_selection=("selected_model",),
            default_on_unit_selection=("selected_unit",),
            default_on_movement_draft=("movement_path_draft", "movement_budget"),
            enabled_by_default=("debug_coordinates",),
        ),
        hotkeys=(
            HotkeyBinding(command_id="cancel", key="escape"),
            HotkeyBinding(command_id="confirm", key="enter"),
            HotkeyBinding(command_id="cycle_selection", key="tab"),
            HotkeyBinding(command_id="show_selected_unit", key="u"),
            HotkeyBinding(command_id="show_selected_model", key="m"),
            HotkeyBinding(command_id="open_selected_unit_actions", key="space"),
            HotkeyBinding(command_id="cycle_entity_layer", key="l"),
            HotkeyBinding(command_id="select_current_entity_group", key="g"),
            HotkeyBinding(command_id="add_entity_selection", key="a", modifiers=("shift",)),
            HotkeyBinding(command_id="subtract_entity_selection", key="s", modifiers=("shift",)),
            HotkeyBinding(command_id="toggle_entity_selection", key="t", modifiers=("shift",)),
            HotkeyBinding(command_id="toggle_overlay", key="b", overlay_id="movement_budget"),
            HotkeyBinding(command_id="toggle_measure_mode", key="r"),
            HotkeyBinding(command_id="toggle_debug_inspector", key="d", modifiers=("ctrl",)),
        ),
        selection=SelectionBehaviorPreferences(
            default_mouse_button="left",
            cycle_overlapping_bases=True,
            show_debug_inspector=False,
        ),
        hud=HudPreferences(
            show_phase=True,
            show_active_player=True,
            show_event_log=True,
            show_config_diagnostics=True,
            show_selected_model_panel=True,
            show_selected_unit_panel=True,
            show_assignment_hud=True,
            assignment_hud_mode="compact",
            show_assignment_warning_markers=True,
            show_chain_breadcrumbs=True,
            text_scale=1.0,
            high_contrast=False,
        ),
        experimental=ExperimentalPreferenceFlags(
            planned_settings={},
            extensions={},
        ),
    )


def dense_debug_preferences() -> UiPreferences:
    """Return a dense/debug profile useful for development."""

    base = default_preferences()
    return UiPreferences(
        schema_version=base.schema_version,
        profile_name="dense-debug",
        overlays=OverlayPreferences(
            default_on_model_selection=("selected_model", "coherency", "engagement_range"),
            default_on_unit_selection=("selected_unit", "objective_control_context", "cover"),
            default_on_movement_draft=(
                "movement_path_draft",
                "movement_budget",
                "coherency",
            ),
            enabled_by_default=("debug_coordinates",),
        ),
        hotkeys=base.hotkeys,
        selection=SelectionBehaviorPreferences(
            default_mouse_button="left",
            cycle_overlapping_bases=True,
            show_debug_inspector=True,
        ),
        hud=HudPreferences(
            show_phase=True,
            show_active_player=True,
            show_event_log=True,
            show_config_diagnostics=True,
            show_selected_model_panel=True,
            show_selected_unit_panel=True,
            show_assignment_hud=True,
            assignment_hud_mode="detailed",
            show_assignment_warning_markers=True,
            show_chain_breadcrumbs=True,
            text_scale=0.9,
            high_contrast=True,
        ),
        experimental=ExperimentalPreferenceFlags(
            planned_settings={
                "hud.minimap_enabled": True,
                "render.cached_text_objects": True,
            },
            extensions={},
        ),
    )


def keyboard_heavy_preferences() -> UiPreferences:
    """Return a keyboard-heavy profile useful for command workflow experiments."""

    base = default_preferences()
    return UiPreferences(
        schema_version=base.schema_version,
        profile_name="keyboard-heavy",
        overlays=base.overlays,
        hotkeys=(
            HotkeyBinding(command_id="cancel", key="escape"),
            HotkeyBinding(command_id="confirm", key="enter"),
            HotkeyBinding(command_id="cycle_selection", key="tab"),
            HotkeyBinding(command_id="show_selected_unit", key="i"),
            HotkeyBinding(command_id="show_selected_model", key="i", modifiers=("shift",)),
            HotkeyBinding(command_id="open_selected_unit_actions", key="space"),
            HotkeyBinding(command_id="cycle_entity_layer", key="l"),
            HotkeyBinding(command_id="select_current_entity_group", key="g"),
            HotkeyBinding(command_id="add_entity_selection", key="a", modifiers=("shift",)),
            HotkeyBinding(command_id="subtract_entity_selection", key="s", modifiers=("shift",)),
            HotkeyBinding(command_id="toggle_entity_selection", key="t", modifiers=("shift",)),
            HotkeyBinding(command_id="toggle_overlay", key="1", overlay_id="movement_budget"),
            HotkeyBinding(command_id="toggle_overlay", key="2", overlay_id="movement_path_draft"),
            HotkeyBinding(
                command_id="toggle_overlay", key="3", overlay_id="objective_control_context"
            ),
            HotkeyBinding(command_id="toggle_measure_mode", key="r"),
            HotkeyBinding(command_id="toggle_debug_inspector", key="d", modifiers=("ctrl",)),
        ),
        selection=base.selection,
        hud=base.hud,
        experimental=ExperimentalPreferenceFlags(
            planned_settings={
                "input.keyboard_first_mode": True,
            },
            extensions={},
        ),
    )
