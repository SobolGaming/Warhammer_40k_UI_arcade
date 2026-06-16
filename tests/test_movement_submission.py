"""Tests for movement proposal submission orchestration."""

from __future__ import annotations

from dataclasses import replace

from warhammer40k_arcade_ui.core_client.fake_client import FakeCoreClient
from warhammer40k_arcade_ui.core_client.protocol import (
    UiClientStatus,
    UiDecision,
    UiEventDelta,
    UiFiniteOption,
    UiGameView,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.state.finite_decision import FiniteDecisionUiState
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft
from warhammer40k_arcade_ui.state.movement_submission import (
    prepare_movement_submission,
    submit_movement_draft,
)
from warhammer40k_arcade_ui.state.selection import SelectionState


def test_prepare_movement_submission_preserves_request_payload_and_result_id() -> None:
    decision = _movement_proposal_decision()
    draft = _ready_draft(decision)

    invalid_status, submission, next_result_index = prepare_movement_submission(
        movement_draft=draft,
        pending_decision=decision,
        next_result_index=4,
    )

    assert invalid_status is None
    assert submission is not None
    assert submission.request_id == "decision-request-000005"
    assert submission.result_id == "ui-result-000004"
    assert submission.payload["proposal_request_id"] == "decision-request-000005"
    assert next_result_index == 5


def test_prepare_movement_submission_rejects_stale_request_before_client_submission() -> None:
    original_decision = _movement_proposal_decision()
    stale_decision = _movement_proposal_decision(request_id="decision-request-000006")
    draft = _ready_draft(original_decision)

    invalid_status, submission, next_result_index = prepare_movement_submission(
        movement_draft=draft,
        pending_decision=stale_decision,
        next_result_index=4,
    )

    assert submission is None
    assert invalid_status is not None
    assert invalid_status.invalid_diagnostics[0].violation_code == "stale_request_id"
    assert invalid_status.invalid_diagnostics[0].field == "request_id"
    assert next_result_index == 4


def test_prepare_movement_submission_rejects_unsupported_parameterized_request() -> None:
    draft = _ready_draft(_movement_proposal_decision())

    invalid_status, submission, next_result_index = prepare_movement_submission(
        movement_draft=draft,
        pending_decision=_shooting_proposal_decision(),
        next_result_index=4,
    )

    assert submission is None
    assert invalid_status is not None
    assert invalid_status.invalid_diagnostics[0].violation_code == (
        "unsupported_parameterized_request"
    )
    assert invalid_status.invalid_diagnostics[0].field == "decision_type"
    assert next_result_index == 4


def test_prepare_movement_submission_requires_ready_payload() -> None:
    decision = _movement_proposal_decision()
    draft = _active_draft(decision).add_waypoint(
        view=default_battlefield_view(),
        world_point=(10.0, 18.0),
    )

    invalid_status, submission, next_result_index = prepare_movement_submission(
        movement_draft=draft,
        pending_decision=decision,
        next_result_index=4,
    )

    assert submission is None
    assert invalid_status is not None
    assert invalid_status.invalid_diagnostics[0].violation_code == "movement_draft_not_ready"
    assert invalid_status.invalid_diagnostics[0].field == "payload"
    assert next_result_index == 4


def test_submit_movement_draft_records_client_submission_and_clears_on_acceptance() -> None:
    decision = _movement_proposal_decision()
    draft = _ready_draft(decision)
    accepted_status = UiClientStatus(
        stage="battle",
        status_kind="advanced",
        decision=None,
        message="Movement accepted.",
        payload={"phase_body_status": "movement_complete"},
    )
    fake = FakeCoreClient(
        status=accepted_status,
        view=_game_view(pending_decision=None),
        event_delta=UiEventDelta(
            viewer_player_id="player_1",
            cursor=2,
            next_cursor=3,
            events=(
                {
                    "event_type": "movement_proposal_accepted",
                    "payload": {"player_id": "player_1"},
                },
            ),
        ),
    )

    result = submit_movement_draft(
        state=FiniteDecisionUiState(
            pending_decision=decision,
            event_cursor=2,
            event_log_lines=("movement proposal pending",),
        ),
        movement_draft=draft,
        client=fake,
        viewer_player_id="player_1",
    )

    assert fake.movement_submissions[0].request_id == "decision-request-000005"
    assert fake.movement_submissions[0].result_id == "ui-result-000001"
    assert fake.movement_submissions[0].payload == draft.payload_preview
    assert fake.advance_call_count == 1
    assert result.clear_movement_draft is True
    assert result.finite_state.next_result_index == 2
    assert result.finite_state.status_message == "Movement accepted."
    assert result.finite_state.event_cursor == 3
    assert result.finite_state.event_log_lines[-1] == "movement_proposal_accepted: player_1"


def test_submit_movement_draft_surfaces_invalid_diagnostics_and_keeps_draft() -> None:
    decision = _movement_proposal_decision()
    retry_decision = _movement_proposal_decision(request_id="decision-request-000006")
    draft = _ready_draft(decision)
    invalid_status = UiClientStatus.from_payload(
        {
            "stage": "battle",
            "status_kind": "invalid",
            "decision_request": retry_decision_payload(retry_decision),
            "message": "Normal Move path is not legal.",
            "payload": {
                "proposal_validation": {
                    "proposal_request_id": "decision-request-000005",
                    "proposal_kind": "normal_move",
                    "is_valid": False,
                    "status": "invalid",
                    "violations": [
                        {
                            "violation_code": "movement_budget_exceeded",
                            "message": "Normal Move path exceeds the movement budget.",
                            "field": "witness",
                        }
                    ],
                }
            },
        }
    )
    fake = FakeCoreClient(
        status=invalid_status,
        view=_game_view(pending_decision=retry_decision),
        event_delta=UiEventDelta(
            viewer_player_id="player_1",
            cursor=0,
            next_cursor=1,
            events=(
                {
                    "event_type": "movement_proposal_invalid",
                    "payload": {"status": "invalid"},
                },
            ),
        ),
    )

    result = submit_movement_draft(
        state=FiniteDecisionUiState(pending_decision=decision),
        movement_draft=draft,
        client=fake,
        viewer_player_id="player_1",
    )
    retry_draft = draft.with_retry_request(
        view=default_battlefield_view(),
        pending_decision=retry_decision,
    )

    assert result.clear_movement_draft is False
    assert fake.advance_call_count == 0
    assert result.finite_state.pending_decision == retry_decision
    assert result.finite_state.diagnostics[0].violation_code == "movement_budget_exceeded"
    assert result.finite_state.diagnostics[0].field == "witness"
    assert retry_draft.proposal_request_id == "decision-request-000006"
    assert retry_draft.payload_preview is None
    assert retry_draft.model_paths == draft.model_paths


def test_submit_movement_draft_without_core_client_returns_local_diagnostic() -> None:
    decision = _movement_proposal_decision()

    result = submit_movement_draft(
        state=FiniteDecisionUiState(pending_decision=decision),
        movement_draft=_ready_draft(decision),
        client=None,
        viewer_player_id="player_1",
    )

    assert result.clear_movement_draft is False
    assert result.refreshed_view is None
    assert result.finite_state.diagnostics[0].violation_code == "no_core_client"


def test_submit_scout_move_draft_uses_generic_parameterized_submission() -> None:
    decision = _scout_move_proposal_decision()
    draft = _ready_draft(decision)
    accepted_status = UiClientStatus(
        stage="battle",
        status_kind="advanced",
        decision=None,
        message="Scout Move accepted.",
        payload={"phase_body_status": "scout_move_complete"},
    )
    fake = FakeCoreClient(
        status=accepted_status,
        view=_game_view(pending_decision=None),
        event_delta=UiEventDelta(
            viewer_player_id="player_1",
            cursor=2,
            next_cursor=3,
            events=(
                {
                    "event_type": "prebattle_scout_move_completed",
                    "payload": {"player_id": "player_1"},
                },
            ),
        ),
    )

    result = submit_movement_draft(
        state=FiniteDecisionUiState(
            pending_decision=decision,
            event_cursor=2,
            event_log_lines=("scout move pending",),
        ),
        movement_draft=draft,
        client=fake,
        viewer_player_id="player_1",
    )

    assert fake.movement_submissions == []
    assert fake.parameterized_submissions[0].request_id == "decision-request-scout-001"
    assert fake.parameterized_submissions[0].payload == draft.payload_preview
    assert result.clear_movement_draft is True


def _active_draft(decision: UiDecision) -> MovementDraft:
    view = default_battlefield_view()
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(),
        pending_decision=decision,
    )
    assert draft is not None
    return draft


