"""Finite routing and source evidence at the Contract 42 UI boundary.

Conformance requests below are core-authored examples. The fake client in that
test only records UI routing; real-session tests use LocalSessionClient.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from functools import cache
from typing import cast

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.adapters.setup_smoke import canonical_setup_prebattle_smoke_config
from warhammer40k_core.core.army_catalog import ArmyCatalog
from warhammer40k_core.core.attributes import Characteristic
from warhammer40k_core.core.datasheet import (
    CatalogAbilitySourceKind,
    CatalogAbilitySupport,
    DatasheetAbilityDescriptor,
)
from warhammer40k_core.core.dice import DiceExpression, DiceRollResult, DiceRollSpec, DiceRollState
from warhammer40k_core.core.dice_extremum import DiceExtremum
from warhammer40k_core.core.missions import ObjectiveMarkerRole
from warhammer40k_core.core.modifiers import ModifierOperation, ModifierTerm
from warhammer40k_core.core.profile_modifier_trace import CharacteristicModifierTrace
from warhammer40k_core.core.random_profile_values import RandomProfileValue
from warhammer40k_core.core.range_profiles import RangeProfile
from warhammer40k_core.core.ruleset_descriptor import RulesetDescriptor
from warhammer40k_core.engine.army_mustering import muster_army
from warhammer40k_core.engine.battlefield_state import ModelPlacement, UnitPlacement
from warhammer40k_core.engine.damage_allocation import DECLINE_DESTRUCTION_REACTION_OPTION_ID
from warhammer40k_core.engine.decision_request import DecisionRequest
from warhammer40k_core.engine.effects import (
    GENERIC_RULE_EFFECT_KIND,
    EffectExpiration,
    PersistingEffect,
)
from warhammer40k_core.engine.event_log import EventLog, JsonValue
from warhammer40k_core.engine.game_state import GameConfig
from warhammer40k_core.engine.lifecycle import GameLifecycle
from warhammer40k_core.engine.mission_setup import MissionSetup
from warhammer40k_core.engine.phase import BattlePhase, GameLifecycleStage
from warhammer40k_core.engine.placement import create_deterministic_battlefield_scenario
from warhammer40k_core.engine.primary_historical_events import (
    record_new_primary_turn_start_evidence_events,
)
from warhammer40k_core.engine.primary_turn_start_evidence import (
    record_primary_turn_start_evidence,
)
from warhammer40k_core.engine.saves import SaveKind, SaveOption, SaveOptionPayload
from warhammer40k_core.geometry.pose import Pose
from warhammer40k_core.rules.mission_pack_import import (
    warhammer_event_companion_2026_07_mission_pack,
)

from tests.support.contract42_battle_fixture import shooting_client
from tests.support.core_contract_examples import (
    required_core_example_path,
    verified_core_examples_root,
)
from warhammer40k_arcade_ui.core_client.fake_client import FakeCoreClient
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientStatus,
    UiClientSubmissionError,
    UiDecision,
    UiEventDelta,
    UiGameView,
)
from warhammer40k_arcade_ui.hud.dice_tray import build_dice_tray_view
from warhammer40k_arcade_ui.state.assignment_workspace import AssignmentWorkspace
from warhammer40k_arcade_ui.state.finite_decision import (
    FiniteDecisionUiState,
    submit_finite_option,
)

NEW_FINITE_FAMILIES = (
    "select_charge_targets",
    "select_core_ability_instance",
    "select_dice_extremum",
    "select_lethal_hit_wound",
    "select_melee_weapon",
    "select_modifier_ignores",
    "select_mortal_wound_model",
    "select_target_replacement",
    "select_unit_split_membership",
)


@cache
def _conformance_requests() -> tuple[JsonObject, ...]:
    path = required_core_example_path("decisions", "interaction-conformance.json")
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    assert type(raw) is dict
    inventory = cast(JsonObject, raw)
    cases_value = inventory["cases"]
    assert type(cases_value) is list
    cases = cast(list[JsonObject], cases_value)
    requests: list[JsonObject] = []
    for case in cases:
        assert type(case) is dict
        request = case["request"]
        assert type(request) is dict
        requests.append(request)
    return tuple(requests)


@pytest.mark.parametrize("family", NEW_FINITE_FAMILIES)
def test_new_finite_family_routes_current_core_example_ids_without_invention(
    family: str,
) -> None:
    matches = tuple(
        request for request in _conformance_requests() if request["decision_type"] == family
    )
    assert len(matches) == 1, family
    decision = UiDecision.from_annotated_payload(matches[0])
    assert not decision.is_parameterized
    assert decision.options
    assert decision.actor_id is not None
    option = decision.options[-1]
    client = FakeCoreClient(
        status=UiClientStatus(stage="battle", status_kind="waiting_for_decision"),
        view=_minimal_view(decision.actor_id),
        event_delta=UiEventDelta(
            viewer_player_id=decision.actor_id, cursor=0, next_cursor=0, events=()
        ),
    )
    state = FiniteDecisionUiState(pending_decision=decision)
    forged = submit_finite_option(
        state=state,
        client=client,
        selected_option_id=f"{option.option_id}:not-issued",
        viewer_player_id=decision.actor_id,
    )
    assert forged.finite_state.diagnostics[0].violation_code == "selected_option_not_pending"
    assert not client.finite_submissions

    routed = submit_finite_option(
        state=state,
        client=client,
        selected_option_id=option.option_id,
        viewer_player_id=decision.actor_id,
    )
    assert routed.refreshed_view is not None
    assert routed.viewer_player_id == decision.actor_id
    assert len(client.finite_submissions) == 1
    submission = client.finite_submissions[0]
    assert submission.request_id == matches[0]["request_id"]
    raw_options = cast(list[JsonObject], matches[0]["options"])
    assert submission.selected_option_id == raw_options[-1]["option_id"]
    assert submission.result_id == "ui-result-000001"


@pytest.mark.integration
def test_real_private_dice_extremum_is_owner_scoped_through_local_facade() -> None:
    """Exercise Core's secret dice choice through current public views and submissions."""

    # Core's canonical fixture imports its sibling `tests` helpers. Temporarily
    # expose that pinned package path without replacing this UI test package.
    core_tests = str(verified_core_examples_root().parents[1] / "tests")
    test_package = importlib.import_module("tests")
    package_path = cast(list[str], test_package.__path__)
    package_path.append(core_tests)
    try:
        helper = importlib.import_module("tests.dice_result_semantics_helpers")
    finally:
        package_path.remove(core_tests)
    extremum_session = cast(
        Callable[..., tuple[LocalGameSession, DiceRollState, DecisionRequest]],
        helper.extremum_session,
    )
    session, roll, request = extremum_session(extremum=DiceExtremum.LOWEST, secret=True)
    client = LocalSessionClient(session=session)
    owner = client.get_view("player-a")
    decision = owner.pending_decision
    assert decision is not None
    assert decision.decision_type == "select_dice_extremum"
    assert decision.actor_id == "player-a"
    assert decision.request_id == request.request_id
    assert tuple(option.option_id for option in decision.options) == tuple(
        option.option_id for option in request.options
    )
    assert len(decision.options) == 2  # Core's tied physical dice need a real choice.
    assert type(decision.payload) is dict
    assert decision.payload["roll_state"] == roll.to_payload()

    opponent = client.get_view("player-b")
    hidden = opponent.pending_decision
    assert hidden is not None
    assert hidden.decision_type == "hidden_decision"
    assert hidden.request_id != request.request_id
    assert hidden.actor_id is None
    assert hidden.options == ()
    assert hidden.interaction is None
    assert hidden.payload == {"secret": True, "hidden": True}
    hidden_json = json.dumps(hidden.payload)
    assert request.request_id not in hidden_json
    assert roll.original_result.roll_id not in hidden_json
    assert all(option.option_id not in hidden_json for option in request.options)
    assert client.get_view("player-a").pending_decision == decision

    owner_before = client.get_events_since(0, "player-a")
    opponent_before = client.get_events_since(0, "player-b")
    referenced = tuple(
        event for event in owner_before.events if event["event_type"] == "dice_extremum_referenced"
    )
    assert len(referenced) == 1
    assert not any(
        "dice_extremum" in cast(str, event["event_type"]) for event in opponent_before.events
    )
    assert request.request_id not in json.dumps(opponent_before.events)

    before_records = session.decision_record_count()
    with pytest.raises(UiClientSubmissionError):
        client.submit_finite(
            request_id=decision.request_id,
            selected_option_id=f"{decision.options[0].option_id}:forged",
            result_id="finite-private-dice-forged",
        )
    assert session.decision_record_count() == before_records
    assert client.get_view("player-a").pending_decision == decision
    assert client.get_view("player-b").pending_decision == hidden
    assert client.get_events_since(0, "player-a") == owner_before
    assert client.get_events_since(0, "player-b") == opponent_before

    result_id = "finite-private-dice-selected"
    accepted = client.submit_finite(
        request_id=decision.request_id,
        selected_option_id=decision.options[0].option_id,
        result_id=result_id,
    )
    assert accepted.status_kind != "invalid", accepted.invalid_diagnostics
    assert session.decision_record_count() == before_records + 1
    owner_after = client.get_view("player-a")
    opponent_after = client.get_view("player-b")
    assert owner_after.pending_decision is not None
    assert owner_after.pending_decision.request_id != decision.request_id
    assert opponent_after.pending_decision is not None
    assert opponent_after.pending_decision.request_id != request.request_id
    owner_new = client.get_events_since(owner_before.next_cursor, "player-a")
    opponent_new = client.get_events_since(opponent_before.next_cursor, "player-b")
    selected = tuple(
        event for event in owner_new.events if event["event_type"] == "dice_extremum_selected"
    )
    assert len(selected) == 1
    selected_payload = cast(JsonObject, selected[0]["payload"])
    assert selected_payload["request_id"] == request.request_id
    assert selected_payload["result_id"] == result_id
    assert selected_payload["selection"] == decision.options[0].payload
    assert not any(
        "dice_extremum" in cast(str, event["event_type"]) for event in opponent_new.events
    )
    opponent_events_json = json.dumps(client.get_events_since(0, "player-b").events)
    assert request.request_id not in opponent_events_json
    assert roll.original_result.roll_id not in opponent_events_json
    assert result_id not in opponent_events_json
    assert all(option.option_id not in opponent_events_json for option in request.options)


