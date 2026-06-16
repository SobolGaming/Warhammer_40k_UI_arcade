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
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientStatus,
    UiDecision,
    UiEventDelta,
    UiFiniteOption,
    UiGameView,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft


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


def test_finite_submission_transition_focuses_new_highlighted_unit() -> None:
    follow_up_decision = _guardian_first_unit_selection_decision()
    core_client = FakeCoreClient(
        status=UiClientStatus(
            stage="battle",
            status_kind="waiting_for_decision",
            decision=follow_up_decision,
            payload=None,
        ),
        view=_game_view(follow_up_decision),
        event_delta=UiEventDelta(
            viewer_player_id="player_1",
            cursor=0,
            next_cursor=1,
            events=(
                {
                    "event_type": "decision_recorded",
                    "payload": {"player_id": "player_1"},
                },
            ),
        ),
    )
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=default_battlefield_view(),
        preferences=default_preferences(),
        pending_decision=_unit_selection_decision(),
        core_client=core_client,
    )
    driver = GuiTestDriver(window=window, core_client=core_client)
    try:
        driver.click_world((7.0, 18.0))

        assert driver.selected_unit_id == "intercessor_squad"
        assert driver.highlighted_finite_option_id == "intercessor"

        driver.press_key(arcade.key.ENTER)

        assert driver.highlighted_finite_option_id == "guardian"
        assert driver.selected_unit_id == "guardian_squad"
        assert driver.selected_model_id is None
    finally:
        driver.close()


def test_finite_submission_actor_handoff_refreshes_with_next_actor_view() -> None:
    follow_up_decision = replace(
        _guardian_first_unit_selection_decision(),
        actor_id="player_2",
    )
    redacted_follow_up_decision = replace(follow_up_decision, options=())
    core_client = FakeCoreClient(
        status=UiClientStatus(
            stage="battle",
            status_kind="waiting_for_decision",
            decision=follow_up_decision,
            payload=None,
        ),
        view_by_player_id={
            "player_1": _game_view(
                redacted_follow_up_decision,
                viewer_player_id="player_1",
            ),
            "player_2": _game_view(
                follow_up_decision,
                viewer_player_id="player_2",
            ),
        },
        event_delta_by_player_id={
            "player_2": UiEventDelta(
                viewer_player_id="player_2",
                cursor=0,
                next_cursor=1,
                events=(
                    {
                        "event_type": "decision_requested",
                        "payload": {"player_id": "player_2"},
                    },
                ),
            )
        },
    )
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=default_battlefield_view(),
        preferences=default_preferences(),
        pending_decision=_unit_selection_decision(),
        core_client=core_client,
        viewer_player_id="player_1",
    )
    driver = GuiTestDriver(window=window, core_client=core_client)
    try:
        driver.click_world((7.0, 18.0))

        assert driver.selected_unit_id == "intercessor_squad"
        assert driver.highlighted_finite_option_id == "intercessor"

        driver.press_key(arcade.key.ENTER)

        assert driver.window.viewer_player_id == "player_2"
        assert core_client.view_requests == ["player_2"]
        assert core_client.event_delta_requests == [(0, "player_2")]
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


def test_confirm_restarts_parameterized_movement_draft_after_cancel(
    driver: GuiTestDriver,
) -> None:
    driver.click_world((7.0, 18.0))
    driver.press_key(arcade.key.ENTER)

    assert driver.pending_decision_type == "submit_movement_proposal"
    assert _movement_draft(driver) is not None

    finite_submission_count = len(driver.finite_submissions)
    driver.press_key(arcade.key.ESCAPE)

    assert _movement_draft(driver) is None

    driver.press_key(arcade.key.ENTER)

    assert len(driver.finite_submissions) == finite_submission_count
    assert driver.pending_decision_type == "submit_movement_proposal"
    assert _movement_draft(driver) is not None
    assert driver.finite_status_kind == "waiting_for_decision"


