"""Contract 17 phase-end Overwatch through the real UI session facade."""

from __future__ import annotations

from copy import deepcopy
from typing import cast

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.engine.command_points import CommandPointSourceKind
from warhammer40k_core.engine.phase import BattlePhase
from warhammer40k_core.engine.phases.movement import MovementPhaseState
from warhammer40k_core.engine.primary_turn_start_evidence import record_primary_turn_start_evidence

from tests.support.contract42_battle_fixture import shooting_client
from tests.support.gui_driver import GuiTestDriver
from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientSubmissionError,
    UiDecision,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow
from warhammer40k_arcade_ui.render.core_projection import battlefield_view_from_game_view
from warhammer40k_arcade_ui.state.assignment_workspace import (
    AssignmentWorkspace,
    ShootingAssignmentSelection,
)

pytestmark = pytest.mark.integration


def _seeded_client() -> LocalSessionClient:
    """Seed a completed opponent Movement phase; let the engine emit the window."""

    client = shooting_client()
    session = client.session
    assert isinstance(session, LocalGameSession)
    state = session.lifecycle.state
    assert state is not None
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.MOVEMENT)
    state.active_player_id = "player-b"
    state.shooting_phase_state = None
    record_primary_turn_start_evidence(state=state, decisions=session.lifecycle.decision_controller)
    grant = state.gain_command_points(
        player_id="player-a",
        amount=1,
        source_id="contract42-overwatch-fixture-cp",
        source_kind=CommandPointSourceKind.OTHER,
        cap_exempt=True,
    )
    assert grant.applied_amount == 1
    state.movement_phase_state = MovementPhaseState(
        battle_round=state.battle_round,
        active_player_id="player-b",
        move_units_completed=True,
    )
    return client


def _window(client: LocalSessionClient) -> UiDecision:
    status = client.advance_until_decision_or_terminal()
    assert status.status_kind == "waiting_for_decision", status
    request = status.decision
    assert request is not None
    assert request.decision_type == "submit_stratagem_target_proposal"
    assert request.actor_id == "player-a"
    proposal = request.parameterized_proposal
    assert proposal is not None
    assert proposal.request_id == request.request_id
    assert proposal.actor_id == request.actor_id
    body = proposal.payload
    catalog_record = cast(JsonObject, body["catalog_record"])
    definition = cast(JsonObject, catalog_record["definition"])
    assert definition["stratagem_id"] == "fire-overwatch"
    assert body["target_binding"] is None
    context = cast(JsonObject, body["context"])
    assert context["player_id"] == request.actor_id
    assert context["active_player_id"] == "player-b"
    assert context["trigger_payload"] == {
        "timing_window_id": "fire-overwatch-end-movement-round-01-player-player-a",
        "trigger_window": "end_opponent_movement_phase",
    }
    for viewer in ("player-a", "player-b"):
        view = client.get_view(viewer)
        assert view.viewer_player_id == viewer
        assert view.active_player_id == "player-b"
        assert view.pending_decision == request
        assert view.pending_proposal == proposal
    return request


def _shooter_payload(request: UiDecision) -> JsonObject:
    workspace = AssignmentWorkspace.start_for_pending(request)
    assert workspace is not None
    assert workspace.stratagem_target_selectable
    selected = workspace.with_stratagem_intent(
        request,
        target_unit_id="army-alpha:shooter",
    )
    assert selected.is_ready
    payload = selected.payload_preview
    assert payload is not None
    return payload


def _events(client: LocalSessionClient, viewer: str, kind: str) -> tuple[JsonObject, ...]:
    return tuple(
        event
        for event in client.get_events_since(0, viewer).events
        if event.get("event_type") == kind
    )


def test_phase_end_window_declines_without_moved_enemy_or_cp_spend() -> None:
    client = _seeded_client()
    request = _window(client)
    workspace = AssignmentWorkspace.start_for_pending(request)
    assert workspace is not None
    assert workspace.declinable
    assert workspace.decline_payload == {"submission_kind": "decline_stratagem_window"}
    session = client.session
    assert isinstance(session, LocalGameSession)
    state = session.lifecycle.state
    assert state is not None
    before_cp = state.command_point_total("player-a")

    status = client.submit_parameterized_payload(
        request_id=request.request_id,
        payload=workspace.decline_payload,
        result_id="contract42-overwatch-decline",
    )

    assert status.status_kind != "invalid", status
    assert state.command_point_total("player-a") == before_cp
    assert state.stratagem_use_records == []
    assert state.current_battle_phase is BattlePhase.SHOOTING
    for viewer in ("player-a", "player-b"):
        assert _events(client, viewer, "stratagem_used") == ()
        view = client.get_view(viewer)
        assert (
            view.pending_decision is None or view.pending_decision.request_id != request.request_id
        )


