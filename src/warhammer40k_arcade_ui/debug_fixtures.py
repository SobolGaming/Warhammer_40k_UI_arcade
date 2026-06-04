"""Opt-in debug fixtures for manual UI validation."""

from __future__ import annotations

from warhammer40k_arcade_ui.core_client.fake_client import FakeCoreClient
from warhammer40k_arcade_ui.core_client.protocol import (
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
                    "context": {"source_selected_option_id": "normal_move"},
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


def _phase6_debug_view(pending_decision: UiDecision) -> UiGameView:
    return UiGameView(
        viewer_player_id="player_1",
        game_id="phase6-debug-game",
        stage="battle",
        battle_round=1,
        active_player_id="player_1",
        current_setup_step=None,
        current_battle_phase="movement",
        player_ids=("player_1", "player_2"),
        battlefield_state=None,
        mission_setup=None,
        public_secondary_mission_choices=(),
        public_secondary_mission_card_states=(),
        public_command_point_ledgers=(),
        public_victory_point_ledgers=(),
        public_stratagem_use_records=(),
        pending_decision=pending_decision,
        pending_proposal=None,
        event_count=1,
    )