def _minimal_view(viewer: str) -> UiGameView:
    return UiGameView(
        viewer_player_id=viewer,
        game_id="finite-routing-example",
        stage="battle",
        battle_round=1,
        active_player_id=viewer,
        current_setup_step=None,
        current_battle_phase="shooting",
        player_ids=("player-a", "player-b"),
        battlefield_state=None,
        mission_setup=None,
        public_secondary_mission_choices=(),
        public_secondary_mission_card_states=(),
        public_command_point_ledgers=(),
        public_victory_point_ledgers=(),
        public_stratagem_use_records=(),
        pending_decision=None,
        pending_proposal=None,
    )


def _ability(ability_id: str, name: str, token: str) -> DatasheetAbilityDescriptor:
    return DatasheetAbilityDescriptor(
        ability_id=ability_id,
        name=name,
        source_id=f"datasheet:core-intercessor-like-infantry:ability:{ability_id}",
        support=CatalogAbilitySupport.DESCRIPTOR_ONLY,
        source_kind=CatalogAbilitySourceKind.CORE,
        effect_description=f"{name} source fixture.",
        parameter_tokens=(token,),
    )


def _duplicate_core_config() -> GameConfig:
    config = canonical_setup_prebattle_smoke_config()
    catalog = config.army_catalog
    assert catalog is not None
    sources = (
        _ability("finite-source-firing-deck-a", "Firing Deck", "2"),
        _ability("finite-source-firing-deck-b", "Firing Deck", "5"),
    )
    return replace(
        config,
        army_catalog=replace(
            catalog,
            datasheets=tuple(
                replace(sheet, abilities=(*sheet.abilities, *sources))
                if sheet.datasheet_id == "core-intercessor-like-infantry"
                else sheet
                for sheet in catalog.datasheets
            ),
        ),
    )