def test_phase_end_shooter_can_be_selected_and_submitted_through_headless_hud() -> None:
    client = _seeded_client()
    request = _window(client)
    view = client.get_view("player-a")
    battlefield = battlefield_view_from_game_view(view)
    shooter = next(unit for unit in battlefield.units if unit.unit_id == "army-alpha:shooter")
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=battlefield,
        preferences=default_preferences(),
        pending_decision=request,
        initial_game_view=view,
        core_client=client,
        viewer_player_id="player-a",
    )
    driver = GuiTestDriver(window=window, core_client=client, viewer_player_id="player-a")
    try:
        driver.click_world(shooter.models[0].position)
        assert window.selection_state.selected_unit_id == shooter.unit_id
        window.on_draw()
        select = next(
            region
            for region in driver.hud_button_hit_regions
            if region.action_kind == "assignment_select" and region.enabled
        )
        driver.click_screen(
            round((select.bounds[0] + select.bounds[2]) / 2),
            round((select.bounds[1] + select.bounds[3]) / 2),
        )
        workspace = window.assignment_workspace
        assert workspace is not None
        assert workspace.is_ready
        assert workspace.payload_preview == _shooter_payload(request)
        window.on_draw()
        submit = next(
            region
            for region in driver.hud_button_hit_regions
            if region.action_kind == "assignment_submit" and region.enabled
        )
        driver.click_screen(
            round((submit.bounds[0] + submit.bounds[2]) / 2),
            round((submit.bounds[1] + submit.bounds[3]) / 2),
        )
        next_request = client.get_view("player-a").pending_decision
        assert next_request is not None
        assert next_request.decision_type == "submit_shooting_declaration"
        assert next_request.actor_id == request.actor_id
        assert window.pending_decision == next_request
        assert len(_events(client, "player-a", "stratagem_used")) == 1
    finally:
        driver.close()


