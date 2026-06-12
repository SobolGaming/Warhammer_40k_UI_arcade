"""Tests for finite decision focus, submission, and refresh state."""

from __future__ import annotations

from warhammer40k_arcade_ui.core_client.fake_client import FakeCoreClient
from warhammer40k_arcade_ui.core_client.protocol import (
    UiClientStatus,
    UiDecision,
    UiEventDelta,
    UiFiniteOption,
    UiGameView,
)
from warhammer40k_arcade_ui.state.finite_decision import (
    FiniteDecisionUiState,
    submit_finite_option,
)


def test_prepare_submission_preserves_request_option_and_result_ids() -> None:
    state = FiniteDecisionUiState(pending_decision=_finite_decision())

    next_state, submission = state.prepare_submission("advance")

    assert submission is not None
    assert submission.request_id == "decision-request-000004"
    assert submission.selected_option_id == "advance"
    assert submission.result_id == "ui-result-000001"
    assert next_state.next_result_index == 2


def test_prepare_submission_rejects_no_pending_request_without_result_id() -> None:
    state = FiniteDecisionUiState()

    next_state, submission = state.prepare_submission()

    assert submission is None
    assert next_state.status_kind == "invalid"
    assert next_state.diagnostics[0].violation_code == "no_pending_decision"
    assert next_state.next_result_index == 1


def test_prepare_submission_rejects_unknown_option_without_client_submission() -> None:
    state = FiniteDecisionUiState(pending_decision=_finite_decision())

    next_state, submission = state.prepare_submission("invented_option")

    assert submission is None
    assert next_state.status_kind == "invalid"
    assert next_state.diagnostics[0].violation_code == "selected_option_not_pending"
    assert next_state.next_result_index == 1


def test_prepare_submission_rejects_parameterized_request() -> None:
    state = FiniteDecisionUiState(pending_decision=_parameterized_decision())

    next_state, submission = state.prepare_submission()

    assert submission is None
    assert next_state.status_kind == "invalid"
    assert next_state.diagnostics[0].violation_code == (
        "finite_submission_for_parameterized_request"
    )


def test_fatal_game_engine_error_state_clears_pending_decision() -> None:
    state = FiniteDecisionUiState(
        pending_decision=_finite_decision(),
        highlighted_option_index=1,
    )

    next_state = state.with_fatal_game_engine_error(
        message="Fatal game engine error. Closing in 4 seconds.",
        detail="Missing engine projection field: 'request_id'.",
    )

    assert next_state.pending_decision is None
    assert next_state.highlighted_option_index == 0
    assert next_state.status_kind == "fatal"
    assert next_state.status_message == "Fatal game engine error. Closing in 4 seconds."
    assert next_state.diagnostics[0].violation_code == "fatal_game_engine_error"
    assert next_state.diagnostics[0].field == "core_engine"
    assert next_state.diagnostics[0].message == "Missing engine projection field: 'request_id'."


def test_submit_finite_option_records_client_submission_and_refreshes_events() -> None:
    follow_up_status = UiClientStatus(
        stage="battle",
        status_kind="waiting_for_decision",
        decision=_parameterized_decision(),
        payload=None,
    )
    fake = FakeCoreClient(
        status=follow_up_status,
        view=_game_view(pending_decision=_parameterized_decision()),
        event_delta=UiEventDelta(
            viewer_player_id="player-a",
            cursor=3,
            next_cursor=4,
            events=(
                {
                    "event_type": "decision_recorded",
                    "payload": {"player_id": "player-a"},
                },
            ),
        ),
    )

    next_state = submit_finite_option(
        state=FiniteDecisionUiState(
            pending_decision=_finite_decision(),
            event_cursor=3,
            event_log_lines=("ready",),
        ),
        client=fake,
        selected_option_id="normal_move",
        viewer_player_id="player-a",
    )

    assert fake.finite_submissions[0].request_id == "decision-request-000004"
    assert fake.finite_submissions[0].selected_option_id == "normal_move"
    assert fake.finite_submissions[0].result_id == "ui-result-000001"
    assert next_state.pending_decision is not None
    assert next_state.pending_decision.is_parameterized is True
    assert next_state.status_message == "Proposal required: normal_move"
    assert next_state.event_cursor == 4
    assert next_state.event_log_lines[-1] == "decision_recorded: player-a"


def test_submit_finite_option_does_not_call_client_for_parameterized_request() -> None:
    fake = FakeCoreClient(
        status=UiClientStatus(stage="battle", status_kind="advanced", payload=None),
        view=_game_view(pending_decision=None),
        event_delta=UiEventDelta(
            viewer_player_id="player-a",
            cursor=0,
            next_cursor=0,
            events=(),
        ),
    )

    next_state = submit_finite_option(
        state=FiniteDecisionUiState(pending_decision=_parameterized_decision()),
        client=fake,
        selected_option_id=None,
        viewer_player_id="player-a",
    )

    assert fake.finite_submissions == []
    assert next_state.status_kind == "invalid"
    assert next_state.diagnostics[0].violation_code == (
        "finite_submission_for_parameterized_request"
    )


