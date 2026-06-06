"""Tests for local selection state and input command mapping."""

from __future__ import annotations

from dataclasses import replace

from warhammer40k_arcade_ui.input.commands import command_for_key
from warhammer40k_arcade_ui.preferences.defaults import default_preferences, dense_debug_preferences
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.render.view_models import (
    BattlefieldView,
    HudView,
    ModelBaseView,
    TableView,
    UnitView,
)
from warhammer40k_arcade_ui.state.selection import SelectionState, model_hits_at


def test_clicking_model_selects_owning_unit_and_active_selection_overlays() -> None:
    view = default_battlefield_view()
    preferences = dense_debug_preferences()
    state = SelectionState.initial(preferences)

    selected = state.select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )

    assert selected.selected_unit_id == "intercessor_squad"
    assert selected.selected_model_id == "intercessor_1"
    assert "selected_model" in selected.active_overlay_ids
    assert "selected_unit" in selected.active_overlay_ids
    assert "coherency" not in selected.active_overlay_ids


def test_model_hit_detection_orders_nearest_base_first() -> None:
    view = _overlapping_view()

    hits = model_hits_at(view=view, world_point=(10.1, 10.0))

    assert [hit.model_id for hit in hits] == ["model_a", "model_b"]


def test_selection_cycles_overlapping_bases_when_preference_allows() -> None:
    view = _overlapping_view()
    preferences = default_preferences()
    state = SelectionState.initial(preferences)

    first = state.select_at(view=view, world_point=(10.1, 10.0), preferences=preferences)
    second = first.select_at(view=view, world_point=(10.1, 10.0), preferences=preferences)

    assert first.selected_model_id == "model_a"
    assert second.selected_model_id == "model_b"


def test_cycle_existing_at_does_not_select_from_hover_only() -> None:
    view = _overlapping_view()
    preferences = default_preferences()
    state = SelectionState.initial(preferences)

    cycled = state.cycle_existing_at(
        view=view,
        world_point=(10.1, 10.0),
        preferences=preferences,
    )

    assert cycled.selected_model_id is None
    assert cycled.selected_unit_id is None


def test_cycle_existing_at_cycles_after_explicit_selection() -> None:
    view = _overlapping_view()
    preferences = default_preferences()
    state = SelectionState.initial(preferences)
    selected = state.select_at(view=view, world_point=(10.1, 10.0), preferences=preferences)

    cycled = selected.cycle_existing_at(
        view=view,
        world_point=(10.1, 10.0),
        preferences=preferences,
    )

    assert cycled.selected_model_id == "model_b"


def test_selection_uses_nearest_base_when_overlap_cycling_is_disabled() -> None:
    view = _overlapping_view()
    base_preferences = default_preferences()
    preferences = replace(
        base_preferences,
        selection=replace(base_preferences.selection, cycle_overlapping_bases=False),
    )
    state = SelectionState.initial(preferences)

    first = state.select_at(view=view, world_point=(10.1, 10.0), preferences=preferences)
    second = first.select_at(view=view, world_point=(10.1, 10.0), preferences=preferences)

    assert first.selected_model_id == "model_a"
    assert second.selected_model_id == "model_a"


def test_hotkeys_are_matched_from_preferences() -> None:
    preferences = default_preferences()

    debug = command_for_key(preferences=preferences, key="d", modifiers=("ctrl",))
    unit_panel = command_for_key(preferences=preferences, key="u")
    summary_toggle = command_for_key(preferences=preferences, key="v")
    summary_review = command_for_key(preferences=preferences, key="v", modifiers=("shift",))

    assert debug is not None
    assert debug.command_id == "toggle_debug_inspector"
    assert unit_panel is not None
    assert unit_panel.command_id == "show_selected_unit"
    assert summary_toggle is not None
    assert summary_toggle.command_id == "toggle_action_summary"
    assert summary_review is not None
    assert summary_review.command_id == "review_action_summary"


def _overlapping_view() -> BattlefieldView:
    return BattlefieldView(
        table=TableView(width=20.0, height=20.0, label="Selection Test Table"),
        deployment_zones=(),
        objectives=(),
        terrain=(),
        units=(
            UnitView(
                unit_id="unit_a",
                player_id="player_1",
                label="Unit A",
                models=(
                    ModelBaseView(
                        model_id="model_a",
                        label="A",
                        position=(10.0, 10.0),
                        base_radius=1.0,
                    ),
                ),
            ),
            UnitView(
                unit_id="unit_b",
                player_id="player_2",
                label="Unit B",
                models=(
                    ModelBaseView(
                        model_id="model_b",
                        label="B",
                        position=(10.4, 10.0),
                        base_radius=1.0,
                    ),
                ),
            ),
        ),
        hud=HudView(
            phase_label="Selection Test",
            active_player_id="player_1",
            pending_decision_summary="No pending decision",
            event_log_lines=("ready",),
        ),
    )
