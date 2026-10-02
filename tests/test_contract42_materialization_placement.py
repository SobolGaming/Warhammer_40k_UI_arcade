# pyright: reportPrivateUsage=false
"""Request-created materialization models remain draftable through the public UI path."""

from __future__ import annotations

import copy
import gzip
import json
import math
from dataclasses import replace
from pathlib import Path
from typing import cast

import arcade
import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.engine import lifecycle as lifecycle_module
from warhammer40k_core.engine.battle_round_flow import BattleRoundFlow
from warhammer40k_core.engine.faction_content.runtime import build_runtime_content_bundle_for_armies
from warhammer40k_core.engine.game_state import GameConfig, GameConfigPayload
from warhammer40k_core.engine.lifecycle import GameLifecycle, GameLifecyclePayload
from warhammer40k_core.engine.movement_proposals import (
    PlacementProposalPayload,
    PlacementProposalPayloadPayload,
)
from warhammer40k_core.engine.phases.fight import FightPhaseHandler
from warhammer40k_core.engine.phases.movement import MovementPhaseHandler
from warhammer40k_core.engine.phases.shooting import ShootingPhaseHandler

from tests.support.core_contract_examples import required_core_example_path
from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.compatibility import (
    DECISION_REQUEST_SCHEMA_VERSION,
    require_supported_core_contract,
)
from warhammer40k_arcade_ui.core_client.fake_client import FakeCoreClient
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    JsonValue,
    UiClientProtocolError,
    UiClientStatus,
    UiEventDelta,
    UiGameView,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow
from warhammer40k_arcade_ui.render.core_projection import battlefield_view_from_game_view
from warhammer40k_arcade_ui.state.finite_decision import FiniteDecisionUiState
from warhammer40k_arcade_ui.state.placement_draft import PlacementDraft, PlacementDraftError
from warhammer40k_arcade_ui.state.placement_submission import (
    prepare_placement_submission,
    submit_placement_draft,
)
from warhammer40k_arcade_ui.state.selection import SelectionState

_DECISION_TYPE = "submit_catalog_model_materialization_placement"
_REQUEST_ID = "materialization-request-001"
_OWNER = "player-a"
_OPPONENT = "player-b"
_CORE_SHA = "6e86f44b87c4559a9297596d5d18dc4247b8cbc3"


