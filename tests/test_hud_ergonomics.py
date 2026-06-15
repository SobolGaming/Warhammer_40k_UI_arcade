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
    assert any(
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
