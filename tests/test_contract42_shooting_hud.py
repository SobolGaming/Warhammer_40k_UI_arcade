"""Headless HUD clicks edit and submit the real Contract 42 Shooting request."""

from __future__ import annotations

from typing import cast

from tests.support.contract42_battle_fixture import shooting_client
from tests.support.gui_driver import GuiTestDriver
from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import JsonObject, UiClientStatus, UiDecision
from warhammer40k_arcade_ui.hud.toolkit import HudButtonHitRegion
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow
from warhammer40k_arcade_ui.render.core_projection import battlefield_view_from_game_view


def test_hud_clear_submits_explicit_empty_declaration() -> None:
    driver, client = _shooting_driver()
    try:
        workspace = driver.window.assignment_workspace
        assert workspace is not None
        assert workspace.payload_preview is not None
        assert cast(list[object], workspace.payload_preview["declarations"])

        _click_action(driver, "assignment_clear")
        empty = driver.window.assignment_workspace
        assert empty is not None
        assert empty.payload_preview is not None
        assert empty.payload_preview["declarations"] == []

        _click_action(driver, "assignment_submit")
        assert driver.finite_status_kind != "invalid"
        refreshed = driver.window.assignment_workspace
        assert refreshed is None or refreshed.request_id != workspace.request_id
        events = client.get_events_since(0, "player-a").events
        accepted = next(
            event for event in events if event["event_type"] == "shooting_declaration_accepted"
        )
        assert cast(JsonObject, accepted["payload"])["attack_pools"] == []
        assert cast(JsonObject, accepted["payload"])["weapons_without_attacks"] == []
    finally:
        driver.close()


def test_hud_can_choose_nullable_target_from_emitted_source() -> None:
    driver, client = _shooting_driver(one_shot=True)
    try:
        workspace = driver.window.assignment_workspace
        assert workspace is not None
        assert workspace.shooting_choices
        assert any(
            choice.selection.target_unit_instance_id is None
            for choice in workspace.shooting_choices
        )
        assert workspace.payload_preview is not None
        assert len(cast(list[object], workspace.payload_preview["declarations"])) == 1

        _click_action(driver, "assignment_next_choice")
        _click_action(driver, "assignment_select")
        chosen = driver.window.assignment_workspace
        assert chosen is not None
        assert chosen.payload_preview is not None
        declarations = chosen.payload_preview["declarations"]
        assert type(declarations) is list
        assert len(declarations) == 1
        declaration = cast(JsonObject, declarations[0])
        assert declaration["target_unit_instance_id"] is None
        assert declaration["weapon_instance_id"] == (
            workspace.shooting_choices[0].selection.weapon_instance_id
        )

        _click_action(driver, "assignment_submit")
        assert driver.finite_status_kind != "invalid"
        events = client.get_events_since(0, "player-a").events
        assert any(event["event_type"] == "shooting_declaration_accepted" for event in events)
    finally:
        driver.close()


def test_hud_next_choice_reaches_second_physical_weapon_copy() -> None:
    driver, _client = _shooting_driver(copies=2)
    try:
        workspace = driver.window.assignment_workspace
        assert workspace is not None
        assert len(workspace.shooting_choices) >= 2
        copy_ids = {choice.selection.weapon_instance_id for choice in workspace.shooting_choices}
        assert len(copy_ids) == 2
        target_choice = next(
            choice
            for choice in workspace.shooting_choices
            if choice.selection.weapon_instance_id
            != workspace.shooting_choices[0].selection.weapon_instance_id
            and choice.selection.target_unit_instance_id is not None
        )

        for _ in range(len(workspace.shooting_choices)):
            driver.window.on_draw()
            visible = next(
                region
                for region in driver.hud_button_hit_regions
                if region.action_kind == "assignment_select"
            )
            if visible.option_id == target_choice.choice_id:
                break
            _click_action(driver, "assignment_next_choice")
        else:
            raise AssertionError("Second physical Shooting copy was not reachable from HUD.")
        _click_action(driver, "assignment_select")
        chosen = driver.window.assignment_workspace
        assert chosen is not None
        assert chosen.payload_preview is not None
        declarations = chosen.payload_preview["declarations"]
        assert type(declarations) is list
        assert len(declarations) == 1
        assert cast(JsonObject, declarations[0])["weapon_instance_id"] == (
            workspace.shooting_choices[0].selection.weapon_instance_id
        )
    finally:
        driver.close()


def _shooting_driver(
    *,
    copies: int = 1,
    one_shot: bool = False,
) -> tuple[GuiTestDriver, LocalSessionClient]:
    client = shooting_client(copies=copies, one_shot=one_shot)
    status = client.advance_until_decision_or_terminal()
    decision = _decision(status, "select_shooting_unit")
    status = client.submit_finite(
        request_id=decision.request_id,
        selected_option_id="army-alpha:shooter",
        result_id="hud-select-unit",
    )
    decision = _decision(status, "select_shooting_type")
    status = client.submit_finite(
        request_id=decision.request_id,
        selected_option_id="normal",
        result_id="hud-select-type",
    )
    _decision(status, "submit_shooting_declaration")
    view = client.get_view("player-a")
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=battlefield_view_from_game_view(view),
        preferences=default_preferences(),
        initial_status=status,
        initial_game_view=view,
        core_client=client,
        viewer_player_id="player-a",
    )
    return GuiTestDriver(window=window, core_client=client, viewer_player_id="player-a"), client


def _decision(status: UiClientStatus, expected_type: str) -> UiDecision:
    assert status.decision is not None
    assert status.decision.decision_type == expected_type
    return status.decision


def _click_action(driver: GuiTestDriver, action_kind: str) -> HudButtonHitRegion:
    driver.window.on_draw()
    region = next(
        region
        for region in driver.hud_button_hit_regions
        if region.action_kind == action_kind and region.enabled
    )
    x = round((region.bounds[0] + region.bounds[2]) / 2.0)
    y = round((region.bounds[1] + region.bounds[3]) / 2.0)
    driver.click_screen(x, y)
    return region
