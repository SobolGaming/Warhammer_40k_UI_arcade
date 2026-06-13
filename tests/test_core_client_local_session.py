"""Tests for the local core session facade."""

from __future__ import annotations

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.engine.decision_request import DecisionOption, DecisionRequest

from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient


def test_local_session_submit_finite_rejects_stale_explicit_request_id() -> None:
    client = LocalSessionClient(session=LocalGameSession())
    client.session.lifecycle.decision_controller.request_decision(_finite_request())

    status = client.submit_finite(
        request_id="decision-request-stale",
        selected_option_id="normal_move",
        result_id="ui-result-000001",
    )

    assert status.status_kind == "invalid"
    assert status.invalid_diagnostics[0].violation_code == "stale_request_id"
    assert status.decision is not None
    assert status.decision.request_id == "decision-request-000004"
    assert client.session.lifecycle.decision_controller.queue.pending_requests[0].request_id == (
        "decision-request-000004"
    )


def test_local_session_submit_finite_requires_explicit_result_id() -> None:
    client = LocalSessionClient(session=LocalGameSession())
    client.session.lifecycle.decision_controller.request_decision(_finite_request())

    with pytest.raises(TypeError):
        client.submit_finite(  # type: ignore[call-arg]
            request_id="decision-request-000004",
            selected_option_id="normal_move",
        )


def test_local_session_submit_finite_rejects_non_pending_option_id() -> None:
    client = LocalSessionClient(session=LocalGameSession())
    client.session.lifecycle.decision_controller.request_decision(_finite_request())

    status = client.submit_finite(
        request_id="decision-request-000004",
        selected_option_id="invented_option",
        result_id="ui-result-000001",
    )

    assert status.status_kind == "invalid"
    assert status.invalid_diagnostics[0].violation_code == "selected_option_not_pending"
    assert status.invalid_diagnostics[0].field == "selected_option_id"


def test_local_session_submit_movement_payload_rejects_finite_request() -> None:
    client = LocalSessionClient(session=LocalGameSession())
    client.session.lifecycle.decision_controller.request_decision(_finite_request())

    status = client.submit_movement_payload(
        request_id="decision-request-000004",
        payload={"proposal_request_id": "decision-request-000004"},
        result_id="ui-result-000001",
    )

    assert status.status_kind == "invalid"
    assert status.invalid_diagnostics[0].violation_code == "movement_payload_for_finite_request"
    assert status.invalid_diagnostics[0].field == "request_id"


def test_local_session_submit_movement_payload_rejects_stale_explicit_request_id() -> None:
    client = LocalSessionClient(session=LocalGameSession())
    client.session.lifecycle.decision_controller.request_decision(_movement_proposal_request())

    status = client.submit_movement_payload(
        request_id="decision-request-stale",
        payload={"proposal_request_id": "decision-request-stale"},
        result_id="ui-result-000001",
    )

    assert status.status_kind == "invalid"
    assert status.invalid_diagnostics[0].violation_code == "stale_request_id"
    assert status.decision is not None
    assert status.decision.is_parameterized is True
    assert status.decision.movement_proposal is not None
    assert status.decision.movement_proposal.request_id == "decision-request-000005"


def test_local_session_submit_movement_payload_requires_explicit_result_id() -> None:
    client = LocalSessionClient(session=LocalGameSession())
    client.session.lifecycle.decision_controller.request_decision(_movement_proposal_request())

    with pytest.raises(TypeError):
        client.submit_movement_payload(  # type: ignore[call-arg]
            request_id="decision-request-000005",
            payload={"proposal_request_id": "decision-request-000005"},
        )


def _finite_request() -> DecisionRequest:
    return DecisionRequest(
        request_id="decision-request-000004",
        decision_type="select_movement_action",
        actor_id="player-a",
        payload={"unit_instance_id": "unit-1"},
        options=(
            DecisionOption(
                option_id="normal_move",
                label="Normal Move",
                payload={"movement_phase_action": "normal_move"},
            ),
        ),
    )


def _movement_proposal_request() -> DecisionRequest:
    return DecisionRequest(
        request_id="decision-request-000005",
        decision_type="submit_movement_proposal",
        actor_id="player-a",
        payload={
            "proposal_request": {
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
        },
        options=(
            DecisionOption(
                option_id="submit_parameterized_payload",
                label="Submit Parameterized Payload",
                payload={"submission_kind": "parameterized"},
            ),
        ),
    )
