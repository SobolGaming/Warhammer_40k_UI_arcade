"""Contract 41 first-failed-save Damage-to-zero through the public UI facade."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import cast

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.core.army_catalog import ArmyCatalog
from warhammer40k_core.core.attributes import Characteristic, CharacteristicValue
from warhammer40k_core.core.datasheet import (
    CatalogAbilitySourceKind,
    CatalogAbilitySupport,
    CatalogJsonObject,
    DatasheetAbilityDescriptor,
)
from warhammer40k_core.core.weapon_profiles import AttackProfile, DamageProfile, WeaponKeyword
from warhammer40k_core.rules.parsed_tokens import TextSpan
from warhammer40k_core.rules.rule_ir import (
    RuleClause,
    RuleDuration,
    RuleDurationKind,
    RuleEffectKind,
    RuleEffectSpec,
    RuleIR,
    RuleTargetKind,
    RuleTargetSpec,
    parameters_from_pairs,
)
from warhammer40k_core.rules.source_packages.warhammer_40000_11th import (
    faction_pack_rule_ir,
)

from tests.support import contract42_battle_fixture
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientStatus,
    UiClientSubmissionError,
    UiDecision,
)
from warhammer40k_arcade_ui.state.assignment_workspace import AssignmentWorkspace
from warhammer40k_arcade_ui.state.finite_decision import (
    FiniteDecisionUiState,
    submit_finite_option,
)

pytestmark = pytest.mark.integration


def _permission_ability() -> DatasheetAbilityDescriptor:
    """Use the Core catalog's passive, source-scoped permission RuleIR shape."""

    text = "This unit can ignore any or all modifiers to Damage."
    span = TextSpan(text=text, start=0, end=len(text))
    rule = RuleIR(
        rule_id="damage-zero-fixture:ignore-rule",
        source_id="damage-zero-fixture:ignore-source",
        normalized_text=text,
        parser_version="damage-zero-fixture:v1",
        clauses=(
            RuleClause(
                clause_id="damage-zero-fixture:ignore-clause",
                source_span=span,
                target=RuleTargetSpec(kind=RuleTargetKind.THIS_UNIT, source_span=span),
                effects=(
                    RuleEffectSpec(
                        kind=RuleEffectKind.GRANT_ABILITY,
                        source_span=span,
                        parameters=parameters_from_pairs(
                            (
                                ("ability", "modifier_ignore_permission"),
                                ("modifier_kinds", ("damage_characteristic",)),
                                ("selection", "any_or_all"),
                            )
                        ),
                    ),
                ),
                duration=RuleDuration(
                    kind=RuleDurationKind.WHILE_CONDITION_TRUE,
                    source_span=span,
                ),
            ),
        ),
    )
    return DatasheetAbilityDescriptor(
        ability_id="damage-zero-fixture:ignore-ability",
        name="Damage Modifier Ignore",
        source_id=rule.source_id,
        support=CatalogAbilitySupport.GENERIC_RULE_IR,
        source_kind=CatalogAbilitySourceKind.DATASHEET,
        effect_description=text,
        rule_ir_payload=cast(CatalogJsonObject, rule.to_payload()),
    )


def _damage_zero_ability() -> DatasheetAbilityDescriptor:
    source_payload = faction_pack_rule_ir.datasheet_rule_ir_payload_by_source_row_id("000002532:4")
    assert source_payload is not None
    rule = RuleIR.from_payload(source_payload)
    return DatasheetAbilityDescriptor(
        ability_id="damage-zero-fixture:channeller-stones",
        name="Channeller Stones",
        source_id=rule.source_id,
        support=CatalogAbilitySupport.GENERIC_RULE_IR,
        source_kind=CatalogAbilitySourceKind.DATASHEET,
        effect_description=rule.normalized_text,
        rule_ir_payload=cast(CatalogJsonObject, source_payload),
    )


