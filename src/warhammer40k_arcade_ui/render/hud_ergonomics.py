"""Primitive adapter for the Phase 20 ergonomic HUD view model."""

from __future__ import annotations

from dataclasses import dataclass, replace

from warhammer40k_arcade_ui.hud.ergonomics import HudErgonomicsView
from warhammer40k_arcade_ui.hud.layouts import HudLayoutView, ScreenRect
from warhammer40k_arcade_ui.hud.toolkit import (
    AssignmentGroupRowView,
    HudColorRole,
    HudComponentNode,
    HudLayoutSpec,
    HudState,
    HudTheme,
    IconTextBarView,
    StatusChipView,
    UnitRailCardView,
    default_hud_theme,
)
from warhammer40k_arcade_ui.hud.toolkit_render import render_component_tree
from warhammer40k_arcade_ui.preferences.schema import JsonObject
from warhammer40k_arcade_ui.render.primitives import RenderPrimitive

_SECTION_GAP_PX = 8.0
_MIN_ROW_HEIGHT_PX = 38.0
_MAX_INSPECTOR_ROWS = 5
_MAX_ACTION_ROWS = 4
_MAX_ASSIGNMENT_ROWS = 4
_MAX_REVIEW_ROWS = 5


def build_ergonomic_hud_primitives(
    *,
    ergonomics: HudErgonomicsView,
    hud_layout: HudLayoutView | None,
    viewport_width_px: int,
    viewport_height_px: int,
) -> tuple[RenderPrimitive, ...]:
    """Render the ergonomic HUD as toolkit-backed screen-space primitives."""

    theme = _scaled_theme(ergonomics)
    primitives: list[RenderPrimitive] = []
    primitives.extend(
        _status_chip_primitives(
            chips=ergonomics.status_chips,
            rect=_region_rect(
                hud_layout,
                ("top_ribbon",),
                fallback=ScreenRect(0.0, viewport_height_px - 72.0, viewport_width_px, 72.0),
            ),
            theme=theme,
        )
    )
    primitives.extend(
        _selected_unit_primitives(
            ergonomics=ergonomics,
            rect=_region_rect(
                hud_layout,
                ("right_inspector", "right_opponent_bench"),
                fallback=ScreenRect(
                    viewport_width_px - 328.0,
                    92.0,
                    328.0,
                    viewport_height_px - 164.0,
                ),
            ),
            theme=theme,
        )
    )
    primitives.extend(
        _workbench_primitives(
            ergonomics=ergonomics,
            rect=_region_rect(
                hud_layout,
                ("bottom_workbench", "bottom_command_bench"),
                fallback=ScreenRect(0.0, 0.0, viewport_width_px, 138.0),
            ),
            theme=theme,
        )
    )
    return tuple(primitives)


def _status_chip_primitives(
    *,
    chips: tuple[StatusChipView, ...],
    rect: ScreenRect,
    theme: HudTheme,
) -> tuple[RenderPrimitive, ...]:
    if not chips or not rect.is_visible:
        return ()
    content = rect.inset(8.0)
    chip_height = min(52.0, max(36.0, content.height))
    available_width = content.width - (_SECTION_GAP_PX * (len(chips) - 1))
    chip_width = min(260.0, max(120.0, available_width / len(chips)))
    y = content.top - chip_height
    primitives: list[RenderPrimitive] = []
    for index, chip in enumerate(chips):
        chip_rect = ScreenRect(
            x=content.x + (index * (chip_width + _SECTION_GAP_PX)),
            y=y,
            width=chip_width,
            height=chip_height,
        )
        primitives.extend(
            _render_node(
                _status_chip_node(chip),
                rect=chip_rect,
                theme=theme,
            )
        )
    return tuple(primitives)


def _selected_unit_primitives(
    *,
    ergonomics: HudErgonomicsView,
    rect: ScreenRect,
    theme: HudTheme,
) -> tuple[RenderPrimitive, ...]:
    if not rect.is_visible or (
        ergonomics.selected_unit_card is None and not ergonomics.selected_unit_rows
    ):
        return ()
    primitives: list[RenderPrimitive] = []
    panel_rect = rect.inset(8.0)
    primitives.extend(
        _render_node(
            _panel_node(
                widget_id="selected_unit_ergonomic_panel",
                title="Selected Unit",
                subtitle="Authoritative projection",
                color_role="player",
            ),
            rect=panel_rect,
            theme=theme,
        )
    )
    content = panel_rect.inset(theme.inner_padding_px)
    row_height = _row_height(theme)
    cursor_top = content.top - (theme.line_height_px * 2.2)
    if ergonomics.selected_unit_card is not None and cursor_top - row_height >= content.y:
        primitives.extend(
            _render_node(
                _unit_card_node(ergonomics.selected_unit_card),
                rect=ScreenRect(content.x, cursor_top - row_height, content.width, row_height),
                theme=theme,
            )
        )
        cursor_top -= row_height + _SECTION_GAP_PX
    for row in ergonomics.selected_unit_rows[:_MAX_INSPECTOR_ROWS]:
        if cursor_top - row_height < content.y:
            break
        primitives.extend(
            _render_node(
                _icon_text_bar_node(row),
                rect=ScreenRect(content.x, cursor_top - row_height, content.width, row_height),
                theme=theme,
            )
        )
        cursor_top -= row_height + _SECTION_GAP_PX
    return tuple(primitives)


