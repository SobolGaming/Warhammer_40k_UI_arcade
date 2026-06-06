"""Configurable HUD zone layout view models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from warhammer40k_arcade_ui.preferences.schema import (
    HudPreferences,
    HudZonePreference,
    UiPreferences,
)

type HudZoneId = Literal[
    "top_ribbon",
    "left_rail",
    "right_inspector",
    "bottom_workbench",
    "left_player_bench",
    "right_opponent_bench",
    "bottom_command_bench",
]

COLLAPSED_ZONE_SIZE_PX = 32.0
MIN_CENTER_VIEWPORT_WIDTH_PX = 360.0
MIN_CENTER_VIEWPORT_HEIGHT_PX = 220.0


@dataclass(frozen=True, slots=True)
class ScreenRect:
    """A screen-space rectangle using Arcade's bottom-left origin."""

    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        """Right edge in screen pixels."""

        return self.x + self.width

    @property
    def top(self) -> float:
        """Top edge in screen pixels."""

        return self.y + self.height

    @property
    def is_visible(self) -> bool:
        """Return whether the rectangle has drawable area."""

        return self.width > 0.0 and self.height > 0.0

    def inset(self, amount: float) -> ScreenRect:
        """Return a rectangle inset on all sides, never below zero dimensions."""

        inset_width = max(0.0, self.width - (amount * 2.0))
        inset_height = max(0.0, self.height - (amount * 2.0))
        return ScreenRect(
            x=self.x + amount,
            y=self.y + amount,
            width=inset_width,
            height=inset_height,
        )

    def line_capacity(self, *, line_height_px: float, top_padding_px: float = 18.0) -> int:
        """Return how many text rows fit in the rectangle."""

        if line_height_px <= 0.0:
            raise ValueError("line_height_px must be positive")
        usable_height = max(0.0, self.height - top_padding_px)
        return max(1, int(usable_height // line_height_px))


@dataclass(frozen=True, slots=True)
class HudRegionView:
    """One named HUD region that can host future panel/widget content."""

    zone_id: str
    label: str
    content_key: str
    rect: ScreenRect
    collapsed: bool
    clips_overflow: bool = True


@dataclass(frozen=True, slots=True)
class HudLayoutView:
    """A resolved HUD layout for the current window size."""

    preset_id: str
    display_label: str
    viewport_width_px: int
    viewport_height_px: int
    center_viewport: ScreenRect
    regions: tuple[HudRegionView, ...]

    def region(self, zone_id: str) -> HudRegionView | None:
        """Return the resolved region for a zone ID, if visible in this preset."""

        for region in self.regions:
            if region.zone_id == zone_id:
                return region
        return None


def build_hud_layout(
    *,
    preferences: UiPreferences,
    viewport_width_px: int,
    viewport_height_px: int,
) -> HudLayoutView:
    """Resolve the active HUD layout preset for the current viewport."""

    if viewport_width_px <= 0:
        raise ValueError("viewport_width_px must be positive")
    if viewport_height_px <= 0:
        raise ValueError("viewport_height_px must be positive")
    hud = preferences.hud
    if hud.layout_preset == "command_bench":
        return _command_bench_layout(
            hud=hud,
            viewport_width_px=viewport_width_px,
            viewport_height_px=viewport_height_px,
        )
    return _compass_ring_layout(
        hud=hud,
        viewport_width_px=viewport_width_px,
        viewport_height_px=viewport_height_px,
    )


def _compass_ring_layout(
    *,
    hud: HudPreferences,
    viewport_width_px: int,
    viewport_height_px: int,
) -> HudLayoutView:
    top_size, bottom_size = _reserve_pair(
        total_size=float(viewport_height_px),
        first_size=_zone_size(hud, "top_ribbon"),
        second_size=_zone_size(hud, "bottom_workbench"),
        minimum_center_size=MIN_CENTER_VIEWPORT_HEIGHT_PX,
    )
    left_size, right_size = _reserve_pair(
        total_size=float(viewport_width_px),
        first_size=_zone_size(hud, "left_rail"),
        second_size=_zone_size(hud, "right_inspector"),
        minimum_center_size=MIN_CENTER_VIEWPORT_WIDTH_PX,
    )
    center = ScreenRect(
        x=left_size,
        y=bottom_size,
        width=max(0.0, float(viewport_width_px) - left_size - right_size),
        height=max(0.0, float(viewport_height_px) - top_size - bottom_size),
    )
    regions = _visible_regions(
        (
            _region(
                hud=hud,
                zone_id="top_ribbon",
                label="Top ribbon",
                content_key="placeholder.score_phase_missions",
                rect=ScreenRect(
                    x=0.0,
                    y=float(viewport_height_px) - top_size,
                    width=float(viewport_width_px),
                    height=top_size,
                ),
            ),
            _region(
                hud=hud,
                zone_id="left_rail",
                label="Army rolodex rail",
                content_key="placeholder.unit_rail",
                rect=ScreenRect(0.0, bottom_size, left_size, center.height),
            ),
            _region(
                hud=hud,
                zone_id="right_inspector",
                label="Inspector panel",
                content_key="placeholder.selected_unit_inspector",
                rect=ScreenRect(
                    float(viewport_width_px) - right_size,
                    bottom_size,
                    right_size,
                    center.height,
                ),
            ),
            _region(
                hud=hud,
                zone_id="bottom_workbench",
                label="Action workbench",
                content_key="placeholder.action_workbench",
                rect=ScreenRect(0.0, 0.0, float(viewport_width_px), bottom_size),
            ),
        )
    )
    return HudLayoutView(
        preset_id="compass_ring",
        display_label="Compass Ring",
        viewport_width_px=viewport_width_px,
        viewport_height_px=viewport_height_px,
        center_viewport=center,
        regions=regions,
    )


def _command_bench_layout(
    *,
    hud: HudPreferences,
    viewport_width_px: int,
    viewport_height_px: int,
) -> HudLayoutView:
    top_size, bottom_size = _reserve_pair(
        total_size=float(viewport_height_px),
        first_size=_zone_size(hud, "top_ribbon"),
        second_size=_zone_size(hud, "bottom_command_bench"),
        minimum_center_size=MIN_CENTER_VIEWPORT_HEIGHT_PX,
    )
    left_size, right_size = _reserve_pair(
        total_size=float(viewport_width_px),
        first_size=_zone_size(hud, "left_player_bench"),
        second_size=_zone_size(hud, "right_opponent_bench"),
        minimum_center_size=MIN_CENTER_VIEWPORT_WIDTH_PX,
    )
    center = ScreenRect(
        x=left_size,
        y=bottom_size,
        width=max(0.0, float(viewport_width_px) - left_size - right_size),
        height=max(0.0, float(viewport_height_px) - top_size - bottom_size),
    )
    regions = _visible_regions(
        (
            _region(
                hud=hud,
                zone_id="top_ribbon",
                label="Compact top ribbon",
                content_key="placeholder.score_phase_timer",
                rect=ScreenRect(
                    x=0.0,
                    y=float(viewport_height_px) - top_size,
                    width=float(viewport_width_px),
                    height=top_size,
                ),
            ),
            _region(
                hud=hud,
                zone_id="left_player_bench",
                label="Player bench",
                content_key="placeholder.player_roster_missions",
                rect=ScreenRect(0.0, bottom_size, left_size, center.height),
            ),
            _region(
                hud=hud,
                zone_id="right_opponent_bench",
                label="Opponent bench",
                content_key="placeholder.opponent_roster_missions",
                rect=ScreenRect(
                    float(viewport_width_px) - right_size,
                    bottom_size,
                    right_size,
                    center.height,
                ),
            ),
            _region(
                hud=hud,
                zone_id="bottom_command_bench",
                label="Command bench",
                content_key="placeholder.command_bench",
                rect=ScreenRect(0.0, 0.0, float(viewport_width_px), bottom_size),
            ),
        )
    )
    return HudLayoutView(
        preset_id="command_bench",
        display_label="Command Bench",
        viewport_width_px=viewport_width_px,
        viewport_height_px=viewport_height_px,
        center_viewport=center,
        regions=regions,
    )


def _visible_regions(regions: tuple[HudRegionView, ...]) -> tuple[HudRegionView, ...]:
    return tuple(region for region in regions if region.rect.is_visible)


def _region(
    *,
    hud: HudPreferences,
    zone_id: HudZoneId,
    label: str,
    content_key: str,
    rect: ScreenRect,
) -> HudRegionView:
    zone = _zone(hud, zone_id)
    return HudRegionView(
        zone_id=zone_id,
        label=label,
        content_key=content_key,
        rect=rect,
        collapsed=zone.collapsed,
    )


def _zone_size(hud: HudPreferences, zone_id: HudZoneId) -> float:
    zone = _zone(hud, zone_id)
    if not zone.visible:
        return 0.0
    if zone.collapsed:
        return COLLAPSED_ZONE_SIZE_PX
    return float(max(0, zone.size_px))


def _zone(hud: HudPreferences, zone_id: HudZoneId) -> HudZonePreference:
    for zone in hud.zones:
        if zone.zone_id == zone_id:
            return zone
    raise ValueError(f"HUD preferences are missing zone: {zone_id}")


def _reserve_pair(
    *,
    total_size: float,
    first_size: float,
    second_size: float,
    minimum_center_size: float,
) -> tuple[float, float]:
    available_size = max(0.0, total_size - minimum_center_size)
    requested_size = first_size + second_size
    if requested_size <= available_size:
        return first_size, second_size
    if requested_size <= 0.0:
        return 0.0, 0.0
    scale = available_size / requested_size
    return first_size * scale, second_size * scale