def _source_catalog(catalog: ArmyCatalog) -> ArmyCatalog:
    abilities = (_damage_zero_ability(), _permission_ability())
    return replace(
        catalog,
        datasheets=tuple(
            replace(sheet, abilities=(*sheet.abilities, *abilities))
            if sheet.datasheet_id == "core-intercessor-like-infantry"
            else sheet
            for sheet in catalog.datasheets
        ),
        wargear=tuple(
            replace(
                item,
                weapon_profiles=tuple(
                    replace(
                        profile,
                        attack_profile=AttackProfile.fixed(4),
                        strength=CharacteristicValue.from_raw(Characteristic.STRENGTH, 20),
                        armor_penetration=CharacteristicValue.from_raw(
                            Characteristic.ARMOR_PENETRATION, -6
                        ),
                        damage_profile=DamageProfile.fixed(1),
                        keywords=(WeaponKeyword.TORRENT,),
                        abilities=(),
                        ability_sources=(),
                    )
                    for profile in item.weapon_profiles
                ),
            )
            if item.wargear_id == "core-bolt-rifle"
            else item
            for item in catalog.wargear
        ),
    )


def _client(monkeypatch: pytest.MonkeyPatch) -> LocalSessionClient:
    """Customize catalog inputs of the canonical real-Core shooting fixture."""

    original_catalog = contract42_battle_fixture._catalog  # pyright: ignore[reportPrivateUsage]

    def sourced_catalog(
        *,
        copies: int,
        no_weapons: bool,
        range_inches: int,
        duplicate_hazardous: bool,
        one_shot: bool,
        dark_pact: bool,
        lethal_attack: bool,
    ) -> ArmyCatalog:
        return _source_catalog(
            original_catalog(
                copies=copies,
                no_weapons=no_weapons,
                range_inches=range_inches,
                duplicate_hazardous=duplicate_hazardous,
                one_shot=one_shot,
                dark_pact=dark_pact,
                lethal_attack=lethal_attack,
            )
        )

    with monkeypatch.context() as scoped_patch:
        scoped_patch.setattr(contract42_battle_fixture, "_catalog", sourced_catalog)
        return contract42_battle_fixture.shooting_client()


def _choose(
    client: LocalSessionClient, decision: UiDecision, option_id: str, index: int
) -> UiClientStatus:
    assert option_id in {option.option_id for option in decision.options}
    status = client.submit_finite(
        request_id=decision.request_id,
        selected_option_id=option_id,
        result_id=f"damage-zero-fixture:setup-{index}",
    )
    assert status.status_kind != "invalid", status.invalid_diagnostics
    return status


def _first_failed_save_request(client: LocalSessionClient) -> UiClientStatus:
    status = client.advance_until_decision_or_terminal()
    decision = status.decision
    assert decision is not None
    assert decision.decision_type == "select_shooting_unit"
    status = _choose(client, decision, "army-alpha:shooter", 0)
    decision = status.decision
    assert decision is not None
    assert decision.decision_type == "select_shooting_type"
    status = _choose(client, decision, "normal", 1)
    decision = status.decision
    assert decision is not None
    assert decision.decision_type == "submit_shooting_declaration"
    workspace = AssignmentWorkspace.start_for_pending(decision)
    assert workspace is not None
    assert workspace.is_ready
    assert workspace.payload_preview is not None
    status = client.submit_parameterized_payload(
        request_id=decision.request_id,
        payload=workspace.payload_preview,
        result_id="damage-zero-fixture:shoot",
    )
    assert status.status_kind != "invalid", status.invalid_diagnostics
    for index in range(20):
        decision = status.decision
        if decision is None:
            status = client.advance_until_decision_or_terminal()
            decision = status.decision
        assert decision is not None, status
        if decision.decision_type == "select_modifier_ignores":
            assert type(decision.payload) is dict
            context = cast(JsonObject, decision.payload["source_context"])
            if context["evaluation_stage"] == "failed-save-damage-replacement":
                return status
        assert not decision.is_parameterized, decision.decision_type
        assert decision.options, decision.decision_type
        status = _choose(client, decision, decision.options[0].option_id, index + 2)
    raise AssertionError("The first-failed-save Damage source decision was not reached.")


