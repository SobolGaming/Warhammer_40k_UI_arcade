"""Bounded Contract 42 setup and arrival consumers through real public sessions.

The test fixture seeds only domain state. Every request, projection, choice, and
placement tested below is emitted or submitted by LocalGameSession.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from typing import cast

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.core.attributes import Characteristic, CharacteristicValue
from warhammer40k_core.core.datasheet import (
    BaseSizeDefinition,
    CatalogAbilitySourceKind,
    CatalogAbilitySupport,
    CatalogJsonObject,
    DatasheetAbilityDescriptor,
)
from warhammer40k_core.engine.army_mustering import muster_army
from warhammer40k_core.engine.battlefield_state import ModelPlacement, UnitPlacement
from warhammer40k_core.engine.effects import EffectExpiration
from warhammer40k_core.engine.event_log import EventLog
from warhammer40k_core.engine.game_state import SecondaryMissionChoice, SecondaryMissionMode
from warhammer40k_core.engine.healing import healing_army_definitions_with_model_wounds
from warhammer40k_core.engine.lifecycle import GameLifecycle
from warhammer40k_core.engine.list_validation import UnitMusterSelection
from warhammer40k_core.engine.phase import BattlePhase, GameLifecycleStage
from warhammer40k_core.engine.placement import create_deterministic_battlefield_scenario
from warhammer40k_core.engine.primary_historical_events import (
    record_new_primary_turn_start_evidence_events,
)
from warhammer40k_core.engine.primary_turn_start_evidence import (
    record_primary_turn_start_evidence,
)
from warhammer40k_core.engine.reserve_arrival_requirements import (
    reposition_destruction_policy,
)
from warhammer40k_core.engine.reserves import ReserveKind, ReserveState
from warhammer40k_core.engine.shock_disembark import shock_disembark_permission_effect
from warhammer40k_core.engine.transports import TransportCapacityProfile, TransportCargoState
from warhammer40k_core.engine.wargear_selections import ModelProfileSelection
from warhammer40k_core.geometry.model_geometry import ModelGeometry
from warhammer40k_core.geometry.pose import Pose
from warhammer40k_core.rules.rule_ir import RuleIR
from warhammer40k_core.rules.source_packages.warhammer_40000_11th import faction_pack_rule_ir

from tests.support.contract42_battle_fixture import shooting_client
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    JsonValue,
    UiClientStatus,
    UiClientSubmissionError,
    UiDecision,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.core_projection import battlefield_view_from_game_view
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft
from warhammer40k_arcade_ui.state.placement_draft import PlacementDraft
from warhammer40k_arcade_ui.state.selection import SelectionState

pytestmark = pytest.mark.integration

_OWNER = "player-a"
_OPPONENT = "player-b"
_PASSENGER = "army-alpha:shooter"
_TRANSPORT = "army-alpha:transport"


def _current(client: LocalSessionClient) -> UiDecision:
    status = client.advance_until_decision_or_terminal()
    assert status.status_kind == "waiting_for_decision", status
    assert status.decision is not None
    return status.decision


def _choose(
    client: LocalSessionClient, request: UiDecision, option_id: str, label: str
) -> UiClientStatus:
    assert option_id in {option.option_id for option in request.options}
    return client.submit_finite(
        request_id=request.request_id,
        selected_option_id=option_id,
        result_id=f"contract42-setup-arrival:{label}",
    )


def _draft(client: LocalSessionClient) -> PlacementDraft:
    view = client.get_view(_OWNER)
    assert view.pending_decision is not None
    assert view.pending_decision.actor_id == _OWNER
    assert view.battlefield_view is not None
    result = PlacementDraft.start_for_pending(
        view=battlefield_view_from_game_view(view),
        selection=SelectionState.initial(default_preferences()),
        pending_decision=view.pending_decision,
        model_display_by_id=view.model_display_by_id,
        authoritative_models_by_id=view.battlefield_view.models_by_id,
        projection_state_hash=view.projection_state_hash,
    )
    assert result is not None
    assert result.proposal_request_id == view.pending_decision.request_id
    return result


def _placed(draft: PlacementDraft, points: tuple[tuple[float, float], ...]) -> PlacementDraft:
    assert len(points) == draft.total_model_count
    for point in points:
        draft = draft.place_current_model(point)
    draft = draft.mark_ready()
    assert draft.is_ready
    assert draft.payload_preview is not None
    return draft


def _submit(client: LocalSessionClient, draft: PlacementDraft, label: str) -> UiClientStatus:
    assert draft.payload_preview is not None
    return client.submit_parameterized_payload(
        request_id=draft.proposal_request_id,
        payload=draft.payload_preview,
        result_id=f"contract42-setup-arrival:{label}",
    )


def _state_snapshot(client: LocalSessionClient) -> JsonObject:
    session = client.session
    assert isinstance(session, LocalGameSession)
    state = session.lifecycle.state
    assert state is not None
    payload = cast(JsonObject, state.to_payload())
    return {
        key: payload[key]
        for key in (
            "army_definitions",
            "battlefield_state",
            "reserve_states",
            "transport_cargo_states",
        )
    }


def _reserve_client(
    *, oversized: bool = False, aircraft: bool = False, support_unit: bool = False
) -> LocalSessionClient:
    client = _reserve_support_client() if support_unit else shooting_client(models=1)
    session = client.session
    assert isinstance(session, LocalGameSession)
    lifecycle = session.lifecycle
    state = lifecycle.state
    assert state is not None
    assert state.battlefield_state is not None
    unit = state.army_definitions[0].unit_by_id(_PASSENGER)
    if oversized:
        base = BaseSizeDefinition.circular(200.0)
        model = replace(
            unit.own_models[0],
            base_size=base,
            geometry=ModelGeometry.from_base_size(
                base,
                geometry_source_id="contract42-setup-oversized",
                keywords=unit.keywords,
            ),
        )
        unit = replace(unit, own_models=(model,))
    if aircraft:
        unit = replace(
            unit,
            own_models=tuple(
                replace(
                    model,
                    keyword_assignment=replace(
                        model.keyword_assignment,
                        keywords=(*model.keywords, "AIRCRAFT", "FLY"),
                    ),
                )
                for model in unit.own_models
            ),
        )
    state.army_definitions[0] = replace(
        state.army_definitions[0],
        units=tuple(
            unit if candidate.unit_instance_id == _PASSENGER else candidate
            for candidate in state.army_definitions[0].units
        ),
    )
    state.replace_battlefield_state(state.battlefield_state.without_unit_placement(_PASSENGER))
    assert state.mission_setup is not None
    state.mission_setup = replace(
        state.mission_setup,
        attacker_battlefield_edge="south_west_corner" if oversized else "south",
        defender_battlefield_edge="north_east_corner" if oversized else "north",
    )
    state.stage = GameLifecycleStage.BATTLE
    state.setup_step_index = None
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.MOVEMENT)
    state.battle_round = 2
    state.active_player_id = _OWNER
    reserve = ReserveState.declared_before_battle(
        player_id=_OWNER,
        unit_instance_id=_PASSENGER,
        reserve_kind=ReserveKind.STRATEGIC_RESERVES,
        destruction_deadline_policy=reposition_destruction_policy(
            mission_setup=state.mission_setup,
            destruction_deadline_policy=None,
        ),
    )
    state.record_reserve_state(reserve)
    lifecycle.decision_controller.event_log.append(
        "reserve_unit_declared",
        {
            "game_id": state.game_id,
            "player_id": _OWNER,
            "unit_instance_id": _PASSENGER,
            "reserve_state": reserve.to_payload(),
        },
    )
    if support_unit:
        objective_ids_before = tuple(
            row.state_id for row in state.primary_objective_turn_start_states
        )
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
    return client


def _reserve_support_client() -> LocalSessionClient:
    """Add a separate mustered friendly shooter to expose the owner's phase after ingress."""

    baseline = shooting_client(models=1)
    session = baseline.session
    assert isinstance(session, LocalGameSession)
    initial = session.lifecycle.config
    alpha, beta = initial.army_muster_requests
    support = replace(alpha.unit_selections[0], unit_selection_id="support")
    config = replace(
        initial,
        game_id="contract42-oversized-setup-turn-ui",
        army_muster_requests=(
            replace(alpha, unit_selections=(*alpha.unit_selections, support)),
            beta,
        ),
    )
    armies = tuple(
        muster_army(catalog=config.army_catalog, request=request)
        for request in config.army_muster_requests
    )
    mission = config.mission_setup
    assert mission is not None
    battlefield = create_deterministic_battlefield_scenario(
        battlefield_id="contract42-oversized-setup-turn-field",
        battlefield_width_inches=mission.battlefield_width_inches,
        battlefield_depth_inches=mission.battlefield_depth_inches,
        armies=armies,
    ).battlefield_state
    for army in armies:
        for unit in army.units:
            if unit.unit_instance_id == _PASSENGER:
                continue
            x = 10.0 if unit.unit_instance_id == "army-alpha:support" else 30.0
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
                            pose=Pose.at(x + index * 1.4, 35.0),
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
    return LocalSessionClient(session=LocalGameSession(lifecycle=lifecycle))