def test_confirm_for_parameterized_movement_with_unrelated_selection_does_not_start_draft(
    driver: GuiTestDriver,
) -> None:
    driver.click_world((7.0, 18.0))
    driver.press_key(arcade.key.ENTER)
    driver.press_key(arcade.key.ESCAPE)
    driver.click_world((53.0, 18.0))

    assert driver.selected_unit_id == "guardian_squad"
    assert _movement_draft(driver) is None

    driver.press_key(arcade.key.ENTER)

    assert _movement_draft(driver) is None
    assert driver.finite_status_kind == "invalid"
    assert driver.window.finite_state.diagnostics[0].violation_code == "no_movement_draft"


def test_invalid_movement_submission_returns_ready_draft_to_preview(
    driver: GuiTestDriver,
) -> None:
    assert isinstance(driver.core_client, FakeCoreClient)
    fake_client = driver.core_client
    driver.click_world((7.0, 18.0))
    driver.press_key(arcade.key.ENTER)
    driver.click_world((10.0, 18.0))
    driver.press_key(arcade.key.ENTER)

    draft = _movement_draft(driver)
    assert draft is not None
    assert draft.is_ready
    pending_decision = driver.window.pending_decision
    assert pending_decision is not None
    fake_client.movement_status = UiClientStatus.invalid(
        stage="battle",
        violation_code="path_validation_failed",
        message="Path witness final pose overlaps another model.",
        field="witness",
        payload={"invalid_reason": "path_validation_failed"},
        decision=pending_decision,
    )
    fake_client.movement_view_from_payload = None
    fake_client.movement_view = fake_client.view
    fake_client.movement_event_delta = UiEventDelta(
        viewer_player_id="player_1",
        cursor=1,
        next_cursor=1,
        events=(),
    )

    driver.press_key(arcade.key.ENTER)

    assert len(driver.movement_submissions) == 1
    draft = _movement_draft(driver)
    assert draft is not None
    assert not draft.is_ready
    assert driver.finite_status_kind == "invalid"

    driver.press_key(arcade.key.ENTER)

    assert len(driver.movement_submissions) == 1
    draft = _movement_draft(driver)
    assert draft is not None
    assert draft.is_ready


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
        assert driver.window.viewer_player_id == "player-a"
        assert driver.pending_decision_type == "select_movement_unit"
        assert driver.battlefield_unit_ids == (
            "army-alpha:scout-redeploy-unit",
            "army-beta:scout-redeploy-unit",
        )

        unit_id = "army-alpha:scout-redeploy-unit"
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
            "army-alpha:scout-redeploy-unit:core-intercessor-like:001",
        )
        assert not driver.movement_draft_ready
    finally:
        driver.close()


def test_player_units_roster_button_selects_matching_battlefield_unit() -> None:
    driver = GuiTestDriver.launch(core_mode="live_core_smoke")
    try:
        driver.window.on_draw()
        roster_button = next(
            region
            for region in driver.hud_button_hit_regions
            if region.action_kind == "select_unit"
            and region.unit_id == "army-alpha:scout-redeploy-unit"
        )
        center_x = round((roster_button.bounds[0] + roster_button.bounds[2]) / 2.0)
        center_y = round((roster_button.bounds[1] + roster_button.bounds[3]) / 2.0)

        driver.click_screen(center_x, center_y)

        assert driver.selected_unit_id == "army-alpha:scout-redeploy-unit"
        assert driver.selected_model_id is None
        assert driver.highlighted_finite_option_id == "army-alpha:scout-redeploy-unit"
    finally:
        driver.close()


