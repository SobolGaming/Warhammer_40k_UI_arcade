"""A real Heroic Intervention can be chosen and submitted from headless HUD input."""

from __future__ import annotations

from typing import cast

from warhammer40k_core.adapters.local_session import LocalGameSession

from tests.support.contract42_charge_fixture import SOURCE, seeded_heroic_client
from tests.support.gui_driver import GuiTestDriver
from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.protocol import JsonObject
from warhammer40k_arcade_ui.hud.toolkit import HudButtonHitRegion
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow
from warhammer40k_arcade_ui.render.core_projection import battlefield_view_from_game_view


def test_hud_selects_source_mode_for_selected_friendly_unit_and_submits() -> None:
    client = seeded_heroic_client()
    status = client.advance_until_decision_or_terminal()
    request = status.decision
    assert request is not None
    assert request.decision_type == "submit_stratagem_target_proposal"
    view = client.get_view("player-a")
    battlefield = battlefield_view_from_game_view(view)
    source = next(unit for unit in battlefield.units if unit.unit_id == SOURCE)
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=battlefield,
        preferences=default_preferences(),
        initial_status=status,
        initial_game_view=view,
        core_client=client,
        viewer_player_id="player-a",
    )
    driver = GuiTestDriver(window=window, core_client=client, viewer_player_id="player-a")
    try:
        workspace = driver.window.assignment_workspace
        assert workspace is not None
        assert not workspace.is_ready
        assert workspace.stratagem_mode_choices == ("leap_to_defend", "into_the_fray")

        driver.window.on_draw()
        driver.click_world(source.models[0].position)
        assert driver.selected_unit_id == SOURCE
        _click_action(
            driver,
            "assignment_select",
            option_id=f"stratagem-mode:{request.request_id}:into_the_fray",
        )
        chosen = driver.window.assignment_workspace
        assert chosen is not None
        assert chosen.is_ready
        assert chosen.payload_preview is not None
        proposal = cast(JsonObject, chosen.payload_preview["proposal"])
        assert proposal["target_binding"] == {
            "target_kind": "friendly_unit",
            "target_player_id": "player-a",
            "target_unit_instance_id": SOURCE,
        }
        assert proposal["effect_selection"] == {"mode": "into_the_fray"}

        _click_action(driver, "assignment_submit")
        assert driver.finite_status_kind != "invalid"
        assert driver.window.pending_decision is not None
        assert driver.window.pending_decision.decision_type == "select_charging_unit"
        assert driver.window.pending_decision.actor_id == "player-a"
        session = client.session
        assert isinstance(session, LocalGameSession)
        state = session.lifecycle.state
        assert state is not None
        assert state.active_player_id == "player-b"
        assert state.command_point_total("player-a") == 1
    finally:
        driver.close()


def _click_action(
    driver: GuiTestDriver, action_kind: str, *, option_id: str | None = None
) -> HudButtonHitRegion:
    driver.window.on_draw()
    region = next(
        region
        for region in driver.hud_button_hit_regions
        if region.action_kind == action_kind
        and region.enabled
        and (option_id is None or region.option_id == option_id)
    )
    x = round((region.bounds[0] + region.bounds[2]) / 2.0)
    y = round((region.bounds[1] + region.bounds[3]) / 2.0)
    driver.click_screen(x, y)
    return region
