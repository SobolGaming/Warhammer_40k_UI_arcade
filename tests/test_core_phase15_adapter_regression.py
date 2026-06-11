"""Regression tests for current core Phase 15D-15F adapter surfaces."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import cast

import pytest

from warhammer40k_arcade_ui.core_client.fake_client import FakeCoreClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    JsonValue,
    UiClientProtocolError,
    UiClientStatus,
    UiDecision,
    UiEventDelta,
    UiGameView,
    UiParameterizedProposalRequest,
)
from warhammer40k_arcade_ui.hud.view_models import (
    build_assignment_hud_panel,
    build_movement_draft_panel,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.state.finite_decision import FiniteDecisionUiState, submit_finite_option
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft
from warhammer40k_arcade_ui.state.movement_submission import prepare_movement_submission
from warhammer40k_arcade_ui.state.selection import SelectionState

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "phase21a_core_requests.json"
PARAMETERIZED_OPTION: JsonObject = {"submission_kind": "parameterized"}


def test_phase21a_current_core_pending_proposals_are_strict_and_json_safe() -> None:
    fixture = _fixture()
    pending_proposals = _object_section(fixture, "pending_proposals")

    for name, proposal in pending_proposals.items():
        parsed = UiParameterizedProposalRequest.from_payload(proposal)
        decision = UiDecision.from_payload(_parameterized_decision_payload(proposal))

        assert parsed.request_id == _required_str(proposal, "request_id"), name
        assert parsed.decision_type == _required_str(proposal, "decision_type"), name
        assert parsed.actor_id == _required_str(proposal, "actor_id"), name
        assert parsed.payload == proposal
        assert decision.is_parameterized is True
        assert decision.parameterized_proposal is not None
        assert decision.parameterized_proposal.payload == proposal


@pytest.mark.parametrize(
    "missing_key",
    [
        pytest.param("request_id"),
        pytest.param("decision_type"),
        pytest.param("actor_id"),
    ],
)
def test_phase21a_pending_proposal_metadata_is_required(missing_key: str) -> None:
    proposal = _proposal("stratagem_counteroffensive")
    proposal.pop(missing_key)

    with pytest.raises(UiClientProtocolError, match=f"{missing_key} is required"):
        UiGameView.from_payload(_game_view_payload(pending_proposal=proposal))


@pytest.mark.parametrize(
    ("proposal_name", "expected_kind"),
    [
        ("pile_in", "pile_in"),
        ("consolidate", "consolidate"),
        ("heroic_intervention_charge_move", "charge_move"),
        ("placement_reinforcement", "reinforcement_placement"),
        ("melee_declaration", "melee_declaration"),
        ("stratagem_counteroffensive", "stratagem_target_binding"),
    ],
)
def test_phase21a_unsupported_parameterized_requests_render_without_draft(
    proposal_name: str,
    expected_kind: str,
) -> None:
    decision = _parameterized_decision(proposal_name)
    view = default_battlefield_view()
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(),
        pending_decision=decision,
    )

    movement_panel = build_movement_draft_panel(
        movement_draft=draft,
        pending_decision=decision,
    )
    assignment_panel = build_assignment_hud_panel(
        movement_draft=draft,
        pending_decision=decision,
        highlighted_option_index=0,
        diagnostics=(),
        preferences=default_preferences(),
        preference_source_label="default.yaml",
        debug_visible=False,
    )

    assert draft is None
    assert movement_panel is not None
    assert movement_panel.status_line == f"Unsupported proposal tool: {expected_kind}"
    assert movement_panel.proposal_kind == expected_kind
    assert assignment_panel is not None
    assert assignment_panel.operation_kind == "unsupported"
    assert assignment_panel.proposal_kind == expected_kind
    assert assignment_panel.groups[0].label == f"Unsupported proposal tool: {expected_kind}"
    assert assignment_panel.advisory_lines == (
        "Visible request only; no local assignment payload will be built.",
    )


@pytest.mark.parametrize(
    "proposal_name",
    [
        pytest.param("pile_in"),
        pytest.param("consolidate"),
        pytest.param("heroic_intervention_charge_move"),
    ],
)
def test_phase21a_movement_submission_blocks_unsupported_movement_kinds(
    proposal_name: str,
) -> None:
    supported_decision = _normal_move_decision()
    draft = _ready_movement_draft(supported_decision)
    unsupported_decision = _parameterized_decision_with_request_id(
        proposal_name=proposal_name,
        request_id=draft.proposal_request_id,
    )

    invalid_status, submission, next_result_index = prepare_movement_submission(
        movement_draft=draft,
        pending_decision=unsupported_decision,
        next_result_index=4,
    )

    assert submission is None
    assert invalid_status is not None
    assert invalid_status.invalid_diagnostics[0].violation_code == (
        "unsupported_movement_proposal_kind"
    )
    assert invalid_status.invalid_diagnostics[0].field == "proposal_kind"
    assert next_result_index == 4


@pytest.mark.parametrize(
    ("decision_name", "option_id"),
    [
        ("complete_reinforcements", "complete_reinforcements"),
        ("complete_disembarks", "complete_disembarks"),
        ("complete_shooting_phase", "complete_shooting_phase"),
        ("complete_charge_phase", "complete_charge_phase"),
        ("eligible_to_fight_pass", "eligible_to_fight_pass"),
        ("decline_fight_interrupt", "decline_fight_interrupt"),
    ],
)
def test_phase21a_finite_completion_and_decline_options_submit_exact_ids(
    decision_name: str,
    option_id: str,
) -> None:
    decision = _finite_decision(decision_name)
    fake = FakeCoreClient(
        status=UiClientStatus(stage="battle", status_kind="advanced", payload=None),
        view=_game_view(pending_decision=None),
        event_delta=UiEventDelta(
            viewer_player_id="player_1",
            cursor=0,
            next_cursor=0,
            events=(),
        ),
    )

    next_state = submit_finite_option(
        state=FiniteDecisionUiState(pending_decision=decision),
        client=fake,
        selected_option_id=option_id,
        viewer_player_id="player_1",
    )

    assert fake.finite_submissions[0].request_id == decision.request_id
    assert fake.finite_submissions[0].selected_option_id == option_id
    assert fake.finite_submissions[0].result_id == "ui-result-000001"
    assert next_state.pending_decision is None


def _fixture() -> JsonObject:
    payload: object = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if type(payload) is not dict:
        raise AssertionError("Phase 21A fixture must be a JSON object.")
    return cast(JsonObject, payload)


def _object_section(payload: JsonObject, key: str) -> dict[str, JsonObject]:
    section = payload[key]
    if type(section) is not dict:
        raise AssertionError(f"Fixture section {key} must be an object.")
    return cast(dict[str, JsonObject], section)


def _proposal(name: str) -> JsonObject:
    return _copy_object(_object_section(_fixture(), "pending_proposals")[name])


def _finite_decision(name: str) -> UiDecision:
    return UiDecision.from_payload(
        _copy_object(_object_section(_fixture(), "finite_decisions")[name])
    )


def _parameterized_decision(name: str) -> UiDecision:
    return UiDecision.from_payload(_parameterized_decision_payload(_proposal(name)))


def _parameterized_decision_with_request_id(*, proposal_name: str, request_id: str) -> UiDecision:
    proposal = _proposal(proposal_name)
    proposal["request_id"] = request_id
    return UiDecision.from_payload(_parameterized_decision_payload(proposal))


def _parameterized_decision_payload(proposal: JsonObject) -> JsonObject:
    return {
        "request_id": _required_str(proposal, "request_id"),
        "decision_type": _required_str(proposal, "decision_type"),
        "actor_id": _required_str(proposal, "actor_id"),
        "payload": {"proposal_request": proposal},
        "is_parameterized": True,
        "options": [
            {
                "option_id": "submit_parameterized_payload",
                "label": "Submit Parameterized Payload",
                "payload": PARAMETERIZED_OPTION,
            }
        ],
    }


def _normal_move_decision() -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": "decision-request-normal-move-001",
            "decision_type": "submit_movement_proposal",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-normal-move-001",
                    "decision_type": "submit_movement_proposal",
                    "actor_id": "player_1",
                    "game_id": "phase21a-normal-move-game",
                    "battle_round": 1,
                    "phase": "movement",
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": "normal_move",
                    "source_decision_request_id": "decision-request-action-001",
                    "source_decision_result_id": "ui-result-action-001",
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
                    "payload": PARAMETERIZED_OPTION,
                }
            ],
        }
    )


def _ready_movement_draft(decision: UiDecision) -> MovementDraft:
    view = default_battlefield_view()
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(),
        pending_decision=decision,
    )
    assert draft is not None
    return draft.add_waypoint(view=view, world_point=(10.0, 18.0)).mark_ready(view=view)


def _selected_intercessors() -> SelectionState:
    view = default_battlefield_view()
    preferences = default_preferences()
    return SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )


def _game_view_payload(*, pending_proposal: JsonValue) -> JsonObject:
    return {
        "viewer_player_id": "player_1",
        "game_id": "phase21a-game",
        "stage": "battle",
        "battle_round": 1,
        "active_player_id": "player_1",
        "current_setup_step": None,
        "current_battle_phase": "fight",
        "player_ids": ["player_1", "player_2"],
        "battlefield_state": None,
        "mission_setup": None,
        "public_secondary_mission_choices": [],
        "public_secondary_mission_card_states": [],
        "public_command_point_ledgers": [],
        "public_victory_point_ledgers": [],
        "public_stratagem_use_records": [],
        "pending_decision": None,
        "pending_proposal": pending_proposal,
        "event_count": 0,
    }


def _game_view(*, pending_decision: UiDecision | None) -> UiGameView:
    return UiGameView(
        viewer_player_id="player_1",
        game_id="phase21a-game",
        stage="battle",
        battle_round=1,
        active_player_id="player_1",
        current_setup_step=None,
        current_battle_phase="fight",
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


def _copy_object(payload: JsonObject) -> JsonObject:
    return copy.deepcopy(payload)


def _required_str(payload: JsonObject, key: str) -> str:
    value = payload[key]
    if type(value) is not str:
        raise AssertionError(f"{key} must be a string in the Phase 21A fixture.")
    return value
