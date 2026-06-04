"""Tests for render view models and primitive generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from warhammer40k_arcade_ui.core_client.protocol import UiDecision, UiFiniteOption
from warhammer40k_arcade_ui.hud.view_models import (
    build_context_menu,
    build_debug_inspector,
    build_finite_decision_panel,
    build_unit_panel,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.primitives import (
    CirclePrimitive,
    PolygonPrimitive,
    TextPrimitive,
    build_hud_primitives,
    build_world_primitives,
)
from warhammer40k_arcade_ui.render.view_models import BattlefieldView, RenderViewModelError
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


def test_hud_primitives_are_screen_space_and_include_mouse_coordinates() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    view = BattlefieldView.from_payload(payload)

    primitives = build_hud_primitives(
        view=view,
        viewport_width_px=1280,
        viewport_height_px=800,
        mouse_world_position=(12.345, 22.0),
    )

    assert all(primitive.coordinate_space == "screen" for primitive in primitives)
    assert primitives[0].position == (16.0, 776.0)
    assert any(primitive.text == "Pending: Select movement action" for primitive in primitives)
    assert any(primitive.text == "Mouse: 12.35, 22.00 in" for primitive in primitives)


def test_hud_primitives_include_selection_panel_menu_and_debug_inspector() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    view = BattlefieldView.from_payload(payload)
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )
    selection = selection.open_context_menu((7.0, 18.0)).toggle_debug_inspector()
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

    primitives = build_hud_primitives(
        view=view,
        viewport_width_px=1280,
        viewport_height_px=800,
        mouse_world_position=(7.0, 18.0),
        unit_panel=build_unit_panel(view=view, selection=selection, pending_decision=decision),
        context_menu=build_context_menu(
            view=view,
            selection=selection,
            pending_decision=decision,
        ),
        finite_decision_panel=build_finite_decision_panel(
            pending_decision=decision,
            highlighted_option_index=0,
            status_message="Waiting: select_movement_action",
            diagnostics=(),
        ),
        debug_inspector=build_debug_inspector(
            selection=selection,
            pending_decision=decision,
            cursor_position=(7.0, 18.0),
            event_cursor=3,
        ),
    )

    texts = [primitive.text for primitive in primitives]
    assert "Unit: Intercessors" in texts
    assert "Action: Normal Move" in texts
    assert "Actions: intercessor_squad" in texts
    assert "Decision" in texts
    assert "> Normal Move [normal_move]" in texts
    assert "Debug inspector" in texts


def test_render_view_model_rejects_incomplete_payload() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    del payload["table"]["width"]

    with pytest.raises(RenderViewModelError, match="width is required"):
        BattlefieldView.from_payload(payload)
