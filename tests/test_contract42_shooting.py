"""Contract 42 Shooting choices through a real local session and UI facade."""

from __future__ import annotations

from copy import deepcopy
from typing import cast

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession

from tests.support.contract42_battle_fixture import shooting_client as _client
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiDecision,
    validate_json_value,
)
from warhammer40k_arcade_ui.state.assignment_workspace import (
    AssignmentWorkspace,
    ShootingAssignmentSelection,
)


def _required_decision(client: LocalSessionClient) -> UiDecision:
    status = client.advance_until_decision_or_terminal()
    assert status.status_kind == "waiting_for_decision", status
    assert status.decision is not None
    return status.decision


def _shooting_request(client: LocalSessionClient) -> UiDecision:
    unit = _required_decision(client)
    assert unit.decision_type == "select_shooting_unit"
    unit_status = client.submit_finite(
        request_id=unit.request_id,
        selected_option_id="army-alpha:shooter",
        result_id="contract42:unit",
    )
    assert unit_status.status_kind == "waiting_for_decision", unit_status
    shooting_type = unit_status.decision
    assert shooting_type is not None
    assert shooting_type.decision_type == "select_shooting_type"
    type_status = client.submit_finite(
        request_id=shooting_type.request_id,
        selected_option_id="normal",
        result_id="contract42:type",
    )
    assert type_status.status_kind == "waiting_for_decision", type_status
    decision = type_status.decision
    assert decision is not None
    assert decision.decision_type == "submit_shooting_declaration"
    assert client.get_view("player-a").pending_decision == decision
    assert client.get_view("player-b").pending_decision == decision
    return decision


def _request_inventory(decision: UiDecision) -> JsonObject:
    proposal = decision.parameterized_proposal
    assert proposal is not None
    return proposal.payload


def _weapon_choices(
    decision: UiDecision, *, target: str | None
) -> tuple[ShootingAssignmentSelection, ...]:
    available = _request_inventory(decision)["available_weapons"]
    assert type(available) is list
    return tuple(
        ShootingAssignmentSelection(
            model_instance_id=cast(str, weapon["model_instance_id"]),
            weapon_instance_id=cast(str, weapon["weapon_instance_id"]),
            weapon_profile_id=cast(str, weapon["weapon_profile_id"]),
            target_unit_instance_id=target,
        )
        for weapon in available
        if type(weapon) is dict
    )


def _accepted_events(client: LocalSessionClient, viewer: str) -> tuple[JsonObject, ...]:
    return tuple(
        event
        for event in client.get_events_since(0, viewer).events
        if event.get("event_type") == "shooting_declaration_accepted"
    )


def _authoritative_snapshot(client: LocalSessionClient) -> JsonObject:
    session = client.session
    assert isinstance(session, LocalGameSession)
    return cast(JsonObject, session.lifecycle.to_payload())


def test_real_session_accepts_explicit_empty_declaration() -> None:
    client = _client()
    decision = _shooting_request(client)
    workspace = AssignmentWorkspace.start_for_pending(decision)
    assert workspace is not None
    empty = workspace.with_shooting_selections(decision, ())
    assert empty.is_ready
    assert empty.payload_preview is not None

    status = client.submit_parameterized_payload(
        request_id=decision.request_id,
        payload=empty.payload_preview,
        result_id="contract42:empty",
    )

    assert status.status_kind != "invalid", status
    assert empty.payload_preview["declarations"] == []
    for viewer in ("player-a", "player-b"):
        events = _accepted_events(client, viewer)
        assert len(events) == 1
        payload = events[0]["payload"]
        assert type(payload) is dict
        assert payload["weapons_without_attacks"] == []
        assert payload["attack_pools"] == []