def _transport_client(*, reserve: bool = False, shock: bool = False) -> LocalSessionClient:
    baseline = shooting_client(models=1)
    baseline_session = baseline.session
    assert isinstance(baseline_session, LocalGameSession)
    initial = baseline_session.lifecycle.config
    alpha, beta = initial.army_muster_requests
    config = replace(
        initial,
        game_id="contract42-transport-arrival-ui",
        army_muster_requests=(
            replace(
                alpha,
                unit_selections=(
                    *alpha.unit_selections,
                    UnitMusterSelection(
                        unit_selection_id="transport",
                        datasheet_id="core-transport",
                        model_profile_selections=(
                            ModelProfileSelection(model_profile_id="core-transport", model_count=1),
                        ),
                    ),
                ),
            ),
            beta,
        ),
    )
    armies = tuple(
        muster_army(catalog=config.army_catalog, request=request)
        for request in config.army_muster_requests
    )
    battlefield = create_deterministic_battlefield_scenario(
        battlefield_id="contract42-transport-arrival-field",
        battlefield_width_inches=100.0,
        battlefield_depth_inches=60.0,
        armies=armies,
    ).battlefield_state
    for army in armies:
        for unit in army.units:
            if unit.unit_instance_id == _PASSENGER or (
                reserve and unit.unit_instance_id == _TRANSPORT
            ):
                battlefield = battlefield.without_unit_placement(unit.unit_instance_id)
                continue
            x, y = (
                (10.0, 10.0)
                if unit.unit_instance_id == _TRANSPORT
                else (50.0, 35.0)
                if reserve
                else (14.5, 10.0)
            )
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
                            pose=Pose.at(x + index * 1.4, y),
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
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.MOVEMENT)
    state.battle_round = 2 if reserve else 1
    state.active_player_id = _OWNER
    state.record_transport_cargo_state(
        TransportCargoState(
            player_id=_OWNER,
            transport_unit_instance_id=_TRANSPORT,
            capacity_profile=TransportCapacityProfile(
                transport_datasheet_id="core-transport",
                max_model_count=12,
                allowed_keywords=("INFANTRY",),
                source_id="contract42-transport-capacity",
            ),
            embarked_unit_instance_ids=(_PASSENGER,),
            phase_battle_round=state.battle_round,
            started_phase_embarked_unit_instance_ids=(_PASSENGER,),
        )
    )
    if reserve:
        reserve_state = ReserveState.declared_before_battle(
            player_id=_OWNER,
            unit_instance_id=_TRANSPORT,
            reserve_kind=ReserveKind.STRATEGIC_RESERVES,
            embarked_unit_instance_ids=(_PASSENGER,),
            destruction_deadline_policy=reposition_destruction_policy(
                mission_setup=state.mission_setup,
                destruction_deadline_policy=None,
            ),
        )
        state.record_reserve_state(reserve_state)
        lifecycle.decision_controller.event_log.append(
            "reserve_unit_declared",
            {
                "game_id": state.game_id,
                "player_id": _OWNER,
                "unit_instance_id": _TRANSPORT,
                "reserve_state": reserve_state.to_payload(),
            },
        )
    if shock:
        state.record_persisting_effect(
            shock_disembark_permission_effect(
                effect_id="contract42-shock-grant",
                source_rule_id="contract42-shock-source",
                owner_player_id=_OWNER,
                transport_unit_instance_id=_TRANSPORT,
                eligible_rules_unit_instance_ids=(_PASSENGER,),
                started_battle_round=state.battle_round,
                started_phase=BattlePhase.MOVEMENT,
                expiration=EffectExpiration.end_phase(
                    battle_round=state.battle_round,
                    phase=BattlePhase.MOVEMENT,
                    player_id=_OWNER,
                ),
            )
        )
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
    return LocalSessionClient(session=LocalGameSession(lifecycle=lifecycle))


