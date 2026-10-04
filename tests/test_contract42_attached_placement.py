# pyright: reportPrivateUsage=false
"""Current public component inventories drive grouped attached placement intent."""

from __future__ import annotations

import copy
from dataclasses import replace
from typing import cast

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.engine.lifecycle import GameLifecycle
from warhammer40k_core.engine.movement_proposals import (
    PlacementProposalPayload,
    PlacementProposalPayloadPayload,
)
from warhammer40k_core.engine.phase import BattlePhase
from warhammer40k_core.engine.reserve_arrival_requirements import (
    reposition_destruction_policy,
)
from warhammer40k_core.engine.reserves import ReserveKind, ReserveState

from tests.support.contract42_charge_fixture import SOURCE
from tests.test_contract42_charge_sources import (
    ATTACHED,
    LEADER,
    _attached_charge_client,
)
from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientSubmissionError,
    UiDecision,
    UiGameView,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow
from warhammer40k_arcade_ui.render.core_projection import battlefield_view_from_game_view
from warhammer40k_arcade_ui.state.placement_draft import PlacementDraft, PlacementDraftError
from warhammer40k_arcade_ui.state.selection import SelectionState

pytestmark = pytest.mark.integration

_OWNER = "player-a"
_OPPONENT = "player-b"
_VALID_POINTS = tuple((15.0 + index * 1.55, 3.0) for index in range(6))


def _attached_reserve_client() -> LocalSessionClient:
    """Move an existing real attached Core scenario into a declared reserve state."""

    baseline = _attached_charge_client(natural_reroll=False)
    session = baseline.session
    assert isinstance(session, LocalGameSession)
    lifecycle = session.lifecycle
    state = lifecycle.state
    assert state is not None
    battlefield = state.battlefield_state
    assert battlefield is not None
    for component_id in (SOURCE, LEADER):
        battlefield = battlefield.without_unit_placement(component_id)
    state.replace_battlefield_state(battlefield)
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.MOVEMENT)
    state.battle_round = 2
    assert state.mission_setup is not None
    reserve = ReserveState.declared_before_battle(
        player_id=_OWNER,
        unit_instance_id=ATTACHED,
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
            "unit_instance_id": ATTACHED,
            "reserve_state": reserve.to_payload(),
        },
    )
    return LocalSessionClient(
        session=LocalGameSession(lifecycle=GameLifecycle.from_payload(lifecycle.to_payload()))
    )


def _reach_placement(
    client: LocalSessionClient,
    *,
    selection: UiDecision | None = None,
    result_prefix: str = "attached-reserve",
) -> UiDecision:
    request = selection
    if request is None:
        status = client.advance_until_decision_or_terminal()
        request = status.decision
    assert request is not None
    assert request.decision_type == "select_movement_unit"
    assert ATTACHED in {option.option_id for option in request.options}
    selected = client.submit_finite(
        request_id=request.request_id,
        selected_option_id=ATTACHED,
        result_id=f"{result_prefix}-select",
    )
    action = selected.decision
    assert action is not None
    assert action.decision_type == "select_movement_action"
    assert "ingress" in {option.option_id for option in action.options}
    requested = client.submit_finite(
        request_id=action.request_id,
        selected_option_id="ingress",
        result_id=f"{result_prefix}-ingress",
    )
    placement = requested.decision
    assert placement is not None
    assert placement.decision_type == "submit_placement_proposal"
    assert placement.actor_id == _OWNER
    return placement


def _draft(
    client: LocalSessionClient, view: UiGameView, decision: UiDecision | None = None
) -> PlacementDraft:
    assert view.battlefield_view is not None
    draft = PlacementDraft.start_for_pending(
        view=battlefield_view_from_game_view(view),
        selection=SelectionState.initial(default_preferences()),
        pending_decision=decision or view.pending_decision,
        model_display_by_id=view.model_display_by_id,
        authoritative_models_by_id=view.battlefield_view.models_by_id,
        battlefield_state=view.battlefield_state,
        support_profile=client.get_support_profile(view.viewer_player_id),
        projection_state_hash=view.projection_state_hash,
    )
    assert draft is not None
    return draft


def _ready(draft: PlacementDraft, points: tuple[tuple[float, float], ...]) -> PlacementDraft:
    assert len(points) == draft.total_model_count
    for point in points:
        draft = draft.place_current_model(point)
    ready = draft.mark_ready()
    assert ready.payload_preview is not None
    return ready