def test_cycle_option_advances_highlight_without_changing_request() -> None:
    state = FiniteDecisionUiState(pending_decision=_finite_decision())

    cycled = state.cycle_option()

    assert cycled.pending_decision is state.pending_decision
    assert cycled.highlighted_option_index == 1
    assert cycled.highlighted_option is not None
    assert cycled.highlighted_option.option_id == "advance"


def test_apply_status_resets_highlight_when_request_changes() -> None:
    state = FiniteDecisionUiState(
        pending_decision=_movement_unit_decision(),
        highlighted_option_index=1,
    )

    next_state = state.apply_status(
        UiClientStatus(
            stage="battle",
            status_kind="waiting_for_decision",
            decision=_movement_action_decision_for("army-alpha:intercessor-unit-3"),
            payload=None,
        )
    )

    assert next_state.highlighted_option is not None
    assert next_state.highlighted_option.option_id == "advance"

    cycled = next_state.cycle_option()

    assert cycled.highlighted_option is not None
    assert cycled.highlighted_option.option_id == "normal_move"


def test_unit_click_does_not_retarget_ambiguous_action_options() -> None:
    state = FiniteDecisionUiState(
        pending_decision=_movement_action_decision_for("army-alpha:intercessor-unit-3"),
        highlighted_option_index=1,
    )

    next_state = state.highlight_option_for_unit("army-alpha:intercessor-unit-3")

    assert next_state.highlighted_option is not None
    assert next_state.highlighted_option.option_id == "normal_move"


def _finite_decision() -> UiDecision:
    return UiDecision(
        request_id="decision-request-000004",
        decision_type="select_movement_action",
        actor_id="player-a",
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


def _movement_unit_decision() -> UiDecision:
    return UiDecision(
        request_id="decision-request-000003",
        decision_type="select_movement_unit",
        actor_id="player-a",
        payload={"phase": "movement"},
        options=(
            UiFiniteOption(
                option_id="army-alpha:intercessor-unit-1",
                label="Intercessors Unit 1",
                payload={"unit_instance_id": "army-alpha:intercessor-unit-1"},
            ),
            UiFiniteOption(
                option_id="army-alpha:intercessor-unit-3",
                label="Intercessors Unit 3",
                payload={"unit_instance_id": "army-alpha:intercessor-unit-3"},
            ),
        ),
        is_parameterized=False,
    )


def _movement_action_decision_for(unit_id: str) -> UiDecision:
    return UiDecision(
        request_id="decision-request-000004",
        decision_type="select_movement_action",
        actor_id="player-a",
        payload={"unit_instance_id": unit_id},
        options=(
            UiFiniteOption(
                option_id="advance",
                label="Advance",
                payload={"movement_phase_action": "advance", "unit_instance_id": unit_id},
            ),
            UiFiniteOption(
                option_id="normal_move",
                label="Normal Move",
                payload={"movement_phase_action": "normal_move", "unit_instance_id": unit_id},
            ),
            UiFiniteOption(
                option_id="remain_stationary",
                label="Remain Stationary",
                payload={
                    "movement_phase_action": "remain_stationary",
                    "unit_instance_id": unit_id,
                },
            ),
        ),
        is_parameterized=False,
    )


def _parameterized_decision() -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": "decision-request-000005",
            "decision_type": "submit_movement_proposal",
            "actor_id": "player-a",
            "payload": {"proposal_request": _movement_proposal_request_payload()},
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


def _game_view(pending_decision: UiDecision | None) -> UiGameView:
    return UiGameView(
        viewer_player_id="player-a",
        game_id="phase6-game",
        stage="battle",
        battle_round=1,
        active_player_id="player-a",
        current_setup_step=None,
        current_battle_phase="movement",
        player_ids=("player-a", "player-b"),
        battlefield_state=None,
        mission_setup=None,
        public_secondary_mission_choices=(),
        public_secondary_mission_card_states=(),
        public_command_point_ledgers=(),
        public_victory_point_ledgers=(),
        public_stratagem_use_records=(),
        pending_decision=pending_decision,
        pending_proposal=None,
        event_count=4,
    )


def _movement_proposal_request_payload() -> dict[str, object]:
    return {
        "request_id": "decision-request-000005",
        "decision_type": "submit_movement_proposal",
        "actor_id": "player-a",
        "game_id": "phase6-game",
        "battle_round": 1,
        "phase": "movement",
        "unit_instance_id": "intercessor_squad",
        "proposal_kind": "normal_move",
        "source_decision_request_id": "decision-request-000004",
        "source_decision_result_id": "ui-result-000001",
        "movement_phase_action": "normal_move",
        "placement_kinds": [],
        "context": {"source_selected_option_id": "normal_move"},
    }
