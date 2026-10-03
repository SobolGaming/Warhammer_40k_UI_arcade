"""Tests for local movement draft state and payload previews."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.support.contract_fixtures import decision_from_fixture
from warhammer40k_arcade_ui.core_client.protocol import JsonObject, UiDecision
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.render.view_models import BattlefieldView
from warhammer40k_arcade_ui.state.entity_selection import EntityRef, entity_ref_for_model
from warhammer40k_arcade_ui.state.movement_draft import (
    MovementDraft,
    MovementDraftError,
    movement_proposal_for_selected_unit,
    unsupported_parameterized_tool_label,
)
from warhammer40k_arcade_ui.state.selection import SelectionState


def test_movement_proposal_for_selected_unit_activates_model_assignment_draft() -> None:
    view = default_battlefield_view()
    selection = _selected_intercessors()
    decision = _movement_proposal_decision()

    proposal = movement_proposal_for_selected_unit(
        view=view,
        selection=selection,
        pending_decision=decision,
    )
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=decision,
    )

    assert proposal is not None
    assert draft is not None
    assert draft.selected_unit_id == "intercessor_squad"
    assert draft.proposal_request_id == "decision-request-000005"
    assert draft.proposal_kind == "normal_move"
    assert draft.movement_phase_action == "normal_move"
    assert draft.movement_mode == "normal"
    assert draft.mode == "model_assignments"
    assert draft.selected_model_ids == ("intercessor_1",)
    assert [path.model_id for path in draft.model_paths] == [
        "intercessor_1",
        "intercessor_2",
        "intercessor_3",
    ]
    assert all(path.points == (path.points[0],) for path in draft.model_paths)


def test_movement_draft_seed_from_unit_selection_expands_to_all_models() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_model_id(
        unit_id="intercessor_squad",
        model_id=None,
        preferences=preferences,
    )

    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=_movement_proposal_decision(),
    )

    assert draft is not None
    assert draft.selected_model_ids == (
        "intercessor_1",
        "intercessor_2",
        "intercessor_3",
    )


def test_normal_move_budget_falls_back_to_datasheet_base_movement() -> None:
    view = _view_with_intercessor_base_movement(6.0)
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(view=view),
        pending_decision=_movement_proposal_decision(
            context={
                "source_selected_option_id": "normal_move",
                "movement_mode": "normal",
            }
        ),
    )

    assert draft is not None
    assert draft.movement_budget_inches == 6.0
    assert draft.base_movement_budget_inches == 6.0
    assert any("movement budget is inferred" in hint for hint in draft.local_hint_lines)


def test_advance_move_budget_uses_datasheet_base_movement_plus_advance_roll() -> None:
    view = _view_with_intercessor_base_movement(6.0)
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(view=view),
        pending_decision=_movement_proposal_decision(
            proposal_kind="advance",
            movement_phase_action="advance",
            context={
                "source_selected_option_id": "advance",
                "movement_mode": "advance",
                "advance_roll": {"value": 6},
            },
        ),
    )

    assert draft is not None
    assert draft.movement_budget_inches == 12.0
    assert draft.base_movement_budget_inches == 6.0
    assert any("movement budget is inferred" in hint for hint in draft.local_hint_lines)


def test_movement_draft_does_not_start_for_unrelated_selected_unit() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_model_id(
        unit_id="guardian_squad",
        model_id="guardian_1",
        preferences=preferences,
    )

    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=_movement_proposal_decision(),
    )

    assert draft is None


def test_one_model_movement_draft_moves_only_active_model() -> None:
    view = default_battlefield_view()
    draft = _active_draft().add_waypoint(view=view, world_point=(10.0, 18.0))

    paths = {path.model_id: path.points for path in draft.model_paths}

    assert paths["intercessor_1"] == ((7.0, 18.0), (10.0, 18.0))
    assert paths["intercessor_2"] == ((7.0, 22.0),)
    assert paths["intercessor_3"] == ((7.0, 26.0),)
    assert draft.assigned_model_count == 1
    assert draft.unchanged_model_count == 2
    assert draft.total_path_length == 3.0


def test_multi_model_subset_receives_same_translated_path() -> None:
    view = default_battlefield_view()
    draft = _active_draft().add_model_selection(
        view=view,
        ref=_model_ref("intercessor_2"),
    )
    moved = draft.add_waypoint(view=view, world_point=(9.0, 20.0))

    paths = {path.model_id: path.points for path in moved.model_paths}

    assert moved.selected_model_ids == ("intercessor_1", "intercessor_2")
    assert paths["intercessor_1"] == ((7.0, 18.0), (9.0, 18.0))
    assert paths["intercessor_2"] == ((7.0, 22.0), (9.0, 22.0))
    assert paths["intercessor_3"] == ((7.0, 26.0),)


def test_whole_unit_group_selection_assigns_all_models_explicitly() -> None:
    view = default_battlefield_view()
    draft = _active_draft().select_current_group(view=view)
    moved = draft.add_waypoint(view=view, world_point=(10.0, 22.0))

    paths = {path.model_id: path.points for path in moved.model_paths}

    assert moved.selected_model_ids == (
        "intercessor_1",
        "intercessor_2",
        "intercessor_3",
    )
    assert paths["intercessor_1"] == ((7.0, 18.0), (10.0, 18.0))
    assert paths["intercessor_2"] == ((7.0, 22.0), (10.0, 22.0))
    assert paths["intercessor_3"] == ((7.0, 26.0), (10.0, 26.0))


def test_separate_model_subsets_can_have_different_paths() -> None:
    view = default_battlefield_view()
    model_2 = _model_ref("intercessor_2")
    model_3 = _model_ref("intercessor_3")
    first = _active_draft().add_waypoint(view=view, world_point=(10.0, 18.0))
    second = (
        first.replace_model_selection(view=view, ref=model_2)
        .add_model_selection(view=view, ref=model_3)
        .add_waypoint(view=view, world_point=(7.0, 27.0))
    )

    paths = {path.model_id: path.points for path in second.model_paths}

    assert paths["intercessor_1"] == ((7.0, 18.0), (10.0, 18.0))
    assert paths["intercessor_2"] == ((7.0, 22.0), (7.0, 25.0))
    assert paths["intercessor_3"] == ((7.0, 26.0), (7.0, 29.0))
    assert second.assigned_model_count == 3
    assert {
        path.assignment_group_id for path in second.model_paths if path.assignment_group_id
    } == {"assignment-group-000001", "assignment-group-000002"}


def test_removing_last_waypoint_affects_only_active_subset() -> None:
    view = default_battlefield_view()
    model_2 = _model_ref("intercessor_2")
    moved = (
        _active_draft()
        .add_waypoint(view=view, world_point=(10.0, 18.0))
        .replace_model_selection(view=view, ref=model_2)
        .add_waypoint(view=view, world_point=(10.0, 22.0))
    )
    removed = moved.remove_last_waypoint(view=view)

    paths = {path.model_id: path.points for path in removed.model_paths}

    assert paths["intercessor_1"] == ((7.0, 18.0), (10.0, 18.0))
    assert paths["intercessor_2"] == ((7.0, 22.0),)
    assert paths["intercessor_3"] == ((7.0, 26.0),)


def test_payload_preview_includes_explicit_no_op_paths_for_unchanged_models() -> None:
    view = default_battlefield_view()
    draft = _active_draft().add_waypoint(view=view, world_point=(10.0, 18.0)).mark_ready(view=view)

    payload = draft.payload_preview

    assert payload is not None
    assert not any("synthetic midpoint witness evidence" in hint for hint in draft.local_hint_lines)
    assert draft.payload_witness_summary_lines == (
        "intercessor_1: 2 witness point(s)",
        "intercessor_2: 2 witness point(s), no-op",
        "intercessor_3: 2 witness point(s), no-op",
    )
    assert payload["proposal_request_id"] == "decision-request-000005"
    assert payload["proposal_kind"] == "normal_move"
    assert payload["unit_instance_id"] == "intercessor_squad"
    assert payload["movement_phase_action"] == "normal_move"
    assert payload["movement_mode"] == "normal"
    witness = payload["witness"]
    assert type(witness) is dict
    model_paths = witness["model_paths"]
    model_movements = payload["model_movements"]
    assert type(model_paths) is list
    assert type(model_movements) is list
    assert len(model_paths) == 3
    assert len(model_movements) == 3
    first_path = model_paths[0]
    second_path = model_paths[1]
    second_movement = model_movements[1]
    assert type(first_path) is dict
    assert type(second_path) is dict
    assert type(second_movement) is dict
    assert first_path["model_id"] == "intercessor_1"
    assert first_path["poses"] == [
        {"position": {"x": 7.0, "y": 18.0, "z": 0.0}, "facing": {"degrees": 0.0}},
        {"position": {"x": 10.0, "y": 18.0, "z": 0.0}, "facing": {"degrees": 0.0}},
    ]
    assert second_path["model_id"] == "intercessor_2"
    assert second_path["poses"] == [
        {"position": {"x": 7.0, "y": 22.0, "z": 0.0}, "facing": {"degrees": 0.0}},
        {"position": {"x": 7.0, "y": 22.0, "z": 0.0}, "facing": {"degrees": 0.0}},
    ]
    assert second_movement["model_instance_id"] == "intercessor_2"
    second_poses = second_path["poses"]
    assert type(second_poses) is list
    assert second_movement["path"] == second_poses
    assert second_movement["final_pose"] == second_poses[-1]


@pytest.mark.parametrize("proposal_kind", ["normal_move", "scout_move"])
def test_movement_payload_preserves_each_model_elevation_and_facing(
    proposal_kind: str,
) -> None:
    view = default_battlefield_view()
    source = view.units[0]
    elevations_and_facings = ((1.5, 45.0), (2.25, 120.0), (-0.5, 270.0))
    source = replace(
        source,
        models=tuple(
            replace(model, elevation_z_inches=z, facing_degrees=facing)
            for model, (z, facing) in zip(source.models, elevations_and_facings, strict=True)
        ),
    )
    view = replace(view, units=(source, *view.units[1:]))
    decision = (
        _scout_move_proposal_decision(action_kind="scout_move")
        if proposal_kind == "scout_move"
        else _movement_proposal_decision()
    )
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(view=view),
        pending_decision=decision,
    )
    assert draft is not None
    payload = (
        draft.add_waypoint(view=view, world_point=(10.0, 18.0))
        .mark_ready(view=view)
        .payload_preview
    )
    assert payload is not None
    paths = _witness_model_paths(payload)
    assert set(paths) == {model.model_id for model in source.models}
    for model in source.models:
        poses = paths[model.model_id]["poses"]
        assert type(poses) is list
        for pose in poses:
            assert type(pose) is dict
            position = pose["position"]
            facing = pose["facing"]
            assert type(position) is dict
            assert type(facing) is dict
            assert position["z"] == model.elevation_z_inches
            assert facing["degrees"] == model.facing_degrees
        if model.model_id != "intercessor_1":
            assert poses == [poses[0], poses[0]]
    if proposal_kind == "normal_move":
        movements = payload["model_movements"]
        assert type(movements) is list
        for row in movements:
            assert type(row) is dict
            model_id = row["model_instance_id"]
            assert type(model_id) is str
            witness_poses = paths[model_id]["poses"]
            assert type(witness_poses) is list
            assert row["path"] == witness_poses
            assert row["final_pose"] == witness_poses[-1]


def test_charge_move_payload_preserves_entered_witness_and_committed_targets() -> None:
    view = default_battlefield_view()
    selection = _selected_intercessors()
    decision = _movement_proposal_decision(
        proposal_kind="charge_move",
        movement_phase_action="charge_move",
        context={
            "movement_mode": "charge",
            "maximum_distance_inches": 7.0,
            "reachable_target_unit_instance_ids": ["guardian_squad", "other_reachable"],
            "target_selection": {"target_ids": ["guardian_squad"]},
        },
    )
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=decision,
    )
    assert draft is not None
    one_waypoint = draft.add_waypoint(view=view, world_point=(10.0, 18.0))
    one_waypoint_witness = one_waypoint.to_payload()["witness"]
    assert type(one_waypoint_witness) is dict
    one_waypoint_paths = one_waypoint_witness["model_paths"]
    assert type(one_waypoint_paths) is list
    one_waypoint_path = one_waypoint_paths[0]
    assert type(one_waypoint_path) is dict
    assert one_waypoint_path["poses"] == [
        {"position": {"x": 7.0, "y": 18.0, "z": 0.0}, "facing": {"degrees": 0.0}},
        {"position": {"x": 10.0, "y": 18.0, "z": 0.0}, "facing": {"degrees": 0.0}},
    ]
    ready = (
        draft.add_waypoint(view=view, world_point=(8.5, 18.0))
        .add_waypoint(view=view, world_point=(10.0, 18.0))
        .mark_ready(view=view)
    )

    payload = ready.payload_preview

    assert payload is not None
    assert payload["proposal_kind"] == "charge_move"
    assert payload["movement_mode"] == "charge"
    assert payload["charge_target_unit_instance_ids"] == ["guardian_squad"]
    witness = payload["witness"]
    assert type(witness) is dict
    model_paths = witness["model_paths"]
    assert type(model_paths) is list
    first_path = model_paths[0]
    assert type(first_path) is dict
    assert first_path["poses"] == [
        {"position": {"x": 7.0, "y": 18.0, "z": 0.0}, "facing": {"degrees": 0.0}},
        {"position": {"x": 8.5, "y": 18.0, "z": 0.0}, "facing": {"degrees": 0.0}},
        {"position": {"x": 10.0, "y": 18.0, "z": 0.0}, "facing": {"degrees": 0.0}},
    ]


@pytest.mark.parametrize(
    ("proposal_kind", "action_kind"),
    [
        ("scout_move", "scout_move"),
        ("scout_move", "dedicated_transport_scout_move"),
        ("pile_in", "pile_in"),
        ("consolidate", "consolidate"),
    ],
)
def test_current_path_witness_preserves_entered_endpoints_and_waypoints(
    proposal_kind: str, action_kind: str
) -> None:
    view = default_battlefield_view()
    decision = (
        _scout_move_proposal_decision(action_kind=action_kind)
        if proposal_kind == "scout_move"
        else _movement_proposal_decision(
            proposal_kind=proposal_kind,
            movement_phase_action=proposal_kind,
            phase="fight",
            context={
                "movement_mode": proposal_kind,
                "maximum_distance_inches": 3.0,
                f"legal_{proposal_kind}_target_unit_instance_ids": ["guardian_squad"],
                "legal_consolidation_modes": ["engaging"] if proposal_kind == "consolidate" else [],
            },
        )
    )
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(),
        pending_decision=decision,
    )
    assert draft is not None

    endpoint_only = draft.add_waypoint(view=view, world_point=(9.0, 18.0)).mark_ready(view=view)
    endpoint_payload = endpoint_only.payload_preview
    assert endpoint_payload is not None
    assert endpoint_payload["proposal_request_id"] == decision.request_id
    assert endpoint_payload["proposal_kind"] == proposal_kind
    if proposal_kind == "scout_move":
        assert endpoint_payload["action_kind"] == action_kind
        assert endpoint_payload["source_rule_id"] == "core:scouts"
        assert endpoint_payload["scout_distance_inches"] == 6.0
    else:
        assert endpoint_payload["movement_mode"] == proposal_kind
        assert endpoint_payload["movement_phase_action"] == proposal_kind
    endpoint_paths = _witness_model_paths(endpoint_payload)
    assert _path_points(endpoint_paths["intercessor_1"]) == ((7.0, 18.0), (9.0, 18.0))
    assert _path_points(endpoint_paths["intercessor_2"]) == ((7.0, 22.0), (7.0, 22.0))
    assert _path_points(endpoint_paths["intercessor_3"]) == ((7.0, 26.0), (7.0, 26.0))
    assert endpoint_only.payload_witness_summary_lines[0] == "intercessor_1: 2 witness point(s)"
    if proposal_kind != "scout_move":
        movements = endpoint_payload["model_movements"]
        assert type(movements) is list
        movement_paths: dict[str, object] = {}
        for row in movements:
            assert type(row) is dict
            model_id = row.get("model_instance_id")
            assert type(model_id) is str
            movement_paths[model_id] = row["path"]
        assert movement_paths == {
            model_id: path["poses"] for model_id, path in endpoint_paths.items()
        }

    with_waypoint = (
        draft.add_waypoint(view=view, world_point=(8.0, 18.5))
        .add_waypoint(view=view, world_point=(9.0, 18.0))
        .mark_ready(view=view)
    )
    waypoint_payload = with_waypoint.payload_preview
    assert waypoint_payload is not None
    waypoint_paths = _witness_model_paths(waypoint_payload)
    assert _path_points(waypoint_paths["intercessor_1"]) == (
        (7.0, 18.0),
        (8.0, 18.5),
        (9.0, 18.0),
    )
    assert with_waypoint.payload_witness_summary_lines[0] == "intercessor_1: 3 witness point(s)"


def test_charge_move_refuses_missing_target_commitment() -> None:
    view = default_battlefield_view()
    decision = _movement_proposal_decision(
        proposal_kind="charge_move",
        movement_phase_action="charge_move",
        context={
            "movement_mode": "charge",
            "maximum_distance_inches": 7.0,
            "reachable_target_unit_instance_ids": ["guardian_squad"],
        },
    )
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(),
        pending_decision=decision,
    )
    assert draft is not None

    with pytest.raises(MovementDraftError, match=r"context.target_selection.*JSON object"):
        draft.add_waypoint(view=view, world_point=(10.0, 18.0)).to_payload()


def test_charge_move_no_move_payload_omits_witness() -> None:
    view = default_battlefield_view()
    decision = _movement_proposal_decision(
        proposal_kind="charge_move",
        movement_phase_action="charge_move",
        context={
            "movement_mode": "charge",
            "maximum_distance_inches": 7.0,
            "reachable_target_unit_instance_ids": ["guardian_squad"],
            "target_selection": {"target_ids": ["guardian_squad"]},
        },
    )
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(),
        pending_decision=decision,
    )
    assert draft is not None

    ready = draft.mark_ready(view=view)
    payload = ready.payload_preview

    assert payload is not None
    assert payload["proposal_kind"] == "charge_move"
    assert payload["charge_target_unit_instance_ids"] == []
    assert "witness" not in payload
    assert "model_movements" not in payload


def test_mouse_hover_preview_does_not_clear_ready_payload() -> None:
    view = default_battlefield_view()
    ready = _active_draft().add_waypoint(view=view, world_point=(10.0, 18.0)).mark_ready(view=view)

    hovered = ready.with_cursor_preview(view=view, world_point=(12.0, 20.0))

    assert hovered.is_ready is True
    assert hovered.payload_preview == ready.payload_preview
    assert hovered.cursor_preview_point == ready.cursor_preview_point


def test_fall_back_payload_preserves_engine_issued_mode_context() -> None:
    view = default_battlefield_view()
    selection = _selected_intercessors()
    decision = _movement_proposal_decision(
        proposal_kind="fall_back",
        movement_phase_action="fall_back",
        context={
            "source_selected_option_id": "fall_back:desperate_escape",
            "movement_mode": "fall_back",
            "fall_back_mode": "desperate_escape",
            "movement_budget_inches": 6.0,
        },
    )
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=decision,
    )

    assert draft is not None
    payload = (
        draft.add_waypoint(view=view, world_point=(9.0, 18.0)).mark_ready(view=view).payload_preview
    )

    assert payload is not None
    assert payload["proposal_kind"] == "fall_back"
    assert payload["movement_phase_action"] == "fall_back"
    assert payload["movement_mode"] == "fall_back"
    assert payload["fall_back_mode"] == "desperate_escape"


def test_missing_movement_mode_context_blocks_movement_draft() -> None:
    view = default_battlefield_view()
    decision = _movement_proposal_decision(
        context={
            "source_selected_option_id": "normal_move",
            "movement_budget_inches": 6.0,
        },
    )

    proposal = movement_proposal_for_selected_unit(
        view=view,
        selection=_selected_intercessors(),
        pending_decision=decision,
    )
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(),
        pending_decision=decision,
    )

    assert proposal is None
    assert draft is None


def test_fall_back_missing_fall_back_mode_context_blocks_movement_draft() -> None:
    view = default_battlefield_view()
    decision = _movement_proposal_decision(
        proposal_kind="fall_back",
        movement_phase_action="fall_back",
        context={
            "source_selected_option_id": "fall_back:desperate_escape",
            "movement_mode": "fall_back",
            "movement_budget_inches": 6.0,
        },
    )

    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(),
        pending_decision=decision,
    )

    assert draft is None


def test_request_drift_starts_new_draft_without_previous_assignments() -> None:
    view = default_battlefield_view()
    selection = _selected_intercessors()
    original = _active_draft().add_waypoint(view=view, world_point=(10.0, 18.0))
    changed_request = _movement_proposal_decision(request_id="decision-request-000006")

    assert original.is_for(selection=selection, pending_decision=changed_request) is False
    replacement = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=changed_request,
    )

    assert replacement is not None
    assert replacement.proposal_request_id == "decision-request-000006"
    assert replacement.assigned_model_count == 0


def test_start_for_pending_does_not_use_proposal_unit_when_selection_drifted() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(53.0, 18.0),
        preferences=preferences,
    )
    decision = _movement_proposal_decision()

    selected_proposal = movement_proposal_for_selected_unit(
        view=view,
        selection=selection,
        pending_decision=decision,
    )
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=decision,
    )

    assert selection.selected_unit_id == "guardian_squad"
    assert selected_proposal is None
    assert draft is None


def test_movement_draft_rejects_foreign_model_in_actor_focus() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    stale = SelectionState.initial(preferences).select_model_id(
        unit_id="intercessor_squad",
        model_id="guardian_1",
        preferences=preferences,
    )
    assert (
        MovementDraft.start_for_pending(
            view=view,
            selection=stale,
            pending_decision=_movement_proposal_decision(),
        )
        is None
    )


def test_assignment_views_expose_summary_friendly_model_states() -> None:
    view = default_battlefield_view()
    model_2 = _model_ref("intercessor_2")
    draft = (
        _active_draft()
        .add_waypoint(view=view, world_point=(10.0, 18.0))
        .replace_model_selection(view=view, ref=model_2)
        .with_cursor_preview(view=view, world_point=(10.0, 22.0))
    )

    assignments = {assignment.model_id: assignment for assignment in draft.assignment_views()}

    assert assignments["intercessor_1"].state == "assigned"
    assert assignments["intercessor_1"].final_point == (10.0, 18.0)
    assert assignments["intercessor_2"].state == "active"
    assert assignments["intercessor_2"].final_point == (10.0, 22.0)
    assert assignments["intercessor_3"].state == "unassigned"


def test_non_movement_parameterized_request_does_not_create_movement_draft() -> None:
    view = default_battlefield_view()
    selection = _selected_intercessors()
    decision = _shooting_proposal_decision()

    proposal = movement_proposal_for_selected_unit(
        view=view,
        selection=selection,
        pending_decision=decision,
    )
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=decision,
    )

    assert proposal is None
    assert draft is None
    assert unsupported_parameterized_tool_label(decision) is None


def test_selection_state_uses_configured_movement_draft_overlays() -> None:
    preferences = default_preferences()
    selection = _selected_intercessors()

    with_draft = selection.with_movement_draft_overlays(preferences)
    without_draft = with_draft.without_movement_draft_overlays(preferences)

    assert "movement_path_draft" in with_draft.active_overlay_ids
    assert "movement_budget" in with_draft.active_overlay_ids
    assert "movement_path_draft" not in without_draft.active_overlay_ids
    assert "movement_budget" not in without_draft.active_overlay_ids
    assert "selected_unit" in without_draft.active_overlay_ids


def _active_draft() -> MovementDraft:
    view = default_battlefield_view()
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(),
        pending_decision=_movement_proposal_decision(),
    )
    assert draft is not None
    return draft


def _selected_intercessors(*, view: BattlefieldView | None = None) -> SelectionState:
    view = default_battlefield_view() if view is None else view
    preferences = default_preferences()
    return SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )


def _view_with_intercessor_base_movement(movement_inches: float) -> BattlefieldView:
    view = default_battlefield_view()
    intercessors, *other_units = view.units
    return replace(
        view,
        units=(
            replace(
                intercessors,
                models=tuple(
                    replace(model, base_movement_inches=movement_inches)
                    for model in intercessors.models
                ),
            ),
            *other_units,
        ),
    )


def _model_ref(model_id: str) -> EntityRef:
    ref = entity_ref_for_model(
        view=default_battlefield_view(),
        unit_id="intercessor_squad",
        model_id=model_id,
    )
    assert ref is not None
    return ref


def _movement_proposal_decision(
    *,
    request_id: str = "decision-request-000005",
    proposal_kind: str = "normal_move",
    movement_phase_action: str = "normal_move",
    phase: str = "movement",
    context: dict[str, object] | None = None,
) -> UiDecision:
    proposal_context = (
        {
            "source_selected_option_id": "normal_move",
            "movement_mode": "normal",
            "movement_budget_inches": 6.0,
        }
        if context is None
        else context
    )
    return decision_from_fixture(
        {
            "request_id": request_id,
            "decision_type": "submit_movement_proposal",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": request_id,
                    "decision_type": "submit_movement_proposal",
                    "actor_id": "player_1",
                    "game_id": "phase9-game",
                    "battle_round": 1,
                    "phase": phase,
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": proposal_kind,
                    "source_decision_request_id": "decision-request-000004",
                    "source_decision_result_id": "ui-result-000001",
                    "movement_phase_action": movement_phase_action,
                    "placement_kinds": [],
                    "context": proposal_context,
                }
            },
            "is_parameterized": True,
            "options": [
                {
                    "option_id": "submit_parameterized_payload",
                    "label": "Submit Parameterized Payload",
                    "payload": {"submission_kind": "parameterized"},
                }
            ],
        }
    )


def _scout_move_proposal_decision(*, action_kind: str) -> UiDecision:
    request_id = "decision-request-scout-endpoints"
    return decision_from_fixture(
        {
            "request_id": request_id,
            "decision_type": "submit_scout_move",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": request_id,
                    "decision_type": "submit_scout_move",
                    "actor_id": "player_1",
                    "game_id": "scout-endpoint-fixture",
                    "setup_step": "resolve_prebattle_actions",
                    "player_id": "player_1",
                    "unit_instance_id": "intercessor_squad",
                    "component_unit_instance_ids": ["intercessor_squad"],
                    "model_instance_ids": [
                        "intercessor_1",
                        "intercessor_2",
                        "intercessor_3",
                    ],
                    "proposal_kind": "scout_move",
                    "action_kind": action_kind,
                    "source_rule_id": "core:scouts",
                    "placement_kind": None,
                    "scout_distance_inches": 6.0,
                    "deployment_zone_ids": ["deployment-zone-a"],
                    "legal_deployment_zones": [],
                    "mission_setup": {},
                    "ruleset_descriptor_hash": "ruleset-scout-endpoints",
                    "source_decision_request_id": "decision-request-prebattle-endpoints",
                    "source_decision_result_id": "ui-result-prebattle-endpoints",
                    "context": {"source_selected_option_id": f"{action_kind}:intercessor_squad"},
                }
            },
            "is_parameterized": True,
            "options": [
                {
                    "option_id": "submit_parameterized_payload",
                    "label": "Submit Parameterized Payload",
                    "payload": {"submission_kind": "parameterized"},
                }
            ],
        }
    )


def _witness_model_paths(payload: JsonObject) -> dict[str, JsonObject]:
    witness = payload.get("witness")
    assert type(witness) is dict
    rows = witness.get("model_paths")
    assert type(rows) is list
    paths: dict[str, JsonObject] = {}
    for row in rows:
        assert type(row) is dict
        model_id = row.get("model_id")
        assert type(model_id) is str
        paths[model_id] = row
    return paths


def _path_points(path: JsonObject) -> tuple[tuple[float, float], ...]:
    poses = path.get("poses")
    assert type(poses) is list
    points: list[tuple[float, float]] = []
    for pose in poses:
        assert type(pose) is dict
        position = pose.get("position")
        assert type(position) is dict
        x, y = position.get("x"), position.get("y")
        assert isinstance(x, (int, float))
        assert not isinstance(x, bool)
        assert isinstance(y, (int, float))
        assert not isinstance(y, bool)
        points.append((float(x), float(y)))
    return tuple(points)


def _shooting_proposal_decision() -> UiDecision:
    return decision_from_fixture(
        {
            "request_id": "decision-request-000009",
            "decision_type": "submit_shooting_declaration",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-000009",
                    "decision_type": "submit_shooting_declaration",
                    "actor_id": "player_1",
                    "proposal_kind": "shooting_declaration",
                }
            },
            "options": [
                {
                    "option_id": "submit_parameterized_payload",
                    "label": "Submit Parameterized Payload",
                    "payload": {"submission_kind": "parameterized"},
                }
            ],
            "is_parameterized": True,
        }
    )