@pytest.mark.integration
def test_real_setup_duplicate_core_sources_are_owner_private_and_reject_forgery() -> None:
    client = LocalSessionClient(session=LocalGameSession())
    status = client.start_game(_duplicate_core_config())
    source_choices = 0
    for index in range(16):
        if status.decision is None:
            status = client.advance_until_decision_or_terminal()
        decision = status.decision
        assert decision is not None
        if decision.decision_type != "select_core_ability_instance":
            break
        assert decision.actor_id is not None
        actor = decision.actor_id
        opponent = "player-b" if actor == "player-a" else "player-a"
        own_view = client.get_view(actor)
        other_view = client.get_view(opponent)
        assert own_view.pending_decision == decision
        assert other_view.pending_decision is not None
        assert other_view.pending_decision.decision_type == "hidden_decision"
        assert "ability_sources" not in json.dumps(other_view.pending_decision.payload)
        assert len(decision.options) == 2
        assert "core_ability_instance" in json.dumps(decision.payload)
        option = decision.options[index % len(decision.options)]
        before_records = cast(LocalGameSession, client.session).decision_record_count()
        before_hash = own_view.projection_state_hash
        with pytest.raises(UiClientSubmissionError):
            client.submit_finite(
                request_id=decision.request_id,
                selected_option_id=f"{option.option_id}:forged",
                result_id=f"finite-source-forged-{index}",
            )
        assert cast(LocalGameSession, client.session).decision_record_count() == before_records
        assert client.get_view(actor).projection_state_hash == before_hash
        accepted = client.submit_finite(
            request_id=decision.request_id,
            selected_option_id=option.option_id,
            result_id=f"finite-source-selected-{index}",
        )
        assert accepted.status_kind != "invalid", accepted.invalid_diagnostics
        assert cast(LocalGameSession, client.session).decision_record_count() == before_records + 1
        own_events = client.get_events_since(0, actor).events
        other_events = client.get_events_since(0, opponent).events
        selected = tuple(
            event
            for event in own_events
            if event["event_type"] == "core_ability_instance_selected"
            and type(event["payload"]) is dict
            and event["payload"].get("result_id") == f"finite-source-selected-{index}"
        )
        assert len(selected) == 1
        assert selected[0] not in other_events
        assert decision.request_id not in json.dumps(other_events)
        stale_records = cast(LocalGameSession, client.session).decision_record_count()
        stale_hash = client.get_view(actor).projection_state_hash
        with pytest.raises(UiClientSubmissionError):
            client.submit_finite(
                request_id=decision.request_id,
                selected_option_id=option.option_id,
                result_id=f"finite-source-stale-{index}",
            )
        assert cast(LocalGameSession, client.session).decision_record_count() == stale_records
        assert client.get_view(actor).projection_state_hash == stale_hash
        status = accepted
        source_choices += 1
    assert source_choices >= 2