def _workbench_primitives(
    *,
    ergonomics: HudErgonomicsView,
    rect: ScreenRect,
    theme: HudTheme,
) -> tuple[RenderPrimitive, ...]:
    if not rect.is_visible:
        return ()
    content = rect.inset(8.0)
    column_rects = _column_rects(content, ratios=(0.38, 0.34, 0.28), gap_px=_SECTION_GAP_PX)
    review_rows = _review_rows(ergonomics)
    sections: tuple[_WorkbenchSection, ...] = (
        _WorkbenchSection(
            section_id="actions",
            title="Decision",
            subtitle="Engine request and local preview",
            rows=tuple(
                _icon_text_bar_node(row) for row in ergonomics.action_rows[:_MAX_ACTION_ROWS]
            ),
            color_role="active",
        ),
        _WorkbenchSection(
            section_id="assignments",
            title="Assignments",
            subtitle="Preview only until submitted",
            rows=tuple(
                _assignment_row_node(row)
                for row in ergonomics.assignment_rows[:_MAX_ASSIGNMENT_ROWS]
            ),
            color_role="preview",
        ),
        _WorkbenchSection(
            section_id="review",
            title="Review",
            subtitle="Diagnostics, events, hotkeys",
            rows=review_rows,
            color_role="debug" if review_rows else "neutral",
        ),
    )
    primitives: list[RenderPrimitive] = []
    for section, column_rect in zip(sections, column_rects, strict=True):
        primitives.extend(_section_primitives(section=section, rect=column_rect, theme=theme))
    return tuple(primitives)


def _section_primitives(
    *,
    section: _WorkbenchSection,
    rect: ScreenRect,
    theme: HudTheme,
) -> tuple[RenderPrimitive, ...]:
    primitives: list[RenderPrimitive] = []
    primitives.extend(
        _render_node(
            _panel_node(
                widget_id=f"ergonomic_{section.section_id}_panel",
                title=section.title,
                subtitle=section.subtitle,
                color_role=section.color_role,
            ),
            rect=rect,
            theme=theme,
        )
    )
    content = rect.inset(theme.inner_padding_px)
    row_height = _row_height(theme)
    cursor_top = content.top - (theme.line_height_px * 2.2)
    for row in section.rows:
        if cursor_top - row_height < content.y:
            break
        primitives.extend(
            _render_node(
                row,
                rect=ScreenRect(content.x, cursor_top - row_height, content.width, row_height),
                theme=theme,
            )
        )
        cursor_top -= row_height + _SECTION_GAP_PX
    return tuple(primitives)


@dataclass(frozen=True, slots=True)
class _WorkbenchSection:
    """Small local grouping object for workbench render columns."""

    section_id: str
    title: str
    subtitle: str
    rows: tuple[HudComponentNode, ...]
    color_role: HudColorRole


def _review_rows(ergonomics: HudErgonomicsView) -> tuple[HudComponentNode, ...]:
    rows: list[HudComponentNode] = []
    rows.extend(
        _tooltip_node(
            widget_id=f"diagnostic_{index}",
            title="Invalid diagnostic",
            body=line,
            color_role="invalid",
        )
        for index, line in enumerate(ergonomics.diagnostic_lines[:_MAX_REVIEW_ROWS])
    )
    if not rows:
        rows.extend(
            _tooltip_node(
                widget_id=f"event_{index}",
                title="Filtered event",
                body=line,
                color_role="debug",
            )
            for index, line in enumerate(ergonomics.event_lines[:_MAX_REVIEW_ROWS])
        )
    remaining = _MAX_REVIEW_ROWS - len(rows)
    if remaining > 0:
        rows.extend(
            _tooltip_node(
                widget_id=f"hotkey_{index}",
                title="Hotkey",
                body=hint,
                color_role="active",
            )
            for index, hint in enumerate(ergonomics.hotkey_hints[:remaining])
        )
    return tuple(rows)


def _status_chip_node(chip: StatusChipView) -> HudComponentNode:
    return HudComponentNode(
        widget_type="StatusChip",
        widget_id=chip.component_id,
        icon_id=chip.icon_id,
        attributes={
            "label": chip.label,
            "value": chip.value,
            "color_role": chip.color_role,
            "state": chip.state,
        },
        layout=_leaf_layout(),
    )


