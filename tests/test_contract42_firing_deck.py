"""Bounded Contract 42 Firing Deck evidence through the public session facade.

The fixture starts with the Transport's first Shooting declaration of the turn.
Its empty shot history is known from test setup; the declaration request does not
publish the shot snapshot required for a general FiringDeckSelection editor.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from functools import cache
from typing import cast

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.core.ability_sources import AbilitySourceInstance
from warhammer40k_core.core.army_catalog import ArmyCatalog
from warhammer40k_core.core.missions import ObjectiveMarkerDefinition, ObjectiveMarkerRole
from warhammer40k_core.core.ruleset_descriptor import RulesetDescriptor
from warhammer40k_core.core.weapon_ability_sources import weapon_keyword_ability_id
from warhammer40k_core.core.weapon_profiles import WeaponKeyword
from warhammer40k_core.engine.army_mustering import ArmyMusterRequest, muster_army
from warhammer40k_core.engine.battlefield_state import ModelPlacement, UnitPlacement
from warhammer40k_core.engine.event_log import EventLog
from warhammer40k_core.engine.game_state import (
    GameConfig,
    SecondaryMissionChoice,
    SecondaryMissionMode,
)
from warhammer40k_core.engine.lifecycle import GameLifecycle, GameLifecyclePayload
from warhammer40k_core.engine.list_validation import DetachmentSelection, UnitMusterSelection
from warhammer40k_core.engine.mission_setup import MissionSetup, PlayerPrimaryMissionAssignment
from warhammer40k_core.engine.phase import BattlePhase, GameLifecycleStage
from warhammer40k_core.engine.placement import create_deterministic_battlefield_scenario
from warhammer40k_core.engine.primary_historical_events import (
    record_new_primary_turn_start_evidence_events,
)
from warhammer40k_core.engine.primary_turn_start_evidence import (
    record_primary_turn_start_evidence,
)
from warhammer40k_core.engine.transports import TransportCapacityProfile, TransportCargoState
from warhammer40k_core.engine.wargear_selections import ModelProfileSelection
from warhammer40k_core.geometry.pose import Pose
from warhammer40k_core.rules.mission_pack_import import (
    warhammer_event_companion_2026_07_mission_pack,
)

from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import JsonObject, UiDecision
from warhammer40k_arcade_ui.state.assignment_workspace import (
    AssignmentWorkspace,
    ShootingAssignmentSelection,
)

_CARGO = ("army-alpha:passenger-1", "army-alpha:passenger-2")
_TRANSPORT = "army-alpha:transport-1"
_TARGET = "army-beta:enemy"


def _mission_setup() -> MissionSetup:
    pack = warhammer_event_companion_2026_07_mission_pack()
    return MissionSetup(
        mission_pack_id=pack.mission_pack_id,
        source_version=pack.source_version,
        source_id=pack.source_id,
        mission_pool_entry_id="mission-purge-the-foe-vs-purge-the-foe-layout-3",
        primary_mission_assignments=tuple(
            PlayerPrimaryMissionAssignment(
                player_id=player_id,
                force_disposition_id="purge-the-foe",
                primary_mission_id="primary-meatgrinder",
            )
            for player_id in ("player-a", "player-b")
        ),
        battlefield_layout_id=None,
        deployment_map_id="contract42-firing-deck-open-map",
        terrain_layout_id="contract42-firing-deck-open-layout",
        attacker_player_id="player-a",
        defender_player_id="player-b",
        battlefield_width_inches=100.0,
        battlefield_depth_inches=60.0,
        objective_markers=(
            ObjectiveMarkerDefinition(
                objective_marker_id="contract42-firing-deck-remote-objective",
                name="Remote objective",
                objective_role=ObjectiveMarkerRole.CENTRAL,
                x_inches=95.0,
                y_inches=55.0,
                source_id="contract42-firing-deck-test",
            ),
        ),
        deployment_zones=(),
        battlefield_regions=(),
        terrain_areas=(),
        terrain_features=(),
    )


def _muster_request(
    catalog: ArmyCatalog,
    *,
    player_id: str,
    units: tuple[tuple[str, str, str, int], ...],
) -> ArmyMusterRequest:
    return ArmyMusterRequest(
        army_id="army-alpha" if player_id == "player-a" else "army-beta",
        player_id=player_id,
        catalog_id=catalog.catalog_id,
        source_package_id=catalog.source_package_id,
        ruleset_id=catalog.ruleset_id,
        detachment_selection=DetachmentSelection(
            faction_id="core-marine-force",
            detachment_ids=("core-combined-arms",),
        ),
        force_disposition_id="purge-the-foe",
        unit_selections=tuple(
            UnitMusterSelection(
                unit_selection_id=unit_id,
                datasheet_id=datasheet_id,
                model_profile_selections=(
                    ModelProfileSelection(
                        model_profile_id=profile_id,
                        model_count=model_count,
                    ),
                ),
            )
            for unit_id, datasheet_id, profile_id, model_count in units
        ),
    )


@cache
def _seeded_lifecycle_payload() -> GameLifecyclePayload:
    """Seed real domain objects, then hand all decisions to the adapter session."""

    base_catalog = ArmyCatalog.phase9a_canonical_content_pack()
    catalog = replace(
        base_catalog,
        wargear=tuple(
            replace(
                item,
                weapon_profiles=tuple(
                    replace(
                        profile,
                        keywords=(WeaponKeyword.HAZARDOUS,),
                        abilities=(),
                        ability_sources=tuple(
                            AbilitySourceInstance(
                                owner_id=profile.stable_identity(),
                                source_id=profile.stable_identity(),
                                source_instance_id=f"contract42-firing-deck-hazardous-{index}",
                                slot_id="hazardous",
                                ability_id=weapon_keyword_ability_id(WeaponKeyword.HAZARDOUS),
                            )
                            for index in range(2)
                        ),
                    )
                    for profile in item.weapon_profiles
                ),
            )
            if item.wargear_id == "core-bolt-rifle"
            else item
            for item in base_catalog.wargear
        ),
    )
    config = GameConfig(
        game_id="contract42-firing-deck-ui",
        allow_legacy_non_strict_rosters=True,
        ruleset_descriptor=RulesetDescriptor.warhammer_40000_eleventh(
            descriptor_version="contract42-firing-deck-ui-test"
        ),
        army_catalog=catalog,
        army_muster_requests=(
            _muster_request(
                catalog,
                player_id="player-a",
                units=(
                    (
                        "passenger-1",
                        "core-intercessor-like-infantry",
                        "core-intercessor-like",
                        5,
                    ),
                    (
                        "passenger-2",
                        "core-intercessor-like-infantry",
                        "core-intercessor-like",
                        5,
                    ),
                    ("transport-1", "core-transport", "core-transport", 1),
                ),
            ),
            _muster_request(
                catalog,
                player_id="player-b",
                units=(("enemy", "core-intercessor-like-infantry", "core-intercessor-like", 5),),
            ),
        ),
        player_ids=("player-a", "player-b"),
        turn_order=("player-a", "player-b"),
        fixed_secondary_mission_ids=("assassination", "bring_it_down", "cleanse"),
        mission_setup=_mission_setup(),
    )
    armies = tuple(
        muster_army(catalog=catalog, request=request, model_geometries=config.model_geometries)
        for request in config.army_muster_requests
    )
    battlefield = create_deterministic_battlefield_scenario(
        battlefield_id="contract42-firing-deck-field",
        battlefield_width_inches=100.0,
        battlefield_depth_inches=60.0,
        armies=armies,
    ).battlefield_state
    for army in armies:
        for unit in army.units:
            if unit.unit_instance_id in _CARGO:
                battlefield = battlefield.without_unit_placement(unit.unit_instance_id)
                continue
            x = 10.0 if unit.unit_instance_id == _TRANSPORT else 30.0
            battlefield = battlefield.with_unit_placement(
                UnitPlacement(
                    army_id=army.army_id,
                    player_id=army.player_id,
                    unit_instance_id=unit.unit_instance_id,
                    model_placements=tuple(
                        ModelPlacement(
                            army_id=army.army_id,
                            player_id=army.player_id,
                            unit_instance_id=unit.unit_instance_id,
                            model_instance_id=model.model_instance_id,
                            pose=Pose.at(x + index * 1.4, 35.0, facing_degrees=0.0),
                        )
                        for index, model in enumerate(unit.own_models)
                    ),
                )
            )
    lifecycle = GameLifecycle()
    lifecycle.start(config)
    lifecycle.decision_controller.event_log = EventLog()
    state = lifecycle.state
    assert state is not None
    for army in armies:
        state.record_army_definition(army)
    state.record_battlefield_state(battlefield)
    for player_id in state.player_ids:
        state.record_secondary_mission_choice(
            SecondaryMissionChoice(
                player_id=player_id,
                mode=SecondaryMissionMode.FIXED,
                fixed_mission_ids=("assassination", "bring_it_down"),
            )
        )
    state.stage = GameLifecycleStage.BATTLE
    state.setup_step_index = None
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.SHOOTING)
    state.battle_round = 1
    state.active_player_id = "player-a"
    state.record_transport_cargo_state(
        TransportCargoState(
            player_id="player-a",
            transport_unit_instance_id=_TRANSPORT,
            capacity_profile=TransportCapacityProfile(
                transport_datasheet_id="core-transport",
                max_model_count=10,
                allowed_keywords=("INFANTRY",),
            ),
            embarked_unit_instance_ids=_CARGO,
            phase_battle_round=1,
            started_phase_embarked_unit_instance_ids=_CARGO,
        )
    )
    assert state.shooting_phase_state is None  # Test-known initial empty shot state.
    objective_ids_before = tuple(row.state_id for row in state.primary_objective_turn_start_states)
    snapshot_ids_before = tuple(
        row.snapshot_id for row in state.primary_rules_unit_turn_start_snapshots
    )
    record_primary_turn_start_evidence(state=state, decisions=lifecycle.decision_controller)
    record_new_primary_turn_start_evidence_events(
        state=state,
        event_log=lifecycle.decision_controller.event_log,
        objective_state_ids_before=objective_ids_before,
        snapshot_ids_before=snapshot_ids_before,
    )
    return lifecycle.to_payload()


def _client() -> LocalSessionClient:
    return LocalSessionClient(
        session=LocalGameSession(
            lifecycle=GameLifecycle.from_payload(deepcopy(_seeded_lifecycle_payload()))
        )
    )


def _declaration_request(client: LocalSessionClient) -> UiDecision:
    status = client.advance_until_decision_or_terminal()
    assert status.status_kind == "waiting_for_decision", status
    unit = status.decision
    assert unit is not None
    assert unit.decision_type == "select_shooting_unit"
    assert _TRANSPORT in {option.option_id for option in unit.options}
    selected = client.submit_finite(
        request_id=unit.request_id,
        selected_option_id=_TRANSPORT,
        result_id="contract42:firing-deck:unit",
    )
    shooting_type = selected.decision
    assert shooting_type is not None
    assert shooting_type.decision_type == "select_shooting_type"
    assert "normal" in {option.option_id for option in shooting_type.options}
    typed = client.submit_finite(
        request_id=shooting_type.request_id,
        selected_option_id="normal",
        result_id="contract42:firing-deck:type",
    )
    decision = typed.decision
    assert decision is not None
    assert decision.decision_type == "submit_shooting_declaration"
    assert typed.status_kind == "waiting_for_decision"
    for viewer in ("player-a", "player-b"):
        projected = client.get_view(viewer).pending_decision
        assert projected is not None
        assert projected.request_id == decision.request_id
    return decision


def _inventory(decision: UiDecision) -> JsonObject:
    proposal = decision.parameterized_proposal
    assert proposal is not None
    inventory = proposal.payload
    assert inventory["firing_deck_embarked_unit_instance_ids"] == list(_CARGO)
    assert type(inventory["firing_deck_value"]) is int
    assert "already_shot_unit_instance_ids" not in inventory
    return inventory


def _workspace_for_choice(
    decision: UiDecision, *, source_unit_id: str | None
) -> tuple[AssignmentWorkspace, ShootingAssignmentSelection]:
    workspace = AssignmentWorkspace.start_for_pending(decision)
    assert workspace is not None
    choices = tuple(
        choice.selection
        for choice in workspace.shooting_choices
        if choice.selection.firing_deck_source_unit_instance_id == source_unit_id
        and choice.selection.target_unit_instance_id == _TARGET
    )
    assert choices
    return workspace, choices[0]


def _firing_deck_evidence(
    decision: UiDecision, selection: ShootingAssignmentSelection
) -> JsonObject:
    inventory = _inventory(decision)
    weapons = inventory["available_weapons"]
    assert type(weapons) is list
    weapon = next(
        row
        for row in weapons
        if type(row) is dict
        and row["weapon_instance_id"] == selection.weapon_instance_id
        and row["weapon_profile_id"] == selection.weapon_profile_id
        and row.get("firing_deck_source_unit_instance_id")
        == selection.firing_deck_source_unit_instance_id
    )
    assert type(weapon) is dict
    assert weapon["model_instance_id"] == selection.model_instance_id
    assert weapon["firing_deck_source_model_instance_id"] == (
        selection.firing_deck_source_model_instance_id
    )
    assert weapon["model_instance_id"] != weapon["firing_deck_source_model_instance_id"]
    return {
        "player_id": inventory["active_player_id"],
        "battle_round": inventory["battle_round"],
        "transport_unit_instance_id": inventory["unit_instance_id"],
        "firing_deck_value": inventory["firing_deck_value"],
        "weapon_selections": [
            {
                "weapon_instance_id": weapon["weapon_instance_id"],
                "embarked_unit_instance_id": weapon["firing_deck_source_unit_instance_id"],
                "model_instance_id": weapon["firing_deck_source_model_instance_id"],
                "wargear_id": weapon["wargear_id"],
                "weapon_profile": weapon["weapon_profile"],
            }
        ],
        # Fixture-only fact: this Transport is the first selected shooter this turn.
        "already_shot_unit_instance_ids": [],
    }


def _accepted_payloads(client: LocalSessionClient) -> tuple[JsonObject, JsonObject]:
    payloads: list[JsonObject] = []
    for viewer in ("player-a", "player-b"):
        events = (
            event
            for event in client.get_events_since(0, viewer).events
            if event["event_type"] == "shooting_declaration_accepted"
        )
        (accepted,) = tuple(events)
        payload = accepted["payload"]
        assert type(payload) is dict
        payloads.append(payload)
    return payloads[0], payloads[1]


def test_real_transport_declaration_preserves_borrowed_copy_and_all_cargo() -> None:
    client = _client()
    decision = _declaration_request(client)
    workspace, choice = _workspace_for_choice(decision, source_unit_id=_CARGO[0])
    assert choice.selected_weapon_ability_ids
    evidence = _firing_deck_evidence(decision, choice)
    selected = workspace.with_shooting_selections(
        decision, (choice,), firing_deck_selection=evidence
    )
    assert selected.is_ready, selected.diagnostic_lines
    payload = selected.payload_preview
    assert payload is not None
    (declaration,) = cast(list[JsonObject], payload["declarations"])
    (weapon,) = cast(list[JsonObject], evidence["weapon_selections"])
    assert declaration["attacker_model_instance_id"] == choice.model_instance_id
    assert declaration["weapon_instance_id"] == weapon["weapon_instance_id"]
    assert declaration["wargear_id"] == weapon["wargear_id"]
    weapon_profile = weapon["weapon_profile"]
    assert type(weapon_profile) is dict
    assert declaration["weapon_profile_id"] == weapon_profile["profile_id"]
    assert declaration["firing_deck_source_unit_instance_id"] == _CARGO[0]
    assert declaration["firing_deck_source_model_instance_id"] == weapon["model_instance_id"]
    assert declaration["selected_weapon_ability_ids"] == list(choice.selected_weapon_ability_ids)
    assert payload["firing_deck_selection"] == evidence

    status = client.submit_parameterized_payload(
        request_id=decision.request_id,
        payload=payload,
        result_id="contract42:firing-deck:accepted",
    )
    assert status.status_kind != "invalid", status.invalid_diagnostics
    owner, opponent = _accepted_payloads(client)
    assert owner == opponent
    assert owner["ineligible_unit_instance_ids"] == list(_CARGO)
    assert owner["request_id"] == decision.request_id
    pools = owner["attack_pools"]
    assert type(pools) is list
    assert pools
    assert all(type(pool) is dict for pool in pools)
    for pool in cast(list[JsonObject], pools):
        assert pool["weapon_instance_id"] == choice.weapon_instance_id
        assert pool["firing_deck_source_unit_instance_id"] == _CARGO[0]
        assert pool["firing_deck_source_model_instance_id"] == (
            choice.firing_deck_source_model_instance_id
        )
        assert pool["selected_weapon_ability_ids"] == list(choice.selected_weapon_ability_ids)


@pytest.mark.parametrize("drift", ["source", "physical_copy"])
def test_source_and_copy_drift_reject_without_state_or_event_mutation(drift: str) -> None:
    client = _client()
    decision = _declaration_request(client)
    workspace, choice = _workspace_for_choice(decision, source_unit_id=_CARGO[0])
    evidence = _firing_deck_evidence(decision, choice)
    selected = workspace.with_shooting_selections(
        decision, (choice,), firing_deck_selection=evidence
    )
    assert selected.is_ready
    assert selected.payload_preview is not None
    forged = deepcopy(selected.payload_preview)
    deck = forged["firing_deck_selection"]
    assert type(deck) is dict
    weapon_selections = deck["weapon_selections"]
    assert type(weapon_selections) is list
    assert type(weapon_selections[0]) is dict
    if drift == "source":
        weapon_selections[0]["embarked_unit_instance_id"] = _CARGO[1]
    else:
        other_weapons = _inventory(decision)["available_weapons"]
        assert type(other_weapons) is list
        other_copy = next(
            row
            for row in other_weapons
            if type(row) is dict and row.get("firing_deck_source_unit_instance_id") == _CARGO[1]
        )
        assert type(other_copy) is dict
        weapon_selections[0]["weapon_instance_id"] = other_copy["weapon_instance_id"]

    before_state = deepcopy(client.session.to_persistence_payload())
    before_events = tuple(
        client.get_events_since(0, viewer).events for viewer in ("player-a", "player-b")
    )
    status = client.submit_parameterized_payload(
        request_id=decision.request_id,
        payload=forged,
        result_id=f"contract42:firing-deck:invalid:{drift}",
    )
    assert status.status_kind == "invalid"
    assert status.invalid_diagnostics
    assert status.invalid_diagnostics[0].violation_code == "firing_deck_weapon_selection_drift"
    assert client.session.to_persistence_payload() == before_state
    for index, viewer in enumerate(("player-a", "player-b")):
        assert client.get_events_since(0, viewer).events == before_events[index]
        pending = client.get_view(viewer).pending_decision
        assert pending is not None
        assert pending.request_id == decision.request_id


@pytest.mark.parametrize("selection_kind", ["empty", "transport_only"])
def test_no_borrowed_contributors_still_records_every_cargo_unit(selection_kind: str) -> None:
    client = _client()
    decision = _declaration_request(client)
    workspace = AssignmentWorkspace.start_for_pending(decision)
    assert workspace is not None
    choices: tuple[ShootingAssignmentSelection, ...] = ()
    if selection_kind == "transport_only":
        workspace, own_choice = _workspace_for_choice(decision, source_unit_id=None)
        choices = (own_choice,)
    selected = workspace.with_shooting_selections(decision, choices)
    assert selected.is_ready, selected.diagnostic_lines
    payload = selected.payload_preview
    assert payload is not None
    assert payload["firing_deck_selection"] is None
    if selection_kind == "empty":
        assert payload["declarations"] == []
    status = client.submit_parameterized_payload(
        request_id=decision.request_id,
        payload=payload,
        result_id=f"contract42:firing-deck:{selection_kind}",
    )
    assert status.status_kind != "invalid", status.invalid_diagnostics
    owner, opponent = _accepted_payloads(client)
    assert owner == opponent
    assert owner["ineligible_unit_instance_ids"] == list(_CARGO)
    if selection_kind == "empty":
        assert owner["attack_pools"] == []
        assert owner["weapons_without_attacks"] == []
    else:
        pools = owner["attack_pools"]
        assert type(pools) is list
        assert pools
        assert all(type(pool) is dict for pool in pools)
        assert all(
            pool["firing_deck_source_unit_instance_id"] is None
            for pool in cast(list[JsonObject], pools)
        )
