"""World-space camera used by the battlefield renderer."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Self

type WorldPoint = tuple[float, float]
type ScreenPoint = tuple[float, float]


@dataclass(frozen=True, slots=True)
class WorldCamera:
    """Converts between table-space inches and screen-space pixels."""

    viewport_width_px: int
    viewport_height_px: int
    center_x: float
    center_y: float
    zoom: float
    min_zoom: float = 4.0
    max_zoom: float = 96.0

    def __post_init__(self) -> None:
        if self.viewport_width_px <= 0:
            raise ValueError("viewport_width_px must be positive")
        if self.viewport_height_px <= 0:
            raise ValueError("viewport_height_px must be positive")
        _validate_finite("center_x", self.center_x)
        _validate_finite("center_y", self.center_y)
        _validate_positive("min_zoom", self.min_zoom)
        _validate_positive("max_zoom", self.max_zoom)
        if self.min_zoom > self.max_zoom:
            raise ValueError("min_zoom must be less than or equal to max_zoom")
        object.__setattr__(self, "zoom", _clamp_zoom(self.zoom, self.min_zoom, self.max_zoom))

    @classmethod
    def fit_table(
        cls,
        *,
        viewport_width_px: int,
        viewport_height_px: int,
        table_width: float,
        table_height: float,
        margin_px: float = 64.0,
        min_zoom: float = 4.0,
        max_zoom: float = 96.0,
    ) -> Self:
        """Create a camera centered on a table with a stable pixel margin."""

        _validate_positive("table_width", table_width)
        _validate_positive("table_height", table_height)
        if margin_px < 0 or not math.isfinite(margin_px):
            raise ValueError("margin_px must be finite and non-negative")
        usable_width = viewport_width_px - (margin_px * 2.0)
        usable_height = viewport_height_px - (margin_px * 2.0)
        _validate_positive("usable viewport width", usable_width)
        _validate_positive("usable viewport height", usable_height)
        fitted_zoom = min(usable_width / table_width, usable_height / table_height)
        return cls(
            viewport_width_px=viewport_width_px,
            viewport_height_px=viewport_height_px,
            center_x=table_width / 2.0,
            center_y=table_height / 2.0,
            zoom=fitted_zoom,
            min_zoom=min_zoom,
            max_zoom=max_zoom,
        )

    def world_to_screen(self, point: WorldPoint) -> ScreenPoint:
        """Convert a world-space table coordinate into a screen pixel coordinate."""

        world_x, world_y = point
        _validate_finite("world_x", world_x)
        _validate_finite("world_y", world_y)
        return (
            ((world_x - self.center_x) * self.zoom) + (self.viewport_width_px / 2.0),
            ((world_y - self.center_y) * self.zoom) + (self.viewport_height_px / 2.0),
        )

    def screen_to_world(self, point: ScreenPoint) -> WorldPoint:
        """Convert a screen pixel coordinate into world-space table inches."""

        screen_x, screen_y = point
        _validate_finite("screen_x", screen_x)
        _validate_finite("screen_y", screen_y)
        return (
            ((screen_x - (self.viewport_width_px / 2.0)) / self.zoom) + self.center_x,
            ((screen_y - (self.viewport_height_px / 2.0)) / self.zoom) + self.center_y,
        )

    def pan_screen(self, delta_x_px: float, delta_y_px: float) -> Self:
        """Move the camera by a screen-space drag delta."""

        _validate_finite("delta_x_px", delta_x_px)
        _validate_finite("delta_y_px", delta_y_px)
        return type(self)(
            viewport_width_px=self.viewport_width_px,
            viewport_height_px=self.viewport_height_px,
            center_x=self.center_x - (delta_x_px / self.zoom),
            center_y=self.center_y - (delta_y_px / self.zoom),
            zoom=self.zoom,
            min_zoom=self.min_zoom,
            max_zoom=self.max_zoom,
        )

    def zoom_at_screen_point(self, *, multiplier: float, screen_point: ScreenPoint) -> Self:
        """Zoom around a screen point while keeping its world coordinate stable."""

        _validate_positive("multiplier", multiplier)
        world_before = self.screen_to_world(screen_point)
        new_zoom = _clamp_zoom(self.zoom * multiplier, self.min_zoom, self.max_zoom)
        screen_x, screen_y = screen_point
        new_center_x = world_before[0] - ((screen_x - (self.viewport_width_px / 2.0)) / new_zoom)
        new_center_y = world_before[1] - ((screen_y - (self.viewport_height_px / 2.0)) / new_zoom)
        return type(self)(
            viewport_width_px=self.viewport_width_px,
            viewport_height_px=self.viewport_height_px,
            center_x=new_center_x,
            center_y=new_center_y,
            zoom=new_zoom,
            min_zoom=self.min_zoom,
            max_zoom=self.max_zoom,
        )

    def resize_viewport(self, *, width_px: int, height_px: int) -> Self:
        """Return a camera with a new viewport size and unchanged world center."""

        return type(self)(
            viewport_width_px=width_px,
            viewport_height_px=height_px,
            center_x=self.center_x,
            center_y=self.center_y,
            zoom=self.zoom,
            min_zoom=self.min_zoom,
            max_zoom=self.max_zoom,
        )


def _clamp_zoom(value: float, minimum: float, maximum: float) -> float:
    _validate_positive("zoom", value)
    return min(max(value, minimum), maximum)


def _validate_positive(name: str, value: float) -> None:
    if value <= 0 or not math.isfinite(value):
        raise ValueError(f"{name} must be finite and positive")


def _validate_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