def _lethal_battle_with_duplicate_demise(
    *, save_sources: bool = False, random_range: bool = False
) -> LocalSessionClient:
    """Seed a genuine battle from a new catalog, then use only public decisions."""

    baseline = shooting_client(lethal_attack=True)
    baseline_lifecycle = cast(LocalGameSession, baseline.session).lifecycle
    baseline_state = baseline_lifecycle.state
    config = baseline_lifecycle.config
    assert baseline_state is not None
    assert baseline_state.battlefield_state is not None
    assert config is not None
    assert config.army_catalog is not None
    catalog = config.army_catalog
    sources = (
        _ability("finite-source-demise-a", "Deadly Demise", "D3"),
        _ability("finite-source-demise-b", "Deadly Demise", "D6"),
    )
    catalog = replace(
        catalog,
        datasheets=tuple(
            replace(
                sheet,
                abilities=(*sheet.abilities, *sources),
                model_profiles=(
                    tuple(
                        replace(
                            profile,
                            characteristics=tuple(
                                CharacteristicModifierTrace(
                                    characteristic=value.characteristic,
                                    source_value=value.raw,
                                    modifiers=(
                                        ModifierTerm(
                                            ModifierOperation.ADD, -1, result_floor=3
                                        ).bind(
                                            modifier_id="finite-save:floor",
                                            source_id="source:finite-save:floor",
                                            characteristic=value.characteristic,
                                        ),
                                        ModifierTerm(ModifierOperation.ADD, 1).bind(
                                            modifier_id="finite-save:unrestricted",
                                            source_id="source:finite-save:unrestricted",
                                            characteristic=value.characteristic,
                                        ),
                                    ),
                                ).value()
                                if value.characteristic is Characteristic.SAVE
                                else value
                                for value in profile.characteristics
                            ),
                        )
                        for profile in sheet.model_profiles
                    )
                    if save_sources
                    else sheet.model_profiles
                ),
            )
            if sheet.datasheet_id == "core-intercessor-like-infantry"
            else sheet
            for sheet in catalog.datasheets
        ),
        wargear=(
            tuple(
                replace(
                    item,
                    weapon_profiles=tuple(
                        replace(
                            profile,
                            range_profile=RangeProfile.random(
                                RandomProfileValue(
                                    Characteristic.RANGE,
                                    DiceExpression(1, 6, 24),
                                    "source:finite-random-range",
                                )
                            ),
                            source_ids=(*profile.source_ids, "source:finite-random-range"),
                        )
                        for profile in item.weapon_profiles
                    ),
                )
                if item.wargear_id == "core-bolt-rifle"
                else item
                for item in catalog.wargear
            )
            if random_range
            else catalog.wargear
        ),
    )
    config = replace(config, army_catalog=catalog)
    armies = tuple(
        muster_army(catalog=catalog, request=request, model_geometries=config.model_geometries)
        for request in config.army_muster_requests
    )
    lifecycle = GameLifecycle()
    lifecycle.start(config)
    lifecycle.decision_controller.event_log = EventLog()
    state = lifecycle.state
    assert state is not None
    for army in armies:
        state.record_army_definition(army)
    state.record_battlefield_state(baseline_state.battlefield_state)
    for choice in baseline_state.secondary_mission_choices:
        state.record_secondary_mission_choice(choice)
    state.stage = GameLifecycleStage.BATTLE
    state.setup_step_index = None
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.SHOOTING)
    state.battle_round = 1
    state.active_player_id = "player-a"
    objective_ids = tuple(row.state_id for row in state.primary_objective_turn_start_states)
    snapshot_ids = tuple(row.snapshot_id for row in state.primary_rules_unit_turn_start_snapshots)
    record_primary_turn_start_evidence(state=state, decisions=lifecycle.decision_controller)
    record_new_primary_turn_start_evidence_events(
        state=state,
        event_log=lifecycle.decision_controller.event_log,
        objective_state_ids_before=objective_ids,
        snapshot_ids_before=snapshot_ids,
    )
    if save_sources:
        for name, effect_kind, parameters in (
            (
                "permission",
                "grant_ability",
                {"ability": "modifier_ignore_permission", "selection": "any_or_all"},
            ),
            (
                "bonus",
                "modify_dice_roll",
                {"roll_type": "save", "delta": 2, "attack_role": "target"},
            ),
            (
                "penalty",
                "modify_dice_roll",
                {"roll_type": "save", "delta": -2, "attack_role": "target"},
            ),
        ):
            state.record_persisting_effect(
                _combat_effect(
                    effect_id=f"finite-save:{name}",
                    owner="player-b",
                    unit_id="army-beta:enemy",
                    effect_kind=effect_kind,
                    parameters=cast(dict[str, JsonValue], parameters),
                )
            )
    if random_range:
        state.record_persisting_effect(
            _combat_effect(
                effect_id="finite-random-range:bonus",
                owner="player-a",
                unit_id="army-alpha:shooter",
                effect_kind="modify_characteristic",
                parameters={"characteristic": "range", "delta": 2},
            )
        )
    return LocalSessionClient(
        session=LocalGameSession(GameLifecycle.from_payload(lifecycle.to_payload()))
    )


@pytest.mark.integration
def test_real_duplicate_deadly_demise_requires_an_issued_source_without_decline() -> None:
    client = _lethal_battle_with_duplicate_demise()
    status = client.advance_until_decision_or_terminal()
    assert status.decision is not None
    assert status.decision.decision_type == "select_shooting_unit"
    status = client.submit_finite(
        request_id=status.decision.request_id,
        selected_option_id="army-alpha:shooter",
        result_id="u",
    )
    assert status.decision is not None
    assert status.decision.decision_type == "select_shooting_type"
    status = client.submit_finite(
        request_id=status.decision.request_id,
        selected_option_id="normal",
        result_id="t",
    )
    assert status.decision is not None
    assert status.decision.decision_type == "submit_shooting_declaration"
    workspace = AssignmentWorkspace.start_for_pending(status.decision)
    assert workspace is not None
    assert workspace.is_ready
    assert workspace.payload_preview is not None
    status = client.submit_parameterized_payload(
        request_id=status.decision.request_id,
        payload=workspace.payload_preview,
        result_id="shot",
    )
    request = status.decision
    assert request is not None
    assert request.decision_type == "select_destruction_reaction"
    assert request.actor_id == "player-b"
    assert type(request.payload) is dict
    assert request.payload["selection_kind"] == "duplicated_deadly_demise_instance"
    assert len(request.options) == 2
    assert all(
        option.option_id != DECLINE_DESTRUCTION_REACTION_OPTION_ID for option in request.options
    )
    assert all(type(option.payload) is dict for option in request.options)
    assert len({option.option_id for option in request.options}) == 2
    current = client.get_view("player-b")
    assert current.pending_decision == request
    before_hash = current.projection_state_hash
    before_records = cast(LocalGameSession, client.session).decision_record_count()
    with pytest.raises(UiClientSubmissionError):
        client.submit_finite(
            request_id=request.request_id,
            selected_option_id=DECLINE_DESTRUCTION_REACTION_OPTION_ID,
            result_id="finite-source-invented-decline",
        )
    assert cast(LocalGameSession, client.session).decision_record_count() == before_records
    assert client.get_view("player-b").projection_state_hash == before_hash
    selected = request.options[1]
    accepted = client.submit_finite(
        request_id=request.request_id,
        selected_option_id=selected.option_id,
        result_id="finite-source-demise-selected",
    )
    assert accepted.status_kind != "invalid", accepted.invalid_diagnostics
    assert cast(LocalGameSession, client.session).decision_record_count() == before_records + 1
    assert any(
        event["event_type"] == "core_ability_instance_selected"
        for event in client.get_events_since(0, "player-b").events
    )
    stale_records = cast(LocalGameSession, client.session).decision_record_count()
    stale_hash = client.get_view("player-b").projection_state_hash
    with pytest.raises(UiClientSubmissionError):
        client.submit_finite(
            request_id=request.request_id,
            selected_option_id=selected.option_id,
            result_id="finite-source-demise-stale",
        )
    assert cast(LocalGameSession, client.session).decision_record_count() == stale_records
    assert client.get_view("player-b").projection_state_hash == stale_hash


