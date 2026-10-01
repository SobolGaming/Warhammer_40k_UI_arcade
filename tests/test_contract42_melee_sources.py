"""A duplicated melee ability source through a real Contract 42 Fight request."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import cast

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.core.weapon_profiles import AbilityDescriptor, WeaponKeyword
from warhammer40k_core.engine.lifecycle import GameLifecycle
from warhammer40k_core.engine.phase import BattlePhase

from tests.support.contract42_battle_fixture import shooting_client
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import JsonObject, UiDecision
from warhammer40k_arcade_ui.state.assignment_workspace import AssignmentWorkspace

pytestmark = pytest.mark.integration


def _seeded_melee_client() -> LocalSessionClient:
    """Put an equipped melee profile and engaged units into a real Fight state."""

    base = shooting_client(enemy_x=11.5)
    session = base.session
    assert isinstance(session, LocalGameSession)
    config = session.lifecycle.config
    blade = next(
        item.weapon_profiles[0]
        for item in config.army_catalog.wargear
        if item.wargear_id == "core-leader-blade"
    )
    profile = replace(
        blade,
        profile_id="core-bolt-rifle:standard",
        keywords=(WeaponKeyword.CLEAVE,),
        abilities=(AbilityDescriptor.cleave(1), AbilityDescriptor.cleave(2)),
        ability_sources=(),
    )
    catalog = replace(
        config.army_catalog,
        wargear=tuple(
            replace(item, weapon_profiles=(profile,))
            if item.wargear_id == "core-bolt-rifle"
            else item
            for item in config.army_catalog.wargear
        ),
    )
    state = session.lifecycle.state
    assert state is not None
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.FIGHT)
    state.shooting_phase_state = None
    seeded = session.lifecycle.to_payload()
    seeded["config"] = replace(config, army_catalog=catalog).to_payload()
    seeded["state"] = state.to_payload()
    return LocalSessionClient(
        session=LocalGameSession(lifecycle=GameLifecycle.from_payload(seeded))
    )


def _melee_request(client: LocalSessionClient) -> UiDecision:
    status = client.advance_until_decision_or_terminal()
    for index in range(8):
        assert status.status_kind == "waiting_for_decision", status
        request = status.decision
        assert request is not None
        if request.decision_type == "submit_melee_declaration":
            assert request.actor_id == "player-a"
            for viewer in ("player-a", "player-b"):
                assert client.get_view(viewer).pending_decision == request
            return request
        if request.decision_type == "submit_movement_proposal":
            proposal = request.parameterized_proposal
            assert proposal is not None
            body = proposal.payload
            context = cast(JsonObject, body["context"])
            assert body["proposal_kind"] == "pile_in"
            status = client.submit_movement_payload(
                request_id=request.request_id,
                result_id=f"contract42-melee-no-move-{index}",
                payload={
                    "proposal_request_id": request.request_id,
                    "proposal_kind": body["proposal_kind"],
                    "unit_instance_id": body["unit_instance_id"],
                    "movement_phase_action": body["movement_phase_action"],
                    "movement_mode": context["movement_mode"],
                },
            )
            continue
        assert request.decision_type == "select_fight_activation"
        option = next(
            option
            for option in request.options
            if type(option.payload) is dict
            and option.payload.get("unit_instance_id") == "army-alpha:shooter"
        )
        status = client.submit_finite(
            request_id=request.request_id,
            selected_option_id=option.option_id,
            result_id=f"contract42-melee-activation-{index}",
        )
    raise AssertionError("Real Fight lifecycle did not emit a melee declaration.")


def _declaration_payload(request: UiDecision) -> tuple[JsonObject, JsonObject, JsonObject]:
    proposal = request.parameterized_proposal
    assert proposal is not None
    body = proposal.payload
    weapons = cast(list[JsonObject], body["available_weapons"])
    assert len(weapons) == 1
    weapon = weapons[0]
    choices = cast(list[JsonObject], weapon["required_weapon_ability_selections"])
    assert len(choices) == 1
    choice = choices[0]
    assert choice["decision_type"] == "select_weapon_ability_instance"
    assert choice["actor_id"] == request.actor_id
    options = cast(list[JsonObject], choice["options"])
    assert len(options) == 2
    option_ids = tuple(cast(str, option["option_id"]) for option in options)
    assert len(set(option_ids)) == 2
    selection_context = cast(JsonObject, weapon["weapon_ability_selection_context"])
    choice_payload = cast(JsonObject, choice["payload"])
    assert choice_payload["selection_context"] == selection_context
    assert selection_context["weapon_instance_id"] == weapon["weapon_instance_id"]
    assert selection_context["source_request_id"] == body["source_decision_result_id"]
    selected = options[0]
    selected_payload = cast(JsonObject, selected["payload"])
    assert selected_payload["selected_ability_instance_id"] == selected["option_id"]
    ability_source = cast(JsonObject, selected_payload["ability_source"])
    assert ability_source["instance_id"] == selected["option_id"]
    target_ids = cast(list[str], weapon["engaged_target_unit_instance_ids"])
    assert target_ids == ["army-beta:enemy"]
    payload: JsonObject = {
        "proposal_request_id": request.request_id,
        "proposal_kind": body["proposal_kind"],
        "player_id": request.actor_id,
        "battle_round": body["battle_round"],
        "unit_instance_id": body["unit_instance_id"],
        "source_decision_request_id": body["source_decision_request_id"],
        "source_decision_result_id": body["source_decision_result_id"],
        "declarations": [
            {
                "attacker_model_instance_id": weapon["model_instance_id"],
                "weapon_instance_id": weapon["weapon_instance_id"],
                "wargear_id": weapon["wargear_id"],
                "weapon_profile_id": weapon["weapon_profile_id"],
                "target_allocations": [{"target_unit_instance_id": target_ids[0]}],
                "selected_weapon_ability_ids": [selected["option_id"]],
            }
        ],
    }
    return payload, weapon, selected


def test_melee_duplicate_source_uses_emitted_instance_and_rejects_forged_or_stale() -> None:
    client = _seeded_melee_client()
    request = _melee_request(client)
    workspace = AssignmentWorkspace.start_for_pending(request)
    assert workspace is not None
    assert workspace.request_id == request.request_id
    assert workspace.editable
    assert not workspace.is_ready
    expected_payload, weapon, selected = _declaration_payload(request)
    assert len(workspace.melee_choices) == 2
    offered = next(
        choice.selection
        for choice in workspace.melee_choices
        if choice.selection.weapon_instance_id == weapon["weapon_instance_id"]
        and choice.selection.selected_weapon_ability_ids == (selected["option_id"],)
    )
    chosen_workspace = workspace.with_melee_selection(request, offered)
    assert chosen_workspace.is_ready
    payload = chosen_workspace.payload_preview
    assert payload == expected_payload
    assert payload is not None
    session = client.session
    assert isinstance(session, LocalGameSession)
    state = session.lifecycle.state
    assert state is not None

    for fault, code in (
        ("forged-option", "weapon_ability_selection_invalid"),
        ("stale-source", "source_decision_result_drift"),
    ):
        invalid_payload = deepcopy(payload)
        if fault == "forged-option":
            cast(list[JsonObject], invalid_payload["declarations"])[0][
                "selected_weapon_ability_ids"
            ] = ["ability-instance:forged"]
        else:
            invalid_payload["source_decision_result_id"] = "stale-result"
        before = state.to_payload()
        rejected = client.submit_parameterized_payload(
            request_id=request.request_id,
            payload=invalid_payload,
            result_id=f"contract42-melee-{fault}",
        )
        assert rejected.status_kind == "invalid"
        assert [diagnostic.violation_code for diagnostic in rejected.invalid_diagnostics] == [code]
        assert state.to_payload() == before
        for viewer in ("player-a", "player-b"):
            assert client.get_view(viewer).pending_decision == request

    accepted = client.submit_parameterized_payload(
        request_id=request.request_id,
        payload=payload,
        result_id="contract42-melee-current-source",
    )
    assert accepted.status_kind != "invalid", accepted
    for viewer in ("player-a", "player-b"):
        events = tuple(
            event
            for event in client.get_events_since(0, viewer).events
            if event.get("event_type") == "melee_declaration_accepted"
        )
        assert len(events) == 1
        event_payload = cast(JsonObject, events[0]["payload"])
        assert event_payload["request_id"] == request.request_id
        assert event_payload["result_id"] == "contract42-melee-current-source"
        accepted_proposal = cast(JsonObject, event_payload["proposal"])
        accepted_row = cast(list[JsonObject], accepted_proposal["declarations"])[0]
        assert accepted_row["weapon_instance_id"] == weapon["weapon_instance_id"]
        assert accepted_row["selected_weapon_ability_ids"] == [selected["option_id"]]
        assert (
            accepted_proposal["source_decision_request_id"] == payload["source_decision_request_id"]
        )
        assert (
            accepted_proposal["source_decision_result_id"] == payload["source_decision_result_id"]
        )
