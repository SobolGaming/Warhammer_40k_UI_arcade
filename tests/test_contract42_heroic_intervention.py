"""Real Contract 42 Heroic Intervention through the public UI session facade."""

from __future__ import annotations

from copy import deepcopy
from typing import cast

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession

from tests.support.contract42_charge_fixture import (
    COMMITTED,
    OTHER_REACHABLE,
    SOURCE,
    seeded_heroic_client,
)
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    JsonValue,
    UiClientSubmissionError,
    UiDecision,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.core_projection import battlefield_view_from_game_view
from warhammer40k_arcade_ui.state.assignment_submission import prepare_assignment_submission
from warhammer40k_arcade_ui.state.assignment_workspace import AssignmentWorkspace
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft
from warhammer40k_arcade_ui.state.selection import SelectionState

pytestmark = pytest.mark.integration


def _request(client: LocalSessionClient) -> UiDecision:
    status = client.advance_until_decision_or_terminal()
    assert status.status_kind == "waiting_for_decision", status
    request = status.decision
    assert request is not None
    assert request.decision_type == "submit_stratagem_target_proposal"
    assert request.actor_id == "player-a"
    assert request.parameterized_proposal is not None
    assert request.parameterized_proposal.request_id == request.request_id
    assert request.parameterized_proposal.actor_id == request.actor_id
    context = cast(JsonObject, request.parameterized_proposal.payload["context"])
    assert context["player_id"] == "player-a"
    assert context["active_player_id"] == "player-b"
    for viewer in ("player-a", "player-b"):
        view = client.get_view(viewer)
        assert view.viewer_player_id == viewer
        assert view.active_player_id == "player-b"
        assert view.pending_decision is not None
        assert view.pending_decision.request_id == request.request_id
    return request


def _source_modes(request: UiDecision) -> dict[str, JsonObject]:
    proposal = request.parameterized_proposal
    assert proposal is not None
    catalog_record = cast(JsonObject, proposal.payload["catalog_record"])
    definition = cast(JsonObject, catalog_record["definition"])
    assert definition["handler_id"] == "core:heroic-intervention"
    source_effect = cast(JsonObject, definition["effect_payload"])
    mode_rows = cast(list[JsonObject], source_effect["modes"])
    modes = {cast(str, row["mode"]): row for row in mode_rows}
    assert set(modes) == {"into_the_fray", "leap_to_defend"}
    return modes


def _proposal_payload(request: UiDecision, *, effect_selection: JsonValue) -> JsonObject:
    proposal = request.parameterized_proposal
    assert proposal is not None
    payload = proposal.payload
    return {
        "proposal": {
            "proposal_kind": payload["proposal_kind"],
            "context": deepcopy(payload["context"]),
            "catalog_record": deepcopy(payload["catalog_record"]),
            "target_binding": {
                "target_kind": "friendly_unit",
                "target_player_id": request.actor_id,
                "target_unit_instance_id": SOURCE,
            },
            "effect_selection": effect_selection,
        }
    }


def _events(client: LocalSessionClient, viewer: str, event_type: str) -> tuple[JsonObject, ...]:
    return tuple(
        event
        for event in client.get_events_since(0, viewer).events
        if event.get("event_type") == event_type
    )


def test_heroic_workspace_sees_current_actor_and_requires_explicit_intent() -> None:
    client = seeded_heroic_client()
    request = _request(client)
    _source_modes(request)
    workspace = AssignmentWorkspace.start_for_pending(request)
    assert workspace is not None
    assert workspace.is_for(request)
    assert workspace.actor_id == "player-a"
    assert workspace.declinable
    assert workspace.payload_preview is None
    assert not workspace.is_ready
    assert set(workspace.stratagem_mode_choices) == set(_source_modes(request))
    assert {row.row_id for row in workspace.rows} == {
        f"stratagem-mode:{request.request_id}:{mode}" for mode in workspace.stratagem_mode_choices
    }
    selected = workspace.with_stratagem_intent(
        request,
        target_unit_id=SOURCE,
        source_mode="into_the_fray",
    )
    assert selected.is_ready
    assert selected.payload_preview is not None
    selected_proposal = cast(JsonObject, selected.payload_preview["proposal"])
    assert selected_proposal["target_binding"] == {
        "target_kind": "friendly_unit",
        "target_player_id": request.actor_id,
        "target_unit_instance_id": SOURCE,
    }
    assert selected_proposal["effect_selection"] == {"mode": "into_the_fray"}

    invalid, submission, next_index = prepare_assignment_submission(
        assignment_workspace=workspace,
        pending_decision=request,
        next_result_index=1,
    )
    assert submission is None
    assert next_index == 1
    assert invalid is not None
    assert invalid.invalid_diagnostics[0].violation_code == "assignment_workspace_not_ready"


