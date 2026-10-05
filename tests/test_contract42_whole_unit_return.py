# pyright: reportPrivateUsage=false
"""Whole-unit return drafts use exact current physical model membership."""

from __future__ import annotations

import copy
import json
import math
from dataclasses import replace
from typing import cast

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.engine.phase import BattlePhase
from warhammer40k_core.engine.return_on_death import (
    PendingReturnOnDeath,
    ReturnDestroyedTargetScope,
    ReturnRestoreWoundsMode,
    build_return_on_death_placement_request,
)

from tests.support.contract42_battle_fixture import shooting_client
from tests.support.core_contract_examples import required_core_example_path
from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    JsonValue,
    UiClientSubmissionError,
    UiGameView,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow
from warhammer40k_arcade_ui.render.core_projection import battlefield_view_from_game_view
from warhammer40k_arcade_ui.state.placement_draft import PlacementDraft, PlacementDraftError
from warhammer40k_arcade_ui.state.selection import SelectionState

pytestmark = pytest.mark.integration

_OWNER = "player-a"


def _whole_unit_return_client() -> tuple[LocalSessionClient, str, dict[str, tuple[float, float]]]:
    client = shooting_client(models=5)
    session = client.session
    assert isinstance(session, LocalGameSession)
    state = session.lifecycle.state
    assert state is not None
    assert state.battlefield_state is not None
    army = next(army for army in state.army_definitions if army.player_id == _OWNER)
    unit = army.units[0]
    originals = {
        model.model_instance_id: state.battlefield_state.model_placement_by_id(
            model.model_instance_id
        )
        for model in unit.own_models
    }
    positions = {
        model_id: (placement.pose.position.x, placement.pose.position.y)
        for model_id, placement in originals.items()
    }
    state.army_definitions = [
        replace(
            current_army,
            units=tuple(
                replace(
                    current_unit,
                    own_models=tuple(
                        replace(model, wounds_remaining=0) for model in current_unit.own_models
                    ),
                )
                if current_unit.unit_instance_id == unit.unit_instance_id
                else current_unit
                for current_unit in current_army.units
            ),
        )
        for current_army in state.army_definitions
    ]
    state.replace_battlefield_state(
        state.battlefield_state.with_removed_models(unit.own_model_ids())
    )
    state.battle_phase_index = state.battle_phase_sequence.index(BattlePhase.COMMAND)
    anchor = originals[unit.own_models[0].model_instance_id]
    pending = PendingReturnOnDeath(
        pending_id="pending:whole-unit-ui-return",
        source_rule_id="rule:whole-unit-ui-return",
        source_ability_id="ability:whole-unit-ui-return",
        source_clause_id="clause:whole-unit-ui-return",
        source_effect_index=0,
        owner_player_id=_OWNER,
        target_scope=ReturnDestroyedTargetScope.DESTROYED_UNIT,
        destroyed_unit_instance_id=unit.unit_instance_id,
        destroyed_model_instance_id=None,
        destroyed_position_payload=cast(
            JsonValue,
            {
                "source": "model_destroyed_event",
                "model_destroyed_event_id": "event:whole-unit-ui-destroyed-position",
                "model_destroyed_payload": {
                    "model_instance_id": anchor.model_instance_id,
                    "destroyed_model_placement": anchor.to_payload(),
                },
            },
        ),
        trigger_battle_round=state.battle_round,
        trigger_phase=BattlePhase.COMMAND.value,
        resolution_timing="phase_end",
        roll_expression="D6",
        roll_count=1,
        success_threshold=2,
        placement_anchor="destroyed_position",
        placement_preference="as_close_as_possible",
        engagement_range_restriction=True,
        restore_wounds_mode=ReturnRestoreWoundsMode.FULL_HEALTH,
        wounds_remaining=None,
        resolved=False,
    )
    state.record_pending_return_on_death(pending)
    request = build_return_on_death_placement_request(state=state, pending=pending)
    session.lifecycle.decision_controller.request_decision(request)
    status = client.advance_until_decision_or_terminal()
    assert status.status_kind == "waiting_for_decision"
    assert status.decision is not None
    assert status.decision.decision_type == "submit_return_on_death_placement"
    return client, unit.unit_instance_id, positions