def test_materialization_editor_opens_edits_and_submits_request_created_models() -> None:
    view = _owner_view()
    assert view.pending_decision is not None
    assert view.pending_decision.placement_proposal is not None
    assert view.battlefield_view is not None
    proposal = view.pending_decision.placement_proposal
    physical = view.battlefield_view.models_by_id
    assert all(model_id not in physical for model_id in proposal.required_model_ids)
    assert all(model_id not in view.model_display_by_id for model_id in proposal.required_model_ids)

    window = _window(view)
    try:
        window._sync_placement_draft()  # pyright: ignore[reportPrivateUsage]
        draft = window.placement_draft
        assert draft is not None
        assert draft.selected_unit_id == proposal.unit_instance_id
        assert draft.army_id == proposal.army_id
        assert draft.placed_model_count == 0
        assert [pose.model_id for pose in draft.model_poses] == list(proposal.required_model_ids)
        expected_base_radius = 32.0 / 25.4 / 2.0
        assert all(
            math.isclose(pose.base_radius, expected_base_radius) for pose in draft.model_poses
        )

        for point in ((20.0, 20.0), (22.0, 20.0)):
            x, y = window.camera.world_to_screen(point)
            window.on_mouse_press(round(x), round(y), arcade.MOUSE_BUTTON_LEFT, 0)
        edited = window.placement_draft
        assert edited is not None
        assert edited.placed_model_count == 2
        ready = edited.mark_ready()
        assert ready.is_ready
        payload = ready.payload_preview
        assert payload is not None
        assert payload["proposal_request_id"] == view.pending_decision.request_id
        assert payload["proposal_kind"] == "model_materialization_placement"
        assert payload["unit_instance_id"] == proposal.unit_instance_id
        assert payload["placement_kind"] == "split_unit"
        placement = cast(JsonObject, payload["attempted_placement"])
        assert placement["army_id"] == proposal.army_id
        assert placement["player_id"] == _OWNER
        assert placement["unit_instance_id"] == proposal.unit_instance_id
        rows = cast(list[JsonObject], placement["model_placements"])
        assert [row["model_instance_id"] for row in rows] == list(proposal.required_model_ids)
        assert all(
            row["army_id"] == proposal.army_id
            and row["player_id"] == _OWNER
            and row["unit_instance_id"] == proposal.unit_instance_id
            and "split_origin" not in row
            for row in rows
        )
        # Core's public payload decoder accepts the exact placement shape.
        assert PlacementProposalPayload.from_payload(cast(PlacementProposalPayloadPayload, payload))

        accepted = UiClientStatus(
            stage="battle",
            status_kind="advanced",
            decision=None,
            message="Placement accepted.",
            payload={"phase_body_status": "placement_complete"},
        )
        client = _fake_client(
            status=accepted, view=replace(view, pending_decision=None, pending_proposal=None)
        )
        result = submit_placement_draft(
            state=FiniteDecisionUiState(pending_decision=view.pending_decision),
            placement_draft=ready,
            client=client,
            viewer_player_id=_OWNER,
            projection_state_hash=view.projection_state_hash,
        )
        assert result.finite_state.status_message == "Placement accepted."
        assert result.clear_placement_draft
        assert result.viewer_player_id == _OWNER
        assert len(client.parameterized_submissions) == 1
        assert client.parameterized_submissions[0].request_id == _REQUEST_ID
        assert client.parameterized_submissions[0].payload == payload
    finally:
        window.close()


def test_rectangular_request_created_base_opens_headless_editor_with_advisory_radius() -> None:
    raw = _owner_view_payload()
    for container in (
        cast(JsonObject, cast(JsonObject, raw["pending_decision"])["payload"]),
        cast(JsonObject, raw["pending_proposal"]),
    ):
        models = cast(list[JsonObject], container["models"])
        models[0]["base_size"] = {
            "kind": "rectangular",
            "diameter_mm": None,
            "length_mm": 50.0,
            "width_mm": 40.0,
        }
    view = UiGameView.from_payload(raw)
    assert view.pending_decision is not None
    proposal = view.pending_decision.placement_proposal
    assert proposal is not None
    window = _window(view)
    try:
        window._sync_placement_draft()  # pyright: ignore[reportPrivateUsage]
        draft = window.placement_draft
        assert draft is not None
        assert tuple(pose.model_id for pose in draft.model_poses) == proposal.required_model_ids
        assert math.isclose(draft.model_poses[0].base_radius, math.hypot(25.0, 20.0) / 25.4)
        assert math.isclose(draft.model_poses[1].base_radius, 32.0 / 25.4 / 2.0)
        for point in ((20.0, 20.0), (22.0, 20.0)):
            x, y = window.camera.world_to_screen(point)
            window.on_mouse_press(round(x), round(y), arcade.MOUSE_BUTTON_LEFT, 0)
        edited = window.placement_draft
        assert edited is not None
        payload = edited.mark_ready().payload_preview
        assert payload is not None
        attempted = cast(JsonObject, payload["attempted_placement"])
        rows = cast(list[JsonObject], attempted["model_placements"])
        assert [row["model_instance_id"] for row in rows] == list(proposal.required_model_ids)
        assert all(row["unit_instance_id"] == proposal.unit_instance_id for row in rows)
        assert all(row["player_id"] == _OWNER for row in rows)
        assert PlacementProposalPayload.from_payload(cast(PlacementProposalPayloadPayload, payload))
    finally:
        window.close()


