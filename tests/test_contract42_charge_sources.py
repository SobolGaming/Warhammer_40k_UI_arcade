"""Selected Contract 42 source choices through the real Arcade client facade."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from typing import cast

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.adapters.setup_smoke import canonical_setup_prebattle_smoke_config
from warhammer40k_core.core.army_catalog import ArmyCatalog
from warhammer40k_core.core.datasheet import (
    CatalogAbilitySourceKind,
    CatalogAbilitySupport,
    CatalogJsonObject,
    DatasheetAbilityDescriptor,
    DatasheetDefinition,
    DatasheetKeywordSet,
)
from warhammer40k_core.core.ruleset_descriptor import MovementMode
from warhammer40k_core.engine.army_mustering import muster_army
from warhammer40k_core.engine.battlefield_state import (
    BattlefieldPlacementKind,
    BattlefieldTransitionBatch,
    ModelPlacement,
    ModelPlacementRecord,
    UnitPlacement,
)
from warhammer40k_core.engine.deployment import create_empty_deployment_battlefield_state
from warhammer40k_core.engine.game_state import (
    GameState,
    SecondaryMissionChoice,
    SecondaryMissionMode,
)
from warhammer40k_core.engine.lifecycle import GameLifecycle, GameLifecyclePayload
from warhammer40k_core.engine.list_validation import AttachmentDeclaration, UnitMusterSelection
from warhammer40k_core.engine.movement_proposals import ProposalKind
from warhammer40k_core.engine.phase import BattlePhase, GameLifecycleStage, SetupStep
from warhammer40k_core.engine.phases.charge import ChargeMoveProposal
from warhammer40k_core.engine.placement import create_deterministic_battlefield_scenario
from warhammer40k_core.engine.setup_flow import army_mustered_event_payload
from warhammer40k_core.engine.transports import (
    TransportCapacityProfile,
    TransportCargoState,
)
from warhammer40k_core.engine.wargear_selections import ModelProfileSelection
from warhammer40k_core.geometry.pathing import PathWitness
from warhammer40k_core.geometry.pose import Pose
from warhammer40k_core.rules.objective_terminology import ObjectiveRuleScope
from warhammer40k_core.rules.rule_compiler import compile_rule_source_text
from warhammer40k_core.rules.source_data import RuleSourceText

from tests.support.contract42_charge_fixture import (
    COMMITTED,
    OTHER_REACHABLE,
    SOURCE,
    seeded_charge_client,
)
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientStatus,
    UiClientSubmissionError,
    UiDecision,
)
from warhammer40k_arcade_ui.hud.view_models import build_finite_decision_panel
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.core_projection import battlefield_view_from_game_view
from warhammer40k_arcade_ui.state.entity_selection import entity_ref_for_model
from warhammer40k_arcade_ui.state.finite_decision import FiniteDecisionUiState
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft
from warhammer40k_arcade_ui.state.selection import SelectionState

pytestmark = pytest.mark.integration

ATTACHED = f"attached-unit:{SOURCE}"
LEADER = "army-alpha:leader"


def _decision(status: UiClientStatus, kind: str) -> UiDecision:
    decision = status.decision
    assert decision is not None, status
    assert decision.decision_type == kind
    return decision


def _object(value: object) -> JsonObject:
    assert type(value) is dict
    return cast(JsonObject, value)


def _natural_charge_catalog(catalog: ArmyCatalog) -> ArmyCatalog:
    source = RuleSourceText.from_raw(
        source_id="ui-test:charge-reroll",
        raw_text="You can re-roll Charge rolls made for this unit.",
        objective_scope=ObjectiveRuleScope.CORE_RULES,
    )
    rule_ir = compile_rule_source_text(source, source_keyword_sequence_parts=("INFANTRY",)).rule_ir
    ability = DatasheetAbilityDescriptor(
        ability_id="ui-test-natural-charge-reroll",
        name="Charge reroll source",
        source_id=source.source_id,
        support=CatalogAbilitySupport.GENERIC_RULE_IR,
        source_kind=CatalogAbilitySourceKind.DATASHEET,
        effect_description=source.raw_text,
        rule_ir_payload=cast(CatalogJsonObject, rule_ir.to_payload()),
    )
    return replace(
        catalog,
        datasheets=tuple(
            replace(sheet, abilities=(*sheet.abilities, ability))
            if sheet.datasheet_id == "core-intercessor-like-infantry"
            else sheet
            for sheet in catalog.datasheets
        ),
    )


def _attached_charge_client(*, natural_reroll: bool) -> LocalSessionClient:
    """Seed domain state only; the lifecycle emits every tested decision."""

    baseline = seeded_charge_client()
    baseline_session = cast(LocalGameSession, baseline.session)
    baseline_lifecycle = baseline_session.lifecycle
    config = baseline_lifecycle.config
    baseline_state = baseline_lifecycle.state
    assert config is not None
    assert config.army_catalog is not None
    assert baseline_state is not None
    assert config.mission_setup is not None
    catalog = (
        _natural_charge_catalog(config.army_catalog) if natural_reroll else config.army_catalog
    )
    alpha, beta = config.army_muster_requests
    leader = UnitMusterSelection(
        unit_selection_id="leader",
        datasheet_id="core-character-leader",
        model_profile_selections=(
            ModelProfileSelection(model_profile_id="core-character-leader", model_count=1),
        ),
    )
    alpha = replace(
        alpha,
        unit_selections=(*alpha.unit_selections, leader),
        attachment_declarations=(
            AttachmentDeclaration(
                source_unit_selection_id="leader", bodyguard_unit_selection_id="source"
            ),
        ),
    )
    config = replace(
        config,
        game_id="ui-contract42-attached-reroll" if natural_reroll else "ui-contract42-attached",
        army_catalog=catalog,
        army_muster_requests=(alpha, beta),
    )
    armies = tuple(muster_army(catalog=catalog, request=request) for request in (alpha, beta))
    mission_setup = config.mission_setup
    assert mission_setup is not None
    battlefield = create_deterministic_battlefield_scenario(
        battlefield_id="ui-contract42-attached-battlefield",
        armies=armies,
        battlefield_width_inches=mission_setup.battlefield_width_inches,
        battlefield_depth_inches=mission_setup.battlefield_depth_inches,
    ).battlefield_state
    origins = {
        SOURCE: Pose.at(10, 20),
        LEADER: Pose.at(17, 20),
        "army-alpha:next": Pose.at(10, 35),
        COMMITTED: Pose.at(10, 26),
        OTHER_REACHABLE: Pose.at(25, 20),
    }
    for army in armies:
        for unit in army.units:
            origin = origins[unit.unit_instance_id]
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
                            pose=Pose.at(origin.position.x + index * 1.4, origin.position.y),
                        )
                        for index, model in enumerate(unit.own_models)
                    ),
                )
            )
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
    for effect in baseline_state.persisting_effects:
        state.record_persisting_effect(effect)
    decisions = GameLifecycle().decision_controller
    for army in armies:
        decisions.event_log.append(
            "army_mustered", army_mustered_event_payload(state=state, army_definition=army)
        )
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


def _select_attached(client: LocalSessionClient) -> UiDecision:
    initial = _decision(client.advance_until_decision_or_terminal(), "select_charging_unit")
    assert initial.actor_id == "player-a"
    assert ATTACHED in {option.option_id for option in initial.options}
    assert SOURCE not in {option.option_id for option in initial.options}
    assert LEADER not in {option.option_id for option in initial.options}
    status = client.submit_finite(
        request_id=initial.request_id,
        selected_option_id=ATTACHED,
        result_id="ui-attached-select",
    )
    assert status.status_kind == "waiting_for_decision", status.invalid_diagnostics
    assert status.decision is not None
    return status.decision


def _finish_optional_command_window(client: LocalSessionClient, decision: UiDecision) -> UiDecision:
    if decision.decision_type != "use_stratagem":
        return decision
    context = _object(_object(decision.payload)["stratagem_context"])
    trigger = _object(context["trigger_payload"])
    assert trigger["charge_action_id"]
    assert ATTACHED in json.dumps(decision.payload)
    status = client.submit_finite(
        request_id=decision.request_id,
        selected_option_id="decline_stratagem_window",
        result_id="ui-attached-decline-command-reroll",
    )
    return _decision(status, "select_charge_targets")


def _select_committed_target(client: LocalSessionClient, decision: UiDecision) -> UiDecision:
    assert decision.decision_type == "select_charge_targets"
    assert decision.actor_id == "player-a"
    option = next(
        option
        for option in decision.options
        if _object(option.payload).get("target_ids") == [COMMITTED]
    )
    finite_state = FiniteDecisionUiState.from_status(
        UiClientStatus(stage="battle", status_kind="waiting_for_decision", decision=decision)
    )
    panel = build_finite_decision_panel(
        pending_decision=decision,
        highlighted_option_index=finite_state.highlighted_option_index,
        status_message=finite_state.status_message,
        diagnostics=finite_state.diagnostics,
    )
    assert {row.option_id for row in panel.options} == {row.option_id for row in decision.options}
    status = client.submit_finite(
        request_id=decision.request_id,
        selected_option_id=option.option_id,
        result_id="ui-attached-commit-target",
    )
    return _decision(status, "submit_movement_proposal")


def _ready_attached_draft(client: LocalSessionClient, decision: UiDecision) -> MovementDraft:
    view = client.get_view("player-a")
    assert view.pending_decision == decision
    battlefield = battlefield_view_from_game_view(view)
    matching = tuple(unit for unit in battlefield.units if unit.unit_id == ATTACHED)
    assert len(matching) == 1, (
        "Canonical attached rules unit is absent from UI battlefield projection"
    )
    unit = matching[0]
    assert len(unit.models) == 6
    selection = SelectionState.initial(default_preferences()).select_model_id(
        unit_id=ATTACHED, model_id=None, preferences=default_preferences()
    )
    draft = MovementDraft.start_for_pending(
        view=battlefield,
        selection=selection,
        pending_decision=decision,
        projection_state_hash=view.projection_state_hash,
    )
    assert draft is not None
    assert {path.model_id for path in draft.model_paths} == {
        model.model_id for model in unit.models
    }
    anchor_x = sum(path.points[0][0] for path in draft.model_paths) / len(draft.model_paths)
    draft = draft.add_waypoint(view=battlefield, world_point=(anchor_x, 22.0))
    draft = draft.add_waypoint(view=battlefield, world_point=(anchor_x, 24.0))
    leader_model = next(path for path in draft.model_paths if path.model_id.startswith(LEADER))
    ref = entity_ref_for_model(view=battlefield, unit_id=ATTACHED, model_id=leader_model.model_id)
    assert ref is not None
    draft = draft.replace_model_selection(view=battlefield, ref=ref)
    draft = draft.add_waypoint(view=battlefield, world_point=(17.0, 25.0))
    ready = draft.mark_ready(view=battlefield)
    assert ready.payload_preview is not None
    return ready


def _test_witnessed_attached_charge_payload(
    client: LocalSessionClient, decision: UiDecision
) -> JsonObject:
    """A test-local physical path used to verify the reroll continuation."""

    session = cast(LocalGameSession, client.session)
    state = session.lifecycle.state
    assert state is not None
    assert state.battlefield_state is not None
    paths: list[tuple[str, tuple[Pose, ...]]] = []
    for component_id in (SOURCE, LEADER):
        placement = state.battlefield_state.unit_placement_by_id(component_id)
        distance = 5.0 if component_id == LEADER else 4.0
        for model in placement.model_placements:
            start = model.pose
            paths.append(
                (
                    model.model_instance_id,
                    (
                        start,
                        Pose.at(start.position.x, start.position.y + distance / 2),
                        Pose.at(start.position.x, start.position.y + distance),
                    ),
                )
            )
    return cast(
        JsonObject,
        ChargeMoveProposal(
            proposal_request_id=decision.request_id,
            proposal_kind=ProposalKind.CHARGE_MOVE,
            unit_instance_id=ATTACHED,
            movement_phase_action="charge_move",
            movement_mode=MovementMode.CHARGE,
            charge_target_unit_instance_ids=(COMMITTED,),
            witness=PathWitness.for_paths(tuple(paths)),
        ).to_payload(),
    )


def _records_and_battlefield(client: LocalSessionClient) -> tuple[int, object]:
    session = cast(LocalGameSession, client.session)
    state = session.lifecycle.state
    assert state is not None
    return session.decision_record_count(), deepcopy(state.battlefield_state)


def test_attached_charge_draft_preserves_components_commitment_and_witness() -> None:
    client = _attached_charge_client(natural_reroll=False)
    decision = _finish_optional_command_window(client, _select_attached(client))
    movement = _select_committed_target(client, decision)
    proposal = movement.movement_proposal
    assert proposal is not None
    assert proposal.unit_instance_id == ATTACHED
    assert _object(proposal.context)["target_selection"] is not None
    draft = _ready_attached_draft(client, movement)
    payload = draft.payload_preview
    assert payload is not None
    assert payload["proposal_request_id"] == movement.request_id
    assert payload["unit_instance_id"] == ATTACHED
    assert payload["charge_target_unit_instance_ids"] == [COMMITTED]
    witness = _object(payload["witness"])
    paths = cast(list[JsonObject], witness["model_paths"])
    assert len(paths) == 6
    assert all(len(cast(list[object], path["poses"])) >= 3 for path in paths)
    assert {LEADER, SOURCE} == {
        model_id.rsplit(":", 2)[0] for model_id in (cast(str, path["model_id"]) for path in paths)
    }
    before = _records_and_battlefield(client)
    invalid = deepcopy(payload)
    invalid["charge_target_unit_instance_ids"] = [OTHER_REACHABLE]
    rejected = client.submit_movement_payload(
        request_id=movement.request_id,
        payload=invalid,
        result_id="ui-attached-uncommitted-target",
    )
    assert rejected.status_kind == "invalid"
    assert rejected.invalid_diagnostics
    assert _records_and_battlefield(client) == before
    assert client.get_view("player-a").pending_decision == movement
    accepted = client.submit_movement_payload(
        request_id=movement.request_id,
        payload=payload,
        result_id="ui-attached-move",
    )
    assert accepted.status_kind != "invalid", accepted.invalid_diagnostics
    owner_events = client.get_events_since(0, "player-a").events
    opponent_events = client.get_events_since(0, "player-b").events
    completion = next(
        event for event in owner_events if event["event_type"] == "charge_move_completed"
    )
    assert completion in opponent_events
    completed_payload = _object(completion["payload"])
    assert completed_payload["unit_instance_id"] == ATTACHED
    rows = cast(list[JsonObject], _object(completed_payload["endpoint_witness"])["model_endpoints"])
    assert len(rows) == 6
    assert {cast(str, row["component_unit_instance_id"]) for row in rows} == {SOURCE, LEADER}


def test_attached_natural_whole_charge_reroll_uses_current_source_and_continues() -> None:
    client = _attached_charge_client(natural_reroll=True)
    reroll = _select_attached(client)
    assert reroll.decision_type == "select_dice_reroll"
    assert reroll.actor_id == "player-a"
    assert {option.option_id for option in reroll.options} == {"decline", "reroll:0,1"}
    reroll_payload = _object(reroll.payload)
    assert ATTACHED in json.dumps(reroll_payload)
    assert "ui-test:charge-reroll" in json.dumps(reroll_payload)
    charge_context = _object(reroll_payload["charge_context"])
    roll_request = _object(charge_context["charge_roll_request"])
    assert roll_request["unit_instance_id"] == ATTACHED
    charge_action_id = roll_request["request_id"]
    assert type(charge_action_id) is str
    assert client.get_view("player-a").pending_decision == reroll
    assert client.get_view("player-b").pending_decision is not None
    before = _records_and_battlefield(client)
    with pytest.raises(UiClientSubmissionError):
        client.submit_finite(
            request_id=reroll.request_id,
            selected_option_id="reroll:0",
            result_id="ui-reroll-forged-subset",
        )
    assert _records_and_battlefield(client) == before
    focused = FiniteDecisionUiState.from_status(
        UiClientStatus(stage="battle", status_kind="waiting_for_decision", decision=reroll)
    ).highlight_option("reroll:0,1")
    _, submission = focused.prepare_submission()
    assert submission is not None
    assert submission.request_id == reroll.request_id
    assert submission.selected_option_id == "reroll:0,1"
    after = client.submit_finite(
        request_id=submission.request_id,
        selected_option_id=submission.selected_option_id,
        result_id="ui-attached-natural-reroll",
    )
    targets = _decision(after, "select_charge_targets")
    assert targets.actor_id == "player-a"
    assert targets.request_id != reroll.request_id
    assert _object(targets.payload)["action_id"] == charge_action_id
    with pytest.raises(UiClientSubmissionError):
        client.submit_finite(
            request_id=reroll.request_id,
            selected_option_id="reroll:0,1",
            result_id="ui-attached-stale-reroll",
        )
    assert client.get_view("player-a").pending_decision == targets
    movement = _select_committed_target(client, targets)
    payload = _test_witnessed_attached_charge_payload(client, movement)
    assert payload["charge_target_unit_instance_ids"] == [COMMITTED]
    accepted = client.submit_movement_payload(
        request_id=movement.request_id,
        payload=payload,
        result_id="ui-attached-after-reroll-move",
    )
    assert accepted.status_kind != "invalid", accepted.invalid_diagnostics
    owner_events = client.get_events_since(0, "player-a").events
    roll = next(event for event in owner_events if event["event_type"] == "charge_roll_resolved")
    roll_payload = _object(roll["payload"])
    assert ATTACHED in json.dumps(roll_payload)
    assert "ui-test:charge-reroll" in json.dumps(owner_events)
    assert charge_action_id in json.dumps(owner_events)
    opponent_events = client.get_events_since(0, "player-b").events
    assert any(event["event_type"] == "charge_move_completed" for event in opponent_events)


def _scout_descriptor(*, datasheet_id: str, distance: int) -> DatasheetAbilityDescriptor:
    return DatasheetAbilityDescriptor(
        ability_id=f"ui-test-core-scouts-{distance}",
        name=f"Core Scouts {distance}",
        source_id=f"ui-test:{datasheet_id}:scouts:{distance}",
        support=CatalogAbilitySupport.DESCRIPTOR_ONLY,
        source_kind=CatalogAbilitySourceKind.CORE,
        effect_description=f"Core Scouts {distance} source",
        timing_tags=("before_battle", "scouts"),
        parameter_tokens=(str(distance),),
    )


def _scout_catalog(base: ArmyCatalog, *, attached: bool, transport: bool) -> ArmyCatalog:
    datasheets: list[DatasheetDefinition] = []
    for sheet in base.datasheets:
        if sheet.datasheet_id == "core-intercessor-like-infantry":
            datasheets.append(
                replace(
                    sheet,
                    abilities=(
                        *sheet.abilities,
                        _scout_descriptor(datasheet_id=sheet.datasheet_id, distance=8),
                    ),
                )
            )
        elif sheet.datasheet_id == "core-character-leader" and attached:
            datasheets.append(
                replace(
                    sheet,
                    keywords=DatasheetKeywordSet(
                        keywords=(*sheet.keywords.keywords, "SCOUTS"),
                        faction_keywords=sheet.keywords.faction_keywords,
                    ),
                    abilities=(
                        *sheet.abilities,
                        _scout_descriptor(datasheet_id=sheet.datasheet_id, distance=8),
                    ),
                )
            )
        elif sheet.datasheet_id == "core-transport" and transport:
            datasheets.append(
                replace(
                    sheet,
                    keywords=DatasheetKeywordSet(
                        keywords=(*sheet.keywords.keywords, "DEDICATED_TRANSPORT"),
                        faction_keywords=sheet.keywords.faction_keywords,
                    ),
                )
            )
        else:
            datasheets.append(sheet)
    return replace(base, datasheets=tuple(datasheets))


def _scout_client(*, attached: bool, transport: bool) -> LocalSessionClient:
    """Seed placed setup state; let the real lifecycle issue the Scout choice."""

    config = canonical_setup_prebattle_smoke_config(
        game_id="ui-contract42-scout-attached" if attached else "ui-contract42-scout-transport"
    )
    assert config.army_catalog is not None
    catalog = _scout_catalog(config.army_catalog, attached=attached, transport=transport)
    alpha, beta = config.army_muster_requests
    alpha_selections: tuple[UnitMusterSelection, ...] = (alpha.unit_selections[0],)
    attachments: tuple[AttachmentDeclaration, ...] = ()
    if attached:
        alpha_selections = (
            *alpha_selections,
            UnitMusterSelection(
                unit_selection_id="leader",
                datasheet_id="core-character-leader",
                model_profile_selections=(
                    ModelProfileSelection(model_profile_id="core-character-leader", model_count=1),
                ),
            ),
        )
        attachments = (
            AttachmentDeclaration(
                source_unit_selection_id="leader",
                bodyguard_unit_selection_id="scout-redeploy-unit",
            ),
        )
    if transport:
        alpha_selections = (
            *alpha_selections,
            UnitMusterSelection(
                unit_selection_id="transport",
                datasheet_id="core-transport",
                model_profile_selections=(
                    ModelProfileSelection(model_profile_id="core-transport", model_count=1),
                ),
            ),
        )
    alpha = replace(alpha, unit_selections=alpha_selections, attachment_declarations=attachments)
    beta = replace(beta, unit_selections=(beta.unit_selections[0],))
    config = replace(
        config, army_catalog=catalog, army_muster_requests=(alpha, beta), reserve_unit_points=()
    )
    armies = tuple(muster_army(catalog=catalog, request=request) for request in (alpha, beta))
    state = GameState.from_config(config)
    for army in armies:
        state.record_army_definition(army)
    # These are test-only starting placements. Their legality remains core-owned.
    battlefield = create_empty_deployment_battlefield_state(state=state)
    for army in armies:
        for unit in army.units:
            unit_id = unit.unit_instance_id
            if transport and unit_id == "army-alpha:scout-redeploy-unit":
                continue
            origin = (
                Pose.at(5.0, 53.0)
                if unit_id == "army-alpha:scout-redeploy-unit"
                else Pose.at(8.6, 54.8)
                if unit_id == "army-alpha:leader"
                else Pose.at(20.0, 55.0)
                if unit_id == "army-alpha:transport"
                else Pose.at(32.0, 7.0)
            )
            battlefield = battlefield.with_added_unit_placement(
                UnitPlacement(
                    army_id=army.army_id,
                    player_id=army.player_id,
                    unit_instance_id=unit_id,
                    model_placements=tuple(
                        ModelPlacement(
                            army_id=army.army_id,
                            player_id=army.player_id,
                            unit_instance_id=unit_id,
                            model_instance_id=model.model_instance_id,
                            pose=Pose.at(
                                origin.position.x + (index % 3) * 1.8,
                                origin.position.y + (index // 3) * 1.8,
                            ),
                        )
                        for index, model in enumerate(unit.own_models)
                    ),
                )
            )
    state.record_battlefield_state(battlefield)
    for player_id in state.player_ids:
        state.record_secondary_mission_choice(
            SecondaryMissionChoice(
                player_id=player_id,
                mode=SecondaryMissionMode.FIXED,
                fixed_mission_ids=("assassination", "bring_it_down"),
            )
        )
    if transport:
        state.record_transport_cargo_state(
            TransportCargoState(
                player_id="player-a",
                transport_unit_instance_id="army-alpha:transport",
                capacity_profile=TransportCapacityProfile(
                    transport_datasheet_id="core-transport",
                    max_model_count=10,
                    allowed_keywords=("Infantry",),
                ),
                embarked_unit_instance_ids=("army-alpha:scout-redeploy-unit",),
                phase_battle_round=None,
                started_phase_embarked_unit_instance_ids=("army-alpha:scout-redeploy-unit",),
                disembarked_this_phase_unit_instance_ids=(),
            )
        )
    while state.current_setup_step is not SetupStep.RESOLVE_PREBATTLE_ACTIONS:
        state.complete_current_setup_step()
    decisions = GameLifecycle().decision_controller
    if attached:
        for army in armies:
            decisions.event_log.append(
                "army_mustered", army_mustered_event_payload(state=state, army_definition=army)
            )
    placements = tuple(
        ModelPlacementRecord(
            model_instance_id=model.model_instance_id,
            placement_kind=BattlefieldPlacementKind.DEPLOYMENT,
            pose=model.pose,
            source_phase="setup",
            source_step="deploy_armies",
        )
        for placed_army in battlefield.placed_armies
        for unit in placed_army.unit_placements
        for model in unit.model_placements
    )
    transition = BattlefieldTransitionBatch(
        placements=tuple(sorted(placements, key=lambda row: row.model_instance_id))
    )
    decisions.event_log.append(
        "battlefield_models_placed",
        {
            "game_id": state.game_id,
            "setup_step": "deploy_armies",
            "battlefield_id": battlefield.battlefield_id,
            "placement_kind": BattlefieldPlacementKind.DEPLOYMENT.value,
            "placed_model_count": len(transition.placements),
            "transition_batch": transition.to_payload(),
        },
    )
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


@pytest.mark.parametrize(
    ("attached", "transport", "expected_unit"),
    [
        (True, False, "attached-unit:army-alpha:scout-redeploy-unit"),
        (False, True, "army-alpha:transport"),
    ],
)
def test_scout_source_distance_choices_are_projected_and_routed(
    attached: bool, transport: bool, expected_unit: str
) -> None:
    client = _scout_client(attached=attached, transport=transport)
    selection = _decision(client.advance_until_decision_or_terminal(), "select_prebattle_action")
    assert selection.actor_id == "player-a"
    prefix = "dedicated_transport_scout_move:" if transport else "scout_move:"
    options = tuple(option for option in selection.options if option.option_id.startswith(prefix))
    assert len(options) == 2
    assert {
        cast(float, _object(option.payload)["scout_distance_inches"]) for option in options
    } == {6.0, 8.0}
    owner = client.get_view("player-a")
    opponent = client.get_view("player-b")
    assert owner.pending_decision == selection
    assert opponent.pending_decision == selection
    panel = build_finite_decision_panel(
        pending_decision=selection,
        highlighted_option_index=0,
        status_message="Choose Scout source",
        diagnostics=(),
    )
    assert {row.option_id for row in panel.options} == {
        option.option_id for option in selection.options
    }
    chosen = next(
        option for option in options if _object(option.payload)["scout_distance_inches"] == 6.0
    )
    source_rows = cast(list[JsonObject], _object(chosen.payload)["scout_ability_instances"])
    assert source_rows
    assert len({cast(str, row["model_instance_id"]) for row in source_rows}) >= 1
    if attached:
        leader_sources = [
            row
            for row in source_rows
            if cast(str, row["model_instance_id"]).startswith("army-alpha:leader")
        ]
        assert len(leader_sources) == 1
        assert leader_sources[0]["distance_inches"] == 8.0
        assert {cast(float, row["distance_inches"]) for row in source_rows} == {6.0, 8.0}
    else:
        assert all(
            cast(str, row["model_instance_id"]).startswith("army-alpha:transport")
            for row in source_rows
        )
        assert all("cargo-distance:" in cast(str, row["source_id"]) for row in source_rows)
        session = cast(LocalGameSession, client.session)
        state = session.lifecycle.state
        assert state is not None
        cargo = state.transport_cargo_state_for_transport("army-alpha:transport")
        assert cargo is not None
        assert cargo.embarked_unit_instance_ids == ("army-alpha:scout-redeploy-unit",)
    before = _records_and_battlefield(client)
    with pytest.raises(UiClientSubmissionError):
        client.submit_finite(
            request_id=selection.request_id,
            selected_option_id=f"{chosen.option_id}:forged",
            result_id="ui-scout-forged-source",
        )
    assert _records_and_battlefield(client) == before
    finite = FiniteDecisionUiState.from_status(
        UiClientStatus(stage="setup", status_kind="waiting_for_decision", decision=selection)
    ).highlight_option(chosen.option_id)
    _, submitted = finite.prepare_submission()
    assert submitted is not None
    proposal_status = client.submit_finite(
        request_id=submitted.request_id,
        selected_option_id=submitted.selected_option_id,
        result_id="ui-scout-select-source",
    )
    proposal = _decision(proposal_status, "submit_scout_move")
    assert proposal.actor_id == "player-a"
    assert proposal.movement_proposal is not None
    assert proposal.movement_proposal.unit_instance_id == expected_unit
    assert proposal.movement_proposal.scout_distance_inches == 6.0
    assert proposal.movement_proposal.source_decision_request_id == selection.request_id
    assert proposal.movement_proposal.source_decision_result_id == "ui-scout-select-source"
    assert proposal.movement_proposal.source_rule_id == _object(chosen.payload)["source_rule_id"]
    assert client.get_view("player-a").pending_decision == proposal
    assert client.get_view("player-b").pending_decision == proposal
    owner_events = client.get_events_since(0, "player-a").events
    opponent_events = client.get_events_since(0, "player-b").events
    selected_event = next(
        event for event in owner_events if event["event_type"] == "prebattle_action_selected"
    )
    assert selected_event in opponent_events
    selected_payload = _object(selected_event["payload"])
    assert selected_payload["selected_option_id"] == chosen.option_id
    assert selected_payload["source_decision_request_id"] == selection.request_id
    assert selected_payload["source_decision_result_id"] == "ui-scout-select-source"
    assert selected_payload["proposal_request_id"] == proposal.request_id
    after_selection = _records_and_battlefield(client)
    with pytest.raises(UiClientSubmissionError):
        client.submit_finite(
            request_id=selection.request_id,
            selected_option_id=chosen.option_id,
            result_id="ui-scout-stale-source",
        )
    assert _records_and_battlefield(client) == after_selection
    if transport:
        _verify_transport_scout_endpoint_submission(client, proposal)


def _verify_transport_scout_endpoint_submission(
    client: LocalSessionClient, proposal: UiDecision
) -> None:
    """Submit a real two-pose Scout witness, after an invalid start-position attempt."""

    owner_view = client.get_view("player-a")
    battlefield = battlefield_view_from_game_view(owner_view)
    unit_id = "army-alpha:transport"
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_model_id(
        unit_id=unit_id,
        model_id=None,
        preferences=preferences,
    )
    draft = MovementDraft.start_for_pending(
        view=battlefield,
        selection=selection,
        pending_decision=proposal,
    )
    assert draft is not None
    start_x, start_y = draft.model_paths[0].points[0]
    ready = draft.add_waypoint(
        view=battlefield,
        world_point=(start_x + 1.0, start_y),
    ).mark_ready(view=battlefield)
    payload = ready.payload_preview
    assert payload is not None
    request = proposal.movement_proposal
    assert request is not None
    assert payload["proposal_request_id"] == proposal.request_id
    assert payload["source_rule_id"] == request.source_rule_id
    assert payload["action_kind"] == "dedicated_transport_scout_move"
    assert payload["context"] == request.context
    paths = cast(list[JsonObject], _object(payload["witness"])["model_paths"])
    assert paths
    assert all(len(cast(list[JsonObject], path["poses"])) == 2 for path in paths)
    before = _records_and_battlefield(client)
    invalid = deepcopy(payload)
    invalid_paths = cast(list[JsonObject], _object(invalid["witness"])["model_paths"])
    first_pose = _object(cast(list[JsonObject], invalid_paths[0]["poses"])[0])
    position = _object(first_pose["position"])
    position["x"] = cast(float, position["x"]) + 1.0
    rejected = client.submit_parameterized_payload(
        request_id=proposal.request_id,
        payload=invalid,
        result_id="ui-scout-invalid-start-path",
    )
    assert rejected.status_kind == "invalid"
    assert any(
        diagnostic.violation_code == "witness_start_drift"
        for diagnostic in rejected.invalid_diagnostics
    )
    assert _records_and_battlefield(client) == before
    assert client.get_view("player-a").pending_decision == proposal
    accepted = client.submit_parameterized_payload(
        request_id=proposal.request_id,
        payload=payload,
        result_id="ui-scout-endpoint-path",
    )
    assert accepted.status_kind != "invalid", accepted.invalid_diagnostics
    completion = next(
        event
        for event in client.get_events_since(0, "player-a").events
        if event["event_type"] == "prebattle_scout_move_completed"
    )
    assert completion in client.get_events_since(0, "player-b").events
