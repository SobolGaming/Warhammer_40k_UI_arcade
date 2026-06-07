"""Pure render primitive generation for battlefield view models."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from warhammer40k_arcade_ui.hud.action_summary import (
    ActionVisualSummary,
    ActionVisualSummaryGroup,
)
from warhammer40k_arcade_ui.hud.layouts import HudLayoutView, HudRegionView, ScreenRect
from warhammer40k_arcade_ui.hud.view_models import (
    AssignmentHudGroupView,
    AssignmentHudPanelView,
    ContextMenuAction,
    ContextMenuView,
    DebugInspectorView,
    FiniteDecisionOptionView,
    FiniteDecisionPanelView,
    MovementDraftPanelView,
    UnitPanelView,
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
HUD_MUTED: Color = (178, 190, 184, 255)
HUD_ZONE_FILL: Color = (14, 18, 20, 122)
HUD_ZONE_OUTLINE: Color = (164, 177, 170, 148)
HUD_CENTER_OUTLINE: Color = (210, 224, 215, 74)
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
class PolylinePrimitive:
    """Polyline primitive in either world or screen coordinates."""

    layer: str
    points: tuple[WorldPoint, ...]
    color: Color
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


def build_hud_primitives(
    *,
    view: BattlefieldView,
    viewport_width_px: int,
    viewport_height_px: int,
    mouse_world_position: WorldPoint | None,
    unit_panel: UnitPanelView | None = None,
    context_menu: ContextMenuView | None = None,
    finite_decision_panel: FiniteDecisionPanelView | None = None,
    movement_draft_panel: MovementDraftPanelView | None = None,
    assignment_hud_panel: AssignmentHudPanelView | None = None,
    debug_inspector: DebugInspectorView | None = None,
    hud_layout: HudLayoutView | None = None,
    include_layout_skeleton: bool = True,
    include_layout_labels: bool = True,
    include_status_text: bool = True,
) -> tuple[RenderPrimitive, ...]:
    """Build screen-space HUD primitives that remain fixed during camera movement."""

    primitives: list[RenderPrimitive] = []
    if hud_layout is not None and include_layout_skeleton:
        primitives.extend(_hud_layout_primitives(hud_layout))
    elif hud_layout is not None and include_layout_labels:
        primitives.extend(_hud_layout_label_primitives(hud_layout))
    top_origin, top_max_lines = _top_status_placement(
        hud_layout=hud_layout,
        viewport_height_px=viewport_height_px,
    )
    event_text = " | ".join(view.hud.event_log_lines)
    lines = _clip_lines(
        (
            f"HUD layout: {_layout_label(hud_layout)}",
            f"Phase: {view.hud.phase_label}",
            f"Active: {view.hud.active_player_id}",
            f"Pending: {view.hud.pending_decision_summary}",
            f"Events: {event_text}",
        ),
        max_lines=top_max_lines,
    )
    if include_status_text:
        primitives.extend(
            TextPrimitive(
                layer="hud",
                text=line,
                position=(top_origin[0], top_origin[1] - (index * 18.0)),
                color=HUD_TEXT,
                font_size=13.0,
                coordinate_space="screen",
            )
            for index, line in enumerate(lines)
        )
    legacy_lines = (
        f"Phase: {view.hud.phase_label}",
        f"Active: {view.hud.active_player_id}",
        f"Pending: {view.hud.pending_decision_summary}",
        f"Events: {event_text}",
    )
    if hud_layout is None and include_status_text:
        primitives = [
            TextPrimitive(
                layer="hud",
                text=line,
                position=(16.0, viewport_height_px - 24.0 - (index * 22.0)),
                color=HUD_TEXT,
                font_size=13.0,
                coordinate_space="screen",
            )
            for index, line in enumerate(legacy_lines)
        ]
    if unit_panel is not None:
        unit_origin, unit_max_lines = _unit_panel_placement(
            hud_layout=hud_layout,
            viewport_width_px=viewport_width_px,
            viewport_height_px=viewport_height_px,
        )
        primitives.extend(
            _unit_panel_primitives(
                panel=unit_panel,
                viewport_width_px=viewport_width_px,
                viewport_height_px=viewport_height_px,
                origin=unit_origin,
                max_lines=unit_max_lines,
            )
        )
    if context_menu is not None:
        primitives.extend(_context_menu_primitives(context_menu))
    if finite_decision_panel is not None:
        finite_origin, finite_max_lines = _finite_panel_placement(
            hud_layout=hud_layout,
            viewport_height_px=viewport_height_px,
        )
        primitives.extend(
            _finite_decision_panel_primitives(
                panel=finite_decision_panel,
                viewport_height_px=viewport_height_px,
                origin=finite_origin,
                max_lines=finite_max_lines,
            )
        )
    if movement_draft_panel is not None:
        movement_origin, movement_max_lines = _movement_panel_placement(
            hud_layout=hud_layout,
            viewport_height_px=viewport_height_px,
        )
        primitives.extend(
            _movement_draft_panel_primitives(
                panel=movement_draft_panel,
                viewport_height_px=viewport_height_px,
                origin=movement_origin,
                max_lines=movement_max_lines,
            )
        )
    if assignment_hud_panel is not None:
        assignment_origin, assignment_max_lines = _assignment_panel_placement(
            hud_layout=hud_layout,
            viewport_height_px=viewport_height_px,
        )
        primitives.extend(
            _assignment_hud_panel_primitives(
                panel=assignment_hud_panel,
                viewport_height_px=viewport_height_px,
                origin=assignment_origin,
                max_lines=assignment_max_lines,
            )
        )
    if debug_inspector is not None:
        debug_origin, debug_max_lines = _debug_panel_placement(
            hud_layout=hud_layout,
            viewport_width_px=viewport_width_px,
        )
        primitives.extend(
            _debug_inspector_primitives(
                inspector=debug_inspector,
                viewport_width_px=viewport_width_px,
                origin=debug_origin,
                max_lines=debug_max_lines,
            )
        )
    if mouse_world_position is not None:
        primitives.append(
            TextPrimitive(
                layer="hud_debug",
                text=(f"Mouse: {mouse_world_position[0]:.2f}, {mouse_world_position[1]:.2f} in"),
                position=(16.0, 18.0),
                color=HUD_ACCENT,
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


def _hud_layout_primitives(layout: HudLayoutView) -> tuple[RenderPrimitive, ...]:
    primitives: list[RenderPrimitive] = [
        PolygonPrimitive(
            layer="hud_center_viewport",
            points=_rect_points(layout.center_viewport),
            fill_color=(0, 0, 0, 0),
            outline_color=HUD_CENTER_OUTLINE,
            line_width=1.0,
            coordinate_space="screen",
        ),
        TextPrimitive(
            layer="hud_center_viewport",
            text="Battlefield viewport",
            position=(layout.center_viewport.x + 10.0, layout.center_viewport.top - 18.0),
            color=HUD_CENTER_OUTLINE,
            font_size=10.0,
            coordinate_space="screen",
        ),
    ]
    for region in layout.regions:
        primitives.append(
            PolygonPrimitive(
                layer=f"hud_zone_{region.zone_id}",
                points=_rect_points(region.rect),
                fill_color=HUD_ZONE_FILL,
                outline_color=HUD_ZONE_OUTLINE,
                line_width=1.0,
                coordinate_space="screen",
            )
        )
    primitives.extend(_hud_layout_label_primitives(layout))
    return tuple(primitives)


def _hud_layout_label_primitives(layout: HudLayoutView) -> tuple[TextPrimitive, ...]:
    primitives: list[TextPrimitive] = []
    for region in layout.regions:
        state = "collapsed" if region.collapsed else "open"
        primitives.append(
            TextPrimitive(
                layer=f"hud_zone_label_{region.zone_id}",
                text=f"{region.label} [{state}]",
                position=(region.rect.x + 10.0, region.rect.top - 16.0),
                color=HUD_MUTED,
                font_size=10.0,
                coordinate_space="screen",
            )
        )
    return tuple(primitives)


def _top_status_placement(
    *,
    hud_layout: HudLayoutView | None,
    viewport_height_px: int,
) -> tuple[WorldPoint, int | None]:
    if hud_layout is None:
        return (16.0, viewport_height_px - 24.0), None
    region = hud_layout.region("top_ribbon")
    if region is None:
        return (16.0, viewport_height_px - 24.0), None
    return _text_origin(region.rect, top_padding_px=24.0), None


def _unit_panel_placement(
    *,
    hud_layout: HudLayoutView | None,
    viewport_width_px: int,
    viewport_height_px: int,
) -> tuple[WorldPoint | None, int | None]:
    if hud_layout is None:
        return None, None
    region = _first_region(hud_layout, ("right_inspector", "right_opponent_bench"))
    if region is None:
        return (max(16.0, viewport_width_px - 340.0), viewport_height_px - 24.0), None
    return _text_origin(region.rect, top_padding_px=38.0), region.rect.line_capacity(
        line_height_px=20.0,
        top_padding_px=42.0,
    )


def _finite_panel_placement(
    *,
    hud_layout: HudLayoutView | None,
    viewport_height_px: int,
) -> tuple[WorldPoint | None, int | None]:
    if hud_layout is None:
        return None, None
    if hud_layout.preset_id == "command_bench":
        region = hud_layout.region("bottom_command_bench")
        if region is not None:
            return _column_origin(region.rect, 0, 3), _column_line_capacity(region.rect, 18.0)
    region = hud_layout.region("left_rail")
    if region is None:
        return (16.0, viewport_height_px - 126.0), None
    return _text_origin(region.rect, top_padding_px=38.0), min(
        7,
        region.rect.line_capacity(line_height_px=18.0, top_padding_px=42.0),
    )


def _movement_panel_placement(
    *,
    hud_layout: HudLayoutView | None,
    viewport_height_px: int,
) -> tuple[WorldPoint | None, int | None]:
    if hud_layout is None:
        return None, None
    if hud_layout.preset_id == "command_bench":
        region = hud_layout.region("bottom_command_bench")
        if region is not None:
            return _column_origin(region.rect, 1, 3), _column_line_capacity(region.rect, 17.0)
    region = hud_layout.region("left_rail")
    if region is None:
        return (16.0, viewport_height_px - 330.0), None
    origin = (region.rect.x + 12.0, max(region.rect.y + 24.0, region.rect.top - 190.0))
    return origin, region.rect.line_capacity(line_height_px=17.0, top_padding_px=190.0)


def _assignment_panel_placement(
    *,
    hud_layout: HudLayoutView | None,
    viewport_height_px: int,
) -> tuple[WorldPoint | None, int | None]:
    if hud_layout is None:
        return None, None
    if hud_layout.preset_id == "command_bench":
        region = hud_layout.region("bottom_command_bench")
        if region is not None:
            return _column_origin(region.rect, 2, 3), _column_line_capacity(region.rect, 15.5)
    region = hud_layout.region("bottom_workbench")
    if region is None:
        return (16.0, viewport_height_px - 522.0), None
    return _text_origin(region.rect, top_padding_px=34.0), region.rect.line_capacity(
        line_height_px=15.5,
        top_padding_px=38.0,
    )


def _debug_panel_placement(
    *,
    hud_layout: HudLayoutView | None,
    viewport_width_px: int,
) -> tuple[WorldPoint | None, int | None]:
    if hud_layout is None:
        return None, None
    region = _first_region(hud_layout, ("right_inspector", "right_opponent_bench"))
    if region is None:
        return (max(16.0, viewport_width_px - 340.0), 142.0), None
    return (region.rect.x + 12.0, region.rect.y + 138.0), min(
        6,
        region.rect.line_capacity(line_height_px=18.0, top_padding_px=18.0),
    )


def _unit_panel_primitives(
    *,
    panel: UnitPanelView,
    viewport_width_px: int,
    viewport_height_px: int,
    origin: WorldPoint | None = None,
    max_lines: int | None = None,
) -> tuple[TextPrimitive, ...]:
    x, y = origin or (max(16.0, viewport_width_px - 340.0), viewport_height_px - 24.0)
    lines = [
        f"Unit: {panel.unit_label}",
        f"ID: {panel.unit_id}",
        f"Models: {panel.model_count}",
        panel.position_summary,
    ]
    if panel.selected_model_id is not None:
        lines.append(f"Model: {panel.selected_model_id}")
    if panel.pending_request_id is not None:
        lines.append(f"Request: {panel.pending_request_id}")
        lines.extend(
            f"Action: {_context_action_text(action)}" for action in panel.available_actions
        )
    else:
        lines.append("Actions: none for selected unit")
    clipped_lines = _clip_lines(tuple(lines), max_lines=max_lines)
    return tuple(
        TextPrimitive(
            layer="selected_unit_panel",
            text=line,
            position=(x, y - (index * 20.0)),
            color=HUD_TEXT if index == 0 else HUD_MUTED,
            font_size=12.0 if index else 13.0,
            coordinate_space="screen",
        )
        for index, line in enumerate(clipped_lines)
    )


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


def _finite_decision_panel_primitives(
    *,
    panel: FiniteDecisionPanelView,
    viewport_height_px: int,
    origin: WorldPoint | None = None,
    max_lines: int | None = None,
) -> tuple[TextPrimitive, ...]:
    x, y = origin or (16.0, viewport_height_px - 126.0)
    lines = [
        "Decision",
        f"Status: {panel.status_line}",
    ]
    if panel.request_id is not None:
        lines.append(f"Request: {panel.request_id}")
    if panel.decision_type is not None:
        lines.append(f"Type: {panel.decision_type}")
    if panel.actor_id is not None:
        lines.append(f"Actor: {panel.actor_id}")
    if panel.proposal_kind is not None:
        lines.append(f"Proposal required: {panel.proposal_kind}")
    lines.extend(_finite_option_line(option) for option in panel.options)
    lines.extend(f"Invalid: {line}" for line in panel.diagnostic_lines)
    clipped_lines = _clip_lines(tuple(lines), max_lines=max_lines)
    return tuple(
        TextPrimitive(
            layer="finite_decision_panel",
            text=line,
            position=(x, y - (index * 18.0)),
            color=HUD_ACCENT if index == 0 else HUD_TEXT,
            font_size=12.0 if index else 13.0,
            coordinate_space="screen",
        )
        for index, line in enumerate(clipped_lines)
    )


def _movement_draft_panel_primitives(
    *,
    panel: MovementDraftPanelView,
    viewport_height_px: int,
    origin: WorldPoint | None = None,
    max_lines: int | None = None,
) -> tuple[TextPrimitive, ...]:
    x, y = origin or (16.0, viewport_height_px - 330.0)
    lines = [
        "Movement draft",
        f"Status: {panel.status_line}",
    ]
    if panel.request_id is not None:
        lines.append(f"Request: {panel.request_id}")
    if panel.unit_id is not None:
        lines.append(f"Unit: {panel.unit_id}")
    if panel.proposal_kind is not None:
        lines.append(f"Proposal: {panel.proposal_kind}")
    if panel.movement_phase_action is not None:
        lines.append(f"Action: {panel.movement_phase_action}")
    if panel.movement_mode is not None:
        lines.append(f"Mode: {panel.movement_mode}")
    if panel.fall_back_mode is not None:
        lines.append(f"Fall Back: {panel.fall_back_mode}")
    if panel.active_layer is not None:
        lines.append(f"Layer: {panel.active_layer}")
    if panel.total_model_count:
        active_models = ", ".join(panel.active_model_ids) if panel.active_model_ids else "none"
        lines.append(f"Active models: {active_models}")
        lines.append(
            "Assignments: "
            f"{panel.assigned_model_count}/{panel.total_model_count} moved, "
            f"{panel.unchanged_model_count} no-op"
        )
    if panel.current_segment_inches is not None:
        lines.append(f"Segment: {panel.current_segment_inches:.2f} in")
    if panel.total_path_inches is not None:
        lines.append(f"Total: {panel.total_path_inches:.2f} in")
    if panel.remaining_budget_inches is not None:
        lines.append(f"Remaining: {panel.remaining_budget_inches:.2f} in")
    if panel.ready:
        lines.append("Payload preview: ready")
    lines.extend(panel.hint_lines)
    lines.extend(f"Invalid: {line}" for line in panel.diagnostic_lines)
    clipped_lines = _clip_lines(tuple(lines), max_lines=max_lines)
    return tuple(
        TextPrimitive(
            layer="movement_draft_panel",
            text=line,
            position=(x, y - (index * 17.0)),
            color=HUD_ACCENT if index == 0 else HUD_TEXT,
            font_size=12.0 if index else 13.0,
            coordinate_space="screen",
        )
        for index, line in enumerate(clipped_lines)
    )


def _debug_inspector_primitives(
    *,
    inspector: DebugInspectorView,
    viewport_width_px: int,
    origin: WorldPoint | None = None,
    max_lines: int | None = None,
) -> tuple[TextPrimitive, ...]:
    x, y = origin or (max(16.0, viewport_width_px - 340.0), 142.0)
    lines = _clip_lines(("Debug inspector", *inspector.lines), max_lines=max_lines)
    return tuple(
        TextPrimitive(
            layer="debug_inspector",
            text=line,
            position=(x, y - (index * 18.0)),
            color=HUD_ACCENT,
            font_size=11.0,
            coordinate_space="screen",
        )
        for index, line in enumerate(lines)
    )


def _assignment_hud_panel_primitives(
    *,
    panel: AssignmentHudPanelView,
    viewport_height_px: int,
    origin: WorldPoint | None = None,
    max_lines: int | None = None,
) -> tuple[TextPrimitive, ...]:
    x, y = origin or (16.0, viewport_height_px - 522.0)
    lines = _clip_lines(_assignment_hud_lines(panel), max_lines=max_lines)
    return tuple(
        TextPrimitive(
            layer="assignment_hud_panel",
            text=line,
            position=(x, y - (index * 15.5)),
            color=_assignment_hud_line_color(line, panel),
            font_size=11.0 if index else 12.0,
            coordinate_space="screen",
        )
        for index, line in enumerate(lines)
    )


def _assignment_hud_lines(panel: AssignmentHudPanelView) -> tuple[str, ...]:
    lines: list[str] = [
        "Assignment review",
        f"Operation: {panel.operation_kind}",
        f"Ready: {panel.readiness_state}",
    ]
    if panel.request_id is not None:
        lines.append(f"Request: {panel.request_id}")
    if panel.decision_type is not None:
        lines.append(f"Type: {panel.decision_type}")
    if panel.actor_id is not None:
        lines.append(f"Actor: {panel.actor_id}")
    if panel.proposal_kind is not None:
        lines.append(f"Proposal: {panel.proposal_kind}")
    if panel.active_layer is not None:
        lines.append(f"Layer: {panel.active_layer}")
    if panel.active_selection_ref_keys:
        lines.append(f"Selected: {_compact_ref_list(panel.active_selection_ref_keys)}")
    if panel.assigned_ref_keys or panel.unassigned_ref_keys:
        lines.append(
            f"Refs: {len(panel.assigned_ref_keys)} assigned, "
            f"{len(panel.unassigned_ref_keys)} unassigned"
        )
    group_limit = 4 if panel.display_mode == "compact" else len(panel.groups)
    for group in panel.groups[:group_limit]:
        lines.extend(_assignment_group_lines(group, detailed=panel.display_mode == "detailed"))
    if group_limit < len(panel.groups):
        lines.append(f"... {len(panel.groups) - group_limit} more group(s)")
    advisory_limit = 2 if panel.display_mode == "compact" else len(panel.advisory_lines)
    for line in panel.advisory_lines[:advisory_limit]:
        prefix = "! " if panel.warning_markers_visible and "warning" in line.lower() else ""
        lines.append(f"Hint: {prefix}{line}")
    for line in panel.diagnostic_lines:
        lines.append(f"Invalid: {line}")
    if panel.chain_breadcrumbs_visible:
        lines.extend(f"Chain: {line}" for line in panel.chain_lines)
    if panel.preference_source_label is not None:
        lines.append(f"UI prefs: {panel.preference_source_label}")
        chain_state = "visible" if panel.chain_breadcrumbs_visible else "hidden"
        lines.append(f"Chain breadcrumbs: {chain_state}")
    return tuple(lines)


def _assignment_group_lines(
    group: AssignmentHudGroupView,
    *,
    detailed: bool,
) -> tuple[str, ...]:
    state_marker = {
        "active": ">",
        "assigned": "+",
        "unassigned": "-",
        "warning": "!",
        "invalid": "x",
    }[group.state]
    lines = [f"{state_marker} {group.label}"]
    if detailed:
        if group.source_ref_keys:
            lines.append(f"  Source: {_compact_ref_list(group.source_ref_keys)}")
        if group.target_ref_keys:
            lines.append(f"  Target: {_compact_ref_list(group.target_ref_keys)}")
        lines.extend(f"  {summary}" for summary in group.summary_lines)
    return tuple(lines)


def _assignment_hud_line_color(line: str, panel: AssignmentHudPanelView) -> Color:
    if line == "Assignment review":
        return HUD_ACCENT
    if line.startswith(("Invalid:", "x ")):
        return MOVEMENT_WARNING
    if panel.warning_markers_visible and line.startswith(("! ", "Hint: !")):
        return MOVEMENT_WARNING
    if line.startswith("> "):
        return MOVEMENT_ACTIVE
    if line.startswith("+ "):
        return MOVEMENT_ASSIGNED
    if line.startswith("- "):
        return MOVEMENT_UNASSIGNED
    return HUD_TEXT


def _compact_ref_list(ref_keys: tuple[str, ...]) -> str:
    if len(ref_keys) <= 3:
        return ", ".join(ref_keys)
    return f"{', '.join(ref_keys[:3])}, +{len(ref_keys) - 3}"


def _layout_label(hud_layout: HudLayoutView | None) -> str:
    if hud_layout is None:
        return "legacy"
    return hud_layout.display_label


def _rect_points(rect: ScreenRect) -> tuple[WorldPoint, ...]:
    return (
        (rect.x, rect.y),
        (rect.right, rect.y),
        (rect.right, rect.top),
        (rect.x, rect.top),
    )


def _text_origin(rect: ScreenRect, *, top_padding_px: float) -> WorldPoint:
    return (rect.x + 12.0, rect.top - top_padding_px)


def _column_origin(rect: ScreenRect, column_index: int, column_count: int) -> WorldPoint:
    column_width = rect.width / float(column_count)
    return (rect.x + 12.0 + (column_width * column_index), rect.top - 34.0)


def _column_line_capacity(rect: ScreenRect, line_height_px: float) -> int:
    return rect.line_capacity(line_height_px=line_height_px, top_padding_px=42.0)


def _first_region(layout: HudLayoutView, zone_ids: tuple[str, ...]) -> HudRegionView | None:
    for zone_id in zone_ids:
        region = layout.region(zone_id)
        if region is not None:
            return region
    return None


def _clip_lines(lines: tuple[str, ...], *, max_lines: int | None) -> tuple[str, ...]:
    if max_lines is None or len(lines) <= max_lines:
        return lines
    if max_lines <= 1:
        return (f"... {len(lines)} more",)
    hidden_count = len(lines) - max_lines + 1
    return (*lines[: max_lines - 1], f"... {hidden_count} more")


def _context_action_text(action: ContextMenuAction) -> str:
    label = (
        action.label
        if action.disabled_reason is None
        else f"{action.label}: {action.disabled_reason}"
    )
    if action.highlighted:
        return f"> {label} <"
    return label


def _finite_option_line(option: FiniteDecisionOptionView) -> str:
    marker = ">" if option.highlighted else " "
    suffix = "" if option.disabled_reason is None else f" ({option.disabled_reason})"
    return f"{marker} {option.label} [{option.option_id}]{suffix}"


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