def test_materialization_rejects_missing_or_ambiguous_request_model_authority() -> None:
    raw = _owner_view_payload()
    decision = cast(JsonObject, raw["pending_decision"])
    request = cast(JsonObject, decision["payload"])
    model_ids = cast(list[str], request["model_instance_ids"])
    request["model_instance_ids"] = list(reversed(model_ids))
    cast(JsonObject, raw["pending_proposal"])["model_instance_ids"] = list(reversed(model_ids))
    with pytest.raises(UiClientProtocolError, match="match the emitted model_instance_ids"):
        UiGameView.from_payload(raw)

    raw = _owner_view_payload()
    request = cast(JsonObject, cast(JsonObject, raw["pending_decision"])["payload"])
    cast(list[JsonObject], request["models"])[0].pop("base_size")
    cast(list[JsonObject], cast(JsonObject, raw["pending_proposal"])["models"])[0].pop("base_size")
    with pytest.raises(UiClientProtocolError, match="base_size is required"):
        UiGameView.from_payload(raw)

    view = _owner_view()
    assert view.pending_decision is not None
    assert view.battlefield_view is not None
    requested_id = view.pending_decision.placement_proposal.required_model_ids[0]  # type: ignore[union-attr]
    physical = dict(view.battlefield_view.models_by_id)
    physical[requested_id] = next(iter(physical.values()))
    with pytest.raises(PlacementDraftError, match="already exists in the physical projection"):
        PlacementDraft.start_for_pending(
            view=battlefield_view_from_game_view(view),
            selection=SelectionState.initial(default_preferences()),
            pending_decision=view.pending_decision,
            model_display_by_id=view.model_display_by_id,
            authoritative_models_by_id=physical,
        )


def test_materialization_stale_and_invalid_submission_preserve_current_request() -> None:
    view = _owner_view()
    assert view.pending_decision is not None
    assert view.battlefield_view is not None
    draft = PlacementDraft.start_for_pending(
        view=battlefield_view_from_game_view(view),
        selection=SelectionState.initial(default_preferences()),
        pending_decision=view.pending_decision,
        model_display_by_id=view.model_display_by_id,
        authoritative_models_by_id=view.battlefield_view.models_by_id,
        projection_state_hash=view.projection_state_hash,
    )
    assert draft is not None
    ready = draft.place_current_model((20.0, 20.0)).place_current_model((22.0, 20.0)).mark_ready()
    assert ready.is_ready
    stale_view = _owner_view(request_id="materialization-request-002")
    invalid, submission, next_index = prepare_placement_submission(
        placement_draft=ready,
        pending_decision=stale_view.pending_decision,
        next_result_index=5,
        projection_state_hash=view.projection_state_hash,
    )
    assert invalid is not None
    assert invalid.invalid_diagnostics[0].violation_code == "stale_request_id"
    assert submission is None
    assert next_index == 5

    invalid, submission, next_index = prepare_placement_submission(
        placement_draft=ready,
        pending_decision=view.pending_decision,
        next_result_index=5,
        projection_state_hash="new-projection-state-hash",
    )
    assert invalid is not None
    assert invalid.invalid_diagnostics[0].violation_code == "stale_projection_state_hash"
    assert submission is None
    assert next_index == 5

    status = UiClientStatus.invalid(
        stage="battle",
        violation_code="model_materialization_placement_invalid",
        message="Placement overlaps an existing model.",
        field="attempted_placement",
        payload={
            "invalid_reason": "model_materialization_placement_invalid",
            "field": "attempted_placement",
        },
        decision=view.pending_decision,
    )
    client = _fake_client(status=status, view=view)
    result = submit_placement_draft(
        state=FiniteDecisionUiState(pending_decision=view.pending_decision),
        placement_draft=ready,
        client=client,
        viewer_player_id=_OWNER,
        projection_state_hash=view.projection_state_hash,
    )
    assert result.finite_state.status_kind == "invalid"
    assert result.finite_state.pending_decision == view.pending_decision
    assert (
        result.finite_state.diagnostics[0].violation_code
        == "model_materialization_placement_invalid"
    )
    assert client.advance_call_count == 0