def test_player_units_roster_button_selects_undeployed_finite_unit_option() -> None:
    driver = GuiTestDriver.live_core_smoke(stop_at_phase="deployment")
    try:
        assert driver.viewer_player_id == "player-b"
        assert driver.pending_decision_type == "select_deployment_unit"
        assert driver.highlighted_finite_option_id == "deploy:army-beta:scout-redeploy-unit"
        assert driver.selected_unit_id == "army-beta:scout-redeploy-unit"

        driver.window.on_draw()
        roster_button = next(
            region
            for region in driver.hud_button_hit_regions
            if region.action_kind == "select_unit"
            and region.unit_id == "army-beta:scout-redeploy-unit"
        )
        center_x = round((roster_button.bounds[0] + roster_button.bounds[2]) / 2.0)
        center_y = round((roster_button.bounds[1] + roster_button.bounds[3]) / 2.0)

        driver.click_screen(center_x, center_y)

        assert driver.selected_unit_id == "army-beta:scout-redeploy-unit"
        assert driver.selected_model_id is None
        assert driver.highlighted_finite_option_id == "deploy:army-beta:scout-redeploy-unit"

        driver.press_key(arcade.key.ENTER)

        assert driver.pending_decision_type == "submit_deployment_placement"
        assert driver.window.pending_decision is not None
        assert driver.window.pending_decision.placement_proposal is not None
        assert driver.window.pending_decision.placement_proposal.unit_instance_id == (
            "army-beta:scout-redeploy-unit"
        )
        assert driver.window.placement_draft is not None
        assert driver.window.placement_draft.selected_unit_id == "army-beta:scout-redeploy-unit"
    finally:
        driver.close()


def test_next_deployment_roster_starts_synced_to_current_action_option() -> None:
    driver = GuiTestDriver.live_core_smoke(stop_at_phase="deployment")
    try:
        assert driver.pending_decision_type == "select_deployment_unit"
        assert driver.highlighted_finite_option_id == "deploy:army-beta:scout-redeploy-unit"
        assert driver.selected_unit_id == "army-beta:scout-redeploy-unit"

        driver.press_key(arcade.key.ENTER)

        assert driver.pending_decision_type == "submit_deployment_placement"
        assert driver.window.placement_draft is not None

        for point in (
            (56.0, 7.0),
            (56.0, 8.6),
            (56.0, 10.2),
            (54.4, 7.8),
            (54.4, 9.4),
        ):
            driver.click_world(point)

        assert driver.window.placement_draft is not None
        assert driver.window.placement_draft.unplaced_model_count == 0

        driver.press_key(arcade.key.ENTER)

        assert driver.window.placement_draft is not None
        assert driver.window.placement_draft.is_ready

        driver.press_key(arcade.key.ENTER)

        assert driver.window.viewer_player_id == "player-a"
        assert driver.pending_decision_type == "select_deployment_unit"
        assert driver.highlighted_finite_option_id == "deploy:army-alpha:scout-redeploy-unit"
        assert driver.selected_unit_id == "army-alpha:scout-redeploy-unit"

        driver.window.on_draw()
        selected_roster_button = next(
            region
            for region in driver.hud_button_hit_regions
            if region.action_kind == "select_unit"
            and region.unit_id == "army-alpha:scout-redeploy-unit"
        )
        assert selected_roster_button.unit_id == driver.selected_unit_id
    finally:
        driver.close()


def test_manual_deployments_refresh_authoritative_projection_before_prebattle() -> None:
    driver = GuiTestDriver.live_core_smoke(stop_at_phase="deployment")
    try:
        _deploy_all_live_smoke_units(driver)

        assert driver.pending_decision_type == "resolve_sequencing_order"
        assert driver.battlefield_unit_ids == (
            "army-alpha:scout-redeploy-unit",
            "army-beta:scout-redeploy-unit",
        )
        assert driver.finite_status_kind == "waiting_for_decision"
    finally:
        driver.close()


