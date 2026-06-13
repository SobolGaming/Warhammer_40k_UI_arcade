"""Tests for configurable HUD zone layouts."""

from __future__ import annotations

from dataclasses import replace

from warhammer40k_arcade_ui.hud.layouts import (
    MIN_CENTER_VIEWPORT_HEIGHT_PX,
    MIN_CENTER_VIEWPORT_WIDTH_PX,
    build_hud_layout,
)
from warhammer40k_arcade_ui.preferences.defaults import (
    command_bench_preferences,
    default_preferences,
)
from warhammer40k_arcade_ui.preferences.schema import HudZonePreference


def test_compass_ring_layout_reserves_four_edge_zones_and_center_viewport() -> None:
    layout = build_hud_layout(
        preferences=default_preferences(),
        viewport_width_px=1280,
        viewport_height_px=800,
    )

    assert layout.preset_id == "compass_ring"
    assert layout.display_label == "Compass Ring"
    assert {region.zone_id for region in layout.regions} == {
        "top_ribbon",
        "left_rail",
        "right_inspector",
        "bottom_workbench",
    }
    assert layout.center_viewport.width == 780.0
    assert layout.center_viewport.height == 560.0
    assert layout.region("left_rail") is not None
    assert layout.region("right_inspector") is not None


def test_command_bench_layout_reserves_player_opponent_and_command_bench_zones() -> None:
    layout = build_hud_layout(
        preferences=command_bench_preferences(),
        viewport_width_px=1280,
        viewport_height_px=800,
    )

    assert layout.preset_id == "command_bench"
    assert layout.display_label == "Command Bench"
    assert {region.zone_id for region in layout.regions} == {
        "top_ribbon",
        "left_player_bench",
        "right_opponent_bench",
        "bottom_command_bench",
    }
    assert layout.region("bottom_command_bench") is not None
    assert layout.center_viewport.width == 800.0
    assert layout.center_viewport.height == 496.0


def test_layout_scales_oversized_zones_to_preserve_center_viewport() -> None:
    preferences = default_preferences()
    oversized = tuple(
        replace(zone, size_px=999)
        if zone.zone_id in {"left_rail", "right_inspector", "bottom_workbench", "top_ribbon"}
        else zone
        for zone in preferences.hud.zones
    )
    preferences = replace(preferences, hud=replace(preferences.hud, zones=oversized))

    layout = build_hud_layout(
        preferences=preferences,
        viewport_width_px=640,
        viewport_height_px=480,
    )

    assert layout.center_viewport.width >= MIN_CENTER_VIEWPORT_WIDTH_PX
    assert layout.center_viewport.height >= MIN_CENTER_VIEWPORT_HEIGHT_PX


def test_collapsed_zone_keeps_small_visible_socket() -> None:
    preferences = default_preferences()
    collapsed = tuple(
        HudZonePreference(
            zone_id=zone.zone_id,
            visible=zone.visible,
            size_px=zone.size_px,
            collapsed=zone.zone_id == "left_rail",
        )
        for zone in preferences.hud.zones
    )
    preferences = replace(preferences, hud=replace(preferences.hud, zones=collapsed))

    layout = build_hud_layout(
        preferences=preferences,
        viewport_width_px=1280,
        viewport_height_px=800,
    )

    left_rail = layout.region("left_rail")
    assert left_rail is not None
    assert left_rail.collapsed is True
    assert left_rail.rect.width == 32.0
