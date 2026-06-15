"""Event-harness tests for player-facing Arcade window workflows."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from typing import cast

import arcade
import pytest

from tests.support.gui_driver import GuiTestDriver
from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.fake_client import FakeCoreClient
from warhammer40k_arcade_ui.core_client.protocol import JsonObject, UiDecision, UiFiniteOption
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view


@pytest.fixture
def driver() -> Iterator[GuiTestDriver]:
    harness = GuiTestDriver.launch(core_mode="phase6_debug")
    try:
        yield harness
    finally:
        harness.close()


def test_click_world_selects_model(driver: GuiTestDriver) -> None:
    driver.click_world((7.0, 18.0))

    assert driver.selected_unit_id == "intercessor_squad"
    assert driver.selected_model_id == "intercessor_1"
    assert "selected_model" in driver.active_overlay_ids
    assert "selected_unit" in driver.active_overlay_ids


def test_hotkey_opens_and_cancel_closes_selected_unit_actions(
    driver: GuiTestDriver,
) -> None:
    driver.click_world((7.0, 18.0))
    driver.press_key(arcade.key.SPACE)
    driver.release_key(arcade.key.SPACE)

    assert driver.context_menu_visible
    assert tuple(action.option_id for action in driver.context_menu_actions) == (
        "normal_move",
        "advance",
    )

    driver.press_key(arcade.key.ESCAPE)

    assert not driver.context_menu_visible


def test_keyboard_confirm_submits_highlighted_finite_option(
    driver: GuiTestDriver,
) -> None:
    driver.click_world((7.0, 18.0))

    assert driver.highlighted_finite_option_id == "normal_move"

    driver.press_key(arcade.key.ENTER)

    assert driver.finite_submissions[0].request_id == "decision-request-phase6-debug-000001"
    assert driver.finite_submissions[0].selected_option_id == "normal_move"
    assert driver.finite_submissions[0].result_id == "ui-result-000001"
    assert driver.pending_decision_type == "submit_movement_proposal"
    assert driver.pending_proposal_kind == "normal_move"
    assert driver.movement_selected_model_ids == ("intercessor_1",)
    assert not driver.movement_draft_ready


def test_hud_finite_option_button_click_updates_highlight_without_battlefield_selection(
    driver: GuiTestDriver,
) -> None:
    driver.click_world((7.0, 18.0))

    assert driver.selected_unit_id == "intercessor_squad"
    assert driver.selected_model_id == "intercessor_1"
    assert driver.highlighted_finite_option_id == "normal_move"

    driver.window.on_draw()
    advance_button = next(
        region for region in driver.hud_button_hit_regions if region.option_id == "advance"
    )
    center_x = round((advance_button.bounds[0] + advance_button.bounds[2]) / 2.0)
    center_y = round((advance_button.bounds[1] + advance_button.bounds[3]) / 2.0)

    driver.click_screen(center_x, center_y)

    assert driver.highlighted_finite_option_id == "advance"
    assert driver.selected_unit_id == "intercessor_squad"
    assert driver.selected_model_id == "intercessor_1"


def test_hud_finite_option_button_click_focuses_matching_projected_unit() -> None:
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=default_battlefield_view(),
        preferences=default_preferences(),
        pending_decision=_unit_selection_decision(),
    )
    driver = GuiTestDriver(window=window)
    try:
        driver.window.on_draw()
        guardian_button = next(
            region for region in driver.hud_button_hit_regions if region.option_id == "guardian"
        )
        center_x = round((guardian_button.bounds[0] + guardian_button.bounds[2]) / 2.0)
        center_y = round((guardian_button.bounds[1] + guardian_button.bounds[3]) / 2.0)

        driver.click_screen(center_x, center_y)

        assert driver.highlighted_finite_option_id == "guardian"
        assert driver.selected_unit_id == "guardian_squad"
        assert driver.selected_model_id is None
    finally:
        driver.close()


def test_keyboard_cycle_finite_option_focuses_matching_projected_unit() -> None:
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=default_battlefield_view(),
        preferences=default_preferences(),
        pending_decision=_unit_selection_decision(),
    )
    driver = GuiTestDriver(window=window)
    try:
        driver.press_key(arcade.key.TAB)

        assert driver.highlighted_finite_option_id == "guardian"
        assert driver.selected_unit_id == "guardian_squad"
        assert driver.selected_model_id is None
    finally:
        driver.close()


def test_fake_fixture_confirm_without_pending_decision_is_noop() -> None:
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=default_battlefield_view(),
        preferences=default_preferences(),
    )
    driver = GuiTestDriver(window=window)
    try:
        driver.click_world((7.0, 18.0))

        assert driver.selected_unit_id == "intercessor_squad"
        assert driver.pending_decision_type is None

        driver.press_key(arcade.key.ENTER)

        assert driver.pending_decision_type is None
        assert driver.finite_status_kind == "idle"
        assert driver.window.finite_state.diagnostics == ()
    finally:
        driver.close()


def test_movement_workflow_marks_ready_survives_hover_and_submits(
    driver: GuiTestDriver,
) -> None:
    driver.click_world((7.0, 18.0))
    driver.press_key(arcade.key.ENTER)
    driver.click_world((10.0, 18.0))

    assert driver.movement_assigned_model_count == 1
    assert driver.movement_unchanged_model_count == 2
    assert not driver.movement_draft_ready

    driver.press_key(arcade.key.ENTER)

    ready_payload = driver.movement_payload
    assert ready_payload is not None
    assert driver.movement_payload == ready_payload

    driver.move_mouse_world((14.0, 18.0))
    driver.step_frames(2)

    assert driver.movement_payload == ready_payload

    driver.press_key(arcade.key.ENTER)

    assert driver.movement_submissions[0].request_id == "decision-request-phase6-debug-000002"
    assert driver.movement_submissions[0].payload == ready_payload
    assert driver.pending_decision_type is None
    assert not driver.movement_payload_ready
    assert driver.finite_status_message == "Debug movement accepted."


def test_movement_submission_flags_unsupported_projection_shape(
    driver: GuiTestDriver,
) -> None:
    assert isinstance(driver.core_client, FakeCoreClient)
    fake_client = driver.core_client
    base_view = fake_client.view
    assert base_view is not None
    driver.click_world((7.0, 18.0))
    driver.press_key(arcade.key.ENTER)
    driver.click_world((10.0, 18.0))
    driver.press_key(arcade.key.ENTER)
    fake_client.movement_view_from_payload = lambda _payload: replace(
        base_view,
        battlefield_state={"unknown": []},
    )

    driver.press_key(arcade.key.ENTER)

    assert driver.finite_status_kind == "fatal"
    assert driver.window.finite_state.diagnostics[0].violation_code == "fatal_game_engine_error"
    assert "Unsupported battlefield_state projection shape" in (
        driver.window.finite_state.diagnostics[0].message
    )


def test_driver_live_core_smoke_click_unit_opens_actions_and_starts_movement_draft() -> None:
    driver = GuiTestDriver.launch(core_mode="live_core_smoke")
    try:
        assert driver.core_mode == "live_core_smoke"
        assert driver.viewer_player_id == "player-a"
        assert driver.pending_decision_type == "select_movement_unit"
        assert driver.battlefield_unit_ids == (
            "army-alpha:intercessor-unit-1",
            "army-alpha:intercessor-unit-3",
            "army-beta:intercessor-unit-2",
            "army-beta:intercessor-unit-4",
        )

        unit_id = "army-alpha:intercessor-unit-3"
        unit_position = driver.first_model_position_for_unit(unit_id)
        driver.click_world(unit_position)

        assert driver.selected_unit_id == unit_id
        assert driver.highlighted_finite_option_id == unit_id

        driver.press_key(arcade.key.ENTER)

        assert driver.pending_decision_type == "select_movement_action"
        assert _pending_payload(driver)["unit_instance_id"] == unit_id
        assert driver.finite_status_kind == "waiting_for_decision"

        driver.press_key(arcade.key.SPACE)

        assert driver.context_menu_visible
        assert tuple(action.option_id for action in driver.context_menu_actions) == (
            "advance",
            "normal_move",
            "remain_stationary",
        )

        driver.press_key(arcade.key.ESCAPE)

        assert driver.highlighted_finite_option_id == "advance"

        driver.press_key(arcade.key.TAB)

        assert driver.highlighted_finite_option_id == "normal_move"

        driver.click_world(unit_position)

        assert driver.selected_unit_id == unit_id
        assert driver.highlighted_finite_option_id == "normal_move"

        driver.press_key(arcade.key.ENTER)

        assert driver.pending_decision_type == "submit_movement_proposal"
        assert driver.pending_proposal_kind == "normal_move"
        assert driver.selected_unit_id == unit_id
        assert driver.movement_selected_model_ids == (
            "army-alpha:intercessor-unit-3:core-intercessor-like:001",
        )
        assert not driver.movement_draft_ready
    finally:
        driver.close()


def _pending_payload(driver: GuiTestDriver) -> JsonObject:
    decision = driver.window.pending_decision
    assert decision is not None
    return cast(JsonObject, decision.payload)


def _unit_selection_decision() -> UiDecision:
    return UiDecision(
        request_id="decision-request-select-unit",
        decision_type="select_target_unit",
        actor_id="player_1",
        payload={"phase": "test"},
        options=(
            UiFiniteOption(
                option_id="intercessor",
                label="Intercessors",
                payload={"unit_instance_id": "intercessor_squad"},
            ),
            UiFiniteOption(
                option_id="guardian",
                label="Guardians",
                payload={"unit_instance_id": "guardian_squad"},
            ),
        ),
        is_parameterized=False,
    )