def test_materialization_draft_is_cleared_when_viewer_changes() -> None:
    owner = _owner_view()
    assert owner.pending_decision is not None
    opponent = replace(
        owner,
        viewer_player_id=_OPPONENT,
        pending_decision=None,
        pending_proposal=None,
        model_display_by_id={},
    )
    window = _window(owner)
    try:
        window._sync_placement_draft()  # pyright: ignore[reportPrivateUsage]
        initial_draft = window.placement_draft
        assert initial_draft is not None
        window._apply_refreshed_game_view(  # pyright: ignore[reportPrivateUsage]
            view=opponent,
            state=FiniteDecisionUiState(),
        )
        window._set_finite_state(FiniteDecisionUiState())  # pyright: ignore[reportPrivateUsage]
        assert window.placement_draft is None
        assert window.selection_state.selected_model_id is None
        window._apply_refreshed_game_view(  # pyright: ignore[reportPrivateUsage]
            view=owner,
            state=FiniteDecisionUiState(pending_decision=owner.pending_decision),
        )
        window._set_finite_state(  # pyright: ignore[reportPrivateUsage]
            FiniteDecisionUiState(pending_decision=owner.pending_decision)
        )
        assert window.placement_draft is not None
    finally:
        window.close()


@pytest.mark.integration
def test_real_core_materialization_accepts_drafted_models_after_invalid_retry() -> None:
    client, owner, opponent = _real_materialization_client()
    status = client.advance_until_decision_or_terminal()
    assert status.status_kind == "waiting_for_decision"
    assert status.decision is not None
    assert status.decision.decision_type == _DECISION_TYPE
    assert status.decision.actor_id == owner
    owner_view = client.get_view(owner)
    opponent_view = client.get_view(opponent)
    assert owner_view.pending_decision is not None
    assert owner_view.battlefield_view is not None
    assert opponent_view.battlefield_view is not None
    proposal = owner_view.pending_decision.placement_proposal
    assert proposal is not None
    assert len(proposal.required_model_ids) == 2
    assert proposal.unit_instance_id not in {
        unit.unit_id for unit in battlefield_view_from_game_view(owner_view).units
    }
    assert all(
        model_id not in owner_view.battlefield_view.models_by_id
        and model_id not in opponent_view.battlefield_view.models_by_id
        for model_id in proposal.required_model_ids
    )
    window = _window(owner_view)
    try:
        window._sync_placement_draft()  # pyright: ignore[reportPrivateUsage]
        opened = window.placement_draft
        assert opened is not None
        assert tuple(pose.model_id for pose in opened.model_poses) == proposal.required_model_ids
    finally:
        window.close()
    draft = PlacementDraft.start_for_pending(
        view=battlefield_view_from_game_view(owner_view),
        selection=SelectionState.initial(default_preferences()),
        pending_decision=owner_view.pending_decision,
        model_display_by_id=owner_view.model_display_by_id,
        authoritative_models_by_id=owner_view.battlefield_view.models_by_id,
        projection_state_hash=owner_view.projection_state_hash,
    )
    assert draft is not None
    ready = draft.place_current_model((10.0, 10.0)).place_current_model((11.2, 10.0)).mark_ready()
    assert ready.payload_preview is not None
    before_records = client.session.decision_record_count()
    before_hash = owner_view.projection_state_hash
    stale_payload = {**ready.payload_preview, "proposal_request_id": "stale-request"}
    stale = client.submit_parameterized_payload(
        request_id=proposal.request_id,
        payload=stale_payload,
        result_id="materialization-stale",
    )
    assert stale.status_kind == "invalid"
    assert stale.invalid_diagnostics
    assert client.session.decision_record_count() == before_records
    assert client.get_view(owner).projection_state_hash == before_hash
    assert client.get_view(owner).pending_decision == owner_view.pending_decision

    outside_payload = copy.deepcopy(ready.payload_preview)
    outside_placement = cast(JsonObject, outside_payload["attempted_placement"])
    outside_models = cast(list[JsonObject], outside_placement["model_placements"])
    outside_pose = cast(JsonObject, outside_models[0]["pose"])
    cast(JsonObject, outside_pose["position"])["x"] = -1.0
    outside = client.submit_parameterized_payload(
        request_id=proposal.request_id,
        payload=outside_payload,
        result_id="materialization-outside-bounds",
    )
    assert outside.status_kind == "invalid"
    assert outside.invalid_diagnostics
    assert client.session.decision_record_count() == before_records
    assert client.get_view(owner).projection_state_hash == before_hash

    accepted = client.submit_parameterized_payload(
        request_id=proposal.request_id,
        payload=ready.payload_preview,
        result_id="materialization-accepted",
    )
    assert accepted.status_kind != "invalid", accepted
    assert client.session.decision_record_count() == before_records + 1
    after_owner = client.get_view(owner)
    after_opponent = client.get_view(opponent)
    assert after_owner.battlefield_view is not None
    assert after_opponent.battlefield_view is not None
    assert all(
        model_id in after_owner.battlefield_view.models_by_id
        and model_id in after_opponent.battlefield_view.models_by_id
        for model_id in proposal.required_model_ids
    )
    for viewer in (owner, opponent):
        events = client.get_events_since(0, viewer).events
        assert any(event["event_type"] == "catalog_models_materialized" for event in events)


