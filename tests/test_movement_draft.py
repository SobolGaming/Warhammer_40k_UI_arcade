"""Tests for local movement draft state and payload previews."""

from __future__ import annotations

from dataclasses import replace

from warhammer40k_arcade_ui.core_client.protocol import UiDecision
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.render.view_models import BattlefieldView
from warhammer40k_arcade_ui.state.entity_selection import EntityRef, entity_ref_for_model
from warhammer40k_arcade_ui.state.movement_draft import (
    MovementDraft,
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
    assert draft.synthetic_witness_model_ids == ()
    assert draft.synthetic_witness_point_count == 0
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


def test_charge_move_payload_uses_sampled_witness_and_charge_targets() -> None:
    view = default_battlefield_view()
    selection = _selected_intercessors()
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
        selection=selection,
        pending_decision=decision,
    )
    assert draft is not None
    ready = draft.add_waypoint(view=view, world_point=(10.0, 18.0)).mark_ready(view=view)

    payload = ready.payload_preview

    assert payload is not None
    assert payload["proposal_kind"] == "charge_move"
    assert payload["movement_mode"] == "charge"
    assert payload["charge_target_unit_instance_ids"] == ["guardian_squad"]
    assert ready.synthetic_witness_model_ids == ("intercessor_1",)
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


def test_charge_move_no_move_payload_omits_witness() -> None:
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
    return UiDecision.from_payload(
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
                    "phase": "movement",
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


def _shooting_proposal_decision() -> UiDecision:
    decision = _movement_proposal_decision()
    proposal = decision.parameterized_proposal
    assert proposal is not None
    return replace(
        decision,
        decision_type="submit_shooting_declaration",
        movement_proposal=None,
        parameterized_proposal=replace(
            proposal,
            decision_type="submit_shooting_declaration",
            proposal_kind="shooting_declaration",
            payload={
                "request_id": "decision-request-000009",
                "decision_type": "submit_shooting_declaration",
                "actor_id": "player_1",
                "proposal_kind": "shooting_declaration",
            },
        ),
    )
