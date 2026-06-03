"""Pure render primitive generation for battlefield view models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from warhammer40k_arcade_ui.render.camera import WorldPoint
from warhammer40k_arcade_ui.render.view_models import BattlefieldView, UnitView

type Color = tuple[int, int, int, int]
type CoordinateSpace = Literal["world", "screen"]
type RenderPrimitive = PolygonPrimitive | CirclePrimitive | TextPrimitive

PLAYER_1_COLOR: Color = (80, 155, 235, 255)
PLAYER_2_COLOR: Color = (235, 110, 95, 255)
NEUTRAL_STEEL: Color = (152, 165, 176, 255)
TABLE_FILL: Color = (37, 49, 44, 255)
TABLE_OUTLINE: Color = (214, 219, 207, 255)
DEPLOYMENT_ALPHA = 62


@dataclass(frozen=True, slots=True)
class PolygonPrimitive:
    """Polygon primitive in either world or screen coordinates."""

    layer: str
    points: tuple[WorldPoint, ...]
    fill_color: Color
    outline_color: Color
    line_width: float
    coordinate_space: CoordinateSpace = "world"


@dataclass(frozen=True, slots=True)
class CirclePrimitive:
    """Circle primitive in either world or screen coordinates."""

    layer: str
    center: WorldPoint
    radius: float
    fill_color: Color
    outline_color: Color
    line_width: float
    coordinate_space: CoordinateSpace = "world"


@dataclass(frozen=True, slots=True)
class TextPrimitive:
    """Text primitive in either world or screen coordinates."""

    layer: str
    text: str
    position: WorldPoint
    color: Color
    font_size: float
    coordinate_space: CoordinateSpace
    anchor_x: Literal["left", "center", "right"] = "left"
    anchor_y: Literal["baseline", "center", "top"] = "baseline"


def build_world_primitives(view: BattlefieldView) -> tuple[RenderPrimitive, ...]:
    """Build deterministic world-space primitives from a battlefield view model."""

    primitives: list[RenderPrimitive] = [
        PolygonPrimitive(
            layer="table_bounds",
            points=(
                (0.0, 0.0),
                (view.table.width, 0.0),
                (view.table.width, view.table.height),
                (0.0, view.table.height),
            ),
            fill_color=TABLE_FILL,
            outline_color=TABLE_OUTLINE,
            line_width=2.0,
        ),
    ]
    primitives.extend(_deployment_zone_primitives(view))
    primitives.extend(_objective_primitives(view))
    primitives.extend(_terrain_primitives(view))
    primitives.extend(_unit_primitives(view))
    return tuple(primitives)


def build_hud_primitives(
    *,
    view: BattlefieldView,
    viewport_width_px: int,
    viewport_height_px: int,
    mouse_world_position: WorldPoint | None,
) -> tuple[TextPrimitive, ...]:
    """Build screen-space HUD primitives that remain fixed during camera movement."""

    del viewport_width_px
    top_y = viewport_height_px - 24.0
    event_text = " | ".join(view.hud.event_log_lines)
    lines = (
        f"Phase: {view.hud.phase_label}",
        f"Active: {view.hud.active_player_id}",
        f"Pending: {view.hud.pending_decision_summary}",
        f"Events: {event_text}",
    )
    primitives = [
        TextPrimitive(
            layer="hud",
            text=line,
            position=(16.0, top_y - (index * 22.0)),
            color=(238, 241, 233, 255),
            font_size=13.0,
            coordinate_space="screen",
        )
        for index, line in enumerate(lines)
    ]
    if mouse_world_position is not None:
        primitives.append(
            TextPrimitive(
                layer="hud_debug",
                text=(f"Mouse: {mouse_world_position[0]:.2f}, {mouse_world_position[1]:.2f} in"),
                position=(16.0, 18.0),
                color=(255, 222, 135, 255),
                font_size=12.0,
                coordinate_space="screen",
            )
        )
    return tuple(primitives)


def _deployment_zone_primitives(view: BattlefieldView) -> tuple[RenderPrimitive, ...]:
    primitives: list[RenderPrimitive] = []
    for zone in view.deployment_zones:
        if not zone.visible:
            continue
        player_color = _player_color(zone.player_id)
        primitives.append(
            PolygonPrimitive(
                layer="deployment_zone",
                points=zone.polygon,
                fill_color=(player_color[0], player_color[1], player_color[2], DEPLOYMENT_ALPHA),
                outline_color=player_color,
                line_width=1.0,
            )
        )
        primitives.append(
            TextPrimitive(
                layer="deployment_zone_label",
                text=zone.label,
                position=_centroid(zone.polygon),
                color=player_color,
                font_size=11.0,
                coordinate_space="world",
                anchor_x="center",
                anchor_y="center",
            )
        )
    return tuple(primitives)


def _objective_primitives(view: BattlefieldView) -> tuple[RenderPrimitive, ...]:
    primitives: list[RenderPrimitive] = []
    for objective in view.objectives:
        primitives.append(
            CirclePrimitive(
                layer="objective",
                center=objective.position,
                radius=objective.radius,
                fill_color=(236, 188, 72, 54),
                outline_color=(236, 188, 72, 255),
                line_width=1.25,
            )
        )
        primitives.append(
            TextPrimitive(
                layer="objective_label",
                text=objective.label,
                position=objective.position,
                color=(255, 245, 205, 255),
                font_size=12.0,
                coordinate_space="world",
                anchor_x="center",
                anchor_y="center",
            )
        )
    return tuple(primitives)


def _terrain_primitives(view: BattlefieldView) -> tuple[RenderPrimitive, ...]:
    primitives: list[RenderPrimitive] = []
    for terrain in view.terrain:
        primitives.append(
            PolygonPrimitive(
                layer="terrain",
                points=terrain.footprint,
                fill_color=(122, 127, 107, 180),
                outline_color=(194, 198, 171, 255),
                line_width=1.0,
            )
        )
        primitives.append(
            TextPrimitive(
                layer="terrain_label",
                text=terrain.label,
                position=_centroid(terrain.footprint),
                color=(237, 236, 214, 255),
                font_size=10.0,
                coordinate_space="world",
                anchor_x="center",
                anchor_y="center",
            )
        )
    return tuple(primitives)


def _unit_primitives(view: BattlefieldView) -> tuple[RenderPrimitive, ...]:
    primitives: list[RenderPrimitive] = []
    for unit in view.units:
        player_color = _player_color(unit.player_id)
        center = _unit_center(unit)
        primitives.append(
            CirclePrimitive(
                layer="unit_token",
                center=center,
                radius=1.1,
                fill_color=(player_color[0], player_color[1], player_color[2], 180),
                outline_color=(248, 250, 246, 255),
                line_width=1.0,
            )
        )
        primitives.append(
            TextPrimitive(
                layer="unit_label",
                text=unit.label,
                position=(center[0], center[1] + 1.7),
                color=(248, 250, 246, 255),
                font_size=10.0,
                coordinate_space="world",
                anchor_x="center",
                anchor_y="center",
            )
        )
        for model in unit.models:
            primitives.append(
                CirclePrimitive(
                    layer="model_base",
                    center=model.position,
                    radius=model.base_radius,
                    fill_color=(22, 25, 27, 230),
                    outline_color=player_color,
                    line_width=1.25,
                )
            )
    return tuple(primitives)


def _player_color(player_id: str) -> Color:
    if player_id == "player_1":
        return PLAYER_1_COLOR
    if player_id == "player_2":
        return PLAYER_2_COLOR
    return NEUTRAL_STEEL


def _unit_center(unit: UnitView) -> WorldPoint:
    x_total = sum(model.position[0] for model in unit.models)
    y_total = sum(model.position[1] for model in unit.models)
    return (x_total / len(unit.models), y_total / len(unit.models))


def _centroid(points: tuple[WorldPoint, ...]) -> WorldPoint:
    x_total = sum(point[0] for point in points)
    y_total = sum(point[1] for point in points)
    return (x_total / len(points), y_total / len(points))