def test_attached_reserve_headless_editor_grouped_retry_and_current_ids() -> None:
    client = _attached_reserve_client()
    request = _reach_placement(client)
    proposal = request.placement_proposal
    assert proposal is not None
    assert proposal.unit_instance_id == ATTACHED
    assert proposal.context["component_unit_instance_ids"] == [LEADER, SOURCE]
    expected_models = cast(list[str], proposal.context["model_instance_ids"])
    assert len(expected_models) == 6
    owner = client.get_view(_OWNER)
    opponent = client.get_view(_OPPONENT)
    assert owner.pending_decision is not None
    assert opponent.pending_decision is not None
    assert owner.pending_decision.request_id == opponent.pending_decision.request_id
    assert owner.battlefield_view is not None
    assert all(model_id in owner.battlefield_view.models_by_id for model_id in expected_models)

    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=battlefield_view_from_game_view(owner),
        preferences=default_preferences(),
        pending_decision=owner.pending_decision,
        initial_game_view=owner,
        viewer_player_id=_OWNER,
    )
    try:
        window._sync_placement_draft()  # pyright: ignore[reportPrivateUsage]
        assert window.placement_draft is not None
        assert window.placement_draft.selected_unit_id == ATTACHED
        assert window.placement_draft.total_model_count == 6
    finally:
        window.close()

    draft = _draft(client, owner)
    assert draft.army_id == "army-alpha"
    assert draft.component_unit_instance_ids == (LEADER, SOURCE)
    assert [pose.model_id for pose in draft.model_poses] == expected_models
    assert {pose.unit_instance_id for pose in draft.model_poses} == {LEADER, SOURCE}
    assert all(pose.owner_player_id == _OWNER for pose in draft.model_poses)
    bad = _ready(draft, ((-2.0, 3.0), *_VALID_POINTS[1:]))
    bad_payload = bad.payload_preview
    assert bad_payload is not None
    assert "attempted_rules_unit_placement" in bad_payload
    assert "attempted_placement" not in bad_payload
    grouped = cast(JsonObject, bad_payload["attempted_rules_unit_placement"])
    assert grouped["rules_unit_instance_id"] == ATTACHED
    components = cast(list[JsonObject], grouped["component_unit_placements"])
    assert [row["unit_instance_id"] for row in components] == [LEADER, SOURCE]
    assert [len(cast(list[JsonObject], row["model_placements"])) for row in components] == [1, 5]
    assert all(row["army_id"] == "army-alpha" and row["player_id"] == _OWNER for row in components)
    assert PlacementProposalPayload.from_payload(cast(PlacementProposalPayloadPayload, bad_payload))

    before = client.session.decision_record_count()
    invalid = client.submit_parameterized_payload(
        request_id=request.request_id,
        payload=bad_payload,
        result_id="attached-reserve-outside-bounds",
    )
    assert invalid.status_kind == "invalid"
    assert invalid.invalid_diagnostics
    assert client.session.decision_record_count() == before + 1
    retry_selection = client.advance_until_decision_or_terminal().decision
    assert retry_selection is not None
    assert retry_selection.decision_type == "select_movement_unit"
    assert retry_selection.actor_id == _OWNER
    assert retry_selection.request_id != request.request_id
    assert ATTACHED in {option.option_id for option in retry_selection.options}
    for viewer in (_OWNER, _OPPONENT):
        projected = client.get_view(viewer).pending_decision
        assert projected is not None
        assert projected.request_id == retry_selection.request_id
    assert (
        PlacementDraft.start_for_pending(
            view=battlefield_view_from_game_view(client.get_view(_OWNER)),
            selection=SelectionState.initial(default_preferences()),
            pending_decision=retry_selection,
        )
        is None
    )
    with pytest.raises(UiClientSubmissionError):
        client.submit_parameterized_payload(
            request_id=request.request_id,
            payload=bad_payload,
            result_id="attached-reserve-stale",
        )
    assert client.session.decision_record_count() == before + 1
    retry = _reach_placement(
        client,
        selection=retry_selection,
        result_prefix="attached-reserve-retry",
    )
    assert retry.request_id != request.request_id
    assert retry.placement_proposal is not None
    assert retry.placement_proposal.context["component_unit_instance_ids"] == [LEADER, SOURCE]
    assert retry.placement_proposal.context["model_instance_ids"] == expected_models
    assert client.session.decision_record_count() == before + 3
    accepted = _ready(_draft(client, client.get_view(_OWNER)), _VALID_POINTS)
    payload = accepted.payload_preview
    assert payload is not None
    result = client.submit_parameterized_payload(
        request_id=retry.request_id,
        payload=payload,
        result_id="attached-reserve-accepted",
    )
    assert result.status_kind != "invalid", result.invalid_diagnostics
    assert client.session.decision_record_count() == before + 4
    for viewer in (_OWNER, _OPPONENT):
        view = client.get_view(viewer)
        assert view.battlefield_view is not None
        assert all(
            cast(JsonObject, view.battlefield_view.models_by_id[model_id])["state"] == "placed"
            for model_id in expected_models
        )
        events = client.get_events_since(0, viewer).events
        assert any(
            event["event_type"] == "reinforcement_unit_arrived"
            and cast(JsonObject, event["payload"])["unit_instance_id"] == ATTACHED
            for event in events
        )


