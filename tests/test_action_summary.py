"""Tests for advisory action visual summary view models."""

from __future__ import annotations

from warhammer40k_arcade_ui.core_client.protocol import UiDecision, UiInvalidDiagnostic
from warhammer40k_arcade_ui.hud.action_summary import build_action_visual_summary
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft
from warhammer40k_arcade_ui.state.selection import SelectionState


def test_movement_action_summary_uses_movement_assignment_paths() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=_movement_proposal_decision(),
    )
    assert draft is not None
    draft = draft.add_waypoint(view=view, world_point=(10.0, 18.0)).mark_ready(view=view)

    summary = build_action_visual_summary(
        movement_draft=draft,
        pending_decision=_movement_proposal_decision(),
        diagnostics=(),
        intensity="dim",
        max_labels=6,
    )

    assert summary is not None
    assert summary.request_id == "decision-request-000005"
    assert summary.operation_kind == "movement"
    assert summary.intensity == "dim"
    assert summary.ready is True
    assert [group.group_id for group in summary.groups] == ["assignment-group-000001"]
    assert summary.groups[0].source_ref_keys == ("model:intercessor_1",)
    assert summary.groups[0].path_points == ((7.0, 18.0), (10.0, 18.0))
    assert summary.groups[0].ghost_center == (10.0, 18.0)
    assert summary.groups[0].summary_lines == ("Path: 3.00 in",)


def test_hidden_action_summary_returns_no_view_model() -> None:
    summary = build_action_visual_summary(
        movement_draft=None,
        pending_decision=_movement_proposal_decision(),
        diagnostics=(),
        intensity="hidden",
        max_labels=6,
    )

    assert summary is None


def test_invalid_movement_diagnostic_marks_summary_warning() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=_movement_proposal_decision(),
    )
    assert draft is not None
    draft = draft.add_waypoint(view=view, world_point=(10.0, 18.0))

    summary = build_action_visual_summary(
        movement_draft=draft,
        pending_decision=_movement_proposal_decision(),
        diagnostics=(
            UiInvalidDiagnostic(
                violation_code="movement_budget_exceeded",
                message="Normal Move path exceeds the movement budget.",
                field="witness",
            ),
        ),
        intensity="review",
        max_labels=6,
    )

    assert summary is not None
    assert summary.groups[0].state == "warning"
    assert summary.groups[0].color_role == "warning"
    assert (
        "movement_budget_exceeded [witness]: Normal Move path exceeds the movement budget."
        in summary.diagnostic_lines
    )


def test_unsupported_charge_summary_is_diagnostic_without_geometry() -> None:
    summary = build_action_visual_summary(
        movement_draft=None,
        pending_decision=_charge_move_proposal_decision(),
        diagnostics=(),
        intensity="review",
        max_labels=6,
    )

    assert summary is not None
    assert summary.operation_kind == "unsupported"
    assert summary.groups == ()
    assert summary.has_drawable_groups is False
    assert summary.diagnostic_lines == (
        "No action visual summary adapter is available for charge_move.",
    )


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
                    "game_id": "phase18-game",
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


def _charge_move_proposal_decision() -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": "decision-request-charge-001",
            "decision_type": "submit_movement_proposal",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-charge-001",
                    "decision_type": "submit_movement_proposal",
                    "actor_id": "player_1",
                    "game_id": "phase18-game",
                    "battle_round": 1,
                    "phase": "charge",
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": "charge_move",
                    "source_decision_request_id": "decision-request-charge-source",
                    "source_decision_result_id": "ui-result-charge-001",
                    "movement_phase_action": "charge_move",
                    "placement_kinds": [],
                    "context": {},
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