def _draft(
    view: UiGameView,
    *,
    client: LocalSessionClient,
    unit_display_by_id: JsonObject | None = None,
    authoritative_models_by_id: JsonObject | None = None,
) -> PlacementDraft:
    assert view.pending_decision is not None
    assert view.battlefield_view is not None
    result = PlacementDraft.start_for_pending(
        view=battlefield_view_from_game_view(view),
        selection=SelectionState.initial(default_preferences()),
        pending_decision=view.pending_decision,
        unit_display_by_id=(
            view.unit_display_by_id if unit_display_by_id is None else unit_display_by_id
        ),
        model_display_by_id=view.model_display_by_id,
        authoritative_models_by_id=(
            view.battlefield_view.models_by_id
            if authoritative_models_by_id is None
            else authoritative_models_by_id
        ),
        battlefield_state=view.battlefield_state,
        support_profile=client.get_support_profile(_OWNER),
        current_game_id=view.game_id,
        projection_state_hash=view.projection_state_hash,
    )
    assert result is not None
    return result


def test_real_whole_unit_return_opens_and_submits_all_destroyed_models() -> None:
    client, unit_id, original_positions = _whole_unit_return_client()
    view = client.get_view(_OWNER)
    assert view.pending_decision is not None
    assert view.pending_decision.placement_proposal is not None
    assert view.pending_decision.placement_proposal.required_model_ids == ()
    assert unit_id not in {unit.unit_id for unit in battlefield_view_from_game_view(view).units}
    assert view.battlefield_view is not None
    target_rows = {
        model_id: cast(JsonObject, row)
        for model_id, row in view.battlefield_view.models_by_id.items()
        if cast(JsonObject, row)["unit_instance_id"] == unit_id
    }
    assert len(target_rows) == 5
    assert all(row["state"] == "destroyed" and row["pose"] is None for row in target_rows.values())
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=battlefield_view_from_game_view(view),
        preferences=default_preferences(),
        pending_decision=view.pending_decision,
        initial_game_view=view,
        initial_support_profile=client.get_support_profile(_OWNER),
        viewer_player_id=_OWNER,
    )
    try:
        window._sync_placement_draft()
        assert window.placement_draft is not None
        assert window.placement_draft.total_model_count == 5
    finally:
        window.close()
    draft = _draft(view, client=client)
    assert tuple(pose.model_id for pose in draft.model_poses) == tuple(
        cast(list[str], cast(JsonObject, view.unit_display_by_id[unit_id])["model_instance_ids"])
    )
    assert draft.army_id == "army-alpha"
    assert all(
        pose.owner_player_id == _OWNER and pose.position is None for pose in draft.model_poses
    )
    assert draft.is_for(
        pending_decision=view.pending_decision,
        projection_state_hash=view.projection_state_hash,
    )
    assert not draft.is_for(
        pending_decision=view.pending_decision,
        projection_state_hash="stale-projection",
    )
    for pose in draft.model_poses:
        draft = draft.place_current_model(original_positions[pose.model_id])
    ready = draft.mark_ready()
    payload = ready.payload_preview
    assert payload is not None
    assert payload["submission_kind"] == "submit_return_on_death_placement"
    attempted = cast(JsonObject, payload["attempted_placement"])
    rows = cast(list[JsonObject], attempted["model_placements"])
    assert {cast(str, row["model_instance_id"]) for row in rows} == set(original_positions)
    assert all(
        row["army_id"] == "army-alpha" and row["unit_instance_id"] == unit_id for row in rows
    )

    before_records = client.session.decision_record_count()
    before_hash = view.projection_state_hash
    incomplete = copy.deepcopy(payload)
    incomplete_rows = cast(
        list[JsonObject],
        cast(JsonObject, incomplete["attempted_placement"])["model_placements"],
    )
    incomplete_rows.pop()
    invalid = client.submit_parameterized_payload(
        request_id=view.pending_decision.request_id,
        payload=incomplete,
        result_id="whole-unit-return-incomplete",
    )
    assert invalid.status_kind == "invalid"
    assert invalid.invalid_diagnostics
    assert client.session.decision_record_count() == before_records
    assert client.get_view(_OWNER).projection_state_hash == before_hash
    with pytest.raises(UiClientSubmissionError):
        client.submit_parameterized_payload(
            request_id="stale-whole-unit-return-request",
            payload=payload,
            result_id="whole-unit-return-stale",
        )
    assert client.session.decision_record_count() == before_records
    accepted = client.submit_parameterized_payload(
        request_id=view.pending_decision.request_id,
        payload=payload,
        result_id="whole-unit-return-accepted",
    )
    assert accepted.status_kind != "invalid", accepted.invalid_diagnostics
    assert client.session.decision_record_count() == before_records + 1
    after = client.get_view(_OWNER)
    assert after.battlefield_view is not None
    assert all(
        cast(JsonObject, after.battlefield_view.models_by_id[model_id])["state"] == "placed"
        for model_id in original_positions
    )


