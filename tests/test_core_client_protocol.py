"""Tests for UI-facing core client protocol models."""

from __future__ import annotations

from warhammer40k_arcade_ui.core_client.fake_client import FakeCoreClient
from warhammer40k_arcade_ui.core_client.protocol import (
    UiClientStatus,
    UiDecision,
    UiEventDelta,
    UiFiniteOption,
    UiGameView,
    UiMovementProposalRequest,
)


def test_status_represents_no_pending_decision() -> None:
    status = UiClientStatus.from_payload(
        {
            "stage": "setup",
            "status_kind": "advanced",
            "decision_request": None,
            "message": None,
            "payload": None,
        }
    )

    assert status.status_kind == "advanced"
    assert status.decision is None
    assert status.invalid_diagnostics == ()


def test_status_represents_finite_decision() -> None:
    status = UiClientStatus.from_payload(
        {
            "stage": "battle",
            "status_kind": "waiting_for_decision",
            "decision_request": {
                "request_id": "decision-request-000004",
                "decision_type": "select_movement_action",
                "actor_id": "player-a",
                "payload": {"unit_instance_id": "unit-1"},
                "options": [
                    {
                        "option_id": "normal_move",
                        "label": "Normal Move",
                        "payload": {"movement_phase_action": "normal_move"},
                    }
                ],
            },
            "message": None,
            "payload": None,
        }
    )

    assert status.decision == UiDecision(
        request_id="decision-request-000004",
        decision_type="select_movement_action",
        actor_id="player-a",
        payload={"unit_instance_id": "unit-1"},
        options=(
            UiFiniteOption(
                option_id="normal_move",
                label="Normal Move",
                payload={"movement_phase_action": "normal_move"},
            ),
        ),
        is_parameterized=False,
    )


def test_status_represents_movement_proposal_request() -> None:
    proposal_payload = _movement_proposal_request_payload()

    status = UiClientStatus.from_payload(
        {
            "stage": "battle",
            "status_kind": "waiting_for_decision",
            "decision_request": {
                "request_id": "decision-request-000005",
                "decision_type": "submit_movement_proposal",
                "actor_id": "player-a",
                "payload": {"proposal_request": proposal_payload},
                "options": [
                    {
                        "option_id": "submit_parameterized_payload",
                        "label": "Submit Parameterized Payload",
                        "payload": {"submission_kind": "parameterized"},
                    }
                ],
            },
            "message": None,
            "payload": None,
        }
    )

    assert status.decision is not None
    assert status.decision.is_parameterized is True
    assert status.decision.movement_proposal == UiMovementProposalRequest.from_payload(
        proposal_payload
    )


def test_invalid_status_represents_proposal_diagnostics() -> None:
    status = UiClientStatus.from_payload(
        {
            "stage": "battle",
            "status_kind": "invalid",
            "decision_request": None,
            "message": "Movement proposal is invalid.",
            "payload": {
                "proposal_validation": {
                    "proposal_request_id": "decision-request-000005",
                    "proposal_kind": "normal_move",
                    "is_valid": False,
                    "status": "invalid",
                    "violations": [
                        {
                            "violation_code": "proposal_payload_missing_field",
                            "message": "Proposal payload missing required field.",
                            "field": "proposal_request_id",
                        }
                    ],
                }
            },
        }
    )

    assert len(status.invalid_diagnostics) == 1
    diagnostic = status.invalid_diagnostics[0]
    assert diagnostic.violation_code == "proposal_payload_missing_field"
    assert diagnostic.proposal_request_id == "decision-request-000005"
    assert diagnostic.proposal_kind == "normal_move"
    assert diagnostic.field == "proposal_request_id"


def test_invalid_status_without_payload_uses_message_diagnostic() -> None:
    status = UiClientStatus.from_payload(
        {
            "stage": "battle",
            "status_kind": "invalid",
            "decision_request": None,
            "message": "Submitted result is invalid.",
            "payload": None,
        }
    )

    assert len(status.invalid_diagnostics) == 1
    assert status.invalid_diagnostics[0].violation_code == "invalid_status"
    assert status.invalid_diagnostics[0].message == "Submitted result is invalid."


def test_status_represents_terminal_state() -> None:
    status = UiClientStatus.from_payload(
        {
            "stage": "complete",
            "status_kind": "terminal",
            "decision_request": None,
            "message": "Game complete.",
            "payload": {"winner": "player-a"},
        }
    )

    assert status.status_kind == "terminal"
    assert status.message == "Game complete."
    assert status.payload == {"winner": "player-a"}


def test_game_view_represents_viewer_projection() -> None:
    view = UiGameView.from_payload(
        {
            "viewer_player_id": "player-a",
            "game_id": "phase2-game",
            "stage": "battle",
            "battle_round": 1,
            "active_player_id": "player-a",
            "current_setup_step": None,
            "current_battle_phase": "movement",
            "player_ids": ["player-a", "player-b"],
            "battlefield_state": None,
            "mission_setup": None,
            "public_secondary_mission_choices": [],
            "public_secondary_mission_card_states": [],
            "public_command_point_ledgers": [],
            "public_victory_point_ledgers": [],
            "public_stratagem_use_records": [],
            "pending_decision": None,
            "pending_proposal": _movement_proposal_request_payload(),
            "event_count": 3,
        }
    )

    assert view.viewer_player_id == "player-a"
    assert view.pending_decision is None
    assert view.pending_proposal is not None
    assert view.pending_proposal.request_id == "decision-request-000005"


def test_fake_core_client_records_explicit_submission_ids() -> None:
    status = UiClientStatus(
        stage="battle",
        status_kind="waiting_for_decision",
        payload=None,
    )
    fake = FakeCoreClient(
        status=status,
        event_delta=UiEventDelta(
            viewer_player_id="player-a",
            cursor=0,
            next_cursor=0,
            events=(),
        ),
    )

    returned = fake.submit_finite(
        request_id="decision-request-000004",
        selected_option_id="normal_move",
        result_id="ui-result-000017",
    )
    fake.submit_movement_payload(
        request_id="decision-request-000005",
        payload={"proposal_request_id": "decision-request-000005"},
        result_id="ui-result-000018",
    )

    assert returned is status
    assert fake.finite_submissions[0].request_id == "decision-request-000004"
    assert fake.finite_submissions[0].selected_option_id == "normal_move"
    assert fake.movement_submissions[0].request_id == "decision-request-000005"


def _movement_proposal_request_payload() -> dict[str, object]:
    return {
        "request_id": "decision-request-000005",
        "decision_type": "submit_movement_proposal",
        "actor_id": "player-a",
        "game_id": "phase2-game",
        "battle_round": 1,
        "phase": "movement",
        "unit_instance_id": "unit-1",
        "proposal_kind": "normal_move",
        "source_decision_request_id": "decision-request-000004",
        "source_decision_result_id": "ui-result-000017",
        "movement_phase_action": "normal_move",
        "placement_kinds": [],
        "context": {
            "source_selected_option_id": "normal_move",
            "movement_mode": "normal",
        },
    }
