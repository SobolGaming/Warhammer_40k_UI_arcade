"""Tests for the Phase 20 ergonomic HUD summary."""

from __future__ import annotations

from dataclasses import replace

from warhammer40k_arcade_ui.core_client.protocol import UiDecision, UiFiniteOption
from warhammer40k_arcade_ui.hud.ergonomics import build_hud_ergonomics_view
from warhammer40k_arcade_ui.hud.layouts import build_hud_layout
from warhammer40k_arcade_ui.hud.view_models import (
    build_assignment_hud_panel,
    build_finite_decision_panel,
    build_movement_draft_panel,
    build_unit_panel,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.render.hud_ergonomics import build_ergonomic_hud_primitives
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
        debug_visible=False,
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
        debug_visible=False,
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

    preview_texts = _text_lines(
        build_ergonomic_hud_primitives(
            ergonomics=preview_ergonomics,
            hud_layout=layout,
            viewport_width_px=1280,
            viewport_height_px=800,
        )
    )
    assert preview_ergonomics.assignment_subtitle == "Drafting paths: preview only"
    assert preview_ergonomics.assignment_color_role == "preview"
    assert "Drafting paths: preview only" in preview_texts

    ready_draft = draft.mark_ready(view=view)
    ready_assignment_panel = build_assignment_hud_panel(
        movement_draft=ready_draft,
        pending_decision=decision,
        highlighted_option_index=0,
        diagnostics=(),
        preferences=preferences,
        preference_source_label="docs/preferences/default.yaml",
        debug_visible=False,
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

    ready_texts = _text_lines(
        build_ergonomic_hud_primitives(
            ergonomics=ready_ergonomics,
            hud_layout=layout,
            viewport_width_px=1280,
            viewport_height_px=800,
        )
    )
    assert ready_ergonomics.assignment_subtitle == "Draft review: ENTER submits to engine"
    assert ready_ergonomics.assignment_color_role == "active"
    assert "Draft review: ENTER submits to engine" in ready_texts


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
        debug_visible=False,
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

    primitives = build_ergonomic_hud_primitives(
        ergonomics=ergonomics,
        hud_layout=layout,
        viewport_width_px=1280,
        viewport_height_px=800,
    )

    texts = _text_lines(primitives)
    assert "Selected Unit" in texts
    assert "Intercessors" in texts
    assert "Decision" in texts
    assert "Assignments" in texts
    assert "Draft review: ENTER submits to engine" in texts
    assert "Review" in texts
    assert any(type(primitive) is PolygonPrimitive for primitive in primitives)
    assert all(primitive.coordinate_space == "screen" for primitive in primitives)


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