def test_real_session_duplicate_copies_keep_source_choices_and_reject_forgery() -> None:
    client = _client(copies=2, duplicate_hazardous=True)
    decision = _shooting_request(client)
    inventory = _request_inventory(decision)
    weapons = inventory["available_weapons"]
    target_candidates = inventory["target_candidates"]
    assert type(weapons) is list
    assert len(weapons) == 2
    assert type(target_candidates) is list
    assert len({cast(str, row["weapon_instance_id"]) for row in weapons if type(row) is dict}) == 2
    selections: list[ShootingAssignmentSelection] = []
    for index, weapon in enumerate(weapons):
        assert type(weapon) is dict
        candidate = next(
            row
            for row in target_candidates
            if type(row) is dict
            and row["weapon_instance_id"] == weapon["weapon_instance_id"]
            and row["target_unit_instance_id"] == "army-beta:enemy"
            and row["is_legal"] is True
        )
        required = candidate["required_weapon_ability_selections"]
        assert type(required) is list
        assert len(required) == 1
        assert type(required[0]) is dict
        options = required[0]["options"]
        assert type(options) is list
        assert len(options) == 2
        option = options[index]
        assert type(option) is dict
        selections.append(
            ShootingAssignmentSelection(
                model_instance_id=cast(str, weapon["model_instance_id"]),
                weapon_instance_id=cast(str, weapon["weapon_instance_id"]),
                weapon_profile_id=cast(str, weapon["weapon_profile_id"]),
                target_unit_instance_id="army-beta:enemy",
                selected_weapon_ability_ids=(cast(str, option["option_id"]),),
            )
        )
    workspace = AssignmentWorkspace.start_for_pending(decision)
    assert workspace is not None
    assert not workspace.is_ready
    selected = workspace.with_shooting_selections(decision, tuple(selections))
    assert selected.is_ready
    assert selected.payload_preview is not None
    rows = selected.payload_preview["declarations"]
    assert type(rows) is list
    assert len(rows) == 2

    for field, value in (
        ("weapon_instance_id", "invented-physical-copy"),
        ("selected_weapon_ability_ids", ["invented-ability-source"]),
    ):
        forged = deepcopy(selected.payload_preview)
        forged_rows = forged["declarations"]
        assert type(forged_rows) is list
        assert type(forged_rows[0]) is dict
        forged_rows[0][field] = validate_json_value(value)
        before = _authoritative_snapshot(client)
        status = client.submit_parameterized_payload(
            request_id=decision.request_id,
            payload=forged,
            result_id=f"contract42:invalid:{field}",
        )
        assert status.status_kind == "invalid"
        assert status.invalid_diagnostics
        assert _authoritative_snapshot(client) == before
        assert client.get_view("player-a").pending_decision == decision

    accepted = client.submit_parameterized_payload(
        request_id=decision.request_id,
        payload=selected.payload_preview,
        result_id="contract42:copies",
    )
    assert accepted.status_kind != "invalid", accepted
    for viewer in ("player-a", "player-b"):
        events = _accepted_events(client, viewer)
        assert len(events) == 1
        payload = events[0]["payload"]
        assert type(payload) is dict
        pools = payload["attack_pools"]
        assert type(pools) is list
        assert len(pools) == 2
        assert [pool["weapon_instance_id"] for pool in pools if type(pool) is dict] == [
            row["weapon_instance_id"] for row in rows if type(row) is dict
        ]
        assert [pool["selected_weapon_ability_ids"] for pool in pools if type(pool) is dict] == [
            row["selected_weapon_ability_ids"] for row in rows if type(row) is dict
        ]
        assert "weapons_without_attacks" not in payload