@pytest.mark.integration
def test_real_save_choice_preserves_floor_and_separate_ap_and_roll_sources() -> None:
    client = _lethal_battle_with_duplicate_demise(save_sources=True)
    status = client.advance_until_decision_or_terminal()
    assert status.decision is not None
    status = client.submit_finite(
        request_id=status.decision.request_id,
        selected_option_id="army-alpha:shooter",
        result_id="u",
    )
    assert status.decision is not None
    status = client.submit_finite(
        request_id=status.decision.request_id,
        selected_option_id="normal",
        result_id="t",
    )
    assert status.decision is not None
    workspace = AssignmentWorkspace.start_for_pending(status.decision)
    assert workspace is not None
    assert workspace.is_ready
    assert workspace.payload_preview is not None
    status = client.submit_parameterized_payload(
        request_id=status.decision.request_id,
        payload=workspace.payload_preview,
        result_id="shot",
    )
    first_request_id: str | None = None
    saw_floor = False
    for index in range(12):
        decision = status.decision
        assert decision is not None
        assert decision.decision_type == "select_modifier_ignores"
        assert decision.actor_id == "player-b"
        assert type(decision.payload) is dict
        subject = cast(JsonObject, decision.payload["subject"])
        rows = cast(list[JsonObject], decision.payload["modifiers"])
        operations = tuple(cast(JsonObject, row["operation"]) for row in rows)
        assert client.get_view("player-b").pending_decision == decision
        other = client.get_view("player-a")
        assert other.pending_decision is not None
        assert other.pending_decision.decision_type == "hidden_decision"
        assert decision.request_id not in json.dumps(other.pending_decision.payload)
        if subject["kind"] == "save_characteristic":
            first_request_id = first_request_id or decision.request_id
            floor = next(
                operation
                for operation in operations
                if operation["modifier_id"] == "finite-save:floor"
            )
            unrestricted = next(
                operation
                for operation in operations
                if operation["modifier_id"] == "finite-save:unrestricted"
            )
            assert floor["result_floor"] == 3
            assert "result_floor" not in unrestricted
            assert floor["source_id"] != unrestricted["source_id"]
            saw_floor = True
        elif subject["kind"] == "save_roll":
            assert saw_floor
            assert first_request_id is not None
            assert all(row["operation_type"] == "roll" for row in rows)
            ap = next(
                operation
                for operation in operations
                if cast(str, operation["modifier_id"]).endswith(":saving-throw-ap")
            )
            other_operations = tuple(operation for operation in operations if operation is not ap)
            assert len(other_operations) == 2
            assert {cast(int, operation["operand"]) for operation in other_operations} == {
                2,
                -2,
            }
            assert cast(str, ap["source_id"]) not in {
                cast(str, operation["source_id"]) for operation in other_operations
            }
            before = cast(LocalGameSession, client.session).decision_record_count()
            before_hash = client.get_view("player-b").projection_state_hash
            with pytest.raises(UiClientSubmissionError):
                client.submit_finite(
                    request_id=first_request_id,
                    selected_option_id=decision.options[0].option_id,
                    result_id="finite-save-stale",
                )
            assert cast(LocalGameSession, client.session).decision_record_count() == before
            assert client.get_view("player-b").projection_state_hash == before_hash
            result = client.submit_finite(
                request_id=decision.request_id,
                selected_option_id="keep-remaining",
                result_id="finite-save-roll-kept",
            )
            assert result.status_kind != "invalid", result.invalid_diagnostics
            assert decision.request_id not in json.dumps(
                client.get_events_since(0, "player-a").events
            )
            return
        else:
            raise AssertionError(f"Unexpected modifier kind: {subject['kind']}")
        status = client.submit_finite(
            request_id=decision.request_id,
            selected_option_id="keep-remaining",
            result_id=f"finite-save-characteristic-{index}",
        )
        assert status.status_kind != "invalid", status.invalid_diagnostics
    raise AssertionError("The saving throw source choice was not reached.")


def test_core_save_option_serialization_requires_inherent_ap_separately_from_roll_sources() -> None:
    """Domain payload shape behind the real save-choice inventory above."""

    from warhammer40k_core.core.modifiers import RollModifier
    from warhammer40k_core.engine.phase import GameLifecycleError
    from warhammer40k_core.engine.save_modifier_operations import save_option_with_roll_modifier

    option = save_option_with_roll_modifier(
        SaveOption(SaveKind.ARMOUR, 5, 3, -2),
        RollModifier("finite-save:bonus", 1, source_id="source:finite-save:bonus"),
    )
    payload = option.to_payload()
    assert len(payload["inherent_roll_modifiers"]) == 2
    assert len(payload["roll_modifiers"]) == 1
    assert {term["modifier_id"] for term in payload["inherent_roll_modifiers"]}.isdisjoint(
        {term["modifier_id"] for term in payload["roll_modifiers"]}
    )
    assert SaveOption.from_payload(payload) == option
    broken = dict(payload)
    del broken["inherent_roll_modifiers"]
    with pytest.raises((GameLifecycleError, KeyError)):
        SaveOption.from_payload(cast(SaveOptionPayload, broken))