def _window(view: UiGameView) -> ArcadeWarhammerWindow:
    return ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=battlefield_view_from_game_view(view),
        preferences=default_preferences(),
        pending_decision=view.pending_decision,
        initial_game_view=view,
        viewer_player_id=view.viewer_player_id,
    )


def _fake_client(*, status: UiClientStatus, view: UiGameView) -> FakeCoreClient:
    return FakeCoreClient(
        status=status,
        view=view,
        event_delta=UiEventDelta(
            viewer_player_id=_OWNER,
            cursor=0,
            next_cursor=0,
            events=(),
        ),
    )


def _owner_view(*, request_id: str = _REQUEST_ID) -> UiGameView:
    return UiGameView.from_payload(_owner_view_payload(request_id=request_id))


def _owner_view_payload(*, request_id: str = _REQUEST_ID) -> JsonObject:
    projection_path = required_core_example_path("projections", "post_deployment_view.json")
    raw = cast(JsonObject, json.loads(projection_path.read_text(encoding="utf-8")))
    physical = cast(
        JsonObject,
        cast(JsonObject, cast(JsonObject, raw["battlefield_view"])["authoritative"])[
            "models_by_id"
        ],
    )
    physical_models = [cast(JsonObject, value) for value in physical.values()]
    source_unit_id = cast(
        str,
        next(
            model["unit_instance_id"]
            for model in physical_models
            if model["owner_player_id"] == _OWNER
        ),
    )
    model_ids = [f"{source_unit_id}:materialized:model-{index}" for index in (1, 2)]
    source_model = _core_model_payload()
    models: list[JsonValue] = []
    for model_id in model_ids:
        model = copy.deepcopy(source_model)
        model["model_instance_id"] = model_id
        models.append(model)
    interaction_path = required_core_example_path("decisions", "interaction-conformance.json")
    cases = cast(JsonObject, json.loads(interaction_path.read_text(encoding="utf-8")))["cases"]
    assert type(cases) is list
    case = next(
        cast(JsonObject, value)
        for value in cases
        if cast(JsonObject, value)["case_id"] == "parameterized:model_materialization_placement"
    )
    canonical = cast(JsonObject, case["request"])
    request_payload: JsonObject = {
        "submission_kind": _DECISION_TYPE,
        "proposal_kind": "model_materialization_placement",
        "placement_kind": "split_unit",
        "attack_sequence_id": "attack-sequence-001",
        "source_phase": "shooting",
        "action_phase": "shooting",
        "parent_battle_phase": "shooting",
        "roll_event_id": "roll-event-001",
        "catalog_record_id": "catalog-record-001",
        "clause_id": "clause-001",
        "source_rule_id": "source-rule-001",
        "materialization_descriptor_id": "descriptor-001",
        "source_unit_instance_id": source_unit_id,
        "army_id": "army-alpha",
        "player_id": _OWNER,
        "models": models,
        "model_instance_ids": cast(list[JsonValue], model_ids),
    }
    raw["pending_decision"] = {
        "schema_version": DECISION_REQUEST_SCHEMA_VERSION,
        "request_id": request_id,
        "decision_type": _DECISION_TYPE,
        "actor_id": _OWNER,
        "payload": request_payload,
        "options": copy.deepcopy(canonical["options"]),
        "is_parameterized": True,
        "interaction": copy.deepcopy(canonical["interaction"]),
    }
    raw["pending_proposal"] = {
        **copy.deepcopy(request_payload),
        "request_id": request_id,
        "decision_type": _DECISION_TYPE,
        "actor_id": _OWNER,
    }
    return raw


