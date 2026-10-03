"""Seeded public-session Charge fixture shared by Contract 42 UI tests."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.core.army_catalog import ArmyCatalog
from warhammer40k_core.core.missions import ObjectiveMarkerDefinition, ObjectiveMarkerRole
from warhammer40k_core.engine.army_mustering import ArmyMusterRequest, muster_army
from warhammer40k_core.engine.battlefield_state import ModelPlacement, UnitPlacement
from warhammer40k_core.engine.charge_phase_state import ChargePhaseState
from warhammer40k_core.engine.command_points import CommandPointSourceKind
from warhammer40k_core.engine.effects import (
    GENERIC_RULE_EFFECT_KIND,
    EffectExpiration,
    PersistingEffect,
)
from warhammer40k_core.engine.event_log import JsonValue, validate_json_value
from warhammer40k_core.engine.game_state import (
    GameConfig,
    GameState,
    SecondaryMissionChoice,
    SecondaryMissionMode,
)
from warhammer40k_core.engine.lifecycle import GameLifecycle, GameLifecyclePayload
from warhammer40k_core.engine.list_validation import DetachmentSelection, UnitMusterSelection
from warhammer40k_core.engine.mission_setup import MissionSetup, PlayerPrimaryMissionAssignment
from warhammer40k_core.engine.mission_state_validation import (
    runtime_ruleset_descriptor_for_mission_setup,
)
from warhammer40k_core.engine.phase import BattlePhase, GameLifecycleStage
from warhammer40k_core.engine.placement import create_deterministic_battlefield_scenario
from warhammer40k_core.engine.unit_factory import UnitInstance
from warhammer40k_core.engine.wargear_selections import ModelProfileSelection
from warhammer40k_core.geometry.pose import Pose
from warhammer40k_core.rules.mission_pack_import import (
    warhammer_event_companion_2026_07_mission_pack,
)

from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient

SOURCE = "army-alpha:source"
COMMITTED = "army-beta:new"
OTHER_REACHABLE = "army-beta:old"


def seeded_charge_client(
    *, fly: bool = False, source_facing_degrees: float = 0.0
) -> LocalSessionClient:
    catalog = ArmyCatalog.phase9a_canonical_content_pack()
    if fly:
        catalog = replace(
            catalog,
            datasheets=tuple(
                replace(
                    sheet,
                    keywords=replace(
                        sheet.keywords,
                        keywords=(*sheet.keywords.keywords, "FLY"),
                    ),
                )
                if sheet.datasheet_id == "core-intercessor-like-infantry"
                else sheet
                for sheet in catalog.datasheets
            ),
        )
    mission_pack = warhammer_event_companion_2026_07_mission_pack()
    mission = MissionSetup(
        mission_pack_id=mission_pack.mission_pack_id,
        source_version=mission_pack.source_version,
        source_id=mission_pack.source_id,
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
        deployment_map_id="phase15a-open-map",
        terrain_layout_id="phase15a-open-layout",
        attacker_player_id="player-a",
        defender_player_id="player-b",
        battlefield_width_inches=100.0,
        battlefield_depth_inches=100.0,
        objective_markers=(
            ObjectiveMarkerDefinition(
                objective_marker_id="charge-remote-objective",
                name="Remote Objective",
                objective_role=ObjectiveMarkerRole.CENTRAL,
                x_inches=95.0,
                y_inches=95.0,
                source_id="charge-test",
            ),
        ),
        deployment_zones=(),
        battlefield_regions=(),
        terrain_areas=(),
        terrain_features=(),
    )
    config = GameConfig(
        game_id="contract42-charge-subset",
        allow_legacy_non_strict_rosters=True,
        ruleset_descriptor=runtime_ruleset_descriptor_for_mission_setup(
            mission, rules_overlay_ids=()
        ),
        army_catalog=catalog,
        army_muster_requests=tuple(
            _muster_request(catalog, player_id, army_id, unit_ids)
            for player_id, army_id, unit_ids in (
                ("player-a", "army-alpha", ("source", "next")),
                ("player-b", "army-beta", ("old", "new")),
            )
        ),
        player_ids=("player-a", "player-b"),
        turn_order=("player-a", "player-b"),
        fixed_secondary_mission_ids=("assassination", "bring_it_down", "cleanse"),
        mission_setup=mission,
    )
    armies = tuple(
        muster_army(catalog=catalog, request=request) for request in config.army_muster_requests
    )
    scenario = create_deterministic_battlefield_scenario(
        battlefield_id="contract42-charge-battlefield",
        armies=armies,
        battlefield_width_inches=mission.battlefield_width_inches,
        battlefield_depth_inches=mission.battlefield_depth_inches,
    )
    battlefield = scenario.battlefield_state
    origins = {
        SOURCE: Pose.at(10, 20),
        "army-alpha:next": Pose.at(10, 35),
        OTHER_REACHABLE: Pose.at(25, 20),
        COMMITTED: Pose.at(10, 26),
    }
    for army in armies:
        for unit in army.units:
            placement = _placed_unit(
                unit, army.army_id, army.player_id, origins[unit.unit_instance_id]
            )
            if unit.unit_instance_id == SOURCE:
                placement = placement.with_model_placements(
                    tuple(
                        model.with_pose(
                            Pose.at(
                                model.pose.position.x,
                                model.pose.position.y,
                                model.pose.position.z,
                                facing_degrees=source_facing_degrees,
                            )
                        )
                        for model in placement.model_placements
                    )
                )
            battlefield = battlefield.with_unit_placement(placement)
    state = GameState.from_config(config)
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
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.CHARGE)
    state.battle_round = 1
    state.active_player_id = "player-a"
    _add_charge_modifier(state, effect_id="charge-roll-bonus", kind="modify_dice_roll", delta=10)
    _add_charge_modifier(
        state, effect_id="charge-move-bonus", kind="modify_move_distance", delta=2.5
    )
    decisions = GameLifecycle().decision_controller
    lifecycle = GameLifecycle.from_payload(
        cast(
            GameLifecyclePayload,
            {
                "config": config.to_payload(),
                "parameterized_movement_proposals": True,
                "state": state.to_payload(),
                "decisions": decisions.to_payload(),
                "reaction_queue": {"frames": []},
            },
        )
    )
    return LocalSessionClient(session=LocalGameSession(lifecycle=lifecycle))


def _muster_request(
    catalog: ArmyCatalog,
    player_id: str,
    army_id: str,
    unit_ids: tuple[str, ...],
) -> ArmyMusterRequest:
    return ArmyMusterRequest(
        army_id=army_id,
        player_id=player_id,
        catalog_id=catalog.catalog_id,
        source_package_id=catalog.source_package_id,
        ruleset_id=catalog.ruleset_id,
        detachment_selection=DetachmentSelection(
            faction_id="core-marine-force", detachment_ids=("core-combined-arms",)
        ),
        force_disposition_id="purge-the-foe",
        unit_selections=tuple(
            UnitMusterSelection(
                unit_selection_id=unit_id,
                datasheet_id="core-intercessor-like-infantry",
                model_profile_selections=(
                    ModelProfileSelection(model_profile_id="core-intercessor-like", model_count=5),
                ),
            )
            for unit_id in unit_ids
        ),
    )


def _placed_unit(unit: UnitInstance, army_id: str, player_id: str, origin: Pose) -> UnitPlacement:
    return UnitPlacement(
        army_id=army_id,
        player_id=player_id,
        unit_instance_id=unit.unit_instance_id,
        model_placements=tuple(
            ModelPlacement(
                army_id=army_id,
                player_id=player_id,
                unit_instance_id=unit.unit_instance_id,
                model_instance_id=model.model_instance_id,
                pose=Pose.at(origin.position.x + index * 1.4, origin.position.y),
            )
            for index, model in enumerate(unit.own_models)
        ),
    )


def _add_charge_modifier(state: GameState, *, effect_id: str, kind: str, delta: float) -> None:
    parameters: dict[str, JsonValue] = {"delta": delta}
    if kind == "modify_dice_roll":
        parameters = {"delta": int(delta), "roll_type": "charge"}
    source_span = {"start": 0, "end": 1, "text": "x"}
    state.record_persisting_effect(
        PersistingEffect(
            effect_id=effect_id,
            source_rule_id=f"source:{effect_id}",
            owner_player_id="player-a",
            target_unit_instance_ids=(SOURCE,),
            started_battle_round=1,
            started_phase=BattlePhase.CHARGE,
            expiration=EffectExpiration.end_phase(
                battle_round=1, phase=BattlePhase.CHARGE, player_id="player-a"
            ),
            effect_payload=validate_json_value(
                {
                    "effect_kind": GENERIC_RULE_EFFECT_KIND,
                    "rule_id": f"rule:{effect_id}",
                    "source_id": f"source:{effect_id}",
                    "rule_ir_hash": "0" * 64,
                    "clause_id": f"clause:{effect_id}",
                    "effect_index": 0,
                    "source_span": source_span,
                    "target": {"kind": "this_unit", "source_span": source_span, "parameters": []},
                    "target_unit_instance_ids": [SOURCE],
                    "duration": None,
                    "conditions": [],
                    "effect": {
                        "kind": kind,
                        "source_span": source_span,
                        "parameters": [
                            {"key": key, "value": value}
                            for key, value in sorted(parameters.items())
                        ],
                    },
                    "context": {
                        "state": None,
                        "player_id": "player-a",
                        "phase": BattlePhase.CHARGE.value,
                        "source_model_instance_id": None,
                        "trigger_payload": None,
                    },
                }
            ),
        )
    )


def seeded_heroic_client() -> LocalSessionClient:
    """Seed only the opponent Charge history; all choices use the public facade."""

    client = seeded_charge_client()
    session = client.session
    assert isinstance(session, LocalGameSession)
    state = session.lifecycle.state
    assert state is not None
    state.active_player_id = "player-b"
    state.replace_charge_phase_state(
        ChargePhaseState(
            battle_round=state.battle_round,
            active_player_id="player-b",
            selected_unit_ids=(COMMITTED,),
            declared_target_unit_instance_ids_by_unit={COMMITTED: (SOURCE,)},
        ).with_phase_complete()
    )
    state.record_persisting_effect(
        PersistingEffect(
            effect_id="contract42-opponent-charge",
            source_rule_id="contract42-opponent-charge-source",
            owner_player_id="player-b",
            target_unit_instance_ids=(COMMITTED,),
            started_battle_round=state.battle_round,
            started_phase=BattlePhase.CHARGE,
            expiration=EffectExpiration.end_turn(
                battle_round=state.battle_round, player_id="player-b"
            ),
            effect_payload={"effect_kind": "charge_grants_fights_first"},
        )
    )
    grant = state.gain_command_points(
        player_id="player-a",
        amount=3,
        source_id="contract42-heroic-fixture-cp",
        source_kind=CommandPointSourceKind.COMMAND_PHASE_START,
    )
    assert grant.applied_amount == 3
    return client
