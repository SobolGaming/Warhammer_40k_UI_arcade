"""Headless framebuffer evidence tests for rendered GUI frames."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import arcade
import pytest

from tests.support.gui_driver import GuiTestDriver
from tests.support.render_capture import (
    RenderCapture,
    RenderEvidenceError,
    assert_color_present,
    assert_region_has_non_background,
)
from warhammer40k_arcade_ui.hud.layouts import ScreenRect, build_hud_layout
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.primitives import (
    HUD_TEXT,
    MOVEMENT_ACTIVE,
    PLAYER_1_COLOR,
    TABLE_FILL,
)


@pytest.fixture
def driver() -> Iterator[GuiTestDriver]:
    harness = GuiTestDriver.launch(core_mode="phase6_debug")
    try:
        yield harness
    finally:
        harness.close()


def test_headless_capture_renders_fake_fixture_world_and_hud(
    driver: GuiTestDriver,
    tmp_path: Path,
) -> None:
    capture = driver.capture_frame(source_name="phase13-fake-fixture")

    capture.assert_nonblank(
        min_non_background_pixels=50_000,
        artifact_name="fake-fixture-nonblank",
        artifact_dir=tmp_path,
    )
    assert_color_present(
        capture,
        color=TABLE_FILL,
        min_pixels=100_000,
        artifact_name="fake-fixture-table",
        artifact_dir=tmp_path,
    )
    assert_color_present(
        capture,
        color=PLAYER_1_COLOR,
        min_pixels=700,
        artifact_name="fake-fixture-player-one",
        artifact_dir=tmp_path,
    )
    assert_color_present(
        capture,
        color=HUD_TEXT,
        min_pixels=150,
        artifact_name="fake-fixture-hud-text",
        artifact_dir=tmp_path,
        region=(0, driver.window.height - 180, 560, 180),
    )
    objective_region = _region_around(driver.screen_for_world((30.0, 22.0)), radius_px=48)
    assert_region_has_non_background(
        capture,
        region=objective_region,
        min_non_background_pixels=400,
        artifact_name="fake-fixture-objective-region",
        artifact_dir=tmp_path,
    )
    artifact_paths = capture.save_artifacts(
        artifact_name="fake-fixture-success",
        artifact_dir=tmp_path,
        metadata={"scenario": "phase13 fake fixture success capture"},
    )

    assert artifact_paths.image_path.exists()
    assert artifact_paths.metadata_path.exists()


def test_headless_capture_renders_hud_zone_panel_shells(
    driver: GuiTestDriver,
    tmp_path: Path,
) -> None:
    capture = driver.capture_frame(source_name="phase19-hud-zone-panels")
    layout = build_hud_layout(
        preferences=default_preferences(),
        viewport_width_px=driver.window.width,
        viewport_height_px=driver.window.height,
    )
    left_rail = layout.region("left_rail")
    assert left_rail is not None

    assert_region_has_non_background(
        capture,
        region=_region_from_rect(left_rail.rect.inset(24.0)),
        min_non_background_pixels=20_000,
        artifact_name="hud-zone-left-rail-panel-shell",
        artifact_dir=tmp_path,
    )


def test_headless_capture_renders_movement_overlay_after_event_driver_actions(
    driver: GuiTestDriver,
    tmp_path: Path,
) -> None:
    driver.click_world((7.0, 18.0))
    driver.press_key(arcade.key.ENTER)
    driver.click_world((10.0, 18.0))

    capture = driver.capture_frame(source_name="phase13-movement-draft")

    capture.assert_nonblank(
        min_non_background_pixels=50_000,
        artifact_name="movement-draft-nonblank",
        artifact_dir=tmp_path,
    )
    assert_color_present(
        capture,
        color=MOVEMENT_ACTIVE,
        min_pixels=100,
        artifact_name="movement-draft-active-overlay",
        artifact_dir=tmp_path,
    )
    endpoint_region = _region_around(driver.screen_for_world((10.0, 18.0)), radius_px=40)
    assert_region_has_non_background(
        capture,
        region=endpoint_region,
        min_non_background_pixels=400,
        artifact_name="movement-draft-endpoint-region",
        artifact_dir=tmp_path,
    )


def test_headless_capture_renders_live_core_smoke_projection(tmp_path: Path) -> None:
    driver = GuiTestDriver.launch(core_mode="live_core_smoke")
    try:
        capture = driver.capture_frame(source_name="phase13-live-core-smoke")
        capture.assert_nonblank(
            min_non_background_pixels=50_000,
            artifact_name="live-core-smoke-nonblank",
            artifact_dir=tmp_path,
        )
        first_model_region = _region_around(
            driver.screen_for_world(
                driver.first_model_position_for_unit("army-alpha:scout-redeploy-unit")
            ),
            radius_px=40,
        )
        assert_region_has_non_background(
            capture,
            region=first_model_region,
            min_non_background_pixels=100,
            artifact_name="live-core-smoke-first-model-region",
            artifact_dir=tmp_path,
        )
    finally:
        driver.close()


def test_render_capture_reports_all_black_readback_with_artifacts(tmp_path: Path) -> None:
    capture = RenderCapture.blank(width=8, height=8, source_name="synthetic-black")

    with pytest.raises(RenderEvidenceError, match="all-black buffer") as exc_info:
        capture.assert_nonblank(
            min_non_background_pixels=1,
            artifact_name="synthetic-black-failure",
            artifact_dir=tmp_path,
        )

    assert "synthetic-black-failure.png" in str(exc_info.value)
    assert (tmp_path / "synthetic-black-failure.png").exists()
    assert (tmp_path / "synthetic-black-failure.json").exists()


def _region_around(screen_point: tuple[int, int], *, radius_px: int) -> tuple[int, int, int, int]:
    x, y = screen_point
    return (x - radius_px, y - radius_px, radius_px * 2, radius_px * 2)


def _region_from_rect(rect: ScreenRect) -> tuple[int, int, int, int]:
    return (round(rect.x), round(rect.y), round(rect.width), round(rect.height))