def _evaluated_random_values(value: JsonValue) -> tuple[JsonObject, ...]:
    found: list[JsonObject] = []
    if type(value) is dict:
        if {"evaluation_raw", "evaluation", "evaluation_id"} <= value.keys():
            found.append(value)
        for child in value.values():
            found.extend(_evaluated_random_values(child))
    elif type(value) is list:
        for child in value:
            found.extend(_evaluated_random_values(child))
    return tuple(found)


@pytest.mark.integration
def test_real_random_range_keeps_raw_evaluation_identity_and_source_modifiers() -> None:
    client = _lethal_battle_with_duplicate_demise(random_range=True)
    status = client.advance_until_decision_or_terminal()
    assert status.decision is not None
    status = client.submit_finite(
        request_id=status.decision.request_id,
        selected_option_id="army-alpha:shooter",
        result_id="u",
    )
    assert status.decision is not None
    status = client.submit_finite(
        request_id=status.decision.request_id,
        selected_option_id="normal",
        result_id="t",
    )
    request = status.decision
    assert request is not None
    assert request.decision_type == "submit_shooting_declaration"
    projected = client.get_view("player-a")
    assert projected.pending_decision == request
    values = _evaluated_random_values(request.payload)
    assert values
    modified = next(value for value in values if value.get("modifiers"))
    evaluation = cast(JsonObject, modified["evaluation"])
    assert modified["source_id"] == "source:finite-random-range"
    assert type(modified["evaluation_raw"]) is int
    assert type(modified["evaluation_id"]) is str
    assert evaluation["raw"] == modified["evaluation_raw"]
    assert evaluation["final"] != modified["evaluation_raw"]
    assert len(cast(list[JsonObject], modified["modifiers"])) == 1
    projected_request = projected.pending_decision
    assert projected_request is not None
    assert modified in _evaluated_random_values(projected_request.payload)
    raw_public = cast(LocalGameSession, client.session).view(viewer_player_id="player-a")
    raw_pending = cast(JsonObject, raw_public["pending_decision"])
    assert modified in _evaluated_random_values(raw_pending["payload"])
    workspace = AssignmentWorkspace.start_for_pending(request)
    assert workspace is not None
    assert workspace.is_ready
    assert workspace.payload_preview is not None
    result = client.submit_parameterized_payload(
        request_id=request.request_id,
        payload=workspace.payload_preview,
        result_id="finite-random-range-shot",
    )
    assert result.status_kind != "invalid", result.invalid_diagnostics


@pytest.mark.integration
@pytest.mark.parametrize(
    ("component_index", "replacement_value"),
    [(0, 9), (None, 14)],
)
def test_core_domain_seeded_override_event_keeps_physical_faces_in_ui_projection(
    component_index: int | None, replacement_value: int
) -> None:
    """Seed typed Core dice evidence, then read it through a real local adapter.

    This fixture verifies presentation of an existing override, not permission to
    create the override as a game action.
    """

    client = shooting_client()
    session = cast(LocalGameSession, client.session)
    original = DiceRollResult.from_values(
        roll_id=f"finite-source-roll-{component_index}",
        spec=DiceRollSpec(
            expression=DiceExpression(2, 6),
            reason="Core physical and assigned result evidence",
            roll_type="charge_roll",
            actor_id="player-a",
        ),
        values=(2, 5),
        source="fixed",
    )
    updated = DiceRollState.from_result(original).with_result_override(
        decision_id=f"finite-source-override-{component_index}",
        request_id=f"finite-source-override-request-{component_index}",
        source_rule_id="gw-11e-core-dice-results:treated-as-set-to",
        replacement_value=replacement_value,
        component_index=component_index,
    )
    event_log = session.lifecycle.decision_controller.event_log
    event_log.append("dice_rolled", original.to_payload())
    event_log.append("dice_result_overridden", {"updated_roll_state": updated.to_payload()})
    for viewer in ("player-a", "player-b"):
        delta = client.get_events_since(0, viewer)
        override = next(
            event for event in delta.events if event["event_type"] == "dice_result_overridden"
        )
        assert cast(JsonObject, override["payload"])["updated_roll_state"] == (updated.to_payload())
        tray = build_dice_tray_view(event_payloads=delta.events, pending_decision=None)
        roll = tray.active_roll
        assert roll is not None
        assert roll.values == original.values
        assert roll.assigned_values == updated.current_values
        assert roll.total == updated.current_total
        assert roll.result_override is not None
        assert roll.result_override["component_index"] == component_index
        assert [column.face for column in tray.face_columns if column.count] == [2, 5]


