"""Tests for opt-in manual validation fixtures."""

from __future__ import annotations

from typing import cast

from warhammer40k_arcade_ui.core_client.protocol import JsonObject, JsonValue
from warhammer40k_arcade_ui.debug_fixtures import (
    phase6_debug_core_client,
    phase6_debug_pending_decision,
)


def test_phase6_debug_fixture_submits_into_parameterized_pending_state() -> None:
    decision = phase6_debug_pending_decision()
    client = phase6_debug_core_client()

    status = client.submit_finite(
        request_id=decision.request_id,
        selected_option_id="normal_move",
        result_id="ui-result-000001",
    )

    assert client.finite_submissions[0].request_id == "decision-request-phase6-debug-000001"
    assert client.finite_submissions[0].selected_option_id == "normal_move"
    assert status.decision is not None
    assert status.decision.is_parameterized is True
    assert status.decision.parameterized_proposal is not None
    assert status.decision.parameterized_proposal.proposal_kind == "normal_move"


def test_phase10_debug_fixture_movement_submission_returns_success_projection_and_events() -> None:
    client = phase6_debug_core_client()

    status = client.submit_movement_payload(
        request_id="decision-request-phase6-debug-000002",
        payload=_movement_payload(),
        result_id="ui-result-000002",
    )
    advanced_status = client.advance_until_decision_or_terminal()

    assert client.movement_submissions[0].request_id == ("decision-request-phase6-debug-000002")
    assert client.movement_submissions[0].result_id == "ui-result-000002"
    assert status.status_kind == "advanced"
    assert status.message == "Debug movement accepted."
    assert status.decision is None
    assert advanced_status == status

    view = client.get_view("player_1")
    assert view.pending_decision is None
    assert view.event_count == 4
    positions = _model_positions(view.battlefield_state)
    assert positions["intercessor_1"] == (10.0, 18.0)
    assert positions["intercessor_2"] == (7.0, 22.0)

    delta = client.get_events_since(1, "player_1")
    assert delta.next_cursor == 4
    assert tuple(event["event_type"] for event in delta.events) == (
        "movement_proposal_submitted",
        "movement_proposal_accepted",
        "battlefield_projection_refreshed",
    )


def _movement_payload() -> JsonObject:
    return {
        "proposal_request_id": "decision-request-phase6-debug-000002",
        "proposal_kind": "normal_move",
        "unit_instance_id": "intercessor_squad",
        "movement_phase_action": "normal_move",
        "movement_mode": "normal",
        "witness": {
            "model_paths": [
                {
                    "model_id": "intercessor_1",
                    "poses": [
                        {"position": {"x": 7.0, "y": 18.0, "z": 0.0}},
                        {"position": {"x": 10.0, "y": 18.0, "z": 0.0}},
                    ],
                },
                {
                    "model_id": "intercessor_2",
                    "poses": [
                        {"position": {"x": 7.0, "y": 22.0, "z": 0.0}},
                        {"position": {"x": 7.0, "y": 22.0, "z": 0.0}},
                    ],
                },
            ]
        },
        "model_movements": [
            {
                "model_instance_id": "intercessor_1",
                "path": [
                    {"position": {"x": 7.0, "y": 18.0, "z": 0.0}},
                    {"position": {"x": 10.0, "y": 18.0, "z": 0.0}},
                ],
                "final_pose": {"position": {"x": 10.0, "y": 18.0, "z": 0.0}},
            },
            {
                "model_instance_id": "intercessor_2",
                "path": [
                    {"position": {"x": 7.0, "y": 22.0, "z": 0.0}},
                    {"position": {"x": 7.0, "y": 22.0, "z": 0.0}},
                ],
                "final_pose": {"position": {"x": 7.0, "y": 22.0, "z": 0.0}},
            },
        ],
    }


def _model_positions(battlefield_state: JsonValue) -> dict[str, tuple[float, float]]:
    battlefield = _json_object("battlefield_state", battlefield_state)
    positions: dict[str, tuple[float, float]] = {}
    for placed_army in _json_list(battlefield, "placed_armies"):
        placed_army_payload = _json_object("placed_army", placed_army)
        for unit_placement in _json_list(placed_army_payload, "unit_placements"):
            unit_placement_payload = _json_object("unit_placement", unit_placement)
            for model_placement in _json_list(unit_placement_payload, "model_placements"):
                model_placement_payload = _json_object("model_placement", model_placement)
                pose = _json_object("pose", model_placement_payload["pose"])
                position = _json_object("position", pose["position"])
                positions[_required_string(model_placement_payload, "model_instance_id")] = (
                    _required_float(position, "x"),
                    _required_float(position, "y"),
                )
    return positions


def _json_object(name: str, payload: object) -> JsonObject:
    if type(payload) is not dict:
        raise AssertionError(f"{name} must be an object.")
    return cast(JsonObject, payload)


def _json_list(payload: JsonObject, key: str) -> list[JsonValue]:
    value = payload.get(key)
    if type(value) is not list:
        raise AssertionError(f"{key} must be a list.")
    return value


def _required_string(payload: JsonObject, key: str) -> str:
    value = payload.get(key)
    if type(value) is not str:
        raise AssertionError(f"{key} must be a string.")
    return value


def _required_float(payload: JsonObject, key: str) -> float:
    value = payload.get(key)
    if type(value) is int:
        return float(value)
    if type(value) is not float:
        raise AssertionError(f"{key} must be a number.")
    return value
