"""Contract 42 Charge targets through the real public local-session facade."""

from __future__ import annotations

from typing import cast

import pytest
from warhammer40k_core.engine.event_log import JsonValue

from tests.support.contract42_charge_fixture import (
    COMMITTED,
    OTHER_REACHABLE,
    SOURCE,
    seeded_charge_client,
)
from warhammer40k_arcade_ui.core_client.protocol import JsonObject, UiClientStatus, UiDecision
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.core_projection import battlefield_view_from_game_view
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft
from warhammer40k_arcade_ui.state.selection import SelectionState

pytestmark = pytest.mark.integration


def test_charge_draft_submits_only_committed_reachable_target() -> None:
    client = seeded_charge_client()
    selection_request = _decision(client.advance_until_decision_or_terminal())
    assert selection_request.decision_type == "select_charging_unit"
    assert selection_request.actor_id == "player-a"

    target_request = _decision(
        client.submit_finite(
            request_id=selection_request.request_id,
            selected_option_id=SOURCE,
            result_id="charge-select-source",
        )
    )
    if target_request.decision_type == "use_stratagem":
        target_request = _decision(
            client.submit_finite(
                request_id=target_request.request_id,
                selected_option_id="decline_stratagem_window",
                result_id="charge-decline-reroll",
            )
        )
    assert target_request.decision_type == "select_charge_targets"
    chosen = next(
        option
        for option in target_request.options
        if isinstance(option.payload, dict) and option.payload.get("target_ids") == [COMMITTED]
    )
    move_request = _decision(
        client.submit_finite(
            request_id=target_request.request_id,
            selected_option_id=chosen.option_id,
            result_id="charge-select-target-subset",
        )
    )
    assert move_request.decision_type == "submit_movement_proposal"
    assert move_request.actor_id == "player-a"
    proposal = move_request.movement_proposal
    assert proposal is not None
    assert proposal.unit_instance_id == SOURCE
    assert proposal.proposal_kind == "charge_move"
    assert proposal.source_decision_request_id == selection_request.request_id
    assert proposal.source_decision_result_id == "charge-select-source"
    context = proposal.context
    assert context["target_selection"] == {
        "request_id": target_request.request_id,
        "result_id": "charge-select-target-subset",
        "unit_instance_id": SOURCE,
        "target_ids": [COMMITTED],
    }
    assert set(cast(list[str], context["reachable_target_unit_instance_ids"])) == {
        COMMITTED,
        OTHER_REACHABLE,
    }
    budget = cast(dict[str, JsonValue], context["movement_budget"])
    modified_roll = cast(dict[str, JsonValue], budget["modified_roll"])
    charge_roll = cast(dict[str, JsonValue], context["charge_roll"])
    roll_request = cast(dict[str, JsonValue], charge_roll["request"])
    assert roll_request["player_id"] == move_request.actor_id
    assert roll_request["unit_instance_id"] == SOURCE
    assert roll_request["source_decision_request_id"] == selection_request.request_id
    assert roll_request["source_decision_result_id"] == "charge-select-source"
    assert charge_roll["value"] == modified_roll["final_value"]
    assert modified_roll["final_value"] == 12
    assert budget["maximum_distance_inches"] == context["maximum_distance_inches"] == 14.5
    distance_modifiers = budget["distance_modifiers"]
    assert type(distance_modifiers) is list
    assert any(
        type(modifier) is dict
        and type(modifier.get("source_id")) is str
        and bool(modifier["source_id"])
        and modifier["delta_inches"] == 2.5
        for modifier in distance_modifiers
    )

    projected = client.get_view("player-a")
    assert projected.pending_decision is not None
    assert projected.pending_decision.request_id == move_request.request_id
    battlefield = battlefield_view_from_game_view(projected)
    source = next(unit for unit in battlefield.units if unit.unit_id == SOURCE)
    first = source.models[0]
    preferences = default_preferences()
    ui_selection = SelectionState.initial(preferences).select_model_id(
        unit_id=SOURCE, model_id=first.model_id, preferences=preferences
    )
    draft = MovementDraft.start_for_pending(
        view=battlefield, selection=ui_selection, pending_decision=move_request
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
    payload = ready.payload_preview
    assert payload is not None
    assert payload["charge_target_unit_instance_ids"] == [COMMITTED]
    assert payload["proposal_request_id"] == move_request.request_id
    assert payload["unit_instance_id"] == SOURCE
    assert ready.synthetic_witness_model_ids == ()
    assert ready.assigned_model_count == len(source.models)
    witness = payload["witness"]
    assert type(witness) is dict
    model_paths = witness["model_paths"]
    assert type(model_paths) is list
    assert len(model_paths) == len(source.models)

    before_battlefield = client.get_view("player-a").battlefield_view
    before_events = client.get_events_since(0, "player-a").events
    wrong: JsonObject = {**payload, "charge_target_unit_instance_ids": [OTHER_REACHABLE]}
    rejected = client.submit_movement_payload(
        request_id=move_request.request_id,
        payload=wrong,
        result_id="charge-wrong-reachable-subset",
    )
    assert rejected.status_kind == "invalid"
    assert rejected.invalid_diagnostics[0].violation_code == "charge_selected_targets_drift"
    assert rejected.invalid_diagnostics[0].message == "Charge path must use its recorded targets."
    assert client.get_view("player-a").battlefield_view == before_battlefield
    assert client.get_events_since(0, "player-a").events == before_events
    assert client.get_view("player-a").pending_decision == move_request

    accepted = client.submit_movement_payload(
        request_id=move_request.request_id,
        payload=payload,
        result_id="charge-accepted-subset",
    )
    assert accepted.status_kind != "invalid", accepted.invalid_diagnostics
    events = client.get_events_since(0, "player-a").events
    assert any(event["event_type"] == "charge_move_completed" for event in events)
    assert client.get_view("player-a").battlefield_view != before_battlefield


def _decision(status: UiClientStatus) -> UiDecision:
    assert status.decision is not None, status
    return status.decision
