# pyright: reportPrivateUsage=false
"""Attached pre-battle editors use current public Core membership and submissions."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import cast

import arcade
import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.engine.phase import SetupStep

from tests.test_contract42_charge_sources import LEADER, _scout_client
from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientStatus,
    UiClientSubmissionError,
    UiDecision,
    UiGameView,
    UiSupportProfile,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow
from warhammer40k_arcade_ui.render.core_projection import battlefield_view_from_game_view
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft, MovementDraftError
from warhammer40k_arcade_ui.state.placement_draft import PlacementDraft, PlacementDraftError
from warhammer40k_arcade_ui.state.selection import SelectionState

pytestmark = pytest.mark.integration

_ATTACHED = "attached-unit:army-alpha:scout-redeploy-unit"
_OWNER = "player-a"
_OPPONENT = "player-b"
_BODYGUARD = "army-alpha:scout-redeploy-unit"
_ENEMY = "army-beta:scout-redeploy-unit"


def _decision(status: UiClientStatus, kind: str) -> UiDecision:
    decision = status.decision
    assert decision is not None, status
    assert decision.decision_type == kind
    return decision


def _object(value: object) -> JsonObject:
    assert type(value) is dict
    return cast(JsonObject, value)


def _empty_deployment_client() -> tuple[LocalSessionClient, dict[str, tuple[float, float]]]:
    """Return a real attached muster at the ordinary empty deployment boundary."""

    client = _scout_client(attached=True, transport=False)
    session = client.session
    assert isinstance(session, LocalGameSession)
    state = session.lifecycle.state
    assert state is not None
    battlefield = state.battlefield_state
    assert battlefield is not None
    original_points = {
        model.model_instance_id: (model.pose.position.x, model.pose.position.y)
        for army in battlefield.placed_armies
        for unit in army.unit_placements
        for model in unit.model_placements
    }
    state.setup_step_index = state.setup_sequence.index(SetupStep.DEPLOY_ARMIES)
    for army in battlefield.placed_armies:
        for unit in army.unit_placements:
            battlefield = battlefield.without_unit_placement(unit.unit_instance_id)
    assert battlefield.placed_armies == ()
    state.replace_battlefield_state(battlefield)
    return client, original_points


def _placement_draft(client: LocalSessionClient, view: UiGameView) -> PlacementDraft:
    assert view.pending_decision is not None
    assert view.battlefield_view is not None
    draft = PlacementDraft.start_for_pending(
        view=battlefield_view_from_game_view(view),
        selection=SelectionState.initial(default_preferences()),
        pending_decision=view.pending_decision,
        model_display_by_id=view.model_display_by_id,
        authoritative_models_by_id=view.battlefield_view.models_by_id,
        battlefield_state=view.battlefield_state,
        support_profile=client.get_support_profile(view.viewer_player_id),
        projection_state_hash=view.projection_state_hash,
    )
    assert draft is not None
    return draft


def _ready_placement(draft: PlacementDraft, points: dict[str, tuple[float, float]]) -> JsonObject:
    for pose in draft.model_poses:
        draft = draft.place_current_model(points[pose.model_id])
    payload = draft.mark_ready().payload_preview
    assert payload is not None
    return payload


def _attached_deployment_request(
    client: LocalSessionClient, original_points: dict[str, tuple[float, float]]
) -> UiDecision:
    first = _decision(client.advance_until_decision_or_terminal(), "select_deployment_unit")
    assert first.actor_id == _OPPONENT
    beta_option = next(
        option
        for option in first.options
        if _object(option.payload).get("unit_instance_id") == _ENEMY
    )
    beta = _decision(
        client.submit_finite(
            request_id=first.request_id,
            selected_option_id=beta_option.option_id,
            result_id="attached-prebattle-beta-select",
        ),
        "submit_deployment_placement",
    )
    beta_view = client.get_view(_OPPONENT)
    beta_payload = _ready_placement(_placement_draft(client, beta_view), original_points)
    beta_status = client.submit_parameterized_payload(
        request_id=beta.request_id,
        payload=beta_payload,
        result_id="attached-prebattle-beta-place",
    )
    assert beta_status.status_kind == "waiting_for_decision", beta_status.invalid_diagnostics
    second = _decision(beta_status, "select_deployment_unit")
    assert second.actor_id == _OWNER
    attached_option = next(
        option
        for option in second.options
        if _object(option.payload).get("is_attached_rules_unit") is True
    )
    assert _object(attached_option.payload)["unit_instance_id"] == _ATTACHED
    attached = _decision(
        client.submit_finite(
            request_id=second.request_id,
            selected_option_id=attached_option.option_id,
            result_id="attached-prebattle-alpha-select",
        ),
        "submit_deployment_placement",
    )
    assert attached.actor_id == _OWNER
    return attached


def _window(client: LocalSessionClient, view: UiGameView) -> ArcadeWarhammerWindow:
    return ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=battlefield_view_from_game_view(view),
        preferences=default_preferences(),
        pending_decision=view.pending_decision,
        initial_game_view=view,
        initial_support_profile=client.get_support_profile(view.viewer_player_id),
        core_client=client,
        viewer_player_id=view.viewer_player_id,
    )


def test_attached_deployment_opens_editor_rejects_nonmember_and_submits_current_request() -> None:
    client, original_points = _empty_deployment_client()
    request = _attached_deployment_request(client, original_points)
    proposal = request.placement_proposal
    assert proposal is not None
    assert proposal.unit_instance_id == _ATTACHED
    assert proposal.component_unit_instance_ids == (LEADER, _BODYGUARD)
    assert len(proposal.required_model_ids) == 6
    owner = client.get_view(_OWNER)
    opponent = client.get_view(_OPPONENT)
    assert owner.pending_decision == request == opponent.pending_decision
    physical = owner.battlefield_view
    assert physical is not None
    assert opponent.battlefield_view is not None
    assert all(
        cast(JsonObject, physical.models_by_id[model_id])["state"] == "undeployed"
        for model_id in proposal.required_model_ids
    )

    window = _window(client, owner)
    try:
        window._sync_placement_draft()
        assert window.placement_draft is not None
        assert window.placement_draft.selected_unit_id == _ATTACHED
        assert window.placement_draft.total_model_count == 6
    finally:
        window.close()

    draft = _placement_draft(client, owner)
    assert draft.army_id == "army-alpha"
    assert draft.component_unit_instance_ids == (LEADER, _BODYGUARD)
    assert tuple(pose.model_id for pose in draft.model_poses) == proposal.required_model_ids
    assert {pose.unit_instance_id for pose in draft.model_poses} == {LEADER, _BODYGUARD}
    assert all(pose.owner_player_id == _OWNER for pose in draft.model_poses)

    forged_projection = deepcopy(physical.models_by_id)
    nonmember = cast(JsonObject, forged_projection[proposal.required_model_ids[0]])
    nonmember["unit_instance_id"] = _ENEMY
    with pytest.raises(PlacementDraftError, match="ownership differs from request"):
        PlacementDraft.start_for_pending(
            view=battlefield_view_from_game_view(owner),
            selection=SelectionState.initial(default_preferences()),
            pending_decision=request,
            model_display_by_id=owner.model_display_by_id,
            authoritative_models_by_id=forged_projection,
            battlefield_state=owner.battlefield_state,
            support_profile=client.get_support_profile(_OWNER),
        )

    points = dict(original_points)
    leader_id = next(pose.model_id for pose in draft.model_poses if pose.unit_instance_id == LEADER)
    points[leader_id] = (8.6, 54.8)
    invalid_points = dict(points)
    invalid_points[leader_id] = (-2.0, 54.8)
    session = client.session
    assert isinstance(session, LocalGameSession)
    state = session.lifecycle.state
    assert state is not None
    battlefield_before = state.battlefield_state
    invalid = client.submit_parameterized_payload(
        request_id=request.request_id,
        payload=_ready_placement(draft, invalid_points),
        result_id="attached-prebattle-out-of-bounds",
    )
    assert invalid.status_kind == "invalid"
    assert invalid.invalid_diagnostics
    assert all(
        diagnostic.violation_code != "invalid_status" for diagnostic in invalid.invalid_diagnostics
    )
    assert state.battlefield_state == battlefield_before
    retry = _decision(client.advance_until_decision_or_terminal(), "submit_deployment_placement")
    assert retry.request_id == request.request_id
    current = _placement_draft(client, client.get_view(_OWNER))
    payload = _ready_placement(current, points)
    assert payload["proposal_request_id"] == retry.request_id
    assert payload["unit_instance_id"] == _ATTACHED
    assert payload["ruleset_descriptor_hash"] == proposal.ruleset_descriptor_hash
    rows = cast(list[JsonObject], payload["model_placements"])
    assert {cast(str, row["model_instance_id"]) for row in rows} == set(proposal.required_model_ids)
    assert {cast(str, row["unit_instance_id"]) for row in rows} == {LEADER, _BODYGUARD}
    assert all(row["army_id"] == "army-alpha" and row["player_id"] == _OWNER for row in rows)
    accepted = client.submit_parameterized_payload(
        request_id=retry.request_id,
        payload=payload,
        result_id="attached-prebattle-current-placement",
    )
    assert accepted.status_kind == "waiting_for_decision", accepted.invalid_diagnostics
    placed = state.battlefield_state
    assert placed is not None
    assert all(
        placed.model_placement_or_none(model_id) is not None
        for model_id in proposal.required_model_ids
    )
    with pytest.raises(UiClientSubmissionError):
        client.submit_parameterized_payload(
            request_id=request.request_id,
            payload=payload,
            result_id="attached-prebattle-stale",
        )
    assert state.battlefield_state == placed
    for viewer in (_OWNER, _OPPONENT):
        events = client.get_events_since(0, viewer).events
        assert any(
            event["event_type"] == "deployment_unit_placed"
            and cast(JsonObject, event["payload"])["unit_instance_id"] == _ATTACHED
            for event in events
        )


def test_attached_deployment_requires_public_army_authority() -> None:
    client, original_points = _empty_deployment_client()
    request = _attached_deployment_request(client, original_points)
    owner = client.get_view(_OWNER)
    profile = client.get_support_profile(_OWNER)
    without_muster = UiSupportProfile.from_payload(
        {**profile.payload, "mustering_support_rows": []}
    )
    assert owner.battlefield_state is not None
    state = cast(JsonObject, owner.battlefield_state)
    assert all(row["player_id"] != _OWNER for row in cast(list[JsonObject], state["placed_armies"]))
    physical = owner.battlefield_view
    assert physical is not None

    def start_with(support_profile: UiSupportProfile) -> PlacementDraft | None:
        return PlacementDraft.start_for_pending(
            view=battlefield_view_from_game_view(owner),
            selection=SelectionState.initial(default_preferences()),
            pending_decision=request,
            model_display_by_id=owner.model_display_by_id,
            authoritative_models_by_id=physical.models_by_id,
            battlefield_state=owner.battlefield_state,
            support_profile=support_profile,
        )

    with pytest.raises(PlacementDraftError, match="public army"):
        start_with(without_muster)

    opponent_profile = client.get_support_profile(_OPPONENT)
    opponent_rows = cast(list[JsonObject], opponent_profile.payload["mustering_support_rows"])
    assert all(row["player_id"] != _OWNER for row in opponent_rows)
    with pytest.raises(PlacementDraftError, match="public army"):
        start_with(opponent_profile)

    muster_rows = cast(list[JsonObject], profile.payload["mustering_support_rows"])
    owner_row = next(row for row in muster_rows if row["player_id"] == _OWNER)
    duplicated = UiSupportProfile.from_payload(
        {**profile.payload, "mustering_support_rows": [*muster_rows, deepcopy(owner_row)]}
    )
    with pytest.raises(PlacementDraftError, match="multiple public owner armies"):
        start_with(duplicated)


def _attached_scout_request(client: LocalSessionClient) -> tuple[UiDecision, UiDecision]:
    selection = _decision(client.advance_until_decision_or_terminal(), "select_prebattle_action")
    assert selection.actor_id == _OWNER
    chosen = next(
        option
        for option in selection.options
        if _object(option.payload).get("unit_instance_id") == _ATTACHED
        and _object(option.payload).get("scout_distance_inches") == 6.0
    )
    request = _decision(
        client.submit_finite(
            request_id=selection.request_id,
            selected_option_id=chosen.option_id,
            result_id="attached-prebattle-scout-source",
        ),
        "submit_scout_move",
    )
    return selection, request


def _scout_draft(client: LocalSessionClient, request: UiDecision) -> MovementDraft:
    view = client.get_view(_OWNER)
    battlefield = battlefield_view_from_game_view(view)
    proposal = request.movement_proposal
    assert proposal is not None
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_model_id(
        unit_id=proposal.unit_instance_id,
        model_id=None,
        preferences=preferences,
    )
    draft = MovementDraft.start_for_pending(
        view=battlefield,
        selection=selection,
        pending_decision=request,
        projection_state_hash=view.projection_state_hash,
    )
    assert draft is not None
    return draft


def test_attached_scout_draft_preserves_public_inventory_and_rejects_membership_drift() -> None:
    client = _scout_client(attached=True, transport=False)
    selection, request = _attached_scout_request(client)
    proposal = request.movement_proposal
    assert proposal is not None
    assert proposal.unit_instance_id == _ATTACHED
    assert proposal.component_unit_instance_ids == (LEADER, _BODYGUARD)
    assert len(proposal.required_model_ids) == 6
    assert proposal.scout_distance_inches == 6.0
    assert proposal.source_decision_request_id == selection.request_id
    assert proposal.source_decision_result_id == "attached-prebattle-scout-source"
    assert client.get_view(_OPPONENT).pending_decision == request
    draft = _scout_draft(client, request)
    assert draft.selected_unit_id == _ATTACHED
    assert tuple(path.model_id for path in draft.model_paths) == proposal.required_model_ids
    assert draft.movement_budget_inches == proposal.scout_distance_inches
    assert set(draft.selected_model_ids) == set(proposal.required_model_ids)
    assert draft.is_for(
        selection=SelectionState.initial(default_preferences()).select_model_id(
            unit_id=_ATTACHED, model_id=None, preferences=default_preferences()
        ),
        pending_decision=request,
        projection_state_hash=client.get_view(_OWNER).projection_state_hash,
    )

    owner = client.get_view(_OWNER)
    assert owner.battlefield_view is not None
    foreign_model = next(
        model_id
        for model_id, row in owner.battlefield_view.models_by_id.items()
        if cast(JsonObject, row)["unit_instance_id"] == _ENEMY
    )
    drifted = replace(
        request,
        movement_proposal=replace(
            proposal,
            required_model_ids=(*proposal.required_model_ids[:-1], foreign_model),
        ),
    )
    with pytest.raises(MovementDraftError, match=r"model|membership|component"):
        MovementDraft.start_for_pending(
            view=battlefield_view_from_game_view(owner),
            selection=SelectionState.initial(default_preferences()).select_model_id(
                unit_id=_ATTACHED, model_id=None, preferences=default_preferences()
            ),
            pending_decision=drifted,
        )

    battlefield = battlefield_view_from_game_view(owner)
    start_x, start_y = draft.model_paths[0].points[0]
    ready = draft.add_waypoint(
        view=battlefield,
        world_point=(start_x + 1.0, start_y),
    ).mark_ready(view=battlefield)
    payload = ready.payload_preview
    assert payload is not None
    malformed = deepcopy(payload)
    del malformed["witness"]
    session = client.session
    assert isinstance(session, LocalGameSession)
    state = session.lifecycle.state
    assert state is not None
    battlefield_before = state.battlefield_state
    records_before = session.decision_record_count()
    invalid = client.submit_parameterized_payload(
        request_id=request.request_id,
        payload=malformed,
        result_id="attached-prebattle-missing-witness",
    )
    assert invalid.status_kind == "invalid"
    assert [row.violation_code for row in invalid.invalid_diagnostics] == [
        "malformed_prebattle_proposal"
    ]
    assert state.battlefield_state == battlefield_before
    assert session.decision_record_count() == records_before
    assert client.get_view(_OWNER).pending_decision == request

    with pytest.raises(UiClientSubmissionError):
        client.submit_finite(
            request_id=selection.request_id,
            selected_option_id=selection.options[0].option_id,
            result_id="attached-prebattle-stale-source",
        )
    assert client.get_view(_OWNER).pending_decision == request


def test_attached_scout_headless_current_action_roster_and_battlefield_stay_in_sync() -> None:
    client = _scout_client(attached=True, transport=False)
    selection = _decision(client.advance_until_decision_or_terminal(), "select_prebattle_action")
    chosen = next(
        option
        for option in selection.options
        if _object(option.payload).get("unit_instance_id") == _ATTACHED
        and _object(option.payload).get("scout_distance_inches") == 6.0
    )
    window = _window(client, client.get_view(_OWNER))
    try:
        window.on_draw()
        current_action = next(
            region
            for region in window.hud_button_hit_regions
            if region.action_kind == "finite_option" and region.option_id == chosen.option_id
        )
        x = round((current_action.bounds[0] + current_action.bounds[2]) / 2.0)
        y = round((current_action.bounds[1] + current_action.bounds[3]) / 2.0)
        window.on_mouse_press(x, y, arcade.MOUSE_BUTTON_LEFT, 0)
        assert window.finite_state.highlighted_option is not None
        assert window.finite_state.highlighted_option.option_id == chosen.option_id
        assert window.selection_state.selected_unit_id == _ATTACHED

        window.on_draw()
        roster = next(
            region
            for region in window.hud_button_hit_regions
            if region.action_kind == "select_unit" and region.unit_id == _BODYGUARD
        )
        x = round((roster.bounds[0] + roster.bounds[2]) / 2.0)
        y = round((roster.bounds[1] + roster.bounds[3]) / 2.0)
        window.on_mouse_press(x, y, arcade.MOUSE_BUTTON_LEFT, 0)
        assert window.finite_state.highlighted_option is not None
        assert window.finite_state.highlighted_option.option_id == chosen.option_id
        assert window.selection_state.selected_unit_id == _ATTACHED

        window.on_key_press(arcade.key.ENTER, 0)
        assert window.pending_decision is not None
        assert window.pending_decision.decision_type == "submit_scout_move"
        assert window.movement_draft is not None
        assert window.movement_draft.selected_unit_id == _ATTACHED
        physical = next(
            unit for unit in window.battlefield_view.units if unit.unit_id == LEADER
        ).models[0]
        screen_x, screen_y = window.camera.world_to_screen(physical.position)
        window.on_mouse_press(round(screen_x), round(screen_y), arcade.MOUSE_BUTTON_LEFT, 0)
        assert window.selection_state.selected_unit_id == _ATTACHED
        assert window.selection_state.selected_model_id == physical.model_id
        assert window.movement_draft is not None
        assert window.movement_draft.selected_model_ids == (physical.model_id,)
    finally:
        window.close()


def test_attached_scout_window_rejects_membership_drift_without_stale_focus() -> None:
    client = _scout_client(attached=True, transport=False)
    _, request = _attached_scout_request(client)
    proposal = request.movement_proposal
    assert proposal is not None
    owner = client.get_view(_OWNER)
    assert owner.battlefield_view is not None
    foreign_model = next(
        model_id
        for model_id, row in owner.battlefield_view.models_by_id.items()
        if cast(JsonObject, row)["unit_instance_id"] == _ENEMY
    )
    drifted = replace(
        request,
        movement_proposal=replace(
            proposal,
            required_model_ids=(*proposal.required_model_ids[:-1], foreign_model),
        ),
    )
    window = _window(client, owner)
    try:
        window._sync_movement_draft()
        initial_draft = window.movement_draft
        assert initial_draft is not None
        assert initial_draft.selected_unit_id == _ATTACHED
        window._set_finite_state(replace(window.finite_state, pending_decision=drifted))
        assert window.movement_draft is None
        refreshed_selection = window.selection_state
        assert refreshed_selection.selected_unit_id is None
        assert refreshed_selection.selected_model_id is None
        assert window.finite_state.diagnostics
        assert window.finite_state.diagnostics[0].violation_code == "movement_draft_unavailable"
    finally:
        window.close()


def test_attached_scout_public_witness_is_accepted_by_core() -> None:
    """A complete current-ID Scout witness must pass the public Core decision path."""

    client = _scout_client(attached=True, transport=False)
    _, request = _attached_scout_request(client)
    proposal = request.movement_proposal
    assert proposal is not None
    view = client.get_view(_OWNER)
    battlefield = battlefield_view_from_game_view(view)
    draft = _scout_draft(client, request)
    start_x, start_y = draft.model_paths[0].points[0]
    ready = draft.add_waypoint(
        view=battlefield,
        world_point=(start_x + 1.0, start_y),
    ).mark_ready(view=battlefield)
    payload = ready.payload_preview
    assert payload is not None
    assert payload["proposal_request_id"] == request.request_id
    assert payload["unit_instance_id"] == _ATTACHED
    assert payload["scout_distance_inches"] == proposal.scout_distance_inches
    assert payload["context"] == proposal.context
    witness = cast(JsonObject, payload["witness"])
    paths = cast(list[JsonObject], witness["model_paths"])
    assert {cast(str, path["model_id"]) for path in paths} == set(proposal.required_model_ids)
    assert all(len(cast(list[JsonObject], path["poses"])) == 2 for path in paths)
    accepted = client.submit_parameterized_payload(
        request_id=request.request_id,
        payload=payload,
        result_id="attached-prebattle-scout-current-witness",
    )
    assert accepted.status_kind == "waiting_for_decision", accepted.invalid_diagnostics
    completion = next(
        event
        for event in client.get_events_since(0, _OWNER).events
        if event["event_type"] == "prebattle_scout_move_completed"
    )
    assert completion in client.get_events_since(0, _OPPONENT).events
    assert cast(JsonObject, completion["payload"])["unit_instance_id"] == _ATTACHED