def _action_oc_catalog(catalog: ArmyCatalog) -> ArmyCatalog:
    return replace(
        catalog,
        datasheets=tuple(
            replace(
                sheet,
                model_profiles=tuple(
                    replace(
                        profile,
                        characteristics=tuple(
                            CharacteristicModifierTrace(
                                characteristic=value.characteristic,
                                source_value=value.raw,
                                modifiers=(
                                    ModifierTerm(ModifierOperation.ADD, 2).bind(
                                        modifier_id="finite-oc:bonus",
                                        source_id="source:finite-oc:bonus",
                                        characteristic=value.characteristic,
                                    ),
                                    ModifierTerm(ModifierOperation.ADD, -2).bind(
                                        modifier_id="finite-oc:penalty",
                                        source_id="source:finite-oc:penalty",
                                        characteristic=value.characteristic,
                                    ),
                                ),
                            ).value()
                            if value.characteristic is Characteristic.OBJECTIVE_CONTROL
                            else value
                            for value in profile.characteristics
                        ),
                    )
                    for profile in sheet.model_profiles
                ),
            )
            for sheet in catalog.datasheets
        ),
        detachments=tuple(
            replace(
                detachment,
                force_disposition_ids=tuple(
                    dict.fromkeys((*detachment.force_disposition_ids, "priority-assets"))
                ),
            )
            if detachment.detachment_id == "core-combined-arms"
            else detachment
            for detachment in catalog.detachments
        ),
    )


def _oc_permission(unit_id: str) -> PersistingEffect:
    effect_id = "finite-source:oc-permission"
    source = f"source:{effect_id}"
    span: JsonObject = {"start": 0, "end": 1, "text": "x"}
    return PersistingEffect(
        effect_id=effect_id,
        source_rule_id=source,
        owner_player_id="player-a",
        target_unit_instance_ids=(unit_id,),
        started_battle_round=1,
        started_phase=BattlePhase.SHOOTING,
        expiration=EffectExpiration.end_phase(
            battle_round=1, phase=BattlePhase.SHOOTING, player_id="player-a"
        ),
        effect_payload={
            "effect_kind": GENERIC_RULE_EFFECT_KIND,
            "rule_id": f"rule:{effect_id}",
            "source_id": source,
            "rule_ir_hash": "0" * 64,
            "clause_id": f"clause:{effect_id}",
            "effect_index": 0,
            "source_span": span,
            "target": {"kind": "this_unit", "source_span": span, "parameters": []},
            "target_unit_instance_ids": [unit_id],
            "duration": None,
            "conditions": [],
            "effect": {
                "kind": "grant_ability",
                "source_span": span,
                "parameters": [
                    {"key": "ability", "value": "modifier_ignore_permission"},
                    {"key": "selection", "value": "any_or_all"},
                ],
            },
            "context": {
                "state": None,
                "player_id": "player-a",
                "phase": BattlePhase.SHOOTING.value,
                "source_model_instance_id": None,
                "trigger_payload": None,
            },
        },
    )


def _combat_effect(
    *,
    effect_id: str,
    owner: str,
    unit_id: str,
    effect_kind: str,
    parameters: dict[str, JsonValue],
) -> PersistingEffect:
    source = f"source:{effect_id}"
    original = _oc_permission(unit_id)
    payload = cast(JsonObject, deepcopy(original.effect_payload))
    effect = cast(JsonObject, payload["effect"])
    context = cast(JsonObject, payload["context"])
    payload["rule_id"] = f"rule:{effect_id}"
    payload["source_id"] = source
    payload["clause_id"] = f"clause:{effect_id}"
    effect["kind"] = effect_kind
    effect["parameters"] = [
        {"key": key, "value": value} for key, value in sorted(parameters.items())
    ]
    context["player_id"] = owner
    return replace(
        original,
        effect_id=effect_id,
        source_rule_id=source,
        owner_player_id=owner,
        effect_payload=payload,
    )