def test_player_units_roster_scroll_region_consumes_wheel_without_zooming() -> None:
    driver = GuiTestDriver.launch(core_mode="live_core_smoke")
    try:
        driver.window.on_draw()
        roster_region = next(
            region
            for region in driver.hud_scroll_hit_regions
            if region.component_id == "player_units_roster"
        )
        center_x = round((roster_region.bounds[0] + roster_region.bounds[2]) / 2.0)
        center_y = round((roster_region.bounds[1] + roster_region.bounds[3]) / 2.0)
        original_zoom = driver.window.camera.zoom

        driver.scroll_screen(center_x, center_y, scroll_y=-1.0)

        assert driver.window.camera.zoom == original_zoom
    finally:
        driver.close()


_LIVE_SMOKE_DEPLOYMENT_POINTS: dict[str, tuple[tuple[float, float], ...]] = {
    "army-beta:scout-redeploy-unit": (
        (56.0, 7.0),
        (56.0, 8.6),
        (56.0, 10.2),
        (54.4, 7.8),
        (54.4, 9.4),
    ),
    "army-alpha:scout-redeploy-unit": (
        (4.0, 7.0),
        (4.0, 8.6),
        (4.0, 10.2),
        (5.6, 7.8),
        (5.6, 9.4),
    ),
}


def _deploy_all_live_smoke_units(driver: GuiTestDriver) -> None:
    for _ in range(len(_LIVE_SMOKE_DEPLOYMENT_POINTS)):
        assert driver.pending_decision_type == "select_deployment_unit"
        unit_id = driver.selected_unit_id
        assert unit_id is not None
        _deploy_current_live_smoke_unit(driver, unit_id)
    assert driver.pending_decision_type == "resolve_sequencing_order"


def _deploy_current_live_smoke_unit(driver: GuiTestDriver, unit_id: str) -> None:
    driver.press_key(arcade.key.ENTER)

    assert driver.pending_decision_type == "submit_deployment_placement"
    assert driver.window.placement_draft is not None
    assert driver.window.placement_draft.selected_unit_id == unit_id

    for point in _LIVE_SMOKE_DEPLOYMENT_POINTS[unit_id]:
        driver.click_world(point)

    assert driver.window.placement_draft is not None
    assert driver.window.placement_draft.unplaced_model_count == 0

    driver.press_key(arcade.key.ENTER)

    assert driver.window.placement_draft is not None
    assert driver.window.placement_draft.is_ready

    driver.press_key(arcade.key.ENTER)

    assert driver.window.placement_history == ()


def _pending_payload(driver: GuiTestDriver) -> JsonObject:
    decision = driver.window.pending_decision
    assert decision is not None
    return cast(JsonObject, decision.payload)


def _movement_draft(driver: GuiTestDriver) -> MovementDraft | None:
    return driver.window.movement_draft


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


def _guardian_first_unit_selection_decision() -> UiDecision:
    return UiDecision(
        request_id="decision-request-select-unit-follow-up",
        decision_type="select_target_unit",
        actor_id="player_1",
        payload={"phase": "test"},
        options=(
            UiFiniteOption(
                option_id="guardian",
                label="Guardians",
                payload={"unit_instance_id": "guardian_squad"},
            ),
            UiFiniteOption(
                option_id="intercessor",
                label="Intercessors",
                payload={"unit_instance_id": "intercessor_squad"},
            ),
        ),
        is_parameterized=False,
    )


def _game_view(
    pending_decision: UiDecision | None,
    *,
    viewer_player_id: str = "player_1",
) -> UiGameView:
    return UiGameView(
        viewer_player_id=viewer_player_id,
        game_id="finite-focus-test-game",
        stage="battle",
        battle_round=1,
        active_player_id=viewer_player_id,
        current_setup_step=None,
        current_battle_phase="movement",
        player_ids=("player_1", "player_2"),
        battlefield_state=None,
        mission_setup=None,
        public_secondary_mission_choices=(),
        public_secondary_mission_card_states=(),
        public_command_point_ledgers=(),
        public_victory_point_ledgers=(),
        public_stratagem_use_records=(),
        pending_decision=pending_decision,
        pending_proposal=None,
        event_count=1,
    )