def _revival_client() -> LocalSessionClient:
    """Seed a casualty and loaded catalog source, then let Command emit the request."""

    baseline = shooting_client(models=1)
    baseline_session = baseline.session
    assert isinstance(baseline_session, LocalGameSession)
    initial = baseline_session.lifecycle.config
    source = faction_pack_rule_ir.datasheet_rule_ir_payload_by_source_row_id("000000588:5")
    assert source is not None
    rule_ir = RuleIR.from_payload(source)
    ability = DatasheetAbilityDescriptor(
        ability_id="contract42-revival-restoration",
        name="Contract 42 restoration",
        source_id=rule_ir.source_id,
        support=CatalogAbilitySupport.GENERIC_RULE_IR,
        source_kind=CatalogAbilitySourceKind.DATASHEET,
        effect_description=rule_ir.normalized_text,
        rule_ir_payload=cast(CatalogJsonObject, rule_ir.to_payload()),
    )
    catalog = replace(
        initial.army_catalog,
        datasheets=tuple(
            replace(sheet, abilities=(*sheet.abilities, ability))
            if sheet.datasheet_id == "core-character-leader"
            else replace(
                sheet,
                keywords=replace(
                    sheet.keywords,
                    keywords=(*sheet.keywords.keywords, "WRAITH CONSTRUCT"),
                ),
            )
            if sheet.datasheet_id == "core-intercessor-like-infantry"
            else sheet
            for sheet in initial.army_catalog.datasheets
        ),
    )
    alpha, beta = initial.army_muster_requests
    recipient = replace(
        alpha.unit_selections[0],
        model_profile_selections=(
            ModelProfileSelection(model_profile_id="core-intercessor-like", model_count=5),
        ),
    )
    leader = UnitMusterSelection(
        unit_selection_id="leader",
        datasheet_id="core-character-leader",
        model_profile_selections=(
            ModelProfileSelection(model_profile_id="core-character-leader", model_count=1),
        ),
    )
    enemy = replace(
        beta.unit_selections[0],
        model_profile_selections=(
            ModelProfileSelection(model_profile_id="core-intercessor-like", model_count=5),
        ),
    )
    second_enemy = replace(enemy, unit_selection_id="new-enemy")
    config = replace(
        initial,
        game_id="contract42-revival-ui",
        army_catalog=catalog,
        army_muster_requests=(
            replace(
                alpha,
                unit_selections=(recipient, leader),
            ),
            replace(beta, unit_selections=(enemy, second_enemy)),
        ),
    )
    armies = tuple(
        muster_army(catalog=catalog, request=request) for request in config.army_muster_requests
    )
    battlefield = create_deterministic_battlefield_scenario(
        battlefield_id="contract42-revival-field",
        battlefield_width_inches=100.0,
        battlefield_depth_inches=60.0,
        armies=armies,
    ).battlefield_state
    positions = {
        _PASSENGER: tuple(Pose.at(10.0, 10.0 + 1.5 * i) for i in range(5)),
        "army-alpha:leader": (Pose.at(8.5, 14.5),),
        "army-beta:enemy": (
            Pose.at(12.0, 10.0),
            Pose.at(13.0, 11.5),
            Pose.at(13.0, 13.0),
            Pose.at(13.0, 14.5),
            Pose.at(14.5, 14.5),
        ),
        "army-beta:new-enemy": (
            Pose.at(13.0, 16.5),
            Pose.at(14.5, 16.5),
            Pose.at(16.0, 16.5),
            Pose.at(17.5, 16.5),
            Pose.at(19.0, 16.5),
        ),
    }
    for army in armies:
        for unit in army.units:
            poses = positions[unit.unit_instance_id]
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
                            pose=pose,
                        )
                        for model, pose in zip(unit.own_models, poses, strict=True)
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
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.COMMAND)
    state.battle_round = 1
    state.active_player_id = _OWNER
    removed_id = armies[0].unit_by_id(_PASSENGER).own_models[-1].model_instance_id
    state.replace_army_definitions(
        list(
            healing_army_definitions_with_model_wounds(
                armies=tuple(state.army_definitions),
                model_instance_id=removed_id,
                wounds_remaining=0,
            )
        )
    )
    assert state.battlefield_state is not None
    state.replace_battlefield_state(state.battlefield_state.with_removed_models((removed_id,)))
    return LocalSessionClient(
        session=LocalGameSession(lifecycle=GameLifecycle.from_payload(lifecycle.to_payload()))
    )