@pytest.mark.parametrize("targetless_count", [1, 2])
def test_real_session_targetless_and_mixed_rows_keep_selected_inventory(
    targetless_count: int,
) -> None:
    client = _client(models=2, one_shot=True)
    decision = _shooting_request(client)
    choices = _weapon_choices(decision, target=None)
    assert len(choices) == 2
    if targetless_count == 1:
        second = choices[1]
        choices = (
            choices[0],
            ShootingAssignmentSelection(
                model_instance_id=second.model_instance_id,
                weapon_instance_id=second.weapon_instance_id,
                weapon_profile_id=second.weapon_profile_id,
                target_unit_instance_id="army-beta:enemy",
            ),
        )
    workspace = AssignmentWorkspace.start_for_pending(decision)
    assert workspace is not None
    selected = workspace.with_shooting_selections(decision, choices)
    assert selected.is_ready
    assert selected.payload_preview is not None
    selected_rows = selected.payload_preview["declarations"]
    assert type(selected_rows) is list
    assert (
        sum(type(row) is dict and row["target_unit_instance_id"] is None for row in selected_rows)
        == targetless_count
    )

    status = client.submit_parameterized_payload(
        request_id=decision.request_id,
        payload=selected.payload_preview,
        result_id=f"contract42:targetless:{targetless_count}",
    )

    assert status.status_kind != "invalid", status
    for viewer in ("player-a", "player-b"):
        events = _accepted_events(client, viewer)
        assert len(events) == 1
        payload = events[0]["payload"]
        assert type(payload) is dict
        without_attacks = payload["weapons_without_attacks"]
        pools = payload["attack_pools"]
        spent = payload["one_shot_weapon_use_records"]
        assert type(without_attacks) is list
        assert len(without_attacks) == targetless_count
        assert type(pools) is list
        assert len(pools) == 2 - targetless_count
        assert type(spent) is list
        assert len(spent) == 2
        for row in without_attacks:
            assert type(row) is dict
            declaration = row.get("declaration")
            assert type(declaration) is dict
            assert declaration["target_unit_instance_id"] is None
            assert type(row.get("source_profile")) is dict


def test_real_session_automatic_no_candidate_completion_has_no_declaration() -> None:
    client = _client(no_weapons=True)
    unit = _required_decision(client)
    assert unit.decision_type == "select_shooting_unit"
    selected = client.submit_finite(
        request_id=unit.request_id,
        selected_option_id="army-alpha:shooter",
        result_id="contract42:auto-unit",
    )
    shooting_type = selected.decision
    assert shooting_type is not None
    assert shooting_type.decision_type == "select_shooting_type"

    completed = client.submit_finite(
        request_id=shooting_type.request_id,
        selected_option_id="normal",
        result_id="contract42:auto-type",
    )

    assert completed.status_kind != "invalid", completed
    for viewer in ("player-a", "player-b"):
        assert _accepted_events(client, viewer) == ()
        terminal = tuple(
            event
            for event in client.get_events_since(0, viewer).events
            if event.get("event_type") == "shooting_without_attacks_completed"
        )
        assert len(terminal) == 1
        payload = terminal[0]["payload"]
        assert type(payload) is dict
        assert payload["unit_instance_id"] == "army-alpha:shooter"
        assert payload["shooting_type"] == "normal"


def test_real_session_rejects_stale_explicit_empty_before_state_change() -> None:
    client = _client()
    decision = _shooting_request(client)
    workspace = AssignmentWorkspace.start_for_pending(decision)
    assert workspace is not None
    empty = workspace.with_shooting_selections(decision, ())
    assert empty.payload_preview is not None
    stale = {**empty.payload_preview, "visibility_cache_key": "stale-cache"}
    before = _authoritative_snapshot(client)

    invalid = client.submit_parameterized_payload(
        request_id=decision.request_id,
        payload=stale,
        result_id="contract42:invalid-empty",
    )

    assert invalid.status_kind == "invalid"
    assert invalid.invalid_diagnostics
    assert _authoritative_snapshot(client) == before
    assert client.get_view("player-a").pending_decision == decision


