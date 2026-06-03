"""Tests for world camera coordinate transforms."""

from __future__ import annotations

import math

from warhammer40k_arcade_ui.render.camera import WorldCamera


def test_camera_round_trips_world_and_screen_coordinates() -> None:
    camera = WorldCamera.fit_table(
        viewport_width_px=1280,
        viewport_height_px=800,
        table_width=60.0,
        table_height=44.0,
    )

    screen_point = camera.world_to_screen((18.5, 31.25))
    world_point = camera.screen_to_world(screen_point)

    assert _point_is_close(world_point, (18.5, 31.25))


def test_camera_clamps_zoom_limits() -> None:
    low_zoom_camera = WorldCamera(
        viewport_width_px=640,
        viewport_height_px=480,
        center_x=30.0,
        center_y=22.0,
        zoom=1.0,
        min_zoom=4.0,
        max_zoom=12.0,
    )
    high_zoom_camera = WorldCamera(
        viewport_width_px=640,
        viewport_height_px=480,
        center_x=30.0,
        center_y=22.0,
        zoom=30.0,
        min_zoom=4.0,
        max_zoom=12.0,
    )

    assert low_zoom_camera.zoom == 4.0
    assert high_zoom_camera.zoom == 12.0


def test_zoom_at_screen_point_preserves_world_coordinate_under_cursor() -> None:
    camera = WorldCamera(
        viewport_width_px=1280,
        viewport_height_px=800,
        center_x=30.0,
        center_y=22.0,
        zoom=14.0,
        min_zoom=4.0,
        max_zoom=96.0,
    )
    screen_point = (820.0, 510.0)
    world_before = camera.screen_to_world(screen_point)

    zoomed_camera = camera.zoom_at_screen_point(multiplier=1.75, screen_point=screen_point)

    assert _point_is_close(zoomed_camera.screen_to_world(screen_point), world_before)


def test_pan_screen_moves_camera_without_distorting_scale() -> None:
    camera = WorldCamera(
        viewport_width_px=1280,
        viewport_height_px=800,
        center_x=30.0,
        center_y=22.0,
        zoom=10.0,
    )

    panned_camera = camera.pan_screen(20.0, -30.0)

    assert math.isclose(panned_camera.center_x, 28.0)
    assert math.isclose(panned_camera.center_y, 25.0)
    assert panned_camera.zoom == 10.0


def _point_is_close(
    actual: tuple[float, float],
    expected: tuple[float, float],
) -> bool:
    return math.isclose(actual[0], expected[0]) and math.isclose(actual[1], expected[1])