def _aircraft_return_client() -> LocalSessionClient:
    """Seed a placed Aircraft at the opponent's Fight phase and let turn end run."""

    baseline = shooting_client(models=1)
    baseline_session = baseline.session
    assert isinstance(baseline_session, LocalGameSession)
    initial = baseline_session.lifecycle.config
    catalog = replace(
        initial.army_catalog,
        datasheets=tuple(
            replace(
                sheet,
                keywords=replace(
                    sheet.keywords,
                    keywords=(*sheet.keywords.keywords, "AIRCRAFT", "FLY"),
                ),
                model_profiles=tuple(
                    replace(
                        profile,
                        characteristics=tuple(
                            CharacteristicValue.source_dash(value.characteristic)
                            if value.characteristic
                            in {Characteristic.MOVEMENT, Characteristic.OBJECTIVE_CONTROL}
                            else value
                            for value in profile.characteristics
                        ),
                    )
                    for profile in sheet.model_profiles
                ),
            )
            if sheet.datasheet_id == "core-intercessor-like-infantry"
            else sheet
            for sheet in initial.army_catalog.datasheets
        ),
    )
    config = replace(
        initial,
        game_id="contract42-aircraft-return-ui",
        army_catalog=catalog,
    )
    armies = tuple(
        muster_army(catalog=catalog, request=request) for request in config.army_muster_requests
    )
    battlefield = create_deterministic_battlefield_scenario(
        battlefield_id="contract42-aircraft-return-field",
        battlefield_width_inches=100.0,
        battlefield_depth_inches=60.0,
        armies=armies,
    ).battlefield_state
    for army in armies:
        unit = army.units[0]
        battlefield = battlefield.with_unit_placement(
            UnitPlacement(
                army_id=army.army_id,
                player_id=army.player_id,
                unit_instance_id=unit.unit_instance_id,
                model_placements=(
                    ModelPlacement(
                        army_id=army.army_id,
                        player_id=army.player_id,
                        unit_instance_id=unit.unit_instance_id,
                        model_instance_id=unit.own_models[0].model_instance_id,
                        pose=Pose.at(10.0 if army.player_id == _OWNER else 30.0, 35.0),
                    ),
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
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.FIGHT)
    state.battle_round = 1
    state.active_player_id = _OPPONENT
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
    return LocalSessionClient(
        session=LocalGameSession(lifecycle=GameLifecycle.from_payload(lifecycle.to_payload()))
    )


def _movement_placement(
    client: LocalSessionClient,
    unit_id: str,
    action: str,
    *,
    result_suffix: str = "",
) -> UiDecision:
    unit = _current(client)
    assert unit.decision_type == "select_movement_unit"
    assert unit.actor_id == _OWNER
    selected = _choose(client, unit, unit_id, f"unit-{action}{result_suffix}")
    decision = selected.decision
    assert decision is not None
    assert decision.decision_type == "select_movement_action"
    placed = _choose(client, decision, action, f"action-{action}{result_suffix}")
    assert placed.status_kind == "waiting_for_decision", placed
    proposal = placed.decision
    assert proposal is not None
    assert proposal.decision_type == "submit_placement_proposal"
    assert proposal.actor_id == _OWNER
    assert proposal.placement_proposal is not None
    assert proposal.placement_proposal.source_decision_request_id == decision.request_id
    return proposal


def test_public_nullable_edges_corner_and_oversized_setup_retry() -> None:
    ordinary = shooting_client(models=1)
    ordinary_mission = ordinary.get_view(_OWNER).mission_setup
    assert type(ordinary_mission) is dict
    assert ordinary_mission["attacker_battlefield_edge"] is None
    assert ordinary_mission["defender_battlefield_edge"] is None

    client = _reserve_client(oversized=True)
    for viewer in (_OWNER, _OPPONENT):
        mission = client.get_view(viewer).mission_setup
        assert type(mission) is dict
        assert mission["attacker_battlefield_edge"] == "south_west_corner"
        assert mission["defender_battlefield_edge"] == "north_east_corner"
    request = _movement_placement(client, _PASSENGER, "ingress")
    proposal = request.placement_proposal
    assert proposal is not None
    assert proposal.context["model_instance_ids"] == [
        "army-alpha:shooter:core-intercessor-like:001"
    ]
    first = _draft(client)
    # The player explicitly chooses the published corner's south edge. This is
    # submitted as intent; the engine proves whether the exception is legal.
    source_model_id = first.model_poses[0].model_id
    assert first.context is not None
    large_model_exceptions: list[JsonValue] = [
        {"model_instance_id": source_model_id, "battlefield_edge": "south"}
    ]
    first = replace(
        first,
        context={
            **first.context,
            "large_model_exceptions": large_model_exceptions,
        },
    )
    invalid_draft = _placed(first, ((15.0, 8.0),))
    assert invalid_draft.payload_preview is not None
    assert invalid_draft.payload_preview["large_model_exceptions"] == large_model_exceptions
    before = _state_snapshot(client)
    invalid = _submit(client, invalid_draft, "oversized-no-contact")
    assert invalid.status_kind == "invalid"
    assert type(invalid.payload) is dict
    violations = invalid.payload["violations"]
    assert type(violations) is list
    assert any(
        type(violation) is dict
        and violation["violation_code"] == "large_model_exception_edge_contact_missing"
        for violation in violations
    )
    assert _state_snapshot(client) == before
    retry_selection = _current(client)
    assert retry_selection.decision_type == "select_movement_unit"
    assert retry_selection.request_id != request.request_id
    assert _PASSENGER in {option.option_id for option in retry_selection.options}
    retry = _movement_placement(client, _PASSENGER, "ingress", result_suffix="-oversized-retry")
    assert retry.request_id != request.request_id
    assert retry.placement_proposal is not None
    assert retry.placement_proposal.source_decision_request_id != (
        proposal.source_decision_request_id
    )
    assert (
        retry.placement_proposal.context["model_instance_ids"]
        == (proposal.context["model_instance_ids"])
    )
    next_draft = _draft(client)
    assert next_draft.context is not None
    next_draft = replace(
        next_draft,
        context={
            **next_draft.context,
            "large_model_exceptions": large_model_exceptions,
        },
    )
    accepted_draft = _placed(next_draft, ((15.0, 200.0 / 25.4 / 2.0),))
    accepted = _submit(client, accepted_draft, "oversized-contact")
    assert accepted.status_kind != "invalid", accepted
    for viewer in (_OWNER, _OPPONENT):
        arrivals = (
            event
            for event in client.get_events_since(0, viewer).events
            if event["event_type"] == "reinforcement_unit_arrived"
        )
        arrival_payloads = [event["payload"] for event in arrivals]
        assert all(type(payload) is dict for payload in arrival_payloads)
        assert any(
            type(payload) is dict and payload["unit_instance_id"] == _PASSENGER
            for payload in arrival_payloads
        )
    movement = _current(client)
    assert movement.decision_type == "select_movement_unit"
    assert _PASSENGER not in {option.option_id for option in movement.options}
    assert any(
        diagnostic.violation_code == "large_model_exception_edge_contact_missing"
        for diagnostic in invalid.invalid_diagnostics
    )


@pytest.mark.parametrize("oversized", [False, True])
def test_oversized_arrival_locks_shooting_during_affected_players_setup_turn(
    oversized: bool,
) -> None:
    client = _reserve_client(oversized=oversized, support_unit=True)
    request = _movement_placement(client, _PASSENGER, "ingress")
    draft = _draft(client)
    if oversized:
        model_id = draft.model_poses[0].model_id
        assert draft.context is not None
        draft = replace(
            draft,
            context={
                **draft.context,
                "large_model_exceptions": [
                    {"model_instance_id": model_id, "battlefield_edge": "south"}
                ],
            },
        )
    ready = _placed(draft, ((15.0, 200.0 / 25.4 / 2.0 if oversized else 3.0),))
    arrived = _submit(client, ready, "oversized-owner-turn")
    assert arrived.status_kind != "invalid", arrived
    assert request.actor_id == _OWNER
    movement = _current(client)
    assert movement.actor_id == _OWNER
    assert movement.decision_type == "select_movement_unit"
    movement_options = {option.option_id for option in movement.options}
    assert "army-alpha:support" in movement_options
    # Core's ordinary ingress lock excludes both cases from further Movement.
    assert _PASSENGER not in movement_options
    selected = _choose(client, movement, "army-alpha:support", "support-movement")
    action = selected.decision
    assert action is not None
    assert action.actor_id == _OWNER
    assert action.decision_type == "select_movement_action"
    stationary = _choose(client, action, "remain_stationary", "support-stationary")
    assert stationary.status_kind != "invalid", stationary
    for viewer in (_OWNER, _OPPONENT):
        view = client.get_view(viewer)
        assert view.active_player_id == _OWNER
        assert view.battle_round == 2
        assert view.current_battle_phase == "shooting"
        assert view.pending_decision is not None
        assert view.pending_decision.actor_id == _OWNER
        assert view.pending_decision.decision_type == "select_shooting_unit"
        option_ids = {option.option_id for option in view.pending_decision.options}
        assert "army-alpha:support" in option_ids
        assert (_PASSENGER in option_ids) == (not oversized)
    current = _current(client)
    assert current.actor_id == _OWNER
    assert current.decision_type == "select_shooting_unit"
    assert (_PASSENGER in {option.option_id for option in current.options}) == (not oversized)
    if oversized:
        before = _state_snapshot(client)
        owner_events = client.get_events_since(0, _OWNER).events
        with pytest.raises(UiClientSubmissionError):
            client.submit_finite(
                request_id=current.request_id,
                selected_option_id=_PASSENGER,
                result_id="contract42-setup-arrival:locked-shooter-forged",
            )
        assert _state_snapshot(client) == before
        assert client.get_events_since(0, _OWNER).events == owner_events
        assert client.get_view(_OWNER).pending_decision == current


def test_round_one_reserve_placement_reports_source_deadline_with_retry() -> None:
    client = _reserve_client()
    session = client.session
    assert isinstance(session, LocalGameSession)
    state = session.lifecycle.state
    assert state is not None
    policy = session.lifecycle.config.ruleset_descriptor.mission_policy
    assert policy.reserves_arrival_blocked_battle_rounds == (1,)
    state.battle_round = 1
    request = _current(client)
    assert request.decision_type == "select_movement_unit"
    # The finite selector offers the unit; Core's placement resolution still
    # validates the source-backed round-one arrival restriction.
    assert _PASSENGER in {option.option_id for option in request.options}
    for viewer in (_OWNER, _OPPONENT):
        view = client.get_view(viewer)
        assert view.pending_decision is not None
        assert view.pending_decision.request_id == request.request_id
    proposal = _movement_placement(client, _PASSENGER, "ingress")
    assert proposal.actor_id == _OWNER
    ready = _placed(_draft(client), ((15.0, 3.0),))
    before = _state_snapshot(client)
    events_before = client.get_events_since(0, _OWNER).events
    invalid = _submit(client, ready, "round-one-deadline")
    assert invalid.status_kind == "invalid"
    assert {
        "reserve_arrival_battle_round_forbidden",
        "strategic_reserves_battle_round_1",
    } <= {diagnostic.violation_code for diagnostic in invalid.invalid_diagnostics}
    assert _state_snapshot(client) == before
    after_events = client.get_events_since(0, _OWNER).events
    assert tuple(event["event_type"] for event in after_events[len(events_before) :]) == (
        "decision_recorded",
        "reinforcement_placement_invalid",
        "movement_setup_failed",
        "decision_requested",
    )
    assert not any(event["event_type"] == "reinforcement_unit_arrived" for event in after_events)
    retry = client.get_view(_OWNER).pending_decision
    assert retry is not None
    assert retry.actor_id == _OWNER
    assert retry.decision_type == "select_movement_unit"
    assert retry.request_id != proposal.request_id
    assert _PASSENGER in {option.option_id for option in retry.options}
    for viewer in (_OWNER, _OPPONENT):
        projected = client.get_view(viewer).pending_decision
        assert projected is not None
        assert projected.request_id == retry.request_id
    selected = _choose(client, retry, _PASSENGER, "round-one-reselect")
    action = selected.decision
    assert action is not None
    assert action.decision_type == "select_movement_action"
    assert "remain_stationary" in {option.option_id for option in action.options}
    stationary = _choose(client, action, "remain_stationary", "round-one-stationary")
    assert stationary.status_kind != "invalid"
    assert _state_snapshot(client) == before
    assert not any(
        event["event_type"] == "reinforcement_unit_arrived"
        for event in client.get_events_since(0, _OWNER).events
    )


def test_round_three_unarrived_reserve_deadline_continues_through_public_session() -> None:
    client = _transport_client(reserve=True)
    session = client.session
    assert isinstance(session, LocalGameSession)
    state = session.lifecycle.state
    assert state is not None
    state.battle_round = 3
    state.active_player_id = _OPPONENT
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.FIGHT)
    objective_ids_before = tuple(row.state_id for row in state.primary_objective_turn_start_states)
    snapshot_ids_before = tuple(
        row.snapshot_id for row in state.primary_rules_unit_turn_start_snapshots
    )
    record_primary_turn_start_evidence(state=state, decisions=session.lifecycle.decision_controller)
    record_new_primary_turn_start_evidence_events(
        state=state,
        event_log=session.lifecycle.decision_controller.event_log,
        objective_state_ids_before=objective_ids_before,
        snapshot_ids_before=snapshot_ids_before,
    )
    restored = GameLifecycle.from_payload(session.lifecycle.to_payload())
    client = LocalSessionClient(session=LocalGameSession(lifecycle=restored))
    before = client.get_view(_OWNER)
    assert before.battle_round == 3
    assert before.active_player_id == _OPPONENT
    assert before.current_battle_phase == "fight"
    assert before.battlefield_view is not None
    transport_model = next(
        model.model_instance_id
        for unit in state.army_definitions[0].units
        if unit.unit_instance_id == _TRANSPORT
        for model in unit.own_models
    )
    passenger_model = next(
        model.model_instance_id
        for unit in state.army_definitions[0].units
        if unit.unit_instance_id == _PASSENGER
        for model in unit.own_models
    )
    before_model = before.battlefield_view.models_by_id[transport_model]
    assert type(before_model) is dict
    assert before_model["state"] == "reserves"
    before_passenger = before.battlefield_view.models_by_id[passenger_model]
    assert type(before_passenger) is dict
    assert before_passenger["state"] == "embarked"

    advanced = client.advance_until_decision_or_terminal()
    assert advanced.status_kind == "waiting_for_decision"
    assert advanced.decision is not None
    assert advanced.decision.decision_type == "select_movement_unit"
    assert advanced.decision.actor_id == _OPPONENT
    for viewer in (_OWNER, _OPPONENT):
        after = client.get_view(viewer)
        assert after.battle_round == 4
        assert after.active_player_id == _OPPONENT
        assert after.current_battle_phase == "movement"
        assert after.battlefield_view is not None
        after_model = after.battlefield_view.models_by_id[transport_model]
        assert type(after_model) is dict
        assert after_model["state"] == "destroyed"
        assert after_model["pose"] is None
        after_passenger = after.battlefield_view.models_by_id[passenger_model]
        assert type(after_passenger) is dict
        assert after_passenger["state"] == "destroyed"
        assert after_passenger["pose"] is None
        if after.pending_decision is not None:
            assert {_TRANSPORT, _PASSENGER}.isdisjoint(
                option.option_id for option in after.pending_decision.options
            )


def test_aircraft_reserve_only_offers_current_ingress_and_no_hover_action() -> None:
    client = _reserve_client(aircraft=True)
    unit = _current(client)
    assert unit.decision_type == "select_movement_unit"
    assert _PASSENGER in {option.option_id for option in unit.options}
    selected = _choose(client, unit, _PASSENGER, "aircraft-unit")
    action = selected.decision
    assert action is not None
    assert action.actor_id == _OWNER
    assert action.decision_type == "select_movement_action"
    option_ids = {option.option_id for option in action.options}
    assert "ingress" in option_ids
    assert option_ids.isdisjoint({"normal", "advance", "fall_back", "hover", "toggle_hover"})
    for viewer in (_OWNER, _OPPONENT):
        view = client.get_view(viewer)
        assert view.pending_decision is not None
        assert view.pending_decision.request_id == action.request_id


def test_mandatory_aircraft_return_is_public_and_next_action_has_no_hover() -> None:
    client = _aircraft_return_client()
    request = _current(client)
    assert request.decision_type == "select_movement_unit"
    assert request.actor_id == _OWNER
    assert _PASSENGER in {option.option_id for option in request.options}
    for viewer in (_OWNER, _OPPONENT):
        events = tuple(
            event
            for event in client.get_events_since(0, viewer).events
            if event["event_type"] == "aircraft_opponent_turn_end_departure"
        )
        assert len(events) == 1
        payload = events[0]["payload"]
        assert type(payload) is dict
        assert payload["active_player_id"] == _OPPONENT
        assert payload["player_id"] == _OWNER
        assert payload["unit_instance_id"] == _PASSENGER
        assert payload["source_rule_id"] == "gw-11e-core-aircraft:movement"
        reserve_state = payload["reserve_state"]
        assert type(reserve_state) is dict
        assert reserve_state["reserve_kind"] == "strategic_reserves"
        view = client.get_view(viewer)
        assert view.pending_decision is not None
        assert view.pending_decision.request_id == request.request_id
        assert view.battlefield_view is not None
        model = view.battlefield_view.models_by_id["army-alpha:shooter:core-intercessor-like:001"]
        assert type(model) is dict
        assert model["state"] == "reserves"
    selected = _choose(client, request, _PASSENGER, "returned-aircraft")
    action = selected.decision
    assert action is not None
    assert action.decision_type == "select_movement_action"
    option_ids = {option.option_id for option in action.options}
    assert "ingress" in option_ids
    assert option_ids.isdisjoint({"normal_move", "advance", "fall_back", "hover", "toggle_hover"})


def test_shock_public_source_and_empty_engagement_are_viewer_consistent() -> None:
    client = _transport_client(shock=True)
    request = _movement_placement(client, _PASSENGER, "disembark:shock_disembark")
    assert request.placement_proposal is not None
    public_context = request.placement_proposal.context
    assert public_context["start_engaged_enemy_unit_instance_ids"] == []
    assert public_context["restriction_overrides"] == [
        {"override_kind": "allow_shock_disembark", "source_rule_id": "contract42-shock-source"}
    ]
    for viewer in (_OWNER, _OPPONENT):
        projected = client.get_view(viewer).pending_decision
        assert projected is not None
        assert projected.request_id == request.request_id
        assert projected.actor_id == request.actor_id
        assert projected.placement_proposal is not None
        assert projected.placement_proposal.context == public_context


def test_loaded_transport_ingress_rapid_disembark_retry_and_private_redaction() -> None:
    client = _transport_client(reserve=True)
    ingress = _movement_placement(client, _TRANSPORT, "ingress")
    draft = _placed(_draft(client), ((12.0, 2.0),))
    assert draft.proposal_request_id == ingress.request_id
    accepted = _submit(client, draft, "transport-ingress")
    assert accepted.status_kind != "invalid", accepted
    for viewer in (_OWNER, _OPPONENT):
        public = {
            "view": asdict(client.get_view(viewer)),
            "events": client.get_events_since(0, viewer).events,
        }
        assert "ingress_placement_restrictions" not in json.dumps(public)
        assert "ingress_placement_history_origin" not in json.dumps(public)
    passenger = _movement_placement(client, _PASSENGER, "disembark")
    context = passenger.placement_proposal
    assert context is not None
    assert context.context["disembark_mode"] == "rapid_disembark"
    assert context.context["transport_unit_instance_id"] == _TRANSPORT
    invalid_draft = _placed(_draft(client), ((12.0, 5.7),))
    before = _state_snapshot(client)
    invalid = _submit(client, invalid_draft, "rapid-invalid")
    assert invalid.status_kind == "invalid"
    assert type(invalid.payload) is dict
    violations = invalid.payload["violations"]
    assert type(violations) is list
    assert any(
        type(violation) is dict
        and violation["violation_code"] == "rapid_disembark_ingress_restriction"
        for violation in violations
    )
    assert _state_snapshot(client) == before
    retry_selection = _current(client)
    assert retry_selection.decision_type == "select_movement_unit"
    assert retry_selection.request_id != passenger.request_id
    assert _PASSENGER in {option.option_id for option in retry_selection.options}
    retry = _movement_placement(client, _PASSENGER, "disembark", result_suffix="-rapid-retry")
    assert retry.placement_proposal is not None
    assert retry.placement_proposal.source_decision_request_id != context.source_decision_request_id
    assert retry.placement_proposal.context["disembark_mode"] == "rapid_disembark"
    assert retry.placement_proposal.context["transport_unit_instance_id"] == _TRANSPORT
    valid = _placed(_draft(client), ((12.0, 5.0),))
    assert valid.proposal_request_id == retry.request_id
    accepted = _submit(client, valid, "rapid-valid")
    assert accepted.status_kind != "invalid", accepted
    for viewer in (_OWNER, _OPPONENT):
        public = {
            "view": asdict(client.get_view(viewer)),
            "events": client.get_events_since(0, viewer).events,
        }
        assert "ingress_placement_restrictions" not in json.dumps(public)
        assert "ingress_placement_history_origin" not in json.dumps(public)
    assert any(
        diagnostic.violation_code == "rapid_disembark_ingress_restriction"
        for diagnostic in invalid.invalid_diagnostics
    )


def test_tactical_disembark_setup_history_suppresses_later_embark_option() -> None:
    client = _transport_client()
    request = _movement_placement(client, _PASSENGER, "disembark")
    assert request.placement_proposal is not None
    assert request.placement_proposal.context["disembark_mode"] == "tactical_disembark"
    placed = _submit(client, _placed(_draft(client), ((10.0, 13.0),)), "tactical-setup")
    assert placed.status_kind != "invalid", placed
    action = placed.decision
    assert action is not None
    assert action.decision_type == "select_movement_action"
    assert "normal_move" in {option.option_id for option in action.options}
    selected = _choose(client, action, "normal_move", "after-tactical-normal")
    movement = selected.decision
    assert movement is not None
    assert movement.decision_type == "submit_movement_proposal"
    view = client.get_view(_OWNER)
    battlefield = battlefield_view_from_game_view(view)
    unit = next(row for row in battlefield.units if row.unit_id == _PASSENGER)
    selection = SelectionState.initial(default_preferences()).select_model_id(
        unit_id=_PASSENGER,
        model_id=unit.models[0].model_id,
        preferences=default_preferences(),
    )
    draft = MovementDraft.start_for_pending(
        view=battlefield,
        selection=selection,
        pending_decision=movement,
    )
    assert draft is not None
    ready = (
        draft.add_waypoint(view=battlefield, world_point=(10.0, 12.85))
        .add_waypoint(view=battlefield, world_point=(10.0, 12.7))
        .mark_ready(view=battlefield)
    )
    assert ready.payload_preview is not None
    moved = client.submit_movement_payload(
        request_id=movement.request_id,
        payload=ready.payload_preview,
        result_id="contract42-setup-arrival:after-tactical-move",
    )
    assert moved.status_kind != "invalid", moved
    after = moved.decision
    assert after is not None
    assert after.decision_type == "select_movement_unit"
    assert _PASSENGER not in {option.option_id for option in after.options}
    assert not any(
        event["event_type"] == "unit_embarked"
        for event in client.get_events_since(0, _OWNER).events
    )


def test_revival_copies_phase_start_witness_and_canonical_enemy_evidence() -> None:
    client = _revival_client()
    source = _current(client)
    assert source.decision_type == "select_faction_rule_command_phase_start_option"
    option = next(
        option
        for option in source.options
        if type(option.payload) is dict
        and option.payload.get("selection_kind") == "catalog_command_restoration"
    )
    assert type(option.payload) is dict
    assert option.payload["target_unit_instance_id"] == _PASSENGER
    selected = _choose(client, source, option.option_id, "revive-source")
    request = selected.decision
    assert request is not None
    assert request.decision_type == "submit_healing_revival_placement"
    assert request.actor_id == _OWNER
    proposal = request.placement_proposal
    assert proposal is not None
    assert proposal.request_id == request.request_id
    assert proposal.unit_instance_id == _PASSENGER
    assert proposal.context["target_rules_unit_instance_id"] == _PASSENGER
    phase_start = proposal.context["revival_phase_start"]
    assert type(phase_start) is dict
    assert phase_start["rule_source_id"] == "gw-11e-core-revival:revival"
    assert phase_start["target_unit_instance_id"] == _PASSENGER
    assert phase_start["phase_start_event_id"]
    assert phase_start["phase_start_window_id"]
    model_ids = phase_start["model_ids"]
    assert type(model_ids) is list
    assert all(type(model_id) is str for model_id in model_ids)
    assert model_ids == sorted(cast(list[str], model_ids))
    for viewer in (_OWNER, _OPPONENT):
        projected = client.get_view(viewer).pending_decision
        assert projected is not None
        assert projected.request_id == request.request_id
        assert projected.actor_id == request.actor_id
        assert projected.placement_proposal is not None
        assert projected.placement_proposal.context["revival_phase_start"] == phase_start

    bad = _placed(_draft(client), ((11.5, 16.5),))
    assert bad.context is not None
    assert bad.context["revival_phase_start"] == phase_start
    assert bad.payload_preview is not None
    assert bad.payload_preview["proposal_request_id"] == request.request_id
    before = _state_snapshot(client)
    rejected = _submit(client, bad, "revive-new-enemy")
    assert rejected.status_kind == "invalid"
    assert rejected.invalid_diagnostics
    assert rejected.invalid_diagnostics[0].violation_code == (
        "malformed_or_invalid:GameLifecycleError"
    )
    assert _state_snapshot(client) == before
    retry = _current(client)
    assert retry.request_id == request.request_id
    assert retry.placement_proposal is not None
    assert retry.placement_proposal.context["revival_phase_start"] == phase_start

    good = _placed(_draft(client), ((11.5, 13.0),))
    accepted = _submit(client, good, "revive-same-enemy")
    assert accepted.status_kind != "invalid", accepted
    for viewer in (_OWNER, _OPPONENT):
        events = tuple(
            event
            for event in client.get_events_since(0, viewer).events
            if event["event_type"] == "healing_step_resolved"
        )
        assert len(events) == 1
        payload = events[0]["payload"]
        assert type(payload) is dict
        assert payload["revival_phase_start"] == phase_start
        engagement = payload["revival_engagement"]
        assert type(engagement) is dict
        assert engagement["target_unit_instance_id"] == _PASSENGER
        assert engagement["engaged_enemy_rules_unit_ids_before"] == ["army-beta:enemy"]
        assert engagement["returned_model_engaged_enemy_rules_unit_ids"] == ["army-beta:enemy"]
        assert "engaged_enemy_model_ids" not in engagement


def test_shock_disembark_copies_explicit_empty_start_engagement_and_retries() -> None:
    client = _transport_client(shock=True)
    request = _movement_placement(client, _PASSENGER, "disembark:shock_disembark")
    proposal = request.placement_proposal
    assert proposal is not None
    assert proposal.context["start_engaged_enemy_unit_instance_ids"] == []
    assert proposal.context["disembark_mode"] == "shock_disembark"
    bad = _placed(_draft(client), ((20.0, 20.0),))
    assert bad.payload_preview is not None
    assert bad.payload_preview["start_engaged_enemy_unit_instance_ids"] == []
    before = _state_snapshot(client)
    events_before = client.get_events_since(0, _OWNER).events
    invalid = _submit(client, bad, "shock-invalid")
    assert invalid.status_kind == "invalid"
    assert "disembark_distance" in {
        diagnostic.violation_code for diagnostic in invalid.invalid_diagnostics
    }
    assert _state_snapshot(client) == before
    events_after = client.get_events_since(0, _OWNER).events
    assert tuple(event["event_type"] for event in events_after[len(events_before) :]) == (
        "decision_recorded",
        "disembark_placement_invalid",
        "movement_setup_failed",
        "decision_requested",
    )
    retry_selection = _current(client)
    assert retry_selection.decision_type == "select_movement_unit"
    assert retry_selection.actor_id == _OWNER
    assert retry_selection.request_id != request.request_id
    assert _PASSENGER in {option.option_id for option in retry_selection.options}
    for viewer in (_OWNER, _OPPONENT):
        pending = client.get_view(viewer).pending_decision
        assert pending is not None
        assert pending.request_id == retry_selection.request_id
    with pytest.raises(UiClientSubmissionError):
        client.submit_parameterized_payload(
            request_id=request.request_id,
            payload=bad.payload_preview,
            result_id="contract42-setup-arrival:shock-stale",
        )
    assert _state_snapshot(client) == before
    assert client.get_events_since(0, _OWNER).events == events_after

    retry = _movement_placement(
        client, _PASSENGER, "disembark:shock_disembark", result_suffix="-shock-retry"
    )
    assert retry.request_id != request.request_id
    retry_proposal = retry.placement_proposal
    assert retry_proposal is not None
    assert retry_proposal.source_decision_request_id != proposal.source_decision_request_id
    assert retry_proposal.context["start_engaged_enemy_unit_instance_ids"] == []
    assert retry_proposal.context["disembark_mode"] == "shock_disembark"
    assert retry_proposal.context["transport_unit_instance_id"] == _TRANSPORT
    assert retry_proposal.context["model_instance_ids"] == proposal.context["model_instance_ids"]
    good = _placed(_draft(client), ((10.0, 14.0),))
    assert good.proposal_request_id == retry.request_id
    assert good.payload_preview is not None
    assert good.payload_preview["start_engaged_enemy_unit_instance_ids"] == []
    accepted = _submit(client, good, "shock-valid")
    assert accepted.status_kind != "invalid", accepted
    events = client.get_events_since(0, _OWNER).events
    assert any(event["event_type"] == "unit_disembarked" for event in events)
