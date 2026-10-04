"""Source-backed public movement and event context at the UI boundary.

The contact event is domain seeded to exercise the shared public redactor; its
engine generation is covered by Core's own geometry suite, not asserted here.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import cast

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.core.datasheet import (
    CatalogAbilitySourceKind,
    CatalogAbilitySupport,
    CatalogJsonObject,
    DatasheetAbilityDescriptor,
)
from warhammer40k_core.engine.army_mustering import muster_army
from warhammer40k_core.engine.lifecycle import GameLifecycle, GameLifecyclePayload
from warhammer40k_core.engine.movement_legality import MovementCapabilitySet
from warhammer40k_core.engine.phase import BattlePhase
from warhammer40k_core.engine.reaction_windows import ReactionWindow, ReactionWindowKind
from warhammer40k_core.engine.triggered_movement import (
    TriggeredMovementDescriptor,
    TriggeredMovementEligibleUnit,
    TriggeredMovementKind,
)
from warhammer40k_core.engine.triggered_movement_selection import (
    triggered_movement_unit_selection_request,
)
from warhammer40k_core.rules.rule_ir import RuleIR
from warhammer40k_core.rules.source_packages.warhammer_40000_11th import faction_pack_rule_ir

from tests.support.contract42_battle_fixture import shooting_client
from tests.support.contract42_charge_fixture import COMMITTED, SOURCE, seeded_charge_client
from warhammer40k_arcade_ui.core_client.live_smoke import build_live_core_smoke_startup
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import UiDecision
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.core_projection import battlefield_view_from_game_view
from warhammer40k_arcade_ui.state.finite_decision import FiniteDecisionUiState
from warhammer40k_arcade_ui.state.movement_draft import (
    MovementDraft,
    movement_proposal_context_diagnostic,
)
from warhammer40k_arcade_ui.state.selection import SelectionState

pytestmark = pytest.mark.integration


def _decision(client: LocalSessionClient) -> UiDecision:
    status = client.advance_until_decision_or_terminal()
    assert status.status_kind == "waiting_for_decision"
    assert status.decision is not None
    return status.decision


def _source_draft(client: LocalSessionClient, decision: UiDecision) -> MovementDraft:
    return _draft_for(client, decision, viewer_id="player-a", unit_id=SOURCE)


def _draft_for(
    client: LocalSessionClient, decision: UiDecision, *, viewer_id: str, unit_id: str
) -> MovementDraft:
    view = client.get_view(viewer_id)
    assert view.pending_decision == decision
    battlefield = battlefield_view_from_game_view(view)
    source = next(unit for unit in battlefield.units if unit.unit_id == unit_id)
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_model_id(
        unit_id=unit_id,
        model_id=source.models[0].model_id,
        preferences=preferences,
    )
    draft = MovementDraft.start_for_pending(
        view=battlefield,
        selection=selection,
        pending_decision=decision,
        projection_state_hash=view.projection_state_hash,
    )
    assert draft is not None
    return draft


def _reactive_normal_client() -> LocalSessionClient:
    """Give the public fixture a genuine catalog RuleIR reactive Normal Move source."""

    raw_rule = faction_pack_rule_ir.datasheet_rule_ir_payload_by_source_row_id("000004090:3")
    assert raw_rule is not None
    rule = RuleIR.from_payload(raw_rule)
    baseline = shooting_client(models=1, enemy_x=18.0)
    session = baseline.session
    assert isinstance(session, LocalGameSession)
    lifecycle = session.lifecycle
    config = lifecycle.config
    state = lifecycle.state
    assert config is not None
    assert state is not None
    ability = DatasheetAbilityDescriptor(
        ability_id="contract42-reactive-normal",
        name="Reactive Normal Move source",
        source_id=rule.source_id,
        support=CatalogAbilitySupport.GENERIC_RULE_IR,
        source_kind=CatalogAbilitySourceKind.DATASHEET,
        effect_description=rule.normalized_text,
        rule_ir_payload=cast(CatalogJsonObject, rule.to_payload()),
    )
    catalog = replace(
        config.army_catalog,
        datasheets=tuple(
            replace(sheet, abilities=(*sheet.abilities, ability))
            if sheet.datasheet_id == "core-intercessor-like-infantry"
            else sheet
            for sheet in config.army_catalog.datasheets
        ),
    )
    new_config = replace(config, army_catalog=catalog)
    armies = tuple(
        muster_army(
            catalog=catalog,
            request=request,
            model_geometries=new_config.model_geometries,
        )
        for request in new_config.army_muster_requests
    )
    state.replace_army_definitions(list(armies))
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.MOVEMENT)
    state.active_player_id = "player-b"
    restored = GameLifecycle.from_payload(
        cast(
            GameLifecyclePayload,
            {
                **lifecycle.to_payload(),
                "config": new_config.to_payload(),
                "state": state.to_payload(),
            },
        )
    )
    return LocalSessionClient(session=LocalGameSession(lifecycle=restored))


def test_real_primary_scoring_event_keeps_issued_scoring_player_identity() -> None:
    startup = build_live_core_smoke_startup(stop_at_phase="movement")
    own_events = startup.core_client.get_events_since(0, "player-a").events
    opposing_events = startup.core_client.get_events_since(0, "player-b").events
    scoring = tuple(
        event
        for event in own_events
        if event["event_type"] == "primary_scoring_commit_checkpoint_recorded"
    )
    assert scoring
    assert all(
        type(event["payload"]) is dict and event["payload"]["scoring_player_id"] == "player-a"
        for event in scoring
    )
    assert all(event not in opposing_events for event in scoring)
    assert startup.status.decision is not None
    assert startup.viewer_player_id == startup.status.decision.actor_id


def test_public_event_preserves_contact_summary_and_nullable_capability_without_query() -> None:
    client = seeded_charge_client()
    session = client.session
    assert isinstance(session, LocalGameSession)
    config = session.lifecycle.config
    assert config is not None
    capability = MovementCapabilitySet.from_keywords(
        (), ruleset_descriptor=config.ruleset_descriptor
    ).to_payload()
    assert capability["horizontal_terrain_transit_height_inches"] is None
    record = session.lifecycle.decision_controller.event_log.append(
        "charge_move_completed",
        {
            "game_id": config.game_id,
            "player_id": "player-a",
            "unit_instance_id": SOURCE,
            "movement_capability": capability,
            "path_result": {
                "deemed_base_contacts": [
                    {
                        "source_rule_id": "source:body-overhang",
                        "enemy_model_instance_id": f"{COMMITTED}:model:001",
                        "movement_query": {"private_path": "source-only"},
                    }
                ],
                "base_contact_query": {"private_path": "source-only"},
                "without_overhang_witness": {"private_path": "source-only"},
            },
        },
    )
    for viewer in ("player-a", "player-b"):
        events = client.get_events_since(0, viewer).events
        public = next(event for event in events if event["event_id"] == record.event_id)
        payload = public["payload"]
        assert type(payload) is dict
        assert payload["movement_capability"] == capability
        path_result = payload["path_result"]
        assert type(path_result) is dict
        contacts = path_result["deemed_base_contacts"]
        assert contacts == [
            {
                "source_rule_id": "source:body-overhang",
                "enemy_model_instance_id": f"{COMMITTED}:model:001",
            }
        ]
        encoded = json.dumps(public)
        assert "base_contact_query" not in encoded
        assert "movement_query" not in encoded
        assert "without_overhang_witness" not in encoded


def _surge_client() -> LocalSessionClient:
    client = seeded_charge_client()
    session = client.session
    assert isinstance(session, LocalGameSession)
    lifecycle = session.lifecycle
    state = lifecycle.state
    assert state is not None
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.SHOOTING)
    trigger = lifecycle.decision_controller.event_log.append(
        "source_rule_triggered",
        {
            "game_id": state.game_id,
            "battle_round": state.battle_round,
            "phase": "shooting",
            "active_player_id": state.active_player_id,
            "source_rule_id": "test:source-backed-surge",
        },
    )
    descriptor = TriggeredMovementDescriptor(
        movement_kind=TriggeredMovementKind.SURGE,
        source_rule_id="test:source-backed-surge",
        trigger_timing=ReactionWindow(
            phase=BattlePhase.SHOOTING,
            window_kind=ReactionWindowKind.RULE_TRIGGER,
            source_step="just_after_enemy_unit_has_shot",
            source_event_id=trigger.event_id,
        ),
        max_distance_inches=3,
    )
    request = triggered_movement_unit_selection_request(
        state=state,
        decisions=lifecycle.decision_controller,
        player_id="player-a",
        descriptor=descriptor,
        eligible_units=(
            TriggeredMovementEligibleUnit(SOURCE, "test:hook", descriptor.source_rule_id),
        ),
    )
    lifecycle.decision_controller.request_decision(request)
    return client


def test_real_surge_choice_keeps_target_and_nullable_mode_through_public_draft() -> None:
    client = _surge_client()
    selection = _decision(client)
    assert selection.decision_type == "select_triggered_movement"
    assert selection.actor_id == "player-a"
    chosen = next(option for option in selection.options if option.option_id.startswith("surge:"))
    assert chosen.option_id == f"surge:{SOURCE}:target:{COMMITTED}"
    assert type(chosen.payload) is dict
    assert chosen.payload["surge_target_unit_instance_id"] == COMMITTED
    assert chosen.payload["take_to_the_skies"] is False
    status = client.submit_finite(
        request_id=selection.request_id,
        selected_option_id=chosen.option_id,
        result_id="ui-surge-target",
    )
    assert status.status_kind != "invalid"
    request = status.decision
    assert request is not None
    assert request.decision_type == "submit_movement_proposal"
    proposal = request.movement_proposal
    assert proposal is not None
    assert proposal.context["selection_option_id"] == chosen.option_id
    assert proposal.context["surge_target_unit_instance_id"] == COMMITTED
    assert "movement_mode" not in proposal.context
    assert movement_proposal_context_diagnostic(proposal) is None
    draft = _source_draft(client, request)
    assert draft.movement_mode is None
    assert draft.movement_budget_inches == 3.0
    battlefield = battlefield_view_from_game_view(client.get_view("player-a"))
    source = next(unit for unit in battlefield.units if unit.unit_id == SOURCE)
    group_x = sum(model.position[0] for model in source.models) / len(source.models)
    ready = (
        draft.select_current_group(view=battlefield)
        .add_waypoint(view=battlefield, world_point=(group_x, 23.0))
        .mark_ready(view=battlefield)
    )
    payload = ready.payload_preview
    assert payload is not None
    assert payload["movement_mode"] is None
    assert "surge_target_unit_instance_id" not in payload
    accepted = client.submit_movement_payload(
        request_id=request.request_id,
        payload=payload,
        result_id="ui-surge-path",
    )
    assert accepted.status_kind != "invalid", accepted.invalid_diagnostics
    public_events = client.get_events_since(0, "player-a").events
    resolved = tuple(
        event for event in public_events if event["event_type"] == "triggered_movement_resolved"
    )
    assert len(resolved) == 1
    resolved_payload = resolved[0]["payload"]
    assert type(resolved_payload) is dict
    assert resolved_payload["surge_target_unit_instance_id"] == COMMITTED
    assert "aircraft_movement_policy" not in resolved_payload


def test_real_flight_option_id_and_mode_survive_current_public_request() -> None:
    client = seeded_charge_client(fly=True)
    session = client.session
    assert isinstance(session, LocalGameSession)
    state = session.lifecycle.state
    assert state is not None
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.MOVEMENT)
    selection = _decision(client)
    assert selection.decision_type == "select_movement_unit"
    action_status = client.submit_finite(
        request_id=selection.request_id,
        selected_option_id=SOURCE,
        result_id="ui-flight-unit",
    )
    action = action_status.decision
    assert action is not None
    assert action.decision_type == "select_movement_action"
    flight = next(
        option for option in action.options if option.option_id == "normal_move:fly_take_to_skies"
    )
    assert type(flight.payload) is dict
    assert flight.payload["movement_mode"] == "fly_take_to_skies"
    proposal_status = client.submit_finite(
        request_id=action.request_id,
        selected_option_id=flight.option_id,
        result_id="ui-flight-selected",
    )
    request = proposal_status.decision
    assert request is not None
    proposal = request.movement_proposal
    assert proposal is not None
    assert proposal.context["source_selected_option_id"] == flight.option_id
    assert proposal.context["movement_mode"] == "fly_take_to_skies"
    draft = _source_draft(client, request)
    assert draft.movement_mode == "fly_take_to_skies"
    battlefield = battlefield_view_from_game_view(client.get_view("player-a"))
    source = next(unit for unit in battlefield.units if unit.unit_id == SOURCE)
    group_x = sum(model.position[0] for model in source.models) / len(source.models)
    ready = (
        draft.select_current_group(view=battlefield)
        .add_waypoint(view=battlefield, world_point=(group_x, 21.0))
        .mark_ready(view=battlefield)
    )
    payload = ready.payload_preview
    assert payload is not None
    assert payload["movement_mode"] == "fly_take_to_skies"
    result = client.submit_movement_payload(
        request_id=request.request_id,
        payload=payload,
        result_id="ui-flight-path",
    )
    assert result.status_kind != "invalid", result.invalid_diagnostics


def test_real_reactive_normal_move_uses_opponent_actor_and_source_mode() -> None:
    client = _reactive_normal_client()
    turn_selection = _decision(client)
    assert turn_selection.decision_type == "select_movement_unit"
    assert turn_selection.actor_id == "player-b"
    turn_action = client.submit_finite(
        request_id=turn_selection.request_id,
        selected_option_id="army-beta:enemy",
        result_id="ui-reactive-turn-unit",
    ).decision
    assert turn_action is not None
    turn_request = client.submit_finite(
        request_id=turn_action.request_id,
        selected_option_id="normal_move",
        result_id="ui-reactive-turn-action",
    ).decision
    assert turn_request is not None
    turn_view = client.get_view("player-b")
    turn_battlefield = battlefield_view_from_game_view(turn_view)
    turn_draft = _draft_for(client, turn_request, viewer_id="player-b", unit_id="army-beta:enemy")
    turn_ready = (
        turn_draft.select_current_group(view=turn_battlefield)
        .add_waypoint(view=turn_battlefield, world_point=(18.5, 35.0))
        .mark_ready(view=turn_battlefield)
    )
    assert turn_ready.payload_preview is not None
    trigger_status = client.submit_movement_payload(
        request_id=turn_request.request_id,
        payload=turn_ready.payload_preview,
        result_id="ui-reactive-turn-path",
    )
    trigger = trigger_status.decision
    assert trigger is not None
    assert trigger.decision_type == "select_triggered_movement"
    assert trigger.actor_id == "player-a"
    option = next(option for option in trigger.options if option.option_id.startswith("triggered:"))
    assert option.option_id == "triggered:army-alpha:shooter"
    assert type(option.payload) is dict
    descriptor = option.payload["descriptor"]
    assert type(descriptor) is dict
    assert descriptor["movement_mode"] == "normal"
    assert descriptor["source_rule_id"] == cast(str, option.payload["source_rule_id"])
    assert option.payload["movement_phase_action"] == "surge_move"
    finite = FiniteDecisionUiState.from_status(trigger_status).highlight_option(option.option_id)
    refreshed, submission = finite.prepare_submission()
    assert refreshed.pending_decision == trigger
    assert submission is not None
    proposal_status = client.submit_finite(
        request_id=submission.request_id,
        selected_option_id=submission.selected_option_id,
        result_id="ui-reactive-select-source",
    )
    request = proposal_status.decision
    assert request is not None
    assert request.decision_type == "submit_movement_proposal"
    assert request.actor_id == "player-a"
    proposal = request.movement_proposal
    assert proposal is not None
    assert proposal.proposal_kind == "surge_move"
    assert "movement_mode" not in proposal.context
    request_descriptor = proposal.context["descriptor"]
    assert type(request_descriptor) is dict
    assert request_descriptor["movement_mode"] == "normal"
    reactive_view = client.get_view("player-a")
    assert reactive_view.pending_decision == request
    reactive_battlefield = battlefield_view_from_game_view(reactive_view)
    reactive_draft = _draft_for(client, request, viewer_id="player-a", unit_id="army-alpha:shooter")
    assert reactive_draft.movement_mode is None
    assert reactive_draft.movement_budget_inches == 6.0
    reactive_ready = (
        reactive_draft.select_current_group(view=reactive_battlefield)
        .add_waypoint(view=reactive_battlefield, world_point=(10.25, 35.0))
        .mark_ready(view=reactive_battlefield)
    )
    assert reactive_ready.payload_preview is not None
    assert reactive_ready.payload_preview["movement_mode"] is None
    resolved = client.submit_movement_payload(
        request_id=request.request_id,
        payload=reactive_ready.payload_preview,
        result_id="ui-reactive-normal-path",
    )
    assert resolved.status_kind != "invalid", resolved.invalid_diagnostics
    assert any(
        event["event_type"] == "triggered_movement_resolved"
        for event in client.get_events_since(0, "player-a").events
    )


def test_ordinary_movement_without_emitted_mode_still_reports_typed_diagnostic() -> None:
    client = seeded_charge_client(fly=True)
    session = client.session
    assert isinstance(session, LocalGameSession)
    state = session.lifecycle.state
    assert state is not None
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.MOVEMENT)
    selection = _decision(client)
    action = client.submit_finite(
        request_id=selection.request_id,
        selected_option_id=SOURCE,
        result_id="ui-mode-unit",
    ).decision
    assert action is not None
    request = client.submit_finite(
        request_id=action.request_id,
        selected_option_id="normal_move",
        result_id="ui-mode-action",
    ).decision
    assert request is not None
    proposal = request.movement_proposal
    assert proposal is not None
    malformed = replace(proposal, context={"source_selected_option_id": "normal_move"})
    diagnostic = movement_proposal_context_diagnostic(malformed)
    assert diagnostic is not None
    assert diagnostic.violation_code == "movement_mode_missing_from_proposal_context"