def _ready_draft(decision: UiDecision) -> MovementDraft:
    view = default_battlefield_view()
    return (
        _active_draft(decision)
        .add_waypoint(
            view=view,
            world_point=(10.0, 18.0),
        )
        .mark_ready(view=view)
    )


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
    request_id: str = "decision-request-000005",
) -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": request_id,
            "decision_type": "submit_movement_proposal",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": request_id,
                    "decision_type": "submit_movement_proposal",
                    "actor_id": "player_1",
                    "game_id": "phase10-game",
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


def _scout_move_proposal_decision() -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": "decision-request-scout-001",
            "decision_type": "submit_scout_move",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-scout-001",
                    "decision_type": "submit_scout_move",
                    "actor_id": "player_1",
                    "game_id": "phase29-scout-game",
                    "setup_step": "resolve_prebattle_actions",
                    "player_id": "player_1",
                    "unit_instance_id": "intercessor_squad",
                    "component_unit_instance_ids": ["intercessor_squad"],
                    "model_instance_ids": ["intercessor_1", "intercessor_2", "intercessor_3"],
                    "proposal_kind": "scout_move",
                    "action_kind": "scout_move",
                    "source_rule_id": "core:scouts",
                    "placement_kind": None,
                    "scout_distance_inches": 6.0,
                    "deployment_zone_ids": ["deployment-zone-a"],
                    "legal_deployment_zones": [],
                    "mission_setup": {},
                    "ruleset_descriptor_hash": "ruleset-phase29",
                    "source_decision_request_id": "decision-request-prebattle-001",
                    "source_decision_result_id": "ui-result-prebattle-001",
                    "context": {"source_selected_option_id": "scout_move:intercessor_squad"},
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


def _shooting_proposal_decision() -> UiDecision:
    proposal = _movement_proposal_decision().parameterized_proposal
    assert proposal is not None
    return replace(
        _movement_proposal_decision(),
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


def retry_decision_payload(decision: UiDecision) -> dict[str, object]:
    return {
        "request_id": decision.request_id,
        "decision_type": decision.decision_type,
        "actor_id": decision.actor_id,
        "payload": decision.payload,
        "options": [option_payload(option) for option in decision.options],
        "is_parameterized": decision.is_parameterized,
    }


def option_payload(option: UiFiniteOption) -> dict[str, object]:
    return {
        "option_id": option.option_id,
        "label": option.label,
        "payload": option.payload,
    }


def _game_view(pending_decision: UiDecision | None) -> UiGameView:
    return UiGameView(
        viewer_player_id="player_1",
        game_id="phase10-game",
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
