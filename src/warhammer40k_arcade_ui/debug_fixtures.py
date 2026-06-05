"""Opt-in debug fixtures for manual UI validation."""

from __future__ import annotations

from typing import cast

from warhammer40k_arcade_ui.core_client.fake_client import FakeCoreClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    JsonValue,
    UiClientStatus,
    UiDecision,
    UiEventDelta,
    UiFiniteOption,
    UiGameView,
)


def phase6_debug_pending_decision() -> UiDecision:
    """Return a finite request targeting the default fixture Intercessors."""

    return UiDecision(
        request_id="decision-request-phase6-debug-000001",
        decision_type="select_movement_action",
        actor_id="player_1",
        payload={"unit_instance_id": "intercessor_squad"},
        options=(
            UiFiniteOption(
                option_id="normal_move",
                label="Normal Move",
                payload={"movement_phase_action": "normal_move"},
            ),
            UiFiniteOption(
                option_id="advance",
                label="Advance",
                payload={"movement_phase_action": "advance"},
            ),
        ),
        is_parameterized=False,
    )


def phase6_debug_core_client() -> FakeCoreClient:
    """Return a fake client that advances the finite action into a proposal request."""

    proposal_decision = phase6_debug_parameterized_decision()
    return FakeCoreClient(
        status=UiClientStatus(
            stage="battle",
            status_kind="waiting_for_decision",
            decision=proposal_decision,
            payload=None,
        ),
        view=_phase6_debug_view(pending_decision=proposal_decision),
        event_delta=UiEventDelta(
            viewer_player_id="player_1",
            cursor=0,
            next_cursor=1,
            events=(
                {
                    "event_type": "decision_recorded",
                    "payload": {"player_id": "player_1"},
                },
            ),
        ),
        movement_status=UiClientStatus(
            stage="battle",
            status_kind="advanced",
            decision=None,
            message="Debug movement accepted.",
            payload={"phase_body_status": "debug_movement_accepted"},
        ),
        movement_event_delta=UiEventDelta(
            viewer_player_id="player_1",
            cursor=1,
            next_cursor=4,
            events=(
                {
                    "event_type": "movement_proposal_submitted",
                    "payload": {"player_id": "player_1", "status": "debug_submitted"},
                },
                {
                    "event_type": "movement_proposal_accepted",
                    "payload": {"player_id": "player_1", "status": "debug_accepted"},
                },
                {
                    "event_type": "battlefield_projection_refreshed",
                    "payload": {"status": "debug_movement_success"},
                },
            ),
        ),
        movement_view_from_payload=_phase10_debug_view_from_movement_payload,
    )


def phase6_debug_parameterized_decision() -> UiDecision:
    """Return the proposal-required follow-up displayed after debug finite submission."""

    return UiDecision.from_payload(
        {
            "request_id": "decision-request-phase6-debug-000002",
            "decision_type": "submit_movement_proposal",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-phase6-debug-000002",
                    "decision_type": "submit_movement_proposal",
                    "actor_id": "player_1",
                    "game_id": "phase6-debug-game",
                    "battle_round": 1,
                    "phase": "movement",
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": "normal_move",
                    "source_decision_request_id": "decision-request-phase6-debug-000001",
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


def _phase6_debug_view(
    pending_decision: UiDecision | None,
    *,
    battlefield_state: JsonValue = None,
    event_count: int = 1,
) -> UiGameView:
    return UiGameView(
        viewer_player_id="player_1",
        game_id="phase6-debug-game",
        stage="battle",
        battle_round=1,
        active_player_id="player_1",
        current_setup_step=None,
        current_battle_phase="movement",
        player_ids=("player_1", "player_2"),
        battlefield_state=battlefield_state,
        mission_setup=None,
        public_secondary_mission_choices=(),
        public_secondary_mission_card_states=(),
        public_command_point_ledgers=(),
        public_victory_point_ledgers=(),
        public_stratagem_use_records=(),
        pending_decision=pending_decision,
        pending_proposal=None,
        event_count=event_count,
    )


def _phase10_debug_view_from_movement_payload(payload: JsonValue) -> UiGameView:
    return _phase6_debug_view(
        pending_decision=None,
        battlefield_state=_battlefield_projection_from_movement_payload(payload),
        event_count=4,
    )


def _battlefield_projection_from_movement_payload(payload: JsonValue) -> JsonObject:
    body = _json_object("movement payload", payload)
    unit_instance_id = _required_string(body, "unit_instance_id")
    model_movements = _required_list(body, "model_movements")
    model_placements: list[JsonValue] = []
    for movement in model_movements:
        movement_body = _json_object("model movement", movement)
        model_placements.append(
            {
                "army_id": "phase10-debug-army",
                "player_id": "player_1",
                "unit_instance_id": unit_instance_id,
                "model_instance_id": _required_string(
                    movement_body,
                    "model_instance_id",
                ),
                "pose": _json_object(
                    "model movement final_pose",
                    movement_body.get("final_pose"),
                ),
            }
        )
    return {
        "battlefield_id": "phase10-debug-battlefield",
        "placed_armies": [
            {
                "army_id": "phase10-debug-army",
                "player_id": "player_1",
                "unit_placements": [
                    {
                        "army_id": "phase10-debug-army",
                        "player_id": "player_1",
                        "unit_instance_id": unit_instance_id,
                        "model_placements": model_placements,
                    }
                ],
            }
        ],
        "removed_model_ids": [],
    }


def _json_object(name: str, payload: object) -> JsonObject:
    if type(payload) is not dict:
        raise ValueError(f"{name} must be a JSON object.")
    return cast(JsonObject, payload)


def _required_list(payload: JsonObject, key: str) -> list[JsonValue]:
    value = payload.get(key)
    if type(value) is not list:
        raise ValueError(f"{key} must be a JSON list.")
    return value


def _required_string(payload: JsonObject, key: str) -> str:
    value = payload.get(key)
    if type(value) is not str or not value:
        raise ValueError(f"{key} must be a non-empty string.")
    return value
