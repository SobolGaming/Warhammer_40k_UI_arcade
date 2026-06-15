"""Pure render primitive generation for battlefield view models."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from warhammer40k_arcade_ui.hud.action_summary import (
    ActionVisualSummary,
    ActionVisualSummaryGroup,
)
from warhammer40k_arcade_ui.hud.layouts import ScreenRect
from warhammer40k_arcade_ui.hud.view_models import (
    ContextMenuAction,
    ContextMenuView,
)
from warhammer40k_arcade_ui.render.camera import WorldPoint
from warhammer40k_arcade_ui.render.view_models import BattlefieldView, UnitView
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft
from warhammer40k_arcade_ui.state.selection import SelectionState, selected_model, selected_unit

type Color = tuple[int, int, int, int]
type CoordinateSpace = Literal["world", "screen"]
type RenderPrimitive = PolygonPrimitive | CirclePrimitive | PolylinePrimitive | TextPrimitive

PLAYER_1_COLOR: Color = (80, 155, 235, 255)
PLAYER_2_COLOR: Color = (235, 110, 95, 255)
NEUTRAL_STEEL: Color = (152, 165, 176, 255)
TABLE_FILL: Color = (37, 49, 44, 255)
TABLE_OUTLINE: Color = (214, 219, 207, 255)
DEPLOYMENT_ALPHA = 62
SELECTION_GOLD: Color = (255, 225, 96, 255)
SELECTION_UNIT_FILL: Color = (255, 225, 96, 28)
HUD_TEXT: Color = (238, 241, 233, 255)
HUD_ACCENT: Color = (255, 222, 135, 255)
MOVEMENT_PATH: Color = (102, 220, 180, 255)
MOVEMENT_PREVIEW: Color = (102, 220, 180, 150)
MOVEMENT_WARNING: Color = (255, 168, 94, 255)
MOVEMENT_GHOST_FILL: Color = (102, 220, 180, 54)
MOVEMENT_ACTIVE: Color = (132, 232, 255, 255)
MOVEMENT_ASSIGNED: Color = (122, 214, 156, 210)
MOVEMENT_UNASSIGNED: Color = (184, 190, 186, 135)
ACTION_SUMMARY_DIM: Color = (138, 210, 164, 105)
ACTION_SUMMARY_REVIEW: Color = (136, 245, 172, 238)
ACTION_SUMMARY_WARNING_DIM: Color = (255, 178, 92, 125)
ACTION_SUMMARY_WARNING_REVIEW: Color = (255, 191, 96, 245)
ACTION_SUMMARY_GHOST_DIM: Color = (138, 210, 164, 34)
ACTION_SUMMARY_GHOST_REVIEW: Color = (136, 245, 172, 74)


@dataclass(frozen=True, slots=True)
class PolygonPrimitive:
    """Polygon primitive in either world or screen coordinates."""

    layer: str
    points: tuple[WorldPoint, ...]
    fill_color: Color
    outline_color: Color
    line_width: float
    coordinate_space: CoordinateSpace = "world"
    clip_rect: ScreenRect | None = None


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
    clip_rect: ScreenRect | None = None


@dataclass(frozen=True, slots=True)
class PolylinePrimitive:
    """Polyline primitive in either world or screen coordinates."""

    layer: str
    points: tuple[WorldPoint, ...]
    color: Color
    line_width: float
    coordinate_space: CoordinateSpace = "world"
    clip_rect: ScreenRect | None = None


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
    clip_rect: ScreenRect | None = None


def build_world_primitives(
    view: BattlefieldView,
    selection_state: SelectionState | None = None,
    movement_draft: MovementDraft | None = None,
    action_summary: ActionVisualSummary | None = None,
) -> tuple[RenderPrimitive, ...]:
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
    if action_summary is not None:
        primitives.extend(_action_visual_summary_primitives(action_summary))
    if selection_state is not None:
        primitives.extend(_selection_primitives(view, selection_state))
        if movement_draft is not None:
            primitives.extend(_movement_draft_primitives(selection_state, movement_draft))
    return tuple(primitives)


def build_screen_overlay_primitives(
    *,
    context_menu: ContextMenuView | None = None,
) -> tuple[RenderPrimitive, ...]:
    """Build non-panel screen-space primitives that remain fixed during camera movement.

    Player-facing panel text is intentionally owned by the ergonomic HUD composition renderer. This
    helper remains only for transient overlays that are not part of the configured HUD, such as the
    selected-unit context menu.
    """

    primitives: list[RenderPrimitive] = []
    if context_menu is not None:
        primitives.extend(_context_menu_primitives(context_menu))
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


def _selection_primitives(
    view: BattlefieldView,
    selection_state: SelectionState,
) -> tuple[RenderPrimitive, ...]:
    primitives: list[RenderPrimitive] = []
    unit = selected_unit(view, selection_state)
    if unit is not None and "selected_unit" in selection_state.active_overlay_ids:
        center = _unit_center(unit)
        primitives.append(
            CirclePrimitive(
                layer="selected_unit_overlay",
                center=center,
                radius=_selected_unit_radius(unit),
                fill_color=SELECTION_UNIT_FILL,
                outline_color=SELECTION_GOLD,
                line_width=1.8,
            )
        )
    model = selected_model(view, selection_state)
    if model is not None and "selected_model" in selection_state.active_overlay_ids:
        primitives.append(
            CirclePrimitive(
                layer="selected_model_overlay",
                center=model.position,
                radius=model.base_radius + 0.25,
                fill_color=(0, 0, 0, 0),
                outline_color=(255, 246, 168, 255),
                line_width=2.0,
            )
        )
    return tuple(primitives)


def _movement_draft_primitives(
    selection_state: SelectionState,
    movement_draft: MovementDraft,
) -> tuple[RenderPrimitive, ...]:
    primitives: list[RenderPrimitive] = []
    warning = any("warning" in hint.lower() for hint in movement_draft.local_hint_lines)
    default_line_color = MOVEMENT_WARNING if warning else MOVEMENT_PATH
    assignment_views = movement_draft.assignment_views()
    if "movement_path_draft" in selection_state.active_overlay_ids:
        for assignment in assignment_views:
            state_color = _movement_assignment_color(assignment.state)
            primitives.append(
                CirclePrimitive(
                    layer=f"movement_{assignment.state}_model_overlay",
                    center=assignment.points[0],
                    radius=assignment.base_radius + 0.18,
                    fill_color=(0, 0, 0, 0),
                    outline_color=state_color,
                    line_width=1.6 if assignment.state == "active" else 1.1,
                )
            )
            line_color = MOVEMENT_WARNING if warning else state_color
            if assignment.has_movement:
                primitives.append(
                    PolylinePrimitive(
                        layer="movement_path",
                        points=assignment.points,
                        color=line_color,
                        line_width=1.5 if assignment.state == "active" else 1.1,
                    )
                )
                primitives.append(
                    CirclePrimitive(
                        layer="movement_ghost_base",
                        center=assignment.final_point,
                        radius=assignment.base_radius,
                        fill_color=MOVEMENT_GHOST_FILL,
                        outline_color=line_color,
                        line_width=1.0,
                    )
                )
                for index, point in enumerate(assignment.points[1:], start=1):
                    primitives.append(
                        CirclePrimitive(
                            layer="movement_waypoint",
                            center=point,
                            radius=0.24,
                            fill_color=line_color,
                            outline_color=(248, 250, 246, 255),
                            line_width=0.8,
                        )
                    )
                    primitives.append(
                        TextPrimitive(
                            layer="movement_waypoint_label",
                            text=f"{assignment.model_id}:{index}",
                            position=(point[0], point[1] + 0.42),
                            color=line_color,
                            font_size=7.5,
                            coordinate_space="world",
                            anchor_x="center",
                            anchor_y="center",
                        )
                    )
        if movement_draft.cursor_preview_point is not None:
            primitives.append(
                CirclePrimitive(
                    layer="movement_preview_endpoint",
                    center=movement_draft.cursor_preview_point,
                    radius=0.18,
                    fill_color=MOVEMENT_PREVIEW,
                    outline_color=default_line_color,
                    line_width=0.8,
                )
            )
    if (
        "movement_budget" in selection_state.active_overlay_ids
        and movement_draft.movement_budget_inches is not None
    ):
        for assignment in assignment_views:
            if assignment.state != "active":
                continue
            primitives.append(
                CirclePrimitive(
                    layer="movement_budget_ring",
                    center=assignment.points[0],
                    radius=movement_draft.movement_budget_inches,
                    fill_color=(0, 0, 0, 0),
                    outline_color=MOVEMENT_PREVIEW,
                    line_width=1.0,
                )
            )
    return tuple(primitives)


def _action_visual_summary_primitives(
    summary: ActionVisualSummary,
) -> tuple[RenderPrimitive, ...]:
    primitives: list[RenderPrimitive] = []
    if summary.operation_kind == "unsupported":
        return ()
    label_count = 0
    for group in summary.groups:
        color = _action_summary_color(summary, group)
        line_width = 1.1 if summary.intensity == "dim" else 2.2
        if group.has_path:
            primitives.append(
                PolylinePrimitive(
                    layer=f"action_summary_{summary.intensity}_path",
                    points=group.path_points,
                    color=color,
                    line_width=line_width,
                )
            )
        if group.ghost_center is not None and group.ghost_radius is not None:
            primitives.append(
                CirclePrimitive(
                    layer=f"action_summary_{summary.intensity}_ghost_base",
                    center=group.ghost_center,
                    radius=group.ghost_radius,
                    fill_color=_action_summary_ghost_fill(summary, group),
                    outline_color=color,
                    line_width=0.9 if summary.intensity == "dim" else 1.6,
                )
            )
        if (
            summary.intensity == "review"
            and group.ghost_center is not None
            and label_count < summary.max_labels
        ):
            primitives.append(
                TextPrimitive(
                    layer="action_summary_review_label",
                    text=group.label,
                    position=(group.ghost_center[0], group.ghost_center[1] + 0.72),
                    color=color,
                    font_size=8.0,
                    coordinate_space="world",
                    anchor_x="center",
                    anchor_y="center",
                )
            )
            label_count += 1
    return tuple(primitives)


def _action_summary_color(
    summary: ActionVisualSummary,
    group: ActionVisualSummaryGroup,
) -> Color:
    if group.color_role == "warning" or group.state in {"warning", "invalid"}:
        return (
            ACTION_SUMMARY_WARNING_DIM
            if summary.intensity == "dim"
            else ACTION_SUMMARY_WARNING_REVIEW
        )
    return ACTION_SUMMARY_DIM if summary.intensity == "dim" else ACTION_SUMMARY_REVIEW


def _action_summary_ghost_fill(
    summary: ActionVisualSummary,
    group: ActionVisualSummaryGroup,
) -> Color:
    if group.color_role == "warning" or group.state in {"warning", "invalid"}:
        color = _action_summary_color(summary, group)
        return (color[0], color[1], color[2], 36 if summary.intensity == "dim" else 80)
    return ACTION_SUMMARY_GHOST_DIM if summary.intensity == "dim" else ACTION_SUMMARY_GHOST_REVIEW


def _context_menu_primitives(menu: ContextMenuView) -> tuple[TextPrimitive, ...]:
    lines = (
        f"Actions: {menu.unit_id}",
        *(_context_action_text(action) for action in menu.actions),
    )
    anchor_x, anchor_y = menu.anchor_world
    return tuple(
        TextPrimitive(
            layer="context_menu",
            text=line,
            position=(anchor_x + 1.0, anchor_y + 1.0 - (index * 1.1)),
            color=HUD_TEXT if index == 0 else HUD_ACCENT,
            font_size=10.5,
            coordinate_space="world",
        )
        for index, line in enumerate(lines)
    )


def _context_action_text(action: ContextMenuAction) -> str:
    label = (
        action.label
        if action.disabled_reason is None
        else f"{action.label}: {action.disabled_reason}"
    )
    if action.highlighted:
        return f"> {label} <"
    return label


def _movement_assignment_color(state: str) -> Color:
    if state == "active":
        return MOVEMENT_ACTIVE
    if state == "assigned":
        return MOVEMENT_ASSIGNED
    return MOVEMENT_UNASSIGNED


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


def _selected_unit_radius(unit: UnitView) -> float:
    center = _unit_center(unit)
    return max(
        math.dist(center, model.position) + model.base_radius + 0.85 for model in unit.models
    )


def _centroid(points: tuple[WorldPoint, ...]) -> WorldPoint:
    x_total = sum(point[0] for point in points)
    y_total = sum(point[1] for point in points)
    return (x_total / len(points), y_total / len(points))
