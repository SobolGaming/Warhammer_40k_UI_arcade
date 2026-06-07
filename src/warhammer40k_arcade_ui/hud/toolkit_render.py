"""Primitive-backed renderer for HUD composition preview and tests."""

from __future__ import annotations

from dataclasses import replace
from math import ceil

from warhammer40k_arcade_ui.hud.composition import (
    HudCompositionProfile,
    find_component,
)
from warhammer40k_arcade_ui.hud.layouts import ScreenRect, build_hud_layout
from warhammer40k_arcade_ui.hud.toolkit import (
    HudComponentNode,
    HudTheme,
    default_hud_theme,
    json_text,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.preferences.schema import JsonObject, JsonValue
from warhammer40k_arcade_ui.render.primitives import (
    CirclePrimitive,
    Color,
    PolygonPrimitive,
    RenderPrimitive,
    TextPrimitive,
)

_PREVIEW_BACKGROUND: Color = (26, 30, 29, 255)
_TRANSPARENT: Color = (0, 0, 0, 0)


def render_composition_profile(
    profile: HudCompositionProfile,
    *,
    viewport_width_px: int,
    viewport_height_px: int,
    component_id: str | None = None,
    theme: HudTheme | None = None,
) -> tuple[RenderPrimitive, ...]:
    """Render a composition profile or one component subtree to deterministic primitives."""

    if viewport_width_px <= 0:
        raise ValueError("viewport_width_px must be positive")
    if viewport_height_px <= 0:
        raise ValueError("viewport_height_px must be positive")
    render_theme = theme or default_hud_theme()
    root_background = PolygonPrimitive(
        layer="hud_preview_background",
        points=_rect_points(ScreenRect(0.0, 0.0, viewport_width_px, viewport_height_px)),
        fill_color=_PREVIEW_BACKGROUND,
        outline_color=_PREVIEW_BACKGROUND,
        line_width=0.0,
        coordinate_space="screen",
    )
    primitives: list[RenderPrimitive] = [root_background]
    if component_id is not None:
        component = find_component(profile, component_id)
        if component is None:
            raise ValueError(f"Unknown HUD component id: {component_id}")
        root_rect = ScreenRect(24.0, 24.0, viewport_width_px - 48.0, viewport_height_px - 48.0)
        primitives.extend(
            render_component_tree(
                component,
                rect=root_rect,
                theme=render_theme,
                sample_data=profile.sample_data,
            )
        )
        return tuple(primitives)

    preferences = default_preferences()
    preferences = replace(
        preferences,
        hud=replace(preferences.hud, layout_preset=profile.layout_preset),
    )
    layout = build_hud_layout(
        preferences=preferences,
        viewport_width_px=viewport_width_px,
        viewport_height_px=viewport_height_px,
    )
    for region in profile.regions:
        resolved_region = layout.region(region.region_id)
        if resolved_region is None:
            continue
        primitives.extend(
            render_component_tree(
                region.widget,
                rect=resolved_region.rect.inset(8.0),
                theme=render_theme,
                sample_data=profile.sample_data,
            )
        )
    return tuple(primitives)


def render_component_tree(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    sample_data: JsonObject,
) -> tuple[RenderPrimitive, ...]:
    """Render one component subtree inside a parent-relative rectangle."""

    primitives: list[RenderPrimitive] = []
    primitives.extend(_component_shell(node, rect=rect, theme=theme, sample_data=sample_data))
    child_rects = _child_rects(node, rect)
    for child, child_rect in zip(node.children, child_rects, strict=True):
        primitives.extend(
            render_component_tree(
                child,
                rect=child_rect,
                theme=theme,
                sample_data=sample_data,
            )
        )
    return tuple(primitives)


def _component_shell(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    sample_data: JsonObject,
) -> tuple[RenderPrimitive, ...]:
    data_value = _data_value(node, sample_data)
    if node.widget_type == "HudContainer":
        render_mode = _attribute_text(node, "render_mode", default="none")
        if render_mode == "none":
            return ()
        if render_mode == "outline":
            return (_panel(rect, theme=theme, fill_color=_TRANSPARENT),)
        return (
            _panel(
                rect,
                theme=theme,
                fill_color=theme.panel_fill if render_mode == "panel" else (118, 99, 172, 52),
            ),
        )
    if node.widget_type == "DonutGauge":
        return _donut_gauge(node, rect=rect, theme=theme, data_value=data_value)
    if node.widget_type == "Separator":
        return _separator(node, rect=rect, theme=theme)
    if node.widget_type == "IconSlot":
        return _icon_slot(node, rect=rect, theme=theme)
    if node.widget_type == "DatasheetPanel":
        return _datasheet_panel(node, rect=rect, theme=theme, data_value=data_value)
    if node.widget_type in (
        "HudPanel",
        "IconTextBar",
        "StatusChip",
        "EntityChip",
        "UnitRailCard",
        "DatasheetHeader",
        "MissionCard",
        "ActionButton",
        "StratagemButton",
        "AssignmentGroupRow",
        "DicePipeline",
        "Tooltip",
        "StatStrip",
        "StatCell",
    ):
        return _labelled_box(node, rect=rect, theme=theme, data_value=data_value)
    return ()


def _labelled_box(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    data_value: JsonValue | None,
) -> tuple[RenderPrimitive, ...]:
    title = _component_title(node, data_value=data_value)
    subtitle = _component_subtitle(node, data_value=data_value)
    color_role = _attribute_text(node, "color_role", default=None)
    accent = theme.color_for_role(color_role)
    primitives: list[RenderPrimitive] = [
        _panel(rect, theme=theme, outline_color=_with_alpha(accent, 184))
    ]
    icon_id = node.icon_id or _attribute_text(node, "icon_id", default="")
    if icon_id:
        icon_rect = ScreenRect(
            rect.x + theme.inner_padding_px,
            rect.top - theme.inner_padding_px - theme.icon_size_px,
            theme.icon_size_px,
            theme.icon_size_px,
        )
        primitives.extend(_icon_placeholder(icon_rect, theme=theme, label=_icon_label(icon_id)))
    text_x = rect.x + theme.inner_padding_px + (theme.icon_size_px + 8.0 if icon_id else 0.0)
    title_y = rect.top - theme.inner_padding_px - 2.0
    primitives.append(
        TextPrimitive(
            layer="hud_widget_text",
            text=_truncate(title, max_chars=_max_chars(rect.width, theme.title_font_size_px)),
            position=(text_x, title_y),
            color=theme.text,
            font_size=theme.title_font_size_px,
            coordinate_space="screen",
            anchor_y="top",
        )
    )
    if subtitle:
        primitives.append(
            TextPrimitive(
                layer="hud_widget_text",
                text=_truncate(
                    subtitle, max_chars=_max_chars(rect.width, theme.compact_font_size_px)
                ),
                position=(text_x, title_y - theme.line_height_px),
                color=theme.muted_text,
                font_size=theme.compact_font_size_px,
                coordinate_space="screen",
                anchor_y="top",
            )
        )
    return tuple(primitives)


def _datasheet_panel(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    data_value: JsonValue | None,
) -> tuple[RenderPrimitive, ...]:
    primitives = list(_labelled_box(node, rect=rect, theme=theme, data_value=data_value))
    stats = _stats_from_data(data_value)
    line_y = rect.top - theme.inner_padding_px - (theme.line_height_px * 2.3)
    if stats:
        stat_cell_height = max(36.0, _attribute_float(node, "stat_cell_height", default=42.0))
        stat_cell_gap = max(0.0, _attribute_float(node, "stat_cell_gap", default=4.0))
        stat_cell_min_width = max(
            24.0,
            _attribute_float(node, "stat_cell_min_width", default=34.0),
        )
        content_width = max(0.0, rect.width - (theme.inner_padding_px * 2.0))
        available_cell_width = max(0.0, content_width - (stat_cell_gap * (len(stats) - 1))) / len(
            stats
        )
        cell_width = max(available_cell_width, stat_cell_min_width)
        if (cell_width * len(stats)) + (stat_cell_gap * (len(stats) - 1)) > content_width:
            cell_width = available_cell_width
        for index, (label, value) in enumerate(stats):
            cell_top = line_y - 4.0
            cell_rect = ScreenRect(
                rect.x + theme.inner_padding_px + (index * (cell_width + stat_cell_gap)),
                cell_top - stat_cell_height,
                max(0.0, cell_width),
                stat_cell_height,
            )
            primitives.extend(_stat_cell(label=label, value=value, rect=cell_rect, theme=theme))
    return tuple(primitives)


def _donut_gauge(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    data_value: JsonValue | None,
) -> tuple[RenderPrimitive, ...]:
    outer_diameter = _attribute_float(node, "outer_diameter", default=min(rect.width, rect.height))
    inner_diameter = _attribute_float(node, "inner_diameter", default=outer_diameter * 0.62)
    progress = _attribute_float(node, "progress_fraction", default=_progress_from_data(data_value))
    clamped_progress = max(0.0, min(1.0, progress))
    outer_radius = max(4.0, min(outer_diameter / 2.0, min(rect.width, rect.height) / 2.0))
    inner_radius = max(1.0, min(inner_diameter / 2.0, outer_radius - 2.0))
    center = (rect.x + (rect.width / 2.0), rect.y + (rect.height / 2.0))
    color_role = _attribute_text(node, "color_role", default="active")
    active = theme.color_for_role(color_role)
    background = (theme.neutral[0], theme.neutral[1], theme.neutral[2], 72)
    primitives: list[RenderPrimitive] = [
        CirclePrimitive(
            layer="hud_widget_ring",
            center=center,
            radius=outer_radius,
            fill_color=background,
            outline_color=theme.panel_border,
            line_width=1.0,
            coordinate_space="screen",
        ),
        CirclePrimitive(
            layer="hud_widget_ring",
            center=center,
            radius=outer_radius * clamped_progress,
            fill_color=_with_alpha(active, 150),
            outline_color=_with_alpha(active, 220),
            line_width=1.0,
            coordinate_space="screen",
        ),
        CirclePrimitive(
            layer="hud_widget_ring",
            center=center,
            radius=inner_radius,
            fill_color=_PREVIEW_BACKGROUND,
            outline_color=_TRANSPARENT,
            line_width=0.0,
            coordinate_space="screen",
        ),
    ]
    label = _attribute_text(
        node,
        "label_text",
        default=_component_title(node, data_value=data_value),
    )
    if label:
        primitives.append(
            TextPrimitive(
                layer="hud_widget_text",
                text=_truncate(label, max_chars=10),
                position=center,
                color=theme.text,
                font_size=theme.compact_font_size_px,
                coordinate_space="screen",
                anchor_x="center",
                anchor_y="center",
            )
        )
    return tuple(primitives)


def _separator(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
) -> tuple[RenderPrimitive, ...]:
    orientation = _attribute_text(node, "orientation", default=node.layout.orientation)
    if orientation == "vertical":
        line_rect = ScreenRect(rect.x + (rect.width / 2.0), rect.y, 1.0, rect.height)
    else:
        line_rect = ScreenRect(rect.x, rect.y + (rect.height / 2.0), rect.width, 1.0)
    return (
        PolygonPrimitive(
            layer="hud_widget_separator",
            points=_rect_points(line_rect),
            fill_color=theme.panel_border,
            outline_color=theme.panel_border,
            line_width=0.0,
            coordinate_space="screen",
        ),
    )


def _icon_slot(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
) -> tuple[RenderPrimitive, ...]:
    icon_id = node.icon_id or _attribute_text(node, "icon_id", default="status.active")
    size = min(rect.width, rect.height, _attribute_float(node, "size", default=theme.icon_size_px))
    icon_rect = ScreenRect(
        rect.x + ((rect.width - size) / 2.0),
        rect.y + ((rect.height - size) / 2.0),
        size,
        size,
    )
    return _icon_placeholder(icon_rect, theme=theme, label=_icon_label(icon_id))


def _stat_cell(
    *,
    label: str,
    value: str,
    rect: ScreenRect,
    theme: HudTheme,
) -> tuple[RenderPrimitive, ...]:
    return (
        _panel(rect, theme=theme, fill_color=(34, 42, 41, 178), outline_color=theme.panel_border),
        TextPrimitive(
            layer="hud_widget_text",
            text=_truncate(label, max_chars=6),
            position=(rect.x + (rect.width / 2.0), rect.top - 6.0),
            color=theme.muted_text,
            font_size=max(9.0, theme.compact_font_size_px - 1.0),
            coordinate_space="screen",
            anchor_x="center",
            anchor_y="top",
        ),
        TextPrimitive(
            layer="hud_widget_text",
            text=_truncate(value, max_chars=6),
            position=(rect.x + (rect.width / 2.0), rect.y + 12.0),
            color=theme.text,
            font_size=max(11.0, theme.base_font_size_px - 1.0),
            coordinate_space="screen",
            anchor_x="center",
            anchor_y="center",
        ),
    )


def _panel(
    rect: ScreenRect,
    *,
    theme: HudTheme,
    fill_color: Color | None = None,
    outline_color: Color | None = None,
) -> PolygonPrimitive:
    return PolygonPrimitive(
        layer="hud_widget_panel",
        points=_rect_points(rect),
        fill_color=theme.panel_fill if fill_color is None else fill_color,
        outline_color=theme.panel_border if outline_color is None else outline_color,
        line_width=1.0,
        coordinate_space="screen",
    )


def _icon_placeholder(
    rect: ScreenRect,
    *,
    theme: HudTheme,
    label: str,
) -> tuple[RenderPrimitive, ...]:
    center = (rect.x + (rect.width / 2.0), rect.y + (rect.height / 2.0))
    return (
        CirclePrimitive(
            layer="hud_widget_icon",
            center=center,
            radius=min(rect.width, rect.height) / 2.0,
            fill_color=(48, 58, 61, 210),
            outline_color=theme.accent,
            line_width=1.0,
            coordinate_space="screen",
        ),
        TextPrimitive(
            layer="hud_widget_icon_text",
            text=label,
            position=center,
            color=theme.text,
            font_size=max(8.0, min(12.0, rect.width * 0.35)),
            coordinate_space="screen",
            anchor_x="center",
            anchor_y="center",
        ),
    )


def _child_rects(node: HudComponentNode, rect: ScreenRect) -> tuple[ScreenRect, ...]:
    if not node.children:
        return ()
    inner = rect.inset(max(0.0, node.layout.padding_px))
    gap = max(0.0, node.layout.gap_px)
    count = len(node.children)
    if node.layout.kind == "grid":
        columns = max(1, node.layout.columns)
        rows = ceil(count / columns)
        cell_width = max(0.0, (inner.width - (gap * (columns - 1))) / columns)
        cell_height = max(0.0, (inner.height - (gap * (rows - 1))) / rows)
        cells: list[ScreenRect] = []
        for index in range(count):
            column = index % columns
            row = index // columns
            cells.append(
                ScreenRect(
                    x=inner.x + (column * (cell_width + gap)),
                    y=inner.top - ((row + 1) * cell_height) - (row * gap),
                    width=cell_width,
                    height=cell_height,
                )
            )
        return tuple(cells)
    if node.layout.orientation == "horizontal":
        child_width = max(0.0, (inner.width - (gap * (count - 1))) / count)
        return tuple(
            ScreenRect(
                x=inner.x + (index * (child_width + gap)),
                y=inner.y,
                width=child_width,
                height=inner.height,
            )
            for index in range(count)
        )
    child_height = max(0.0, (inner.height - (gap * (count - 1))) / count)
    return tuple(
        ScreenRect(
            x=inner.x,
            y=inner.top - ((index + 1) * child_height) - (index * gap),
            width=inner.width,
            height=child_height,
        )
        for index in range(count)
    )


def _component_title(node: HudComponentNode, *, data_value: JsonValue | None) -> str:
    for key in ("title", "primary_label", "label", "unit_label", "group_label"):
        value = node.attributes.get(key)
        text = json_text(value)
        if text:
            return text
    if type(data_value) is dict:
        for key in ("title", "label", "name", "unit_label", "action_label"):
            text = json_text(data_value.get(key))
            if text:
                return text
    return node.widget_id


def _component_subtitle(node: HudComponentNode, *, data_value: JsonValue | None) -> str:
    for key in (
        "subtitle",
        "secondary_label",
        "value",
        "value_text",
        "status_summary",
        "body",
        "hotkey_hint",
    ):
        value = node.attributes.get(key)
        text = json_text(value)
        if text:
            return text
    summary_lines = node.attributes.get("summary_lines")
    if type(summary_lines) is list:
        summaries = tuple(json_text(line) for line in summary_lines)
        return " | ".join(summary for summary in summaries[:2] if summary)
    if type(data_value) is dict:
        for key in ("subtitle", "summary", "status", "value"):
            text = json_text(data_value.get(key))
            if text:
                return text
    return ""


def _stats_from_data(data_value: JsonValue | None) -> tuple[tuple[str, str], ...]:
    if type(data_value) is not dict:
        return ()
    raw_stats = data_value.get("stats")
    if type(raw_stats) is not dict:
        return ()
    stats: list[tuple[str, str]] = []
    for key, value in raw_stats.items():
        stats.append((str(key), json_text(value, default="-")))
    return tuple(stats[:6])


def _data_value(node: HudComponentNode, sample_data: JsonObject) -> JsonValue | None:
    if node.data_ref is None:
        return None
    return sample_data.get(node.data_ref)


def _progress_from_data(data_value: JsonValue | None) -> float:
    if type(data_value) is dict:
        raw_progress = data_value.get("progress_fraction")
        if type(raw_progress) is int or type(raw_progress) is float:
            return float(raw_progress)
        current = data_value.get("current")
        maximum = data_value.get("maximum")
        if (type(current) is int or type(current) is float) and (
            type(maximum) is int or type(maximum) is float
        ):
            if float(maximum) <= 0.0:
                return 0.0
            return float(current) / float(maximum)
    return 0.0


def _attribute_text(
    node: HudComponentNode,
    key: str,
    *,
    default: str | None,
) -> str:
    value = node.attributes.get(key)
    return json_text(value, default=default or "")


def _attribute_float(node: HudComponentNode, key: str, *, default: float) -> float:
    value = node.attributes.get(key)
    if type(value) is int or type(value) is float:
        return float(value)
    return default


def _icon_label(icon_id: str) -> str:
    parts = icon_id.split(".")
    tail = parts[-1] if parts else icon_id
    return tail[:2].upper()


def _rect_points(rect: ScreenRect) -> tuple[tuple[float, float], ...]:
    return (
        (rect.x, rect.y),
        (rect.right, rect.y),
        (rect.right, rect.top),
        (rect.x, rect.top),
    )


def _with_alpha(color: Color, alpha: int) -> Color:
    return (color[0], color[1], color[2], alpha)


def _truncate(text: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= 1:
        return text[:max_chars]
    return f"{text[: max_chars - 1]}..."


def _max_chars(width_px: float, font_size_px: float) -> int:
    if font_size_px <= 0.0:
        return 1
    return max(1, int(width_px / (font_size_px * 0.58)))