def test_grouped_placement_rejects_component_or_owner_drift_and_shares_disembark_shape() -> None:
    client = _attached_reserve_client()
    request = _reach_placement(client)
    view = client.get_view(_OWNER)
    assert view.battlefield_view is not None
    assert view.pending_decision is not None
    projected = copy.deepcopy(view.battlefield_view.models_by_id)
    # Select a requested model; unrelated physical models are outside this strict check.
    assert request.placement_proposal is not None
    requested_id = cast(list[str], request.placement_proposal.context["model_instance_ids"])[0]
    row = cast(JsonObject, projected[requested_id])
    row["owner_player_id"] = _OPPONENT
    with pytest.raises(PlacementDraftError, match="ownership differs from request"):
        PlacementDraft.start_for_pending(
            view=battlefield_view_from_game_view(view),
            selection=SelectionState.initial(default_preferences()),
            pending_decision=view.pending_decision,
            model_display_by_id=view.model_display_by_id,
            authoritative_models_by_id=projected,
            battlefield_state=view.battlefield_state,
            support_profile=client.get_support_profile(_OWNER),
        )

    projected = copy.deepcopy(view.battlefield_view.models_by_id)
    row = cast(JsonObject, projected[requested_id])
    row["unit_instance_id"] = "army-alpha:next"
    with pytest.raises(PlacementDraftError, match="ownership differs from request"):
        PlacementDraft.start_for_pending(
            view=battlefield_view_from_game_view(view),
            selection=SelectionState.initial(default_preferences()),
            pending_decision=view.pending_decision,
            model_display_by_id=view.model_display_by_id,
            authoritative_models_by_id=projected,
            battlefield_state=view.battlefield_state,
            support_profile=client.get_support_profile(_OWNER),
        )

    proposal = view.pending_decision.placement_proposal
    assert proposal is not None
    missing_component = replace(
        view.pending_decision,
        placement_proposal=replace(
            proposal,
            context={**proposal.context, "component_unit_instance_ids": [SOURCE]},
        ),
    )
    with pytest.raises(PlacementDraftError, match="ownership differs from request"):
        _draft(client, view, decision=missing_component)

    foreign_model_id = next(
        model_id
        for model_id, value in view.battlefield_view.models_by_id.items()
        if cast(JsonObject, value)["unit_instance_id"] == "army-alpha:next"
    )
    wrong_model = replace(
        view.pending_decision,
        placement_proposal=replace(
            proposal,
            context={
                **proposal.context,
                "model_instance_ids": [
                    *cast(list[str], proposal.context["model_instance_ids"]),
                    foreign_model_id,
                ],
            },
        ),
    )
    with pytest.raises(PlacementDraftError, match="ownership differs from request"):
        _draft(client, view, decision=wrong_model)

    draft = _draft(client, view)
    disembark = replace(
        draft,
        proposal_kind="disembark_placement",
        placement_kind="disembark",
        context={
            **(draft.context or {}),
            "transport_unit_instance_id": "army-alpha:transport",
            "disembark_mode": "tactical_disembark",
            "transport_movement_status": "not_moved",
        },
    )
    ready = _ready(disembark, _VALID_POINTS)
    payload = ready.payload_preview
    assert payload is not None
    assert "attempted_rules_unit_placement" in payload
    assert "attempted_placement" not in payload
    assert payload["transport_unit_instance_id"] == "army-alpha:transport"
    assert payload["disembark_mode"] == "tactical_disembark"
    assert PlacementProposalPayload.from_payload(cast(PlacementProposalPayloadPayload, payload))


def test_grouped_editor_reports_missing_public_army_authority() -> None:
    client = _attached_reserve_client()
    _reach_placement(client)
    view = client.get_view(_OWNER)
    state = cast(JsonObject, view.battlefield_state)
    placed = cast(list[JsonObject], state["placed_armies"])
    no_owner_army = replace(
        view,
        battlefield_state={
            **state,
            "placed_armies": [row for row in placed if row["player_id"] != _OWNER],
        },
    )
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=battlefield_view_from_game_view(view),
        preferences=default_preferences(),
        pending_decision=view.pending_decision,
        initial_game_view=no_owner_army,
        viewer_player_id=_OWNER,
    )
    try:
        window._sync_placement_draft()  # pyright: ignore[reportPrivateUsage]
        assert window.placement_draft is None
        assert window.finite_state.status_kind == "invalid"
        assert window.finite_state.diagnostics[0].violation_code == "placement_draft_unavailable"
        assert "one public army" in window.finite_state.status_message
    finally:
        window.close()
