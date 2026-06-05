"""Event-harness tests for player-facing Arcade window workflows."""

from __future__ import annotations

from collections.abc import Iterator

import arcade
import pytest

from tests.support.gui_driver import GuiTestDriver


@pytest.fixture
def driver() -> Iterator[GuiTestDriver]:
    harness = GuiTestDriver.phase6_debug()
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