def _core_model_payload() -> JsonObject:
    persistence_path = required_core_example_path("persistence", "session-persistence.json")
    payload = json.loads(persistence_path.read_text(encoding="utf-8"))
    stack: list[object] = [payload]
    while stack:
        value = stack.pop()
        if type(value) is dict:
            row = cast(JsonObject, value)
            if {"model_instance_id", "keyword_assignment", "base_size"} <= row.keys():
                return row
            stack.extend(row.values())
        elif type(value) is list:
            stack.extend(cast(list[object], value))
    raise AssertionError("Core persistence example has no complete model payload.")


def _real_materialization_client() -> tuple[LocalSessionClient, str, str]:
    require_supported_core_contract()
    fixture_path = Path(__file__).parent / "fixtures/contract42_materialization_checkpoint.json.gz"
    fixture = cast(JsonObject, json.loads(gzip.decompress(fixture_path.read_bytes())))
    assert fixture["core_sha"] == _CORE_SHA
    lifecycle = GameLifecycle.from_payload(cast(GameLifecyclePayload, fixture["lifecycle"]))
    config = GameConfig.from_payload(cast(GameConfigPayload, fixture["config"]))
    state = lifecycle.state
    assert state is not None
    # The committed checkpoint is a Core integration scenario, not a roster-start save.
    # Recreate the same runtime bundle and phase handlers that Core's fixture uses before
    # exercising its public LocalGameSession / LocalSessionClient submission methods.
    bundle = build_runtime_content_bundle_for_armies(
        config=config, armies=tuple(state.army_definitions)
    )
    lifecycle._config = config
    lifecycle._runtime_content_bundle = bundle
    lifecycle._runtime_content_activation_input_hash = (
        lifecycle_module._runtime_content_activation_input_hash(
            config=config, armies=tuple(state.army_definitions)
        )
    )
    lifecycle._movement_phase_handler = MovementPhaseHandler(
        ruleset_descriptor=config.ruleset_descriptor,
        army_catalog=config.army_catalog,
    )
    lifecycle._shooting_phase_handler = ShootingPhaseHandler(
        ruleset_descriptor=config.ruleset_descriptor,
        army_catalog=config.army_catalog,
        attack_sequence_completed_hooks=bundle.attack_sequence_completed_hook_registry,
        ability_indexes_by_player_id=bundle.ability_indexes_by_player_id,
        runtime_modifier_registry=bundle.runtime_modifier_registry,
    )
    lifecycle._fight_phase_handler = FightPhaseHandler(
        ruleset_descriptor=config.ruleset_descriptor,
        army_catalog=config.army_catalog,
        attack_sequence_completed_hooks=bundle.attack_sequence_completed_hook_registry,
        runtime_modifier_registry=bundle.runtime_modifier_registry,
    )
    lifecycle._battle_round_flow = BattleRoundFlow(
        phase_handlers=lifecycle._phase_handlers(),
        runtime_modifier_registry=bundle.runtime_modifier_registry,
        runtime_event_index=bundle.event_index,
        ruleset_descriptor=config.ruleset_descriptor,
        army_catalog=config.army_catalog,
    )
    return (
        LocalSessionClient(session=LocalGameSession(lifecycle=lifecycle)),
        cast(str, fixture["owner"]),
        cast(str, fixture["opponent"]),
    )
