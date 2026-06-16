"""Tests for the Phase 20 ergonomic HUD summary."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from warhammer40k_arcade_ui.core_client.protocol import UiDecision, UiFiniteOption
from warhammer40k_arcade_ui.hud.composition import load_hud_composition_reference
from warhammer40k_arcade_ui.hud.ergonomics import HudErgonomicsView, build_hud_ergonomics_view
from warhammer40k_arcade_ui.hud.layouts import HudLayoutView, build_hud_layout
from warhammer40k_arcade_ui.hud.runtime_data import runtime_data_for_ergonomic_hud
from warhammer40k_arcade_ui.hud.toolkit_render import render_composition_profile
from warhammer40k_arcade_ui.hud.view_models import (
    build_assignment_hud_panel,
    build_finite_decision_panel,
    build_movement_draft_panel,
    build_placement_draft_panel,
    build_unit_panel,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.preferences.schema import JsonObject
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.render.primitives import (
    PolygonPrimitive,
    RenderPrimitive,
    TextPrimitive,
)
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft
from warhammer40k_arcade_ui.state.placement_draft import PlacementDraft
from warhammer40k_arcade_ui.state.selection import SelectionState


def test_ergonomic_hud_view_summarizes_selected_unit_movement_and_hotkeys() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )
    decision = _movement_proposal_decision()
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=decision,
    )
    assert draft is not None
    draft = draft.add_waypoint(view=view, world_point=(10.0, 18.0)).mark_ready(view=view)

    finite_panel = build_finite_decision_panel(
        pending_decision=decision,
        highlighted_option_index=0,
        status_message="Movement draft ready",
        diagnostics=(),
    )
    movement_panel = build_movement_draft_panel(
        movement_draft=draft,
        pending_decision=decision,
    )
    assignment_panel = build_assignment_hud_panel(
        movement_draft=draft,
        pending_decision=decision,
        highlighted_option_index=0,
        diagnostics=(),
        preferences=preferences,
        preference_source_label="docs/preferences/default.yaml",
        event_log_lines=("movement_proposal_submitted: player_1",),
    )

    ergonomics = build_hud_ergonomics_view(
        view=view,
        preferences=preferences,
        unit_panel=build_unit_panel(
            view=view,
            selection=selection,
            pending_decision=decision,
        ),
        finite_decision_panel=finite_panel,
        movement_draft_panel=movement_panel,
        assignment_hud_panel=assignment_panel,
        event_log_lines=("movement_proposal_submitted: player_1", "opponent event"),
    )

    assert [chip.label for chip in ergonomics.status_chips] == ["Phase", "Active", "Pending"]
    assert ergonomics.selected_unit_card is not None
    assert ergonomics.selected_unit_card.unit_label == "Intercessors"
    assert any(row.primary_label == "Movement" for row in ergonomics.action_rows)
    assert ergonomics.assignment_rows
    assert ergonomics.assignment_rows[0].operation_kind == "movement"
    assert not any(
        "Synthetic midpoint witness evidence" in row.secondary_label
        for row in ergonomics.assignment_notice_rows
    )
    assert ergonomics.assignment_subtitle == "Draft review: ENTER submits to engine"
    assert ergonomics.assignment_color_role == "active"
    assert "ENTER: Confirm local UI action" in ergonomics.hotkey_hints
    assert ergonomics.event_lines == ("movement_proposal_submitted: player_1",)


def test_ergonomic_hud_view_honors_phase_and_event_visibility_preferences() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    preferences = replace(
        preferences,
        hud=replace(
            preferences.hud,
            show_phase=False,
            show_event_log=False,
        ),
    )
    finite_panel = build_finite_decision_panel(
        pending_decision=None,
        highlighted_option_index=0,
        status_message="Idle",
        diagnostics=(),
    )

    ergonomics = build_hud_ergonomics_view(
        view=view,
        preferences=preferences,
        unit_panel=None,
        finite_decision_panel=finite_panel,
        movement_draft_panel=None,
        assignment_hud_panel=None,
        event_log_lines=("movement_proposal_submitted: player_1",),
    )

    assert [chip.label for chip in ergonomics.status_chips] == ["Active", "Pending"]
    assert ergonomics.event_lines == ()
    assert ergonomics.assignment_subtitle == "No active assignment draft"


def test_player_units_roster_runtime_data_filters_and_highlights_viewer_units() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )
    finite_panel = build_finite_decision_panel(
        pending_decision=None,
        highlighted_option_index=0,
        status_message="Idle",
        diagnostics=(),
    )

    ergonomics = build_hud_ergonomics_view(
        view=view,
        preferences=preferences,
        unit_panel=build_unit_panel(
            view=view,
            selection=selection,
            pending_decision=None,
        ),
        finite_decision_panel=finite_panel,
        movement_draft_panel=None,
        assignment_hud_panel=None,
        event_log_lines=(),
        selected_unit_id=selection.selected_unit_id,
        viewer_player_id="player_1",
    )
    runtime = runtime_data_for_ergonomic_hud(ergonomics)
    roster = cast(JsonObject, runtime["hud.player_units.roster"])
    buttons = cast(list[JsonObject], roster["buttons"])

    assert [button["unit_id"] for button in buttons] == ["intercessor_squad"]
    assert buttons[0]["selected"] is True
    assert buttons[0]["action_kind"] == "select_unit"


def test_selected_unit_datasheet_uses_core_model_display_characteristics() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )
    finite_panel = build_finite_decision_panel(
        pending_decision=None,
        highlighted_option_index=0,
        status_message="Idle",
        diagnostics=(),
    )

    ergonomics = build_hud_ergonomics_view(
        view=view,
        preferences=preferences,
        unit_panel=build_unit_panel(
            view=view,
            selection=selection,
            pending_decision=None,
        ),
        finite_decision_panel=finite_panel,
        movement_draft_panel=None,
        assignment_hud_panel=None,
        event_log_lines=(),
        selected_unit_id=selection.selected_unit_id,
        viewer_player_id="player_1",
        unit_display_by_id={
            "intercessor_squad": {
                "unit_instance_id": "intercessor_squad",
                "owner_player_id": "player_1",
                "unit_display_name": "CORE Intercessor-like Infantry",
                "datasheet_id": "core-intercessor-like-infantry",
                "model_instance_ids": ["intercessor_1", "intercessor_2", "intercessor_3"],
            }
        },
        model_display_by_id={
            "intercessor_1": {
                "model_instance_id": "intercessor_1",
                "unit_instance_id": "intercessor_squad",
                "current_characteristics": {
                    "M": _characteristic("M", "6"),
                    "T": _characteristic("T", "4"),
                    "SV": _characteristic("SV", "3+"),
                    "InSv": _characteristic("InSv", "-"),
                    "W": _characteristic("W", "2"),
                    "LD": _characteristic("LD", "6+"),
                    "OC": _characteristic("OC", "2"),
                },
            }
        },
    )
    runtime = runtime_data_for_ergonomic_hud(ergonomics)
    selected_unit = cast(JsonObject, runtime["selected_unit"])
    selected_stats = cast(JsonObject, selected_unit["stats"])

    assert selected_unit["unit_label"] == "CORE Intercessor-like Infantry"
    assert selected_unit["status"] == "core-intercessor-like-infantry"
    assert selected_stats == {
        "M": "6",
        "T": "4",
        "SV": "3+",
        "W": "2",
        "LD": "6+",
        "OC": "2",
    }


def test_placement_draft_updates_current_action_and_player_units_status() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    selection = SelectionState.initial(preferences)
    decision = _placement_proposal_decision()
    draft = PlacementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=decision,
    )
    assert draft is not None
    draft = draft.place_current_model((8.0, 18.0))
    finite_panel = build_finite_decision_panel(
        pending_decision=decision,
        highlighted_option_index=0,
        status_message="Placement proposal pending",
        diagnostics=(),
    )
    placement_panel = build_placement_draft_panel(
        placement_draft=draft,
        pending_decision=decision,
    )

    ergonomics = build_hud_ergonomics_view(
        view=view,
        preferences=preferences,
        unit_panel=None,
        finite_decision_panel=finite_panel,
        movement_draft_panel=None,
        placement_draft_panel=placement_panel,
        assignment_hud_panel=build_assignment_hud_panel(
            movement_draft=None,
            placement_draft=draft,
            pending_decision=decision,
            highlighted_option_index=0,
            diagnostics=(),
            preferences=preferences,
            preference_source_label="default.yaml",
        ),
        event_log_lines=(),
        selected_unit_id=draft.selected_unit_id,
        viewer_player_id="player_1",
    )
    runtime = runtime_data_for_ergonomic_hud(ergonomics)
    roster = cast(JsonObject, runtime["hud.player_units.roster"])
    buttons = cast(list[JsonObject], roster["buttons"])
    current_action = cast(JsonObject, runtime["current_action"])
    placement_metadata = cast(JsonObject, buttons[0]["metadata"])
    current_action_buttons = cast(list[JsonObject], current_action["buttons"])
    current_action_summary = cast(str, current_action["summary"])

    assert placement_metadata["placement_status"] == "unplaced"
    assert current_action["source_kind"] == "local_gui"
    assert "1/3 placed" in current_action_summary
    assert [button["action_kind"] for button in current_action_buttons] == [
        "placement_submit",
        "placement_next_model",
        "placement_clear",
    ]


def test_player_units_roster_includes_pending_placement_unit_before_projection() -> None:
    view = replace(default_battlefield_view(), units=())
    preferences = default_preferences()
    decision = _deployment_placement_proposal_decision()
    finite_panel = build_finite_decision_panel(
        pending_decision=decision,
        highlighted_option_index=0,
        status_message="Placement proposal pending",
        diagnostics=(),
    )
    placement_panel = build_placement_draft_panel(
        placement_draft=None,
        pending_decision=decision,
    )
    assert placement_panel is not None

    ergonomics = build_hud_ergonomics_view(
        view=view,
        preferences=preferences,
        unit_panel=None,
        finite_decision_panel=finite_panel,
        movement_draft_panel=None,
        placement_draft_panel=placement_panel,
        assignment_hud_panel=None,
        event_log_lines=(),
        selected_unit_id=placement_panel.unit_id,
        viewer_player_id="player-b",
    )
    runtime = runtime_data_for_ergonomic_hud(ergonomics)
    roster = cast(JsonObject, runtime["hud.player_units.roster"])
    buttons = cast(list[JsonObject], roster["buttons"])
    metadata = cast(JsonObject, buttons[0]["metadata"])

    assert [button["unit_id"] for button in buttons] == ["army-beta:intercessor-unit-2"]
    assert buttons[0]["selected"] is True
    assert buttons[0]["state"] == "selected"
    assert buttons[0]["label"] == "Intercessor Unit 2"
    assert metadata["model_count"] == 5
    assert metadata["placement_status"] == "unplaced"


def test_player_units_roster_can_use_core_display_maps_for_undeployed_units() -> None:
    view = replace(default_battlefield_view(), units=())
    preferences = default_preferences()
    finite_panel = build_finite_decision_panel(
        pending_decision=None,
        highlighted_option_index=0,
        status_message="Idle",
        diagnostics=(),
    )

    ergonomics = build_hud_ergonomics_view(
        view=view,
        preferences=preferences,
        unit_panel=None,
        finite_decision_panel=finite_panel,
        movement_draft_panel=None,
        assignment_hud_panel=None,
        event_log_lines=(),
        viewer_player_id="player-a",
        unit_display_by_id={
            "army-alpha:intercessor-unit-1": {
                "unit_instance_id": "army-alpha:intercessor-unit-1",
                "owner_player_id": "player-a",
                "unit_display_name": "Alpha Intercessors",
                "model_instance_ids": ["model-1", "model-2"],
            },
            "army-beta:intercessor-unit-2": {
                "unit_instance_id": "army-beta:intercessor-unit-2",
                "owner_player_id": "player-b",
                "unit_display_name": "Beta Intercessors",
                "model_instance_ids": ["model-3", "model-4"],
            },
        },
    )
    runtime = runtime_data_for_ergonomic_hud(ergonomics)
    roster = cast(JsonObject, runtime["hud.player_units.roster"])
    buttons = cast(list[JsonObject], roster["buttons"])
    metadata = cast(JsonObject, buttons[0]["metadata"])

    assert [button["unit_id"] for button in buttons] == ["army-alpha:intercessor-unit-1"]
    assert buttons[0]["label"] == "Alpha Intercessors"
    assert buttons[0]["state"] == "normal"
    assert buttons[0]["color_role"] == "neutral"
    assert metadata["model_count"] == 2
    assert metadata["placement_status"] == "unplaced"


def test_player_units_roster_distinguishes_placed_and_unplaced_display_map_units() -> None:
    view = replace(default_battlefield_view(), units=(default_battlefield_view().units[0],))
    preferences = default_preferences()
    finite_panel = build_finite_decision_panel(
        pending_decision=None,
        highlighted_option_index=0,
        status_message="Idle",
        diagnostics=(),
    )

    ergonomics = build_hud_ergonomics_view(
        view=view,
        preferences=preferences,
        unit_panel=None,
        finite_decision_panel=finite_panel,
        movement_draft_panel=None,
        assignment_hud_panel=None,
        event_log_lines=(),
        viewer_player_id="player_1",
        unit_display_by_id={
            "intercessor_squad": {
                "unit_instance_id": "intercessor_squad",
                "owner_player_id": "player_1",
                "unit_display_name": "Intercessors",
                "model_instance_ids": ["intercessor_1", "intercessor_2", "intercessor_3"],
            },
            "reserve_squad": {
                "unit_instance_id": "reserve_squad",
                "owner_player_id": "player_1",
                "unit_display_name": "Reserve Squad",
                "model_instance_ids": ["reserve_1", "reserve_2"],
            },
        },
    )
    runtime = runtime_data_for_ergonomic_hud(ergonomics)
    roster = cast(JsonObject, runtime["hud.player_units.roster"])
    buttons = cast(list[JsonObject], roster["buttons"])
    status_by_unit = {
        cast(str, button["unit_id"]): cast(JsonObject, button["metadata"])["placement_status"]
        for button in buttons
    }
    color_by_unit = {cast(str, button["unit_id"]): button["color_role"] for button in buttons}

    assert [button["unit_id"] for button in buttons] == ["intercessor_squad", "reserve_squad"]
    assert status_by_unit == {"intercessor_squad": "placed", "reserve_squad": "unplaced"}
    assert color_by_unit == {"intercessor_squad": "active", "reserve_squad": "neutral"}


def test_ergonomic_selected_unit_actions_mark_highlighted_option() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )
    decision = UiDecision(
        request_id="decision-request-000004",
        decision_type="select_movement_action",
        actor_id="player_1",
        payload={"unit_instance_id": "intercessor_squad"},
        options=(
            UiFiniteOption(
                option_id="advance",
                label="Advance",
                payload={"movement_phase_action": "advance"},
            ),
            UiFiniteOption(
                option_id="normal_move",
                label="Normal Move",
                payload={"movement_phase_action": "normal_move"},
            ),
        ),
        is_parameterized=False,
    )
    finite_panel = build_finite_decision_panel(
        pending_decision=decision,
        highlighted_option_index=1,
        status_message="Waiting: select_movement_action",
        diagnostics=(),
    )

    ergonomics = build_hud_ergonomics_view(
        view=view,
        preferences=preferences,
        unit_panel=build_unit_panel(
            view=view,
            selection=selection,
            pending_decision=decision,
            highlighted_option_id="normal_move",
        ),
        finite_decision_panel=finite_panel,
        movement_draft_panel=None,
        assignment_hud_panel=None,
        event_log_lines=(),
    )

    action_row = next(
        row for row in ergonomics.selected_unit_rows if row.component_id == "selected_unit_actions"
    )
    assert action_row.secondary_label == "Advance, > Normal Move <"
    assert action_row.state == "selected"
    runtime = runtime_data_for_ergonomic_hud(ergonomics)
    current_action = runtime["current_action"]
    assert type(current_action) is dict
    buttons = current_action["buttons"]
    assert type(buttons) is list
    selected_button = cast(JsonObject, buttons[1])
    assert selected_button["option_id"] == "normal_move"
    assert selected_button["selected"] is True


def test_current_action_panel_renders_finite_options_as_buttons() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    layout = build_hud_layout(
        preferences=preferences,
        viewport_width_px=1280,
        viewport_height_px=800,
    )
    selection = SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )
    decision = UiDecision(
        request_id="decision-request-000004",
        decision_type="select_movement_action",
        actor_id="player_1",
        payload={"unit_instance_id": "intercessor_squad"},
        options=(
            UiFiniteOption(
                option_id="advance",
                label="Advance",
                payload={"movement_phase_action": "advance"},
            ),
            UiFiniteOption(
                option_id="normal_move",
                label="Normal Move",
                payload={"movement_phase_action": "normal_move"},
            ),
        ),
        is_parameterized=False,
    )
    finite_panel = build_finite_decision_panel(
        pending_decision=decision,
        highlighted_option_index=1,
        status_message="Waiting: select_movement_action",
        diagnostics=(),
    )
    ergonomics = build_hud_ergonomics_view(
        view=view,
        preferences=preferences,
        unit_panel=build_unit_panel(
            view=view,
            selection=selection,
            pending_decision=decision,
            highlighted_option_id="normal_move",
        ),
        finite_decision_panel=finite_panel,
        movement_draft_panel=None,
        assignment_hud_panel=None,
        event_log_lines=(),
    )

    texts = _composition_text_lines(ergonomics, layout)

    assert "Current Action" in texts
    assert "Advance" in texts
    assert "Normal Move" in texts


def test_ergonomic_assignment_subtitle_distinguishes_preview_from_ready_review() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    layout = build_hud_layout(
        preferences=preferences,
        viewport_width_px=1280,
        viewport_height_px=800,
    )
    selection = SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )
    decision = _movement_proposal_decision()
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=decision,
    )
    assert draft is not None
    draft = draft.add_waypoint(view=view, world_point=(10.0, 18.0))

    finite_panel = build_finite_decision_panel(
        pending_decision=decision,
        highlighted_option_index=0,
        status_message="Movement draft preview",
        diagnostics=(),
    )
    movement_panel = build_movement_draft_panel(
        movement_draft=draft,
        pending_decision=decision,
    )
    preview_assignment_panel = build_assignment_hud_panel(
        movement_draft=draft,
        pending_decision=decision,
        highlighted_option_index=0,
        diagnostics=(),
        preferences=preferences,
        preference_source_label="docs/preferences/default.yaml",
    )
    preview_ergonomics = build_hud_ergonomics_view(
        view=view,
        preferences=preferences,
        unit_panel=build_unit_panel(
            view=view,
            selection=selection,
            pending_decision=decision,
        ),
        finite_decision_panel=finite_panel,
        movement_draft_panel=movement_panel,
        assignment_hud_panel=preview_assignment_panel,
        event_log_lines=(),
    )

    preview_texts = _composition_text_lines(preview_ergonomics, layout)
    preview_runtime = runtime_data_for_ergonomic_hud(preview_ergonomics)
    preview_assignment = preview_runtime["current_assignment"]
    assert type(preview_assignment) is dict
    assert preview_ergonomics.assignment_subtitle == "Drafting paths: preview only"
    assert preview_ergonomics.assignment_color_role == "preview"
    assert preview_assignment["status"] == "Drafting paths: preview only"
    assert "Current Assignment" in preview_texts

    ready_draft = draft.mark_ready(view=view)
    ready_assignment_panel = build_assignment_hud_panel(
        movement_draft=ready_draft,
        pending_decision=decision,
        highlighted_option_index=0,
        diagnostics=(),
        preferences=preferences,
        preference_source_label="docs/preferences/default.yaml",
    )
    ready_ergonomics = build_hud_ergonomics_view(
        view=view,
        preferences=preferences,
        unit_panel=build_unit_panel(
            view=view,
            selection=selection,
            pending_decision=decision,
        ),
        finite_decision_panel=finite_panel,
        movement_draft_panel=build_movement_draft_panel(
            movement_draft=ready_draft,
            pending_decision=decision,
        ),
        assignment_hud_panel=ready_assignment_panel,
        event_log_lines=(),
    )

    ready_texts = _composition_text_lines(ready_ergonomics, layout)
    ready_runtime = runtime_data_for_ergonomic_hud(ready_ergonomics)
    ready_assignment = ready_runtime["current_assignment"]
    assert type(ready_assignment) is dict
    assert ready_ergonomics.assignment_subtitle == "Draft review: ENTER submits to engine"
    assert ready_ergonomics.assignment_color_role == "active"
    assert ready_assignment["status"] == "Draft review: ENTER submits to engine"
    assert "Current Assignment" in ready_texts


def test_ergonomic_hud_primitives_use_toolkit_components_in_screen_space() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    layout = build_hud_layout(
        preferences=preferences,
        viewport_width_px=1280,
        viewport_height_px=800,
    )
    selection = SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )
    decision = _movement_proposal_decision()
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=decision,
    )
    assert draft is not None
    draft = draft.add_waypoint(view=view, world_point=(10.0, 18.0)).mark_ready(view=view)
    finite_panel = build_finite_decision_panel(
        pending_decision=decision,
        highlighted_option_index=0,
        status_message="Movement draft ready",
        diagnostics=(),
    )
    movement_panel = build_movement_draft_panel(
        movement_draft=draft,
        pending_decision=decision,
    )
    assignment_panel = build_assignment_hud_panel(
        movement_draft=draft,
        pending_decision=decision,
        highlighted_option_index=0,
        diagnostics=(),
        preferences=preferences,
        preference_source_label="docs/preferences/default.yaml",
    )
    ergonomics = build_hud_ergonomics_view(
        view=view,
        preferences=preferences,
        unit_panel=build_unit_panel(
            view=view,
            selection=selection,
            pending_decision=decision,
        ),
        finite_decision_panel=finite_panel,
        movement_draft_panel=movement_panel,
        assignment_hud_panel=assignment_panel,
        event_log_lines=("movement_proposal_submitted: player_1",),
    )

    result = load_hud_composition_reference("default-hud")
    assert result.profile is not None, result.diagnostics
    primitives = render_composition_profile(
        result.profile,
        viewport_width_px=1280,
        viewport_height_px=800,
        runtime_data=runtime_data_for_ergonomic_hud(ergonomics),
        hud_layout=layout,
        include_background=False,
    )

    texts = _text_lines(primitives)
    assert "Selected Unit" in texts
    assert "Intercessors" in texts
    assert "Current Action" in texts
    assert "Current Assignment" in texts
    assert any("Movement draft ready" in text for text in texts)
    assert any(type(primitive) is PolygonPrimitive for primitive in primitives)
    assert all(primitive.coordinate_space == "screen" for primitive in primitives)


def test_ergonomic_hud_renders_through_configured_default_composition() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    layout = build_hud_layout(
        preferences=preferences,
        viewport_width_px=1280,
        viewport_height_px=800,
    )
    selection = SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )
    decision = _movement_proposal_decision()
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=decision,
    )
    assert draft is not None
    draft = draft.add_waypoint(view=view, world_point=(10.0, 18.0)).mark_ready(view=view)
    finite_panel = build_finite_decision_panel(
        pending_decision=decision,
        highlighted_option_index=0,
        status_message="Movement draft ready",
        diagnostics=(),
    )
    assignment_panel = build_assignment_hud_panel(
        movement_draft=draft,
        pending_decision=decision,
        highlighted_option_index=0,
        diagnostics=(),
        preferences=preferences,
        preference_source_label="docs/preferences/default.yaml",
    )
    ergonomics = build_hud_ergonomics_view(
        view=view,
        preferences=preferences,
        unit_panel=build_unit_panel(
            view=view,
            selection=selection,
            pending_decision=decision,
        ),
        finite_decision_panel=finite_panel,
        movement_draft_panel=build_movement_draft_panel(
            movement_draft=draft,
            pending_decision=decision,
        ),
        assignment_hud_panel=assignment_panel,
        event_log_lines=("movement_proposal_submitted: player_1",),
        event_payloads=(
            {
                "event_type": "dice_rolled",
                "payload": {
                    "roll_id": "roll-advance-000001",
                    "spec": {
                        "roll_type": "advance",
                        "reason": "CORE Intercessor-like Infantry",
                        "expression": {"dice_count": 1, "sides": 6},
                    },
                    "values": [4],
                    "total": 4,
                    "source": "CORE",
                },
            },
        ),
    )
    result = load_hud_composition_reference("default-hud")
    assert result.profile is not None, result.diagnostics

    primitives = render_composition_profile(
        result.profile,
        viewport_width_px=1280,
        viewport_height_px=800,
        runtime_data=runtime_data_for_ergonomic_hud(ergonomics),
        hud_layout=layout,
        include_background=False,
    )

    texts = _text_lines(primitives)
    polygon_layers = {
        primitive.layer for primitive in primitives if type(primitive) is PolygonPrimitive
    }
    assert "hud_preview_background" not in polygon_layers
    assert not any(layer.startswith("hud_zone_") for layer in polygon_layers)
    assert "Selected Unit" in texts
    assert "Intercessors" in texts
    assert {"M", "T", "SV", "W", "LD", "OC"}.issubset(set(texts))
    assert "?" in texts
    assert "Current Action" in texts
    assert any("Fixture: Command Phase" in text for text in texts)
    assert any("Movement draft ready" in text for text in texts)
    assert "Current Assignment" in texts
    assert "Dice Tray" in texts
    assert "x1" in texts


def _movement_proposal_decision() -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": "decision-request-000005",
            "decision_type": "submit_movement_proposal",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-000005",
                    "decision_type": "submit_movement_proposal",
                    "actor_id": "player_1",
                    "game_id": "phase20-game",
                    "battle_round": 1,
                    "phase": "movement",
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": "normal_move",
                    "source_decision_request_id": "decision-request-000004",
                    "source_decision_result_id": "ui-result-000001",
                    "movement_phase_action": "normal_move",
                    "placement_kinds": [],
                    "context": {
                        "source_selected_option_id": "normal_move",
                        "movement_mode": "normal",
                        "movement_budget_inches": 6.0,
                    },
                }
            },
            "is_parameterized": True,
            "options": [
                {
                    "option_id": "submit_parameterized_payload",
                    "label": "Submit Parameterized Payload",
                    "payload": {"submission_kind": "parameterized"},
                }
            ],
        }
    )


def _placement_proposal_decision() -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": "decision-request-placement-001",
            "decision_type": "submit_placement_proposal",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-placement-001",
                    "decision_type": "submit_placement_proposal",
                    "actor_id": "player_1",
                    "game_id": "phase28-game",
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": "reinforcement_placement",
                    "source_decision_request_id": "decision-request-unit-001",
                    "source_decision_result_id": "ui-result-unit-001",
                    "placement_kinds": ["reinforcement"],
                    "context": {"placement_kind": "reinforcement"},
                }
            },
            "is_parameterized": True,
            "options": [
                {
                    "option_id": "submit_parameterized_payload",
                    "label": "Submit Parameterized Payload",
                    "payload": {"submission_kind": "parameterized"},
                }
            ],
        }
    )


def _deployment_placement_proposal_decision() -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": "decision-request-deployment-001",
            "decision_type": "submit_deployment_placement",
            "actor_id": "player-b",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-deployment-001",
                    "decision_type": "submit_deployment_placement",
                    "actor_id": "player-b",
                    "game_id": "phase28-game",
                    "player_id": "player-b",
                    "unit_instance_id": "army-beta:intercessor-unit-2",
                    "proposal_kind": "deployment_placement",
                    "placement_kind": "deployment",
                    "placement_kinds": ["deployment"],
                    "model_instance_ids": [
                        "army-beta:intercessor-unit-2:core-intercessor-like:001",
                        "army-beta:intercessor-unit-2:core-intercessor-like:002",
                        "army-beta:intercessor-unit-2:core-intercessor-like:003",
                        "army-beta:intercessor-unit-2:core-intercessor-like:004",
                        "army-beta:intercessor-unit-2:core-intercessor-like:005",
                    ],
                    "source_decision_request_id": "decision-request-unit-001",
                    "source_decision_result_id": "ui-result-unit-001",
                    "context": {"placement_kind": "deployment"},
                }
            },
            "is_parameterized": True,
            "options": [
                {
                    "option_id": "submit_parameterized_payload",
                    "label": "Submit Parameterized Payload",
                    "payload": {"submission_kind": "parameterized"},
                }
            ],
        }
    )


def _characteristic(label: str, display_value: str) -> JsonObject:
    return {
        "characteristic": label,
        "label": label,
        "value_kind": "numeric" if display_value not in {"-", "?"} else "source_dash",
        "raw": None,
        "base": None,
        "final": None,
        "display_value": display_value,
        "applied_modifier_ids": [],
        "redaction": None,
    }


def _text_lines(primitives: tuple[RenderPrimitive, ...]) -> list[str]:
    return [primitive.text for primitive in primitives if type(primitive) is TextPrimitive]


def _composition_text_lines(
    ergonomics: HudErgonomicsView,
    layout: HudLayoutView,
) -> list[str]:
    result = load_hud_composition_reference("default-hud")
    assert result.profile is not None, result.diagnostics
    primitives = render_composition_profile(
        result.profile,
        viewport_width_px=1280,
        viewport_height_px=800,
        runtime_data=runtime_data_for_ergonomic_hud(ergonomics),
        hud_layout=layout,
        include_background=False,
    )
    return _text_lines(primitives)