def _mission_action_client() -> tuple[LocalSessionClient, str]:
    baseline = shooting_client(models=5)
    config = cast(LocalGameSession, baseline.session).lifecycle.config
    assert config is not None
    assert config.army_catalog is not None
    setup = MissionSetup.from_mission_pack(
        mission_pack=warhammer_event_companion_2026_07_mission_pack(),
        mission_pool_entry_id="mission-purge-the-foe-vs-priority-assets-layout-1",
        terrain_layout_id="purge-the-foe-vs-priority-assets-layout-1",
        attacker_player_id="player-b",
        defender_player_id="player-a",
        attacker_force_disposition_id="purge-the-foe",
        defender_force_disposition_id="priority-assets",
    )
    catalog = _action_oc_catalog(config.army_catalog)
    config = replace(
        config,
        ruleset_descriptor=(
            RulesetDescriptor.warhammer_40000_eleventh_chapter_approved_2026_27(
                descriptor_version="finite-source-action"
            )
        ),
        army_catalog=catalog,
        mission_setup=setup,
        army_muster_requests=tuple(
            replace(
                request,
                force_disposition_id=(
                    "priority-assets" if request.player_id == "player-a" else "purge-the-foe"
                ),
            )
            for request in config.army_muster_requests
        ),
    )
    armies = tuple(
        muster_army(catalog=catalog, request=request, model_geometries=config.model_geometries)
        for request in config.army_muster_requests
    )
    field = create_deterministic_battlefield_scenario(
        battlefield_id="finite-source-action-field",
        battlefield_width_inches=setup.battlefield_width_inches,
        battlefield_depth_inches=setup.battlefield_depth_inches,
        armies=armies,
    ).battlefield_state
    field = replace(field, terrain_features=setup.terrain_features)
    marker = next(
        item
        for item in setup.objective_markers
        if item.objective_role is ObjectiveMarkerRole.CENTRAL
    )
    unit = armies[0].units[0]
    field = field.with_unit_placement(
        UnitPlacement(
            army_id=armies[0].army_id,
            player_id="player-a",
            unit_instance_id=unit.unit_instance_id,
            model_placements=tuple(
                ModelPlacement(
                    army_id=armies[0].army_id,
                    player_id="player-a",
                    unit_instance_id=unit.unit_instance_id,
                    model_instance_id=model.model_instance_id,
                    pose=Pose.at(
                        marker.x_inches + (index % 3) * 1.5,
                        marker.y_inches + (index // 3) * 1.5,
                    ),
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
    state.record_battlefield_state(field)
    baseline_state = cast(LocalGameSession, baseline.session).lifecycle.state
    assert baseline_state is not None
    for choice in baseline_state.secondary_mission_choices:
        state.record_secondary_mission_choice(choice)
    state.stage = GameLifecycleStage.BATTLE
    state.setup_step_index = None
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.SHOOTING)
    state.battle_round = 1
    state.active_player_id = "player-a"
    objective_ids = tuple(row.state_id for row in state.primary_objective_turn_start_states)
    snapshot_ids = tuple(row.snapshot_id for row in state.primary_rules_unit_turn_start_snapshots)
    record_primary_turn_start_evidence(state=state, decisions=lifecycle.decision_controller)
    record_new_primary_turn_start_evidence_events(
        state=state,
        event_log=lifecycle.decision_controller.event_log,
        objective_state_ids_before=objective_ids,
        snapshot_ids_before=snapshot_ids,
    )
    state.record_persisting_effect(_oc_permission(unit.unit_instance_id))
    return (
        LocalSessionClient(
            session=LocalGameSession(GameLifecycle.from_payload(lifecycle.to_payload()))
        ),
        unit.unit_instance_id,
    )


@pytest.mark.integration
@pytest.mark.parametrize("ignore_bonus", [False, True])
def test_real_action_oc_scope_reenumerates_after_source_choices(ignore_bonus: bool) -> None:
    client, unit_id = _mission_action_client()
    status = client.advance_until_decision_or_terminal()
    source_requests = 0
    first_request_id: str | None = None
    for index in range(14):
        decision = status.decision
        assert decision is not None
        if decision.decision_type != "select_modifier_ignores":
            break
        first_request_id = first_request_id or decision.request_id
        source_requests += 1
        assert decision.actor_id == "player-a"
        assert type(decision.payload) is dict
        body = decision.payload
        subject = cast(JsonObject, body["subject"])
        source_context = cast(JsonObject, body["source_context"])
        assert subject["kind"] == "objective_control_characteristic"
        assert source_context["source_kind"] == ("mission_action_objective_control")
        assert unit_id == subject["unit_instance_id"]
        own = client.get_view("player-a")
        other = client.get_view("player-b")
        assert own.pending_decision == decision
        assert other.pending_decision is not None
        assert other.pending_decision.decision_type == "hidden_decision"
        operations = cast(list[JsonObject], body["modifiers"])
        decided = cast(list[str], body["decided_modifier_ids"])
        current = cast(JsonObject, operations[len(decided)]["operation"])
        operand = current["operand"]
        assert type(operand) is int
        ignore = ignore_bonus and operand > 0
        prefix = "ignore:" if ignore else "keep:"
        option_id = next(
            (
                option.option_id
                for option in decision.options
                if option.option_id.startswith(prefix)
            ),
            "ignore-remaining" if ignore else "keep-remaining",
        )
        option = next(option for option in decision.options if option.option_id == option_id)
        records = cast(LocalGameSession, client.session).decision_record_count()
        before_hash = own.projection_state_hash
        with pytest.raises(UiClientSubmissionError):
            client.submit_finite(
                request_id=decision.request_id,
                selected_option_id=f"{option.option_id}:forged",
                result_id=f"finite-oc-forged-{index}",
            )
        assert cast(LocalGameSession, client.session).decision_record_count() == records
        assert client.get_view("player-a").projection_state_hash == before_hash
        status = client.submit_finite(
            request_id=decision.request_id,
            selected_option_id=option.option_id,
            result_id=f"finite-oc-choice-{index}",
        )
        assert status.status_kind != "invalid", status.invalid_diagnostics
    else:
        raise AssertionError("Objective Control choices did not finish.")
    assert source_requests >= 2
    assert first_request_id is not None
    assert first_request_id not in json.dumps(client.get_events_since(0, "player-b").events)
    if ignore_bonus:
        assert status.decision is None or status.decision.decision_type != "start_mission_action"
    else:
        request = status.decision
        assert request is not None
        assert request.decision_type == "start_mission_action"
        assert type(request.payload) is dict
        scope = request.payload["objective_control_modifier_scope_id"]
        assert type(scope) is str
        assert scope
        assert all(
            type(option.payload) is dict
            and option.payload["objective_control_modifier_scope_id"] == scope
            for option in request.options
        )
        assert any(
            type(option.payload) is dict and option.payload.get("unit_instance_id") == unit_id
            for option in request.options
        )
        before = cast(LocalGameSession, client.session).decision_record_count()
        before_hash = client.get_view("player-a").projection_state_hash
        with pytest.raises(UiClientSubmissionError):
            client.submit_finite(
                request_id=first_request_id,
                selected_option_id=request.options[0].option_id,
                result_id="finite-oc-stale",
            )
        assert cast(LocalGameSession, client.session).decision_record_count() == before
        assert client.get_view("player-a").projection_state_hash == before_hash
        action_option = next(
            option
            for option in request.options
            if type(option.payload) is dict and option.payload.get("unit_instance_id") == unit_id
        )
        accepted = client.submit_finite(
            request_id=request.request_id,
            selected_option_id=action_option.option_id,
            result_id="finite-oc-action-started",
        )
        assert accepted.status_kind != "invalid", accepted.invalid_diagnostics
        assert cast(LocalGameSession, client.session).decision_record_count() == before + 1