@pytest.mark.parametrize(
    ("effect_selection", "expected_code"),
    [
        (None, "heroic_intervention_mode_required"),
        ({}, "heroic_intervention_mode_required"),
        ({"mode": "not-in-source"}, "heroic_intervention_mode_unknown"),
    ],
)
def test_missing_or_invalid_mode_rejects_before_cp_or_state_change(
    effect_selection: JsonValue, expected_code: str
) -> None:
    client = seeded_heroic_client()
    request = _request(client)
    session = client.session
    assert isinstance(session, LocalGameSession)
    state = session.lifecycle.state
    assert state is not None
    before_state = state.to_payload()
    before_events = {
        viewer: client.get_events_since(0, viewer).events for viewer in state.player_ids
    }

    rejected = client.submit_parameterized_payload(
        request_id=request.request_id,
        payload=_proposal_payload(request, effect_selection=effect_selection),
        result_id=f"contract42-heroic-invalid-{expected_code}",
    )

    assert rejected.status_kind == "invalid"
    assert rejected.invalid_diagnostics[0].violation_code == expected_code
    assert state.to_payload() == before_state
    assert state.command_point_total("player-a") == 3
    assert state.stratagem_use_records == []
    for viewer in state.player_ids:
        assert client.get_events_since(0, viewer).events == before_events[viewer]
        pending = client.get_view(viewer).pending_decision
        assert pending is not None
        assert pending.request_id == request.request_id


