"""Tests for render view models and primitive generation."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from warhammer40k_arcade_ui.core_client.protocol import (
    UiDecision,
    UiFiniteOption,
)
from warhammer40k_arcade_ui.hud.action_summary import (
    ActionVisualSummary,
    ActionVisualSummaryGroup,
    build_action_visual_summary,
)
from warhammer40k_arcade_ui.hud.view_models import (
    build_context_menu,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.render.primitives import (
    CirclePrimitive,
    PolygonPrimitive,
    PolylinePrimitive,
    RenderPrimitive,
    TextPrimitive,
    build_screen_overlay_primitives,
    build_world_primitives,
)
from warhammer40k_arcade_ui.render.view_models import (
    BattlefieldView,
    RenderViewModelError,
    UnitView,
)
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft
from warhammer40k_arcade_ui.state.placement_draft import PlacementDraft
from warhammer40k_arcade_ui.state.selection import SelectionState

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "phase03_battlefield_view.json"


def test_battlefield_view_loads_from_fixture_payload() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    view = BattlefieldView.from_payload(payload)

    assert view.table.width == 60.0
    assert view.table.height == 44.0
    assert len(view.deployment_zones) == 2
    assert len(view.objectives) == 2
    assert len(view.terrain) == 1
    assert len(view.units) == 2
    assert view.units[0].models[0].model_id == "intercessor_1"


def test_fixture_payload_builds_expected_world_primitives() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    view = BattlefieldView.from_payload(payload)

    primitives = build_world_primitives(view)

    polygon_layers = [
        primitive.layer for primitive in primitives if type(primitive) is PolygonPrimitive
    ]
    circle_layers = [
        primitive.layer for primitive in primitives if type(primitive) is CirclePrimitive
    ]
    text_layers = [primitive.layer for primitive in primitives if type(primitive) is TextPrimitive]

    assert polygon_layers.count("table_bounds") == 1
    assert polygon_layers.count("deployment_zone") == 2
    assert polygon_layers.count("terrain") == 1
    assert circle_layers.count("objective") == 2
    assert circle_layers.count("unit_token") == 2
    assert circle_layers.count("model_base") == 4
    assert "unit_label" in text_layers


def test_selected_unit_builds_selection_overlay_primitives() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    view = BattlefieldView.from_payload(payload)
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )

    primitives = build_world_primitives(view, selection)

    circle_layers = [
        primitive.layer for primitive in primitives if type(primitive) is CirclePrimitive
    ]
    assert "selected_unit_overlay" in circle_layers
    assert "selected_model_overlay" in circle_layers


def test_movement_draft_builds_path_waypoint_ghost_and_budget_primitives() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )
    selection = selection.with_movement_draft_overlays(preferences)
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=_movement_proposal_decision(),
    )
    assert draft is not None
    draft = draft.add_waypoint(view=view, world_point=(10.0, 18.0))

    primitives = build_world_primitives(view, selection, draft)

    line_layers = [
        primitive.layer for primitive in primitives if type(primitive) is PolylinePrimitive
    ]
    circle_layers = [
        primitive.layer for primitive in primitives if type(primitive) is CirclePrimitive
    ]
    text_layers = [primitive.layer for primitive in primitives if type(primitive) is TextPrimitive]
    assert line_layers.count("movement_path") == 1
    assert circle_layers.count("movement_active_model_overlay") == 1
    assert circle_layers.count("movement_unassigned_model_overlay") == 2
    assert circle_layers.count("movement_ghost_base") == 1
    assert "movement_waypoint" in circle_layers
    assert "movement_budget_ring" in circle_layers
    assert "movement_waypoint_label" not in text_layers


def test_placement_draft_builds_ghost_primitives_without_labels() -> None:
    view = default_battlefield_view()
    draft = PlacementDraft.start_for_pending(
        view=view,
        selection=SelectionState.initial(default_preferences()),
        pending_decision=_placement_proposal_decision(),
    )
    assert draft is not None
    draft = draft.place_current_model((8.0, 18.0))

    primitives = build_world_primitives(view, placement_draft=draft)

    circle_layers = [
        primitive.layer for primitive in primitives if type(primitive) is CirclePrimitive
    ]
    text_layers = [primitive.layer for primitive in primitives if type(primitive) is TextPrimitive]
    assert "placement_placed_ghost_base" in circle_layers
    assert "placement_current_ghost_base" not in circle_layers
    assert not any(layer.startswith("placement_") for layer in text_layers)


def test_action_visual_summary_builds_dim_path_and_ghost_primitives() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=selection,
        pending_decision=_movement_proposal_decision(),
    )
    assert draft is not None
    draft = draft.add_waypoint(view=view, world_point=(10.0, 18.0))
    summary = build_action_visual_summary(
        movement_draft=draft,
        pending_decision=_movement_proposal_decision(),
        diagnostics=(),
        intensity="dim",
        max_labels=6,
    )
    assert summary is not None

    primitives = build_world_primitives(view, action_summary=summary)

    line_layers = [
        primitive.layer for primitive in primitives if type(primitive) is PolylinePrimitive
    ]
    circle_layers = [
        primitive.layer for primitive in primitives if type(primitive) is CirclePrimitive
    ]
    assert "action_summary_dim_path" in line_layers
    assert "action_summary_dim_ghost_base" in circle_layers


def test_action_visual_summary_review_mode_labels_are_capped() -> None:
    view = default_battlefield_view()
    summary = ActionVisualSummary(
        request_id="decision-request-000005",
        operation_kind="movement",
        intensity="review",
        groups=(
            _summary_group("group-1", "first", (7.0, 18.0), (10.0, 18.0)),
            _summary_group("group-2", "second", (7.0, 22.0), (10.0, 22.0)),
        ),
        diagnostic_lines=(),
        ready=True,
        max_labels=1,
    )

    primitives = build_world_primitives(view, action_summary=summary)

    review_labels = [
        primitive.text
        for primitive in _text_primitives(primitives)
        if primitive.layer == "action_summary_review_label"
    ]
    assert review_labels == ["first"]


def test_screen_overlay_primitives_are_empty_without_transient_overlays() -> None:
    primitives = build_screen_overlay_primitives()

    assert primitives == ()


def test_screen_overlay_primitives_include_context_menu_without_legacy_panels() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    view = BattlefieldView.from_payload(payload)
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )
    selection = selection.open_context_menu((7.0, 18.0))
    decision = UiDecision(
        request_id="decision-request-000004",
        decision_type="select_movement_action",
        actor_id="player_1",
        payload={"unit_instance_id": "intercessor_squad"},
        options=(
            UiFiniteOption(
                option_id="normal_move",
                label="Normal Move",
                payload={"movement_phase_action": "normal_move"},
            ),
        ),
        is_parameterized=False,
    )

    primitives = build_screen_overlay_primitives(
        context_menu=build_context_menu(
            view=view,
            selection=selection,
            pending_decision=decision,
        ),
    )

    texts = _text_lines(primitives)
    assert "Actions: intercessor_squad" in texts
    assert "Normal Move" in texts
    assert "Unit: Intercessors" not in texts
    assert "Decision" not in texts
    assert "Debug inspector" not in texts


def test_battlefield_view_refreshes_matching_core_runtime_model_positions() -> None:
    view = default_battlefield_view()

    refreshed = view.refreshed_from_projection(
        battlefield_state={
            "battlefield_id": "battlefield-1",
            "placed_armies": [
                {
                    "army_id": "army-player-1",
                    "player_id": "player_1",
                    "unit_placements": [
                        {
                            "army_id": "army-player-1",
                            "player_id": "player_1",
                            "unit_instance_id": "intercessor_squad",
                            "model_placements": [
                                {
                                    "army_id": "army-player-1",
                                    "player_id": "player_1",
                                    "unit_instance_id": "intercessor_squad",
                                    "model_instance_id": "intercessor_1",
                                    "pose": {
                                        "position": {"x": 10.0, "y": 18.0, "z": 0.0},
                                        "facing": {"degrees": 0.0},
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
            "removed_model_ids": [],
        },
        phase_label="movement",
        active_player_id="player_1",
        pending_decision_summary="No pending engine decision",
        event_log_lines=("movement_proposal_accepted: player_1",),
    )

    intercessors = next(unit for unit in refreshed.units if unit.unit_id == "intercessor_squad")
    moved_model = next(model for model in intercessors.models if model.model_id == "intercessor_1")
    unchanged_model = next(
        model for model in intercessors.models if model.model_id == "intercessor_2"
    )
    assert moved_model.position == (10.0, 18.0)
    assert unchanged_model.position == (7.0, 22.0)
    assert refreshed.hud.event_log_lines == ("movement_proposal_accepted: player_1",)


def test_battlefield_view_refreshes_from_render_payload_shape() -> None:
    view = default_battlefield_view()
    moved_unit = replace(
        view.units[0],
        models=(
            replace(view.units[0].models[0], position=(11.0, 18.0)),
            *view.units[0].models[1:],
        ),
    )
    render_payload = {
        "table": {
            "width": view.table.width,
            "height": view.table.height,
            "label": view.table.label,
        },
        "deployment_zones": [
            {
                "zone_id": zone.zone_id,
                "player_id": zone.player_id,
                "label": zone.label,
                "polygon": list(zone.polygon),
                "visible": zone.visible,
            }
            for zone in view.deployment_zones
        ],
        "objectives": [
            {
                "objective_id": objective.objective_id,
                "label": objective.label,
                "position": objective.position,
                "radius": objective.radius,
            }
            for objective in view.objectives
        ],
        "terrain": [
            {
                "terrain_id": terrain.terrain_id,
                "label": terrain.label,
                "footprint": list(terrain.footprint),
            }
            for terrain in view.terrain
        ],
        "units": [
            _unit_payload(moved_unit),
            *(_unit_payload(unit) for unit in view.units[1:]),
        ],
        "hud": {
            "phase_label": "fixture phase",
            "active_player_id": "player_1",
            "pending_decision_summary": "fixture pending",
            "event_log_lines": ["fixture event"],
        },
    }

    refreshed = view.refreshed_from_projection(
        battlefield_state=render_payload,
        phase_label="movement",
        active_player_id="player_1",
        pending_decision_summary="No pending engine decision",
        event_log_lines=("movement_proposal_accepted: player_1",),
    )

    intercessors = next(unit for unit in refreshed.units if unit.unit_id == "intercessor_squad")
    moved_model = next(model for model in intercessors.models if model.model_id == "intercessor_1")
    assert moved_model.position == (11.0, 18.0)
    assert refreshed.hud.phase_label == "movement"
    assert refreshed.hud.pending_decision_summary == "No pending engine decision"


def test_battlefield_view_refresh_keeps_geometry_for_absent_projection_state() -> None:
    view = default_battlefield_view()

    refreshed = view.refreshed_from_projection(
        battlefield_state=None,
        phase_label="movement",
        active_player_id="player_1",
        pending_decision_summary="No pending engine decision",
        event_log_lines=("status refresh",),
    )

    assert refreshed.units == view.units
    assert refreshed.hud.phase_label == "movement"
    assert refreshed.hud.event_log_lines == ("status refresh",)


def test_battlefield_view_refresh_rejects_unsupported_projection_shape() -> None:
    view = default_battlefield_view()

    with pytest.raises(
        RenderViewModelError,
        match=r"Unsupported battlefield_state projection shape: object keys=\['unknown'\]",
    ):
        view.refreshed_from_projection(
            battlefield_state={"unknown": []},
            phase_label="movement",
            active_player_id="player_1",
            pending_decision_summary="No pending engine decision",
            event_log_lines=("status refresh",),
        )


def test_render_view_model_rejects_incomplete_payload() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    del payload["table"]["width"]

    with pytest.raises(RenderViewModelError, match="width is required"):
        BattlefieldView.from_payload(payload)


def _unit_payload(unit: UnitView) -> dict[str, object]:
    return {
        "unit_id": unit.unit_id,
        "player_id": unit.player_id,
        "label": unit.label,
        "models": [
            {
                "model_id": model.model_id,
                "label": model.label,
                "position": model.position,
                "base_radius": model.base_radius,
            }
            for model in unit.models
        ],
    }


def _summary_group(
    group_id: str,
    label: str,
    start: tuple[float, float],
    end: tuple[float, float],
) -> ActionVisualSummaryGroup:
    return ActionVisualSummaryGroup(
        group_id=group_id,
        label=label,
        state="assigned",
        source_ref_keys=(f"model:{label}",),
        target_ref_keys=(),
        path_points=(start, end),
        ghost_center=end,
        ghost_radius=1.0,
        icon_id=None,
        color_role="movement",
        summary_lines=("Path: 3.00 in",),
    )


def _movement_proposal_decision() -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": "decision-request-000005",
            "decision_type": "submit_movement_proposal",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-000005",
                    "decision_type": "submit_movement_proposal",
                    "actor_id": "player_1",
                    "game_id": "phase7-game",
                    "battle_round": 1,
                    "phase": "movement",
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": "normal_move",
                    "source_decision_request_id": "decision-request-000004",
                    "source_decision_result_id": "ui-result-000001",
                    "movement_phase_action": "normal_move",
                    "placement_kinds": [],
                    "context": {
                        "source_selected_option_id": "normal_move",
                        "movement_mode": "normal",
                        "movement_budget_inches": 6.0,
                    },
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


def _placement_proposal_decision() -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": "decision-request-placement-001",
            "decision_type": "submit_placement_proposal",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-placement-001",
                    "decision_type": "submit_placement_proposal",
                    "actor_id": "player_1",
                    "game_id": "phase28-game",
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": "reinforcement_placement",
                    "source_decision_request_id": "decision-request-unit-001",
                    "source_decision_result_id": "ui-result-unit-001",
                    "placement_kinds": ["reinforcement"],
                    "context": {"placement_kind": "reinforcement"},
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


def _text_primitives(primitives: tuple[RenderPrimitive, ...]) -> tuple[TextPrimitive, ...]:
    return tuple(primitive for primitive in primitives if type(primitive) is TextPrimitive)


def _text_lines(primitives: tuple[RenderPrimitive, ...]) -> list[str]:
    return [primitive.text for primitive in _text_primitives(primitives)]