@pytest.mark.parametrize("ignore", [False, True])
def test_real_first_failed_save_damage_zero_preserves_source_and_authority(
    monkeypatch: pytest.MonkeyPatch, ignore: bool
) -> None:
    client = _client(monkeypatch)
    status = _first_failed_save_request(client)
    decision = status.decision
    assert decision is not None
    assert decision.decision_type == "select_modifier_ignores"
    assert decision.actor_id == "player-a"
    assert type(decision.payload) is dict
    payload = decision.payload
    assert cast(JsonObject, payload["subject"])["kind"] == "damage_characteristic"
    context = cast(JsonObject, payload["source_context"])
    assert context["evaluation_stage"] == "failed-save-damage-replacement"
    operations = cast(list[JsonObject], payload["modifiers"])
    assert len(operations) == 1
    operation = cast(JsonObject, operations[0]["operation"])
    assert operation["operation"] == "set"
    assert operation["operand"] == 0
    source_payload = faction_pack_rule_ir.datasheet_rule_ir_payload_by_source_row_id("000002532:4")
    assert source_payload is not None
    source_rule = RuleIR.from_payload(source_payload)
    assert source_rule.clauses[0].clause_id in cast(str, operation["source_id"])
    assert "army-beta:enemy" in cast(str, operation["source_id"])
    assert cast(str, operation["modifier_id"]).endswith(":failed-save-damage")
    assert operations[0]["operation_type"] == "characteristic"
    assert json.loads(json.dumps(payload)) == payload

    owner = client.get_view("player-a")
    opponent = client.get_view("player-b")
    assert owner.pending_decision == decision
    assert opponent.pending_decision is not None
    assert opponent.pending_decision.decision_type == "hidden_decision"
    assert decision.request_id not in json.dumps(opponent.pending_decision.payload)
    assert cast(str, operation["modifier_id"]) not in json.dumps(opponent.pending_decision.payload)
    session = client.session
    assert isinstance(session, LocalGameSession)
    records_before = session.decision_record_count()
    events_before = client.get_events_since(0, "player-a").events
    assert any(
        event["event_type"] == "attack_sequence_step"
        and type(event["payload"]) is dict
        and event["payload"].get("step") == "save"
        for event in events_before
    )
    assert not any(event["event_type"] == "failed_save_damage_replaced" for event in events_before)

    local_invalid = submit_finite_option(
        state=FiniteDecisionUiState.from_status(status),
        client=client,
        selected_option_id=f"{decision.options[0].option_id}:forged",
        viewer_player_id="player-a",
    )
    assert local_invalid.finite_state.diagnostics[0].violation_code == (
        "selected_option_not_pending"
    )
    assert session.decision_record_count() == records_before
    assert client.get_view("player-a").projection_state_hash == owner.projection_state_hash
    assert client.get_view("player-b").projection_state_hash == opponent.projection_state_hash
    with pytest.raises(UiClientSubmissionError):
        client.submit_finite(
            request_id=decision.request_id,
            selected_option_id=f"{decision.options[0].option_id}:forged",
            result_id="damage-zero-fixture:forged",
        )
    assert session.decision_record_count() == records_before
    assert client.get_view("player-a").projection_state_hash == owner.projection_state_hash
    assert client.get_view("player-b").projection_state_hash == opponent.projection_state_hash

    option_id = "ignore-remaining" if ignore else "keep-remaining"
    option = next(option for option in decision.options if option.option_id == option_id)
    accepted = submit_finite_option(
        state=FiniteDecisionUiState.from_status(status),
        client=client,
        selected_option_id=option.option_id,
        viewer_player_id="player-a",
    )
    assert accepted.viewer_player_id == "player-a"
    assert accepted.refreshed_view is not None
    assert accepted.finite_state.status_kind != "invalid"
    assert not accepted.finite_state.diagnostics
    assert session.decision_record_count() == records_before + 1
    next_decision = accepted.finite_state.pending_decision
    assert next_decision is not None
    assert next_decision.decision_type != "select_modifier_ignores"

    owner_events = client.get_events_since(0, "player-a").events
    opponent_events = client.get_events_since(0, "player-b").events
    assert (
        sum(
            event["event_type"] == "attack_sequence_step"
            and type(event["payload"]) is dict
            and event["payload"].get("step") == "damage"
            for event in owner_events
        )
        >= 2
    )
    recorded_results: list[JsonObject] = []
    for event in owner_events:
        if event["event_type"] != "decision_recorded":
            continue
        record = cast(JsonObject, event["payload"])
        result = cast(JsonObject, record["result"])
        if result["request_id"] == decision.request_id:
            recorded_results.append(result)
    assert len(recorded_results) == 1
    assert recorded_results[0]["selected_option_id"] == option.option_id
    assert recorded_results[0]["payload"] == option.payload
    assert recorded_results[0]["result_id"] == "ui-result-000001"
    assert decision.request_id not in json.dumps(opponent_events)
    assert "modifier_ignores_selected" not in json.dumps(opponent_events)
    assert "failed_save_damage_replacement_ignored" not in json.dumps(opponent_events)
    assert "restore_origin" not in json.dumps(owner_events)
    assert "restore_origin" not in json.dumps(opponent_events)
    damage_steps = tuple(
        event["payload"]
        for event in owner_events
        if event["event_type"] == "attack_sequence_step"
        and type(event["payload"]) is dict
        and event["payload"].get("step") == "damage"
        and event["payload"].get("attack_context_id") == context["attack_context_id"]
    )
    assert len(damage_steps) == 1
    opponent_damage_steps = tuple(
        event["payload"]
        for event in opponent_events
        if event["event_type"] == "attack_sequence_step"
        and type(event["payload"]) is dict
        and event["payload"].get("step") == "damage"
        and event["payload"].get("attack_context_id") == context["attack_context_id"]
    )
    assert opponent_damage_steps == damage_steps
    damage_payload = cast(JsonObject, damage_steps[0]["payload"])
    if ignore:
        application = cast(JsonObject, damage_payload["damage_application"])
        assert application["target_unit_instance_id"] == "army-beta:enemy"
        assert application["requested_damage"] == 1
        assert application["wounds_lost"] == 1
        assert cast(int, application["final_wounds_remaining"]) < cast(
            int, application["starting_wounds_remaining"]
        )
        assert not any(
            event["event_type"] == "failed_save_damage_replaced" for event in owner_events
        )
    else:
        assert damage_payload["damage_application"] is None
        replacements = tuple(
            event for event in owner_events if event["event_type"] == "failed_save_damage_replaced"
        )
        assert len(replacements) == 1
        replacement = cast(JsonObject, replacements[0]["payload"])
        assert replacement["source_id"] == operation["source_id"]
        assert replacement["source_unit_instance_id"] == "army-beta:enemy"
        assert replacement["attack_context_id"] == context["attack_context_id"]
        assert replacement["replacement_damage"] == 0
        assert replacements[0] in opponent_events

    stable = client.get_view("player-a")
    stable_records = session.decision_record_count()
    stable_events = client.get_events_since(0, "player-a").events
    with pytest.raises(UiClientSubmissionError):
        client.submit_finite(
            request_id=decision.request_id,
            selected_option_id=option.option_id,
            result_id="damage-zero-fixture:stale",
        )
    assert session.decision_record_count() == stable_records
    assert client.get_view("player-a").projection_state_hash == stable.projection_state_hash
    assert client.get_events_since(0, "player-a").events == stable_events
    refreshed_opponent = client.get_view("player-b")
    if refreshed_opponent.pending_decision is not None:
        assert decision.request_id not in json.dumps(refreshed_opponent.pending_decision.payload)