def test_real_session_targetless_duplicate_source_uses_targetless_inventory() -> None:
    client = _client(duplicate_hazardous=True)
    decision = _shooting_request(client)
    inventory = _request_inventory(decision)
    targetless_candidates = inventory["targetless_weapon_candidates"]
    assert type(targetless_candidates) is list
    assert len(targetless_candidates) == 1
    candidate = targetless_candidates[0]
    assert type(candidate) is dict
    assert candidate["target_unit_instance_id"] is None
    choices = candidate["required_weapon_ability_selections"]
    assert type(choices) is list
    assert len(choices) == 1
    assert type(choices[0]) is dict
    options = choices[0]["options"]
    assert type(options) is list
    assert len(options) == 2
    option = options[1]
    assert type(option) is dict
    choice = ShootingAssignmentSelection(
        model_instance_id=cast(str, candidate["model_instance_id"]),
        weapon_instance_id=cast(str, candidate["weapon_instance_id"]),
        weapon_profile_id=cast(str, candidate["weapon_profile_id"]),
        target_unit_instance_id=None,
        selected_weapon_ability_ids=(cast(str, option["option_id"]),),
    )
    workspace = AssignmentWorkspace.start_for_pending(decision)
    assert workspace is not None
    selected = workspace.with_shooting_selections(decision, (choice,))
    assert selected.is_ready
    assert selected.payload_preview is not None

    accepted = client.submit_parameterized_payload(
        request_id=decision.request_id,
        payload=selected.payload_preview,
        result_id="contract42:targetless-source",
    )

    assert accepted.status_kind != "invalid", accepted
    event = _accepted_events(client, "player-a")[0]
    payload = event["payload"]
    assert type(payload) is dict
    without_attacks = payload["weapons_without_attacks"]
    assert type(without_attacks) is list
    assert len(without_attacks) == 1
    assert type(without_attacks[0]) is dict
    selected_declaration = without_attacks[0]["declaration"]
    assert type(selected_declaration) is dict
    assert selected_declaration["selected_weapon_ability_ids"] == [option["option_id"]]


@pytest.mark.parametrize("origin", ["empty", "targetless", "automatic"])
def test_real_session_selected_only_obligation_survives_each_zero_attack_origin(
    origin: str,
) -> None:
    from warhammer40k_core.engine.faction_content.warhammer_40000_11th.chaos_space_marines import (
        army_rule,
    )

    client = _client(dark_pact=True, range_inches=1 if origin == "automatic" else 48)
    unit = _required_decision(client)
    assert unit.decision_type == "select_shooting_unit"
    selected = client.submit_finite(
        request_id=unit.request_id,
        selected_option_id="army-alpha:shooter",
        result_id=f"contract42:{origin}:unit",
    )
    grant = selected.decision
    assert grant is not None
    assert grant.decision_type == "select_shooting_unit_grant"
    granted = client.submit_finite(
        request_id=grant.request_id,
        selected_option_id=army_rule.SHOOTING_LETHAL_HITS_HOOK_ID,
        result_id=f"contract42:{origin}:grant",
    )
    shooting_type = granted.decision
    assert shooting_type is not None
    assert shooting_type.decision_type == "select_shooting_type"
    after_type = client.submit_finite(
        request_id=shooting_type.request_id,
        selected_option_id="normal",
        result_id=f"contract42:{origin}:type",
    )
    if origin != "automatic":
        declaration = after_type.decision
        assert declaration is not None
        assert declaration.decision_type == "submit_shooting_declaration"
        workspace = AssignmentWorkspace.start_for_pending(declaration)
        assert workspace is not None
        choices = () if origin == "empty" else _weapon_choices(declaration, target=None)
        selected_workspace = workspace.with_shooting_selections(declaration, choices)
        assert selected_workspace.is_ready
        assert selected_workspace.payload_preview is not None
        submitted = client.submit_parameterized_payload(
            request_id=declaration.request_id,
            payload=selected_workspace.payload_preview,
            result_id=f"contract42:{origin}:declared",
        )
        assert submitted.status_kind != "invalid", submitted
    for viewer in ("player-a", "player-b"):
        events = client.get_events_since(0, viewer).events
        assert (
            sum(
                event.get("event_type") == "chaos_space_marines_dark_pact_resolved"
                for event in events
            )
            == 1
        )
        assert sum(
            event.get("event_type") == "shooting_without_attacks_completed" for event in events
        ) == (origin == "automatic")
        assert len(_accepted_events(client, viewer)) == (origin != "automatic")