def _unit_card_node(card: UnitRailCardView) -> HudComponentNode:
    return HudComponentNode(
        widget_type="UnitRailCard",
        widget_id=card.component_id,
        attributes={
            "unit_label": card.unit_label,
            "status_summary": _join_non_empty(
                card.short_label,
                card.model_count_summary,
                card.activation_state,
            ),
            "color_role": card.color_role,
            "activation_state": card.activation_state,
        },
        layout=_leaf_layout(),
    )


def _icon_text_bar_node(row: IconTextBarView) -> HudComponentNode:
    secondary = _join_non_empty(row.secondary_label, row.value_text)
    return HudComponentNode(
        widget_type="IconTextBar",
        widget_id=row.component_id,
        icon_id=row.icon_id,
        attributes={
            "primary_label": row.primary_label,
            "secondary_label": secondary,
            "icon_side": row.icon_side,
            "density": row.density,
            "state": row.state,
            "color_role": _role_for_state(row.state),
        },
        layout=_leaf_layout(),
    )


def _assignment_row_node(row: AssignmentGroupRowView) -> HudComponentNode:
    return HudComponentNode(
        widget_type="AssignmentGroupRow",
        widget_id=row.component_id,
        attributes={
            "group_label": row.group_label,
            "operation_kind": row.operation_kind,
            "summary_lines": list(row.summary_lines),
            "state": row.state,
            "color_role": _role_for_state(row.state),
        },
        layout=_leaf_layout(),
    )


def _tooltip_node(
    *,
    widget_id: str,
    title: str,
    body: str,
    color_role: HudColorRole,
) -> HudComponentNode:
    return HudComponentNode(
        widget_type="Tooltip",
        widget_id=widget_id,
        attributes={
            "title": title,
            "body": body,
            "color_role": color_role,
        },
        layout=_leaf_layout(),
    )


def _panel_node(
    *,
    widget_id: str,
    title: str,
    subtitle: str,
    color_role: HudColorRole,
) -> HudComponentNode:
    return HudComponentNode(
        widget_type="HudPanel",
        widget_id=widget_id,
        attributes={
            "title": title,
            "subtitle": subtitle,
            "color_role": color_role,
        },
        layout=_leaf_layout(),
    )


def _render_node(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
) -> tuple[RenderPrimitive, ...]:
    return render_component_tree(node, rect=rect, theme=theme, sample_data=_NO_SAMPLE_DATA)


def _scaled_theme(ergonomics: HudErgonomicsView) -> HudTheme:
    scale = max(0.75, min(1.6, ergonomics.text_scale))
    theme = default_hud_theme(high_contrast=ergonomics.high_contrast)
    return replace(
        theme,
        base_font_size_px=theme.base_font_size_px * scale,
        compact_font_size_px=theme.compact_font_size_px * scale,
        title_font_size_px=theme.title_font_size_px * scale,
        line_height_px=theme.line_height_px * scale,
        inner_padding_px=theme.inner_padding_px * scale,
        gap_x_px=theme.gap_x_px * scale,
        gap_y_px=theme.gap_y_px * scale,
        icon_size_px=theme.icon_size_px * scale,
    )


def _region_rect(
    layout: HudLayoutView | None,
    zone_ids: tuple[str, ...],
    *,
    fallback: ScreenRect,
) -> ScreenRect:
    if layout is None:
        return fallback
    for zone_id in zone_ids:
        region = layout.region(zone_id)
        if region is not None:
            return region.rect
    return fallback


def _column_rects(
    rect: ScreenRect,
    *,
    ratios: tuple[float, float, float],
    gap_px: float,
) -> tuple[ScreenRect, ScreenRect, ScreenRect]:
    available_width = max(0.0, rect.width - (gap_px * (len(ratios) - 1)))
    widths = tuple(available_width * ratio for ratio in ratios)
    first = ScreenRect(rect.x, rect.y, widths[0], rect.height)
    second = ScreenRect(rect.x + widths[0] + gap_px, rect.y, widths[1], rect.height)
    third = ScreenRect(
        rect.x + widths[0] + widths[1] + (gap_px * 2.0),
        rect.y,
        widths[2],
        rect.height,
    )
    return (first, second, third)


def _row_height(theme: HudTheme) -> float:
    return max(_MIN_ROW_HEIGHT_PX, theme.line_height_px * 2.25)


def _leaf_layout() -> HudLayoutSpec:
    return HudLayoutSpec(kind="stack", padding_px=0.0, gap_px=0.0)


def _role_for_state(state: HudState) -> HudColorRole:
    if state == "selected":
        return "selected"
    if state == "active":
        return "active"
    if state == "warning":
        return "warning"
    if state == "invalid":
        return "invalid"
    if state == "disabled":
        return "disabled"
    return "neutral"


def _join_non_empty(*values: str) -> str:
    return " | ".join(value for value in values if value)


_NO_SAMPLE_DATA: JsonObject = {}
