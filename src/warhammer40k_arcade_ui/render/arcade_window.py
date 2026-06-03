"""Arcade window for the inspectable battlefield milestone."""

from __future__ import annotations

import arcade

from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.render.camera import WorldCamera, WorldPoint
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.render.primitives import (
    CirclePrimitive,
    PolygonPrimitive,
    RenderPrimitive,
    TextPrimitive,
    build_hud_primitives,
    build_world_primitives,
)
from warhammer40k_arcade_ui.render.view_models import BattlefieldView

MOUSE_ZOOM_BASE = 1.12


class ArcadeWarhammerWindow(arcade.Window):
    """Arcade window that renders a read-only battlefield projection."""

    def __init__(
        self,
        *,
        config: AppConfig | None = None,
        battlefield_view: BattlefieldView | None = None,
    ) -> None:
        resolved_config = config or AppConfig()
        super().__init__(
            width=resolved_config.window_width,
            height=resolved_config.window_height,
            title=resolved_config.title,
            resizable=resolved_config.resizable,
        )
        self.background_color = arcade.color.DARK_SLATE_GRAY
        self._battlefield_view = battlefield_view or default_battlefield_view()
        self._camera = WorldCamera.fit_table(
            viewport_width_px=resolved_config.window_width,
            viewport_height_px=resolved_config.window_height,
            table_width=self._battlefield_view.table.width,
            table_height=self._battlefield_view.table.height,
        )
        self._mouse_world_position: WorldPoint | None = None

    @property
    def camera(self) -> WorldCamera:
        """Current world camera."""

        return self._camera

    @property
    def mouse_world_position(self) -> WorldPoint | None:
        """Last mouse position converted into table coordinates."""

        return self._mouse_world_position

    def on_draw(self) -> None:
        """Render the battlefield and fixed HUD."""

        self.clear()
        world_primitives = build_world_primitives(self._battlefield_view)
        hud_primitives = build_hud_primitives(
            view=self._battlefield_view,
            viewport_width_px=self.width,
            viewport_height_px=self.height,
            mouse_world_position=self._mouse_world_position,
        )
        _draw_world_primitives(world_primitives, self._camera)
        _draw_text_primitives(hud_primitives, self._camera)

    def on_resize(self, width: int, height: int) -> None:
        """Keep camera viewport dimensions aligned with the Arcade window."""

        super().on_resize(width, height)
        self._camera = self._camera.resize_viewport(width_px=width, height_px=height)

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        """Track table coordinates under the mouse for debug display."""

        del dx, dy
        self._mouse_world_position = self._camera.screen_to_world((float(x), float(y)))

    def on_mouse_drag(
        self,
        x: int,
        y: int,
        dx: int,
        dy: int,
        buttons: int,
        modifiers: int,
    ) -> None:
        """Pan the camera with right- or middle-button drag."""

        del modifiers
        pan_buttons = arcade.MOUSE_BUTTON_RIGHT | arcade.MOUSE_BUTTON_MIDDLE
        if buttons & pan_buttons:
            self._camera = self._camera.pan_screen(float(dx), float(dy))
            self._mouse_world_position = self._camera.screen_to_world((float(x), float(y)))

    def on_mouse_scroll(self, x: int, y: int, scroll_x: float, scroll_y: float) -> None:
        """Zoom the camera around the mouse cursor."""

        del scroll_x
        if scroll_y == 0.0:
            return
        self._camera = self._camera.zoom_at_screen_point(
            multiplier=MOUSE_ZOOM_BASE**scroll_y,
            screen_point=(float(x), float(y)),
        )
        self._mouse_world_position = self._camera.screen_to_world((float(x), float(y)))


def _draw_world_primitives(
    primitives: tuple[RenderPrimitive, ...],
    camera: WorldCamera,
) -> None:
    for primitive in primitives:
        if type(primitive) is PolygonPrimitive:
            _draw_polygon_primitive(primitive, camera)
        elif type(primitive) is CirclePrimitive:
            _draw_circle_primitive(primitive, camera)
        elif type(primitive) is TextPrimitive:
            _draw_text_primitive(primitive, camera)


def _draw_text_primitives(
    primitives: tuple[TextPrimitive, ...],
    camera: WorldCamera,
) -> None:
    for primitive in primitives:
        _draw_text_primitive(primitive, camera)


def _draw_polygon_primitive(primitive: PolygonPrimitive, camera: WorldCamera) -> None:
    points = tuple(
        _screen_point(point, primitive.coordinate_space, camera) for point in primitive.points
    )
    if primitive.fill_color[3] > 0:
        arcade.draw_polygon_filled(points, primitive.fill_color)
    arcade.draw_polygon_outline(points, primitive.outline_color, primitive.line_width)


def _draw_circle_primitive(primitive: CirclePrimitive, camera: WorldCamera) -> None:
    center_x, center_y = _screen_point(primitive.center, primitive.coordinate_space, camera)
    radius = (
        primitive.radius
        if primitive.coordinate_space == "screen"
        else primitive.radius * camera.zoom
    )
    if primitive.fill_color[3] > 0:
        arcade.draw_circle_filled(center_x, center_y, radius, primitive.fill_color)
    arcade.draw_circle_outline(
        center_x,
        center_y,
        radius,
        primitive.outline_color,
        primitive.line_width,
    )


def _draw_text_primitive(primitive: TextPrimitive, camera: WorldCamera) -> None:
    x, y = _screen_point(primitive.position, primitive.coordinate_space, camera)
    arcade.draw_text(
        primitive.text,
        x,
        y,
        primitive.color,
        font_size=primitive.font_size,
        anchor_x=primitive.anchor_x,
        anchor_y=primitive.anchor_y,
    )


def _screen_point(
    point: WorldPoint,
    coordinate_space: str,
    camera: WorldCamera,
) -> tuple[float, float]:
    if coordinate_space == "world":
        return camera.world_to_screen(point)
    return point