def test_whole_unit_return_oval_and_rectangle_previews_use_current_physical_geometry() -> None:
    client, unit_id, _positions = _whole_unit_return_client()
    raw = cast(JsonObject, copy.deepcopy(client.session.view(viewer_player_id=_OWNER)))
    source_display = cast(JsonObject, cast(JsonObject, raw["unit_display_by_id"])[unit_id])
    model_ids = cast(list[str], source_display["model_instance_ids"])
    assert len(model_ids) >= 2
    physical = cast(
        JsonObject,
        cast(JsonObject, cast(JsonObject, raw["battlefield_view"])["authoritative"])[
            "models_by_id"
        ],
    )
    example_path = required_core_example_path("battlefield", "geometry-conformance.json")
    example = cast(JsonObject, json.loads(example_path.read_text(encoding="utf-8")))
    example_models = cast(JsonObject, cast(JsonObject, example["authoritative"])["models_by_id"])
    oval_example = cast(JsonObject, example_models["geometry-conformance-oval-model"])
    oval_geometry = cast(JsonObject, oval_example["geometry"])
    oval_shape = cast(JsonObject, copy.deepcopy(oval_geometry["support_shape"]))
    oval_shape["width_inches"] = 1.0
    oval_shape["length_inches"] = 2.0

    model_displays = cast(JsonObject, raw["model_display_by_id"])
    for model_id, physical_kind, display_kind in (
        (model_ids[0], "ellipse", "oval"),
        (model_ids[1], "rectangle", "rectangular"),
    ):
        row = cast(JsonObject, physical[model_id])
        assert row["state"] == "destroyed"
        assert row["pose"] is None
        geometry = cast(JsonObject, row["geometry"])
        shape = copy.deepcopy(oval_shape)
        shape["kind"] = physical_kind
        geometry["support_shape"] = shape
        display = cast(JsonObject, model_displays[model_id])
        display["base_size"] = {
            "kind": display_kind,
            "diameter_mm": None,
            "length_mm": 50.8,
            "width_mm": 25.4,
        }

    view = UiGameView.from_payload(raw)
    expected_radii = {
        model_ids[0]: 1.0,
        model_ids[1]: math.hypot(1.0, 0.5),
    }
    draft = _draft(view, client=client)
    assert set(expected_radii) <= {pose.model_id for pose in draft.model_poses}
    for pose in draft.model_poses:
        if pose.model_id in expected_radii:
            assert math.isclose(pose.base_radius, expected_radii[pose.model_id])

    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=battlefield_view_from_game_view(view),
        preferences=default_preferences(),
        pending_decision=view.pending_decision,
        initial_game_view=view,
        initial_support_profile=client.get_support_profile(_OWNER),
        viewer_player_id=_OWNER,
    )
    try:
        window._sync_placement_draft()
        assert window.placement_draft is not None
        assignments = {
            assignment.model_id: assignment
            for assignment in window.placement_draft.assignment_views()
        }
        for model_id, radius in expected_radii.items():
            assert math.isclose(assignments[model_id].base_radius, radius)
    finally:
        window.close()