@pytest.mark.parametrize("mode", ["into_the_fray", "leap_to_defend"])
def test_source_mode_continues_through_shared_charge_and_witnessed_move(mode: str) -> None:
    client = seeded_heroic_client()
    request = _request(client)
    source_mode = _source_modes(request)[mode]
    workspace = AssignmentWorkspace.start_for_pending(request)
    assert workspace is not None
    selected = workspace.with_stratagem_intent(
        request,
        target_unit_id=SOURCE,
        source_mode=cast(str, source_mode["mode"]),
    )
    payload = selected.payload_preview
    assert payload is not None
    session = client.session
    assert isinstance(session, LocalGameSession)
    state = session.lifecycle.state
    assert state is not None
    before_cp = state.command_point_total("player-a")

    accepted_use = client.submit_parameterized_payload(
        request_id=request.request_id,
        payload=payload,
        result_id=f"contract42-heroic-use-{mode}",
    )
    assert accepted_use.status_kind == "waiting_for_decision", accepted_use
    declaration = accepted_use.decision
    assert declaration is not None
    assert declaration.decision_type == "select_charging_unit"
    assert declaration.actor_id == "player-a"
    assert SOURCE in {option.option_id for option in declaration.options}
    assert state.active_player_id == "player-b"
    assert state.effective_active_player_id() == "player-a"
    assert len(state.stratagem_use_records) == 1
    use = state.stratagem_use_records[0]
    assert use.effect_selection == {"mode": mode}
    assert before_cp - state.command_point_total("player-a") == use.command_point_cost
    for viewer in state.player_ids:
        used = _events(client, viewer, "stratagem_used")
        assert len(used) == 1
        public_use = cast(JsonObject, used[0]["payload"])
        assert public_use["request_id"] == request.request_id
        assert public_use["effect_selection"] == {"mode": mode}

    before_stale_state = state.to_payload()
    with pytest.raises(UiClientSubmissionError, match="request_id does not match pending request"):
        client.submit_parameterized_payload(
            request_id=request.request_id,
            payload=payload,
            result_id=f"contract42-heroic-stale-{mode}",
        )
    assert state.to_payload() == before_stale_state

    after_declaration = client.submit_finite(
        request_id=declaration.request_id,
        selected_option_id=SOURCE,
        result_id=f"contract42-heroic-declare-{mode}",
    )
    targets = after_declaration.decision
    assert targets is not None
    assert targets.decision_type == "select_charge_targets"
    assert targets.actor_id == "player-a"
    chosen = next(
        option
        for option in targets.options
        if type(option.payload) is dict and option.payload.get("target_ids") == [COMMITTED]
    )
    after_targets = client.submit_finite(
        request_id=targets.request_id,
        selected_option_id=chosen.option_id,
        result_id=f"contract42-heroic-targets-{mode}",
    )
    movement = after_targets.decision
    assert movement is not None
    assert movement.decision_type == "submit_movement_proposal"
    assert movement.actor_id == "player-a"
    proposal = movement.movement_proposal
    assert proposal is not None
    assert proposal.proposal_kind == "charge_move"
    assert proposal.unit_instance_id == SOURCE
    assert proposal.source_decision_request_id == declaration.request_id
    assert proposal.source_decision_result_id == f"contract42-heroic-declare-{mode}"
    context = proposal.context
    assert context["target_selection"] == {
        "request_id": targets.request_id,
        "result_id": f"contract42-heroic-targets-{mode}",
        "unit_instance_id": SOURCE,
        "target_ids": [COMMITTED],
    }
    budget = cast(JsonObject, context["movement_budget"])
    charge_roll = cast(JsonObject, context["charge_roll"])
    roll_request = cast(JsonObject, charge_roll["request"])
    assert roll_request["player_id"] == movement.actor_id
    maximum_distance = budget["maximum_distance_inches"]
    roll_value = charge_roll["value"]
    assert isinstance(maximum_distance, (int, float))
    assert isinstance(roll_value, (int, float))
    assert maximum_distance == context["maximum_distance_inches"]
    assert maximum_distance > roll_value
    if mode == "into_the_fray":
        limit = cast(JsonObject, budget["roll_limit"])
        source_proposal = request.parameterized_proposal
        assert source_proposal is not None
        catalog_record = cast(JsonObject, source_proposal.payload["catalog_record"])
        definition = cast(JsonObject, catalog_record["definition"])
        assert limit["source_id"] == definition["source_id"]
        assert charge_roll["value"] == limit["maximum"]
    else:
        assert budget["roll_limit"] is None
        modified_roll = cast(JsonObject, budget["modified_roll"])
        assert charge_roll["value"] == modified_roll["final_value"]

    owner_view = client.get_view("player-a")
    battlefield = battlefield_view_from_game_view(owner_view)
    source = next(unit for unit in battlefield.units if unit.unit_id == SOURCE)
    first = source.models[0]
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_model_id(
        unit_id=SOURCE, model_id=first.model_id, preferences=preferences
    )
    draft = MovementDraft.start_for_pending(
        view=battlefield, selection=selection, pending_decision=movement
    )
    assert draft is not None
    assert draft.movement_budget_inches == budget["maximum_distance_inches"]
    group_x = sum(model.position[0] for model in source.models) / len(source.models)
    ready = (
        draft.select_current_group(view=battlefield)
        .add_waypoint(view=battlefield, world_point=(group_x, first.position[1] + 2))
        .add_waypoint(view=battlefield, world_point=(group_x, first.position[1] + 4))
        .mark_ready(view=battlefield)
    )
    move_payload = ready.payload_preview
    assert move_payload is not None
    assert move_payload["proposal_request_id"] == movement.request_id
    assert move_payload["charge_target_unit_instance_ids"] == [COMMITTED]
    assert ready.synthetic_witness_model_ids == ()
    witness = cast(JsonObject, move_payload["witness"])
    model_paths = cast(list[JsonObject], witness["model_paths"])
    assert len(model_paths) == len(source.models)

    before_move_state = state.to_payload()
    wrong_targets: JsonObject = {
        **move_payload,
        "charge_target_unit_instance_ids": [OTHER_REACHABLE],
    }
    rejected = client.submit_movement_payload(
        request_id=movement.request_id,
        payload=wrong_targets,
        result_id=f"contract42-heroic-wrong-target-{mode}",
    )
    assert rejected.status_kind == "invalid"
    assert rejected.invalid_diagnostics[0].violation_code == "charge_target_not_reachable"
    assert state.to_payload() == before_move_state

    accepted_move = client.submit_movement_payload(
        request_id=movement.request_id,
        payload=move_payload,
        result_id=f"contract42-heroic-move-{mode}",
    )
    assert accepted_move.status_kind != "invalid", accepted_move.invalid_diagnostics
    assert state.to_payload() != before_move_state
    for viewer in state.player_ids:
        assert len(_events(client, viewer, "charge_move_completed")) == 1