def test_phase_end_shooter_and_snap_target_keep_current_source_and_hit_evidence() -> None:
    client = _seeded_client()
    window = _window(client)
    session = client.session
    assert isinstance(session, LocalGameSession)
    state = session.lifecycle.state
    assert state is not None
    shooter_payload = _shooter_payload(window)
    stale_source = deepcopy(shooter_payload)
    stale_proposal = cast(JsonObject, stale_source["proposal"])
    stale_context = cast(JsonObject, stale_proposal["context"])
    stale_context["timing_window_id"] = "stale-window"
    before = state.to_payload()
    rejected_source = client.submit_parameterized_payload(
        request_id=window.request_id,
        payload=stale_source,
        result_id="contract42-overwatch-stale-source",
    )
    assert rejected_source.status_kind == "invalid"
    assert [row.violation_code for row in rejected_source.invalid_diagnostics] == ["wrong_context"]
    assert state.to_payload() == before
    for viewer in ("player-a", "player-b"):
        assert client.get_view(viewer).pending_decision == window

    selected = client.submit_parameterized_payload(
        request_id=window.request_id,
        payload=shooter_payload,
        result_id="contract42-overwatch-shooter",
    )
    assert selected.status_kind == "waiting_for_decision", selected
    declaration = selected.decision
    assert declaration is not None
    assert declaration.decision_type == "submit_shooting_declaration"
    assert declaration.actor_id == window.actor_id
    source = declaration.parameterized_proposal
    assert source is not None
    assert source.payload["source_decision_request_id"] == window.request_id
    assert source.payload["source_decision_result_id"] == "contract42-overwatch-shooter"
    assert state.active_player_id == "player-b"
    assert state.current_battle_phase is BattlePhase.MOVEMENT
    assert state.command_point_total("player-a") == 0
    candidates = cast(list[JsonObject], source.payload["target_candidates"])
    legal = tuple(candidate for candidate in candidates if candidate["is_legal"] is True)
    assert len(legal) == 1
    candidate = legal[0]
    target_id = candidate["target_unit_instance_id"]
    assert isinstance(target_id, str)
    assert target_id == "army-beta:enemy"
    assert candidate["shooting_types"] == ["snap"]
    available_weapons = cast(list[JsonObject], source.payload["available_weapons"])
    assert len(available_weapons) == 1
    weapon = available_weapons[0]
    assert candidate["weapon_instance_id"] == weapon["weapon_instance_id"]
    for viewer in ("player-a", "player-b"):
        view = client.get_view(viewer)
        assert view.pending_decision == declaration
        assert view.active_player_id == "player-b"
        use = _events(client, viewer, "stratagem_used")
        assert len(use) == 1
        use_payload = cast(JsonObject, use[0]["payload"])
        assert use_payload["request_id"] == window.request_id
        assert use_payload["result_id"] == "contract42-overwatch-shooter"
        assert (
            use_payload["target_binding"]
            == cast(JsonObject, shooter_payload["proposal"])["target_binding"]
        )

    workspace = AssignmentWorkspace.start_for_pending(declaration)
    assert workspace is not None
    selected_workspace = workspace.with_shooting_selections(
        declaration,
        (
            ShootingAssignmentSelection(
                model_instance_id=cast(str, weapon["model_instance_id"]),
                weapon_instance_id=cast(str, weapon["weapon_instance_id"]),
                weapon_profile_id=cast(str, weapon["weapon_profile_id"]),
                target_unit_instance_id=target_id,
            ),
        ),
    )
    assert selected_workspace.is_ready
    payload = selected_workspace.payload_preview
    assert payload is not None
    row = cast(list[JsonObject], payload["declarations"])[0]
    assert row["shooting_type"] == "snap"
    assert row["target_unit_instance_id"] == candidate["target_unit_instance_id"]
    assert row["weapon_instance_id"] == candidate["weapon_instance_id"]
    assert payload["source_decision_request_id"] == window.request_id
    assert payload["source_decision_result_id"] == "contract42-overwatch-shooter"

    forged_target = deepcopy(payload)
    cast(list[JsonObject], forged_target["declarations"])[0]["target_unit_instance_id"] = (
        "army-beta:forged"
    )
    before = state.to_payload()
    rejected_target = client.submit_parameterized_payload(
        request_id=declaration.request_id,
        payload=forged_target,
        result_id="contract42-overwatch-forged-target",
    )
    assert rejected_target.status_kind == "invalid"
    assert [row.violation_code for row in rejected_target.invalid_diagnostics] == [
        "out_of_phase_target_unit_drift"
    ]
    assert state.to_payload() == before
    for viewer in ("player-a", "player-b"):
        assert client.get_view(viewer).pending_decision == declaration

    with pytest.raises(UiClientSubmissionError, match="request_id does not match pending request"):
        client.submit_parameterized_payload(
            request_id=window.request_id,
            payload=shooter_payload,
            result_id="contract42-overwatch-reused-window",
        )
    assert state.to_payload() == before

    accepted = client.submit_parameterized_payload(
        request_id=declaration.request_id,
        payload=payload,
        result_id="contract42-overwatch-snap",
    )
    assert accepted.status_kind != "invalid", accepted
    for viewer in ("player-a", "player-b"):
        declaration_events = _events(client, viewer, "out_of_phase_shooting_declaration_accepted")
        assert len(declaration_events) == 1
        declaration_payload = cast(JsonObject, declaration_events[0]["payload"])
        assert declaration_payload["request_id"] == declaration.request_id
        pools = cast(list[JsonObject], declaration_payload["attack_pools"])
        assert pools
        assert all(
            pool["target_unit_instance_id"] == candidate["target_unit_instance_id"]
            for pool in pools
        )
        assert all(pool["weapon_instance_id"] == candidate["weapon_instance_id"] for pool in pools)
        hit_steps = tuple(
            cast(JsonObject, event["payload"])
            for event in _events(client, viewer, "attack_sequence_step")
            if cast(JsonObject, event["payload"])["step"] == "hit"
        )
        assert hit_steps
        for step in hit_steps:
            hit = cast(JsonObject, step["payload"])
            assert hit["critical_threshold"] == 6
            assert hit["critical_is_threshold"] is False
            assert hit["success_requires_exact"] is True
            assert hit["minimum_unmodified_success"] == 6
            assert cast(list[str], hit["threshold_source_ids"])
        hit_dice = tuple(
            cast(JsonObject, event["payload"])
            for event in _events(client, viewer, "dice_rolled")
            if cast(JsonObject, cast(JsonObject, event["payload"])["spec"])["roll_type"]
            == "attack_sequence.hit"
        )
        assert hit_dice
        assert all(
            cast(JsonObject, die["spec"])["reroll_forbidden_rule_ids"] == ["core:snap-shooting"]
            for die in hit_dice
        )
