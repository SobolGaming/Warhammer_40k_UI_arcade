"""Self-contained seeded Contract 42 battle fixture for public session tests."""

from __future__ import annotations

from dataclasses import replace
from functools import cache

from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.core.ability_sources import AbilitySourceInstance
from warhammer40k_core.core.army_catalog import ArmyCatalog
from warhammer40k_core.core.attributes import Characteristic, CharacteristicValue
from warhammer40k_core.core.datasheet import (
    DatasheetDefinition,
    DatasheetWargearOption,
    UnitCompositionDefinition,
)
from warhammer40k_core.core.faction_aliases import CHAOS_SPACE_MARINES_FACTION_ID
from warhammer40k_core.core.missions import ObjectiveMarkerDefinition, ObjectiveMarkerRole
from warhammer40k_core.core.ruleset_descriptor import RulesetDescriptor
from warhammer40k_core.core.wargear import Wargear
from warhammer40k_core.core.weapon_ability_sources import weapon_keyword_ability_id
from warhammer40k_core.core.weapon_profiles import (
    AttackProfile,
    DamageProfile,
    RangeProfile,
    WeaponKeyword,
    WeaponProfile,
)
from warhammer40k_core.engine.army_mustering import ArmyMusterRequest, muster_army
from warhammer40k_core.engine.battlefield_state import ModelPlacement, UnitPlacement
from warhammer40k_core.engine.event_log import EventLog
from warhammer40k_core.engine.game_state import (
    GameConfig,
    SecondaryMissionChoice,
    SecondaryMissionMode,
)
from warhammer40k_core.engine.lifecycle import GameLifecycle
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
from warhammer40k_core.engine.wargear_selections import ModelProfileSelection
from warhammer40k_core.geometry.pose import Pose
from warhammer40k_core.rules.mission_pack_import import (
    warhammer_event_companion_2026_07_mission_pack,
)

from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient


@cache
def _mission_setup() -> MissionSetup:
    mission_pack = warhammer_event_companion_2026_07_mission_pack()
    return MissionSetup(
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
        deployment_map_id="contract42-open-map",
        terrain_layout_id="contract42-open-layout",
        attacker_player_id="player-a",
        defender_player_id="player-b",
        battlefield_width_inches=100.0,
        battlefield_depth_inches=60.0,
        objective_markers=(
            ObjectiveMarkerDefinition(
                objective_marker_id="contract42-remote-objective",
                name="Remote objective",
                objective_role=ObjectiveMarkerRole.CENTRAL,
                x_inches=95.0,
                y_inches=55.0,
                source_id="contract42-test",
            ),
        ),
        deployment_zones=(),
        battlefield_regions=(),
        terrain_areas=(),
        terrain_features=(),
    )


def _catalog(
    *,
    copies: int,
    no_weapons: bool,
    range_inches: int,
    duplicate_hazardous: bool,
    one_shot: bool,
    dark_pact: bool,
    lethal_attack: bool,
) -> ArmyCatalog:
    catalog = ArmyCatalog.phase9a_canonical_content_pack()
    datasheets: list[DatasheetDefinition] = []
    for sheet in catalog.datasheets:
        if sheet.datasheet_id != "core-intercessor-like-infantry":
            datasheets.append(sheet)
            continue
        options = sheet.wargear_options
        if no_weapons:
            options = tuple(
                replace(option, default_wargear_ids=(), min_selections=0) for option in options
            )
        elif copies == 2:
            options = (
                *options,
                DatasheetWargearOption(
                    option_id=f"{sheet.datasheet_id}:second-bolt-rifle",
                    model_profile_id=sheet.model_profiles[0].model_profile_id,
                    default_wargear_ids=("core-bolt-rifle",),
                    allowed_wargear_ids=("core-bolt-rifle",),
                    min_selections=1,
                    max_selections=1,
                ),
            )
        datasheets.append(
            replace(
                sheet,
                keywords=(
                    replace(
                        sheet.keywords,
                        faction_keywords=(
                            *sheet.keywords.faction_keywords,
                            "CHAOS SPACE MARINES",
                        ),
                    )
                    if dark_pact
                    else sheet.keywords
                ),
                composition=tuple(
                    UnitCompositionDefinition(
                        model_profile_id=part.model_profile_id,
                        min_models=1,
                        max_models=part.max_models,
                    )
                    for part in sheet.composition
                ),
                wargear_options=options,
            )
        )
    wargear: list[Wargear] = []
    for item in catalog.wargear:
        if item.wargear_id != "core-bolt-rifle":
            wargear.append(item)
            continue
        profiles: list[WeaponProfile] = []
        for profile in item.weapon_profiles:
            if lethal_attack:
                profiles.append(
                    replace(
                        profile,
                        attack_profile=AttackProfile.fixed(1),
                        damage_profile=DamageProfile.fixed(100),
                        strength=CharacteristicValue.from_raw(Characteristic.STRENGTH, 100),
                        armor_penetration=CharacteristicValue.from_raw(
                            Characteristic.ARMOR_PENETRATION, -10
                        ),
                        keywords=(WeaponKeyword.TORRENT,),
                        abilities=(),
                        ability_sources=(),
                    )
                )
                continue
            keywords = tuple(
                keyword
                for keyword in profile.keywords
                if keyword not in (WeaponKeyword.ONE_SHOT, WeaponKeyword.HAZARDOUS)
            )
            if one_shot:
                keywords = (*keywords, WeaponKeyword.ONE_SHOT)
            if duplicate_hazardous:
                keywords = (WeaponKeyword.HAZARDOUS,)
            profiles.append(
                replace(
                    profile,
                    range_profile=RangeProfile.distance(range_inches),
                    keywords=keywords,
                    abilities=() if duplicate_hazardous else profile.abilities,
                    ability_sources=(
                        tuple(
                            AbilitySourceInstance(
                                owner_id=profile.stable_identity(),
                                source_id=profile.stable_identity(),
                                source_instance_id=f"contract42-hazardous-{index}",
                                slot_id="hazardous",
                                ability_id=weapon_keyword_ability_id(WeaponKeyword.HAZARDOUS),
                            )
                            for index in range(2)
                        )
                        if duplicate_hazardous
                        else ()
                    ),
                )
            )
        wargear.append(replace(item, weapon_profiles=tuple(profiles)))
    factions = catalog.factions
    detachments = catalog.detachments
    if dark_pact:
        factions = (
            *factions,
            replace(
                factions[0],
                faction_id=CHAOS_SPACE_MARINES_FACTION_ID,
                name="Contract 42 Chaos Space Marines",
                faction_keywords=("CHAOS SPACE MARINES",),
                army_rule_ids=(),
            ),
        )
        detachments = (
            *detachments,
            replace(
                detachments[0],
                detachment_id="contract42-csm-detachment",
                canonical_detachment_id="contract42-csm-detachment",
                faction_id=CHAOS_SPACE_MARINES_FACTION_ID,
            ),
        )
    return replace(
        catalog,
        datasheets=tuple(datasheets),
        wargear=tuple(wargear),
        factions=factions,
        detachments=detachments,
    )


