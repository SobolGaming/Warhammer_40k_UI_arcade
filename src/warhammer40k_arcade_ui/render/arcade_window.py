"""Arcade window for the inspectable battlefield milestone."""

from __future__ import annotations

import arcade

from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.protocol import UiDecision
from warhammer40k_arcade_ui.hud.view_models import (
    build_context_menu,
    build_debug_inspector,
    build_unit_panel,
)
from warhammer40k_arcade_ui.input.commands import command_for_key
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.preferences.diagnostics import PreferenceDiagnostic
from warhammer40k_arcade_ui.preferences.io import load_preferences
from warhammer40k_arcade_ui.preferences.schema import UiPreferences
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
from warhammer40k_arcade_ui.state.selection import SelectionState, selected_unit, unit_center

MOUSE_ZOOM_BASE = 1.12


class ArcadeWarhammerWindow(arcade.Window):
    """Arcade window that renders a read-only battlefield projection."""

    def __init__(
        self,
        *,
        config: AppConfig | None = None,
        battlefield_view: BattlefieldView | None = None,
        preferences: UiPreferences | None = None,
        pending_decision: UiDecision | None = None,
        event_cursor: int = 0,
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
        if preferences is None:
            loaded_preferences = load_preferences()
            self._preferences = loaded_preferences.preferences or default_preferences()
            self._preference_diagnostics = loaded_preferences.diagnostics
        else:
            self._preferences = preferences
            self._preference_diagnostics = ()
        self._selection_state = SelectionState.initial(self._preferences)
        self._pending_decision = pending_decision
        self._event_cursor = event_cursor
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

    @property
    def selection_state(self) -> SelectionState:
        """Current local selection state."""

        return self._selection_state

    @property
    def preference_diagnostics(self) -> tuple[PreferenceDiagnostic, ...]:
        """Diagnostics produced while loading UI preferences."""

        return self._preference_diagnostics

    def on_draw(self) -> None:
        """Render the battlefield and fixed HUD."""

        self.clear()
        unit_panel = (
            build_unit_panel(
                view=self._battlefield_view,
                selection=self._selection_state,
                pending_decision=self._pending_decision,
            )
            if self._selection_state.selected_unit_panel_visible
            else None
        )
        context_menu = build_context_menu(
            view=self._battlefield_view,
            selection=self._selection_state,
            pending_decision=self._pending_decision,
            fallback_anchor_world=self._mouse_world_position,
        )
        debug_inspector = build_debug_inspector(
            selection=self._selection_state,
            pending_decision=self._pending_decision,
            cursor_position=self._mouse_world_position,
            event_cursor=self._event_cursor,
        )
        world_primitives = build_world_primitives(self._battlefield_view, self._selection_state)
        hud_primitives = build_hud_primitives(
            view=self._battlefield_view,
            viewport_width_px=self.width,
            viewport_height_px=self.height,
            mouse_world_position=self._mouse_world_position,
            unit_panel=unit_panel,
            context_menu=context_menu,
            debug_inspector=debug_inspector,
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

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        """Select models with the configured default mouse button."""

        del modifiers
        self._mouse_world_position = self._camera.screen_to_world((float(x), float(y)))
        if _mouse_button_name(button) != self._preferences.selection.default_mouse_button:
            return
        self._selection_state = self._selection_state.select_at(
            view=self._battlefield_view,
            world_point=self._mouse_world_position,
            preferences=self._preferences,
        )

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

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        """Apply configured local UI hotkeys."""

        invocation = command_for_key(
            preferences=self._preferences,
            key=_key_name(symbol),
            modifiers=_modifier_names(modifiers),
        )
        if invocation is None:
            return
        if invocation.command_id == "toggle_debug_inspector":
            self._selection_state = self._selection_state.toggle_debug_inspector()
        elif invocation.command_id == "show_selected_unit":
            self._selection_state = self._selection_state.show_selected_unit_panel()
        elif invocation.command_id == "show_selected_model":
            self._selection_state = self._selection_state.show_selected_model_panel()
        elif invocation.command_id == "toggle_overlay" and invocation.overlay_id is not None:
            self._selection_state = self._selection_state.toggle_overlay(invocation.overlay_id)
        elif invocation.command_id == "open_selected_unit_actions":
            self._selection_state = self._selection_state.open_context_menu(
                self._context_anchor_world()
            )
        elif invocation.command_id == "cycle_selection" and self._mouse_world_position is not None:
            self._selection_state = self._selection_state.select_at(
                view=self._battlefield_view,
                world_point=self._mouse_world_position,
                preferences=self._preferences,
                force_cycle=True,
            )
        elif invocation.command_id == "cancel":
            self._selection_state = self._selection_state.close_context_menu()

    def _context_anchor_world(self) -> WorldPoint:
        if self._mouse_world_position is not None:
            return self._mouse_world_position
        unit = selected_unit(self._battlefield_view, self._selection_state)
        if unit is not None:
            return unit_center(unit)
        return (0.0, 0.0)


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


def _mouse_button_name(button: int) -> str:
    if button == arcade.MOUSE_BUTTON_LEFT:
        return "left"
    if button == arcade.MOUSE_BUTTON_RIGHT:
        return "right"
    if button == arcade.MOUSE_BUTTON_MIDDLE:
        return "middle"
    return "unknown"


def _key_name(key: int) -> str:
    special_keys = {
        arcade.key.ESCAPE: "escape",
        arcade.key.ENTER: "enter",
        arcade.key.RETURN: "enter",
        arcade.key.TAB: "tab",
        arcade.key.SPACE: "space",
        arcade.key.BACKSPACE: "backspace",
        arcade.key.DELETE: "delete",
        arcade.key.UP: "up",
        arcade.key.DOWN: "down",
        arcade.key.LEFT: "left",
        arcade.key.RIGHT: "right",
        arcade.key.PAGEUP: "pageup",
        arcade.key.PAGEDOWN: "pagedown",
        arcade.key.HOME: "home",
        arcade.key.END: "end",
        arcade.key.F1: "f1",
        arcade.key.F2: "f2",
        arcade.key.F3: "f3",
        arcade.key.F4: "f4",
        arcade.key.F5: "f5",
        arcade.key.F6: "f6",
        arcade.key.F7: "f7",
        arcade.key.F8: "f8",
        arcade.key.F9: "f9",
        arcade.key.F10: "f10",
        arcade.key.F11: "f11",
        arcade.key.F12: "f12",
    }
    if key in special_keys:
        return special_keys[key]
    if arcade.key.A <= key <= arcade.key.Z:
        return chr(key).lower()
    if ord("0") <= key <= ord("9"):
        return chr(key)
    return "unknown"


def _modifier_names(modifiers: int) -> tuple[str, ...]:
    names: list[str] = []
    if modifiers & arcade.key.MOD_CTRL:
        names.append("ctrl")
    if modifiers & arcade.key.MOD_ALT:
        names.append("alt")
    if modifiers & arcade.key.MOD_SHIFT:
        names.append("shift")
    if modifiers & arcade.key.MOD_COMMAND:
        names.append("meta")
    return tuple(names)
