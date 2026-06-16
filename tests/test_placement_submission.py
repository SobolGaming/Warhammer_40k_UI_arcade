"""Tests for placement proposal submission orchestration."""

from __future__ import annotations

from warhammer40k_arcade_ui.core_client.fake_client import FakeCoreClient
from warhammer40k_arcade_ui.core_client.protocol import (
    UiClientStatus,
    UiDecision,
    UiEventDelta,
    UiGameView,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.state.finite_decision import FiniteDecisionUiState
from warhammer40k_arcade_ui.state.placement_draft import PlacementDraft
from warhammer40k_arcade_ui.state.placement_submission import (
    prepare_placement_submission,
    submit_placement_draft,
)
from warhammer40k_arcade_ui.state.selection import SelectionState


def test_prepare_placement_submission_preserves_request_payload_and_result_id() -> None:
    decision = _placement_proposal_decision()
    draft = _ready_draft(decision)

    invalid_status, submission, next_result_index = prepare_placement_submission(
        placement_draft=draft,
        pending_decision=decision,
        next_result_index=7,
    )

    assert invalid_status is None
    assert submission is not None
    assert submission.request_id == "decision-request-placement-001"
    assert submission.result_id == "ui-result-000007"
    assert submission.payload == draft.payload_preview
    assert next_result_index == 8


def test_prepare_placement_submission_requires_ready_payload() -> None:
    decision = _placement_proposal_decision()
    draft = _active_draft(decision).place_current_model((8.0, 18.0))

    invalid_status, submission, next_result_index = prepare_placement_submission(
        placement_draft=draft,
        pending_decision=decision,
        next_result_index=7,
    )

    assert submission is None
    assert invalid_status is not None
    assert invalid_status.invalid_diagnostics[0].violation_code == "placement_draft_not_ready"
    assert invalid_status.invalid_diagnostics[0].field == "payload"
    assert next_result_index == 7


def test_submit_placement_draft_records_generic_parameterized_submission() -> None:
    decision = _placement_proposal_decision()
    draft = _ready_draft(decision)
    accepted_status = UiClientStatus(
        stage="battle",
        status_kind="advanced",
        decision=None,
        message="Placement accepted.",
        payload={"phase_body_status": "placement_complete"},
    )
    fake = FakeCoreClient(
        status=accepted_status,
        view=_game_view(pending_decision=None),
        event_delta=UiEventDelta(
            viewer_player_id="player_1",
            cursor=3,
            next_cursor=4,
            events=(
                {
                    "event_type": "placement_proposal_accepted",
                    "payload": {"player_id": "player_1"},
                },
            ),
        ),
    )

    result = submit_placement_draft(
        state=FiniteDecisionUiState(pending_decision=decision, event_cursor=3),
        placement_draft=draft,
        client=fake,
        viewer_player_id="player_1",
    )

    assert fake.parameterized_submissions[0].request_id == "decision-request-placement-001"
    assert fake.parameterized_submissions[0].result_id == "ui-result-000001"
    assert fake.parameterized_submissions[0].payload == draft.payload_preview
    assert fake.advance_call_count == 1
    assert result.clear_placement_draft is True
    assert result.finite_state.next_result_index == 2
    assert result.finite_state.status_message == "Placement accepted."
    assert result.finite_state.event_cursor == 4
    assert result.finite_state.event_log_lines[-1] == "placement_proposal_accepted: player_1"
    assert result.viewer_player_id == "player_1"


def test_submit_placement_draft_refreshes_next_actor_viewer() -> None:
    decision = _placement_proposal_decision()
    draft = _ready_draft(decision)
    next_decision = UiDecision(
        request_id="decision-request-placement-002",
        decision_type="submit_deployment_placement",
        actor_id="player_2",
        payload={},
        options=(),
        is_parameterized=True,
    )
    accepted_status = UiClientStatus(
        stage="battle",
        status_kind="waiting_for_decision",
        decision=next_decision,
        message=None,
        payload=None,
    )
    fake = FakeCoreClient(
        status=accepted_status,
        view=_game_view(pending_decision=next_decision, viewer_player_id="player_2"),
        event_delta=UiEventDelta(
            viewer_player_id="player_2",
            cursor=3,
            next_cursor=4,
            events=(),
        ),
    )

    result = submit_placement_draft(
        state=FiniteDecisionUiState(pending_decision=decision, event_cursor=3),
        placement_draft=draft,
        client=fake,
        viewer_player_id="player_1",
    )

    assert result.viewer_player_id == "player_2"
    assert result.refreshed_view is not None
    assert result.refreshed_view.viewer_player_id == "player_2"


def test_submit_placement_draft_clears_submitted_draft_after_engine_invalid() -> None:
    decision = _placement_proposal_decision()
    draft = _ready_draft(decision)
    invalid_status = UiClientStatus.invalid(
        stage="battle",
        violation_code="invalid_placement",
        message="Placement rejected.",
        field="payload",
        payload={"invalid_reason": "invalid_placement", "field": "payload"},
        decision=decision,
    )
    fake = FakeCoreClient(
        status=invalid_status,
        view=_game_view(pending_decision=decision),
        event_delta=UiEventDelta(
            viewer_player_id="player_1",
            cursor=3,
            next_cursor=4,
            events=(),
        ),
    )

    result = submit_placement_draft(
        state=FiniteDecisionUiState(pending_decision=decision, event_cursor=3),
        placement_draft=draft,
        client=fake,
        viewer_player_id="player_1",
    )

    assert fake.parameterized_submissions[0].request_id == "decision-request-placement-001"
    assert fake.advance_call_count == 0
    assert result.clear_placement_draft is True
    assert result.finite_state.status_kind == "invalid"
    assert result.finite_state.diagnostics[0].violation_code == "invalid_placement"


def test_submit_placement_draft_without_core_client_returns_local_diagnostic() -> None:
    decision = _placement_proposal_decision()

    result = submit_placement_draft(
        state=FiniteDecisionUiState(pending_decision=decision),
        placement_draft=_ready_draft(decision),
        client=None,
        viewer_player_id="player_1",
    )

    assert result.clear_placement_draft is False
    assert result.refreshed_view is None
    assert result.finite_state.status_kind == "invalid"
    assert result.finite_state.diagnostics[0].violation_code == "no_core_client"


def _ready_draft(decision: UiDecision) -> PlacementDraft:
    draft = _active_draft(decision)
    draft = draft.place_current_model((8.0, 18.0))
    draft = draft.place_current_model((8.0, 22.0))
    return draft.place_current_model((8.0, 26.0)).mark_ready()


def _active_draft(decision: UiDecision) -> PlacementDraft:
    draft = PlacementDraft.start_for_pending(
        view=default_battlefield_view(),
        selection=SelectionState.initial(default_preferences()),
        pending_decision=decision,
    )
    assert draft is not None
    return draft


def _placement_proposal_decision() -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": "decision-request-placement-001",
            "decision_type": "submit_placement_proposal",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-placement-001",
                    "decision_type": "submit_placement_proposal",
                    "actor_id": "player_1",
                    "game_id": "phase28-game",
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": "reinforcement_placement",
                    "source_decision_request_id": "decision-request-unit-001",
                    "source_decision_result_id": "ui-result-unit-001",
                    "placement_kinds": ["reinforcement"],
                    "context": {"placement_kind": "reinforcement"},
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


def _game_view(
    *,
    pending_decision: UiDecision | None,
    viewer_player_id: str = "player_1",
) -> UiGameView:
    return UiGameView(
        viewer_player_id=viewer_player_id,
        game_id="phase28-game",
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
        event_count=0,
    )