def _muster_request(
    *,
    catalog: ArmyCatalog,
    player_id: str,
    unit_id: str,
    models: int,
    dark_pact: bool,
) -> ArmyMusterRequest:
    army_id = "army-alpha" if player_id == "player-a" else "army-beta"
    return ArmyMusterRequest(
        army_id=army_id,
        player_id=player_id,
        catalog_id=catalog.catalog_id,
        source_package_id=catalog.source_package_id,
        ruleset_id=catalog.ruleset_id,
        detachment_selection=DetachmentSelection(
            faction_id=(
                CHAOS_SPACE_MARINES_FACTION_ID
                if dark_pact and player_id == "player-a"
                else "core-marine-force"
            ),
            detachment_ids=(
                ("contract42-csm-detachment",)
                if dark_pact and player_id == "player-a"
                else ("core-combined-arms",)
            ),
        ),
        force_disposition_id="purge-the-foe",
        unit_selections=(
            UnitMusterSelection(
                unit_selection_id=unit_id,
                datasheet_id="core-intercessor-like-infantry",
                model_profile_selections=(
                    ModelProfileSelection(
                        model_profile_id="core-intercessor-like",
                        model_count=models,
                    ),
                ),
            ),
        ),
    )


def shooting_client(
    *,
    copies: int = 1,
    models: int = 1,
    no_weapons: bool = False,
    range_inches: int = 48,
    enemy_x: float = 30.0,
    duplicate_hazardous: bool = False,
    one_shot: bool = False,
    dark_pact: bool = False,
    lethal_attack: bool = False,
) -> LocalSessionClient:
    catalog = _catalog(
        copies=copies,
        no_weapons=no_weapons,
        range_inches=range_inches,
        duplicate_hazardous=duplicate_hazardous,
        one_shot=one_shot,
        dark_pact=dark_pact,
        lethal_attack=lethal_attack,
    )
    config = GameConfig(
        game_id="contract42-shooting-ui",
        allow_legacy_non_strict_rosters=True,
        ruleset_descriptor=RulesetDescriptor.warhammer_40000_eleventh(
            descriptor_version="contract42-ui-test"
        ),
        army_catalog=catalog,
        army_muster_requests=(
            _muster_request(
                catalog=catalog,
                player_id="player-a",
                unit_id="shooter",
                models=models,
                dark_pact=dark_pact,
            ),
            _muster_request(
                catalog=catalog,
                player_id="player-b",
                unit_id="enemy",
                models=1,
                dark_pact=dark_pact,
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
        battlefield_id="contract42-shooting-field",
        battlefield_width_inches=100.0,
        battlefield_depth_inches=60.0,
        armies=armies,
    ).battlefield_state
    for army in armies:
        unit = army.units[0]
        x = 10.0 if army.player_id == "player-a" else enemy_x
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
        session=LocalGameSession(GameLifecycle.from_payload(lifecycle.to_payload()))
    )
