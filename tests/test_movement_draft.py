"""Tests for local movement draft state and payload previews."""

from __future__ import annotations

from dataclasses import replace

from warhammer40k_arcade_ui.core_client.protocol import UiDecision
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.state.movement_draft import (
    MovementDraft,
    movement_proposal_for_selected_unit,
    unsupported_parameterized_tool_label,
)
from warhammer40k_arcade_ui.state.selection import SelectionState


def test_movement_proposal_for_selected_unit_activates_draft() -> None:
    view = default_battlefield_view()
    selection = _selected_intercessors()
    decision = _movement_proposal_decision()

    proposal = movement_proposal_for_selected_unit(
        view=view,
        selection=selection,
        pending_decision=decision,
    )
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=decision,
    )

    assert proposal is not None
    assert draft is not None
    assert draft.selected_unit_id == "intercessor_squad"
    assert draft.proposal_request_id == "decision-request-000005"
    assert draft.proposal_kind == "normal_move"
    assert draft.movement_phase_action == "normal_move"
    assert draft.movement_mode == "normal"
    assert draft.anchor_points == ((7.0, 22.0),)
    assert [path.model_id for path in draft.model_paths] == [
        "intercessor_1",
        "intercessor_2",
        "intercessor_3",
    ]


def test_movement_draft_waypoint_preview_ready_and_remove_transitions() -> None:
    view = default_battlefield_view()
    draft = _active_draft()

    previewed = draft.with_cursor_preview(view=view, world_point=(10.0, 22.0))
    ready = previewed.mark_ready(view=view)
    removed = ready.remove_last_waypoint(view=view)

    assert previewed.current_segment_length == 3.0
    assert ready.is_ready is True
    assert ready.anchor_points == ((7.0, 22.0), (10.0, 22.0))
    assert removed.ready_payload is None
    assert removed.anchor_points == ((7.0, 22.0),)
    assert all(path.points == (path.points[0],) for path in removed.model_paths)


def test_movement_payload_shape_from_simple_two_point_path() -> None:
    view = default_battlefield_view()
    draft = _active_draft().add_waypoint(view=view, world_point=(10.0, 22.0)).mark_ready(view=view)

    payload = draft.payload_preview

    assert payload is not None
    assert payload["proposal_request_id"] == "decision-request-000005"
    assert payload["proposal_kind"] == "normal_move"
    assert payload["unit_instance_id"] == "intercessor_squad"
    assert payload["movement_phase_action"] == "normal_move"
    assert payload["movement_mode"] == "normal"
    witness = payload["witness"]
    assert type(witness) is dict
    model_paths = witness["model_paths"]
    assert type(model_paths) is list
    assert len(model_paths) == 3
    first_path = model_paths[0]
    assert type(first_path) is dict
    assert first_path["model_id"] == "intercessor_1"
    assert first_path["poses"] == [
        {"position": {"x": 7.0, "y": 18.0, "z": 0.0}, "facing": {"degrees": 0.0}},
        {"position": {"x": 10.0, "y": 18.0, "z": 0.0}, "facing": {"degrees": 0.0}},
    ]
    assert "model_movements" in payload


def test_fall_back_payload_preserves_engine_issued_mode_context() -> None:
    view = default_battlefield_view()
    selection = _selected_intercessors()
    decision = _movement_proposal_decision(
        proposal_kind="fall_back",
        movement_phase_action="fall_back",
        context={
            "source_selected_option_id": "fall_back:desperate_escape",
            "movement_mode": "fall_back",
            "fall_back_mode": "desperate_escape",
            "movement_budget_inches": 6.0,
        },
    )
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=decision,
    )

    assert draft is not None
    payload = (
        draft.add_waypoint(view=view, world_point=(9.0, 22.0)).mark_ready(view=view).payload_preview
    )

    assert payload is not None
    assert payload["proposal_kind"] == "fall_back"
    assert payload["movement_phase_action"] == "fall_back"
    assert payload["movement_mode"] == "fall_back"
    assert payload["fall_back_mode"] == "desperate_escape"


def test_non_movement_parameterized_request_does_not_create_movement_draft() -> None:
    view = default_battlefield_view()
    selection = _selected_intercessors()
    decision = _shooting_proposal_decision()

    proposal = movement_proposal_for_selected_unit(
        view=view,
        selection=selection,
        pending_decision=decision,
    )
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=decision,
    )

    assert proposal is None
    assert draft is None
    assert unsupported_parameterized_tool_label(decision) == "shooting_declaration"


def test_selection_state_uses_configured_movement_draft_overlays() -> None:
    preferences = default_preferences()
    selection = _selected_intercessors()

    with_draft = selection.with_movement_draft_overlays(preferences)
    without_draft = with_draft.without_movement_draft_overlays(preferences)

    assert "movement_path_draft" in with_draft.active_overlay_ids
    assert "movement_budget" in with_draft.active_overlay_ids
    assert "movement_path_draft" not in without_draft.active_overlay_ids
    assert "movement_budget" not in without_draft.active_overlay_ids
    assert "selected_unit" in without_draft.active_overlay_ids


def _active_draft() -> MovementDraft:
    view = default_battlefield_view()
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(),
        pending_decision=_movement_proposal_decision(),
    )
    assert draft is not None
    return draft


def _selected_intercessors() -> SelectionState:
    view = default_battlefield_view()
    preferences = default_preferences()
    return SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )


def _movement_proposal_decision(
    *,
    proposal_kind: str = "normal_move",
    movement_phase_action: str = "normal_move",
    context: dict[str, object] | None = None,
) -> UiDecision:
    proposal_context = (
        {
            "source_selected_option_id": "normal_move",
            "movement_mode": "normal",
            "movement_budget_inches": 6.0,
        }
        if context is None
        else context
    )
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
                    "game_id": "phase7-game",
                    "battle_round": 1,
                    "phase": "movement",
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": proposal_kind,
                    "source_decision_request_id": "decision-request-000004",
                    "source_decision_result_id": "ui-result-000001",
                    "movement_phase_action": movement_phase_action,
                    "placement_kinds": [],
                    "context": proposal_context,
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


def _shooting_proposal_decision() -> UiDecision:
    decision = _movement_proposal_decision()
    proposal = decision.parameterized_proposal
    assert proposal is not None
    return replace(
        decision,
        decision_type="submit_shooting_declaration",
        movement_proposal=None,
        parameterized_proposal=replace(
            proposal,
            decision_type="submit_shooting_declaration",
            proposal_kind="shooting_declaration",
            payload={
                "request_id": "decision-request-000009",
                "decision_type": "submit_shooting_declaration",
                "actor_id": "player_1",
                "proposal_kind": "shooting_declaration",
            },
        ),
    )