def test_whole_unit_return_rejects_missing_or_foreign_current_model_authority() -> None:
    client, unit_id, positions = _whole_unit_return_client()
    view = client.get_view(_OWNER)
    assert view.battlefield_view is not None
    target_display = cast(JsonObject, view.unit_display_by_id[unit_id])
    target_id = cast(list[str], target_display["model_instance_ids"])[0]
    physical = copy.deepcopy(view.battlefield_view.models_by_id)
    physical.pop(target_id)
    with pytest.raises(PlacementDraftError, match="model inventories differ"):
        _draft(view, client=client, authoritative_models_by_id=physical)

    physical = copy.deepcopy(view.battlefield_view.models_by_id)
    cast(JsonObject, physical[target_id])["owner_player_id"] = "player-b"
    with pytest.raises(PlacementDraftError, match="identity differs from request"):
        _draft(view, client=client, authoritative_models_by_id=physical)

    physical = copy.deepcopy(view.battlefield_view.models_by_id)
    cast(JsonObject, physical[target_id])["model_instance_id"] = "forged-model"
    with pytest.raises(PlacementDraftError, match="identity differs from request"):
        _draft(view, client=client, authoritative_models_by_id=physical)

    physical = copy.deepcopy(view.battlefield_view.models_by_id)
    cast(JsonObject, physical[target_id]).pop("geometry")
    with pytest.raises(PlacementDraftError, match="physical model geometry"):
        _draft(view, client=client, authoritative_models_by_id=physical)

    physical = copy.deepcopy(view.battlefield_view.models_by_id)
    own_display = cast(JsonObject, view.unit_display_by_id[unit_id])
    own_ids = cast(list[str], own_display["model_instance_ids"])
    unrelated_id = next(model_id for model_id in physical if model_id not in own_ids)
    cast(JsonObject, physical[unrelated_id])["rules_unit_instance_id"] = unit_id
    assert len(_draft(view, client=client, authoritative_models_by_id=physical).model_poses) == 5

    physical = copy.deepcopy(view.battlefield_view.models_by_id)
    split_origin: JsonObject = {
        "source_unit_instance_id": "physical-source-unit",
        "split_id": "split-current-001",
        "successor_index": 0,
    }
    cast(JsonObject, physical[target_id])["split_origin"] = split_origin
    split_draft = _draft(view, client=client, authoritative_models_by_id=physical)
    assert split_draft.model_poses[0].split_origin == split_origin
    for pose in split_draft.model_poses:
        split_draft = split_draft.place_current_model(positions[pose.model_id])
    split_payload = split_draft.mark_ready().payload_preview
    assert split_payload is not None
    split_rows = cast(
        list[JsonObject],
        cast(JsonObject, split_payload["attempted_placement"])["model_placements"],
    )
    assert split_rows[0]["split_origin"] == split_origin

    with pytest.raises(PlacementDraftError, match="current public model authority"):
        PlacementDraft.start_for_pending(
            view=battlefield_view_from_game_view(view),
            selection=SelectionState.initial(default_preferences()),
            pending_decision=view.pending_decision,
            unit_display_by_id=view.unit_display_by_id,
            model_display_by_id=view.model_display_by_id,
            battlefield_state=view.battlefield_state,
            support_profile=client.get_support_profile(_OWNER),
            current_game_id=view.game_id,
        )

    missing = replace(
        view,
        unit_display_by_id={
            key: value for key, value in view.unit_display_by_id.items() if key != unit_id
        },
    )
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=battlefield_view_from_game_view(missing),
        preferences=default_preferences(),
        pending_decision=missing.pending_decision,
        initial_game_view=missing,
        viewer_player_id=_OWNER,
    )
    try:
        window._sync_placement_draft()
        assert window.placement_draft is None
        assert window.finite_state.status_kind == "invalid"
        assert window.finite_state.diagnostics[0].violation_code == "placement_draft_unavailable"
    finally:
        window.close()
