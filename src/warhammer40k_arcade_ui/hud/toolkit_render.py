"""Primitive-backed renderer for HUD composition preview and tests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from math import ceil

from warhammer40k_arcade_ui.hud.composition import (
    HudCompositionProfile,
    find_component,
)
from warhammer40k_arcade_ui.hud.layouts import HudLayoutView, ScreenRect, build_hud_layout
from warhammer40k_arcade_ui.hud.toolkit import (
    HudButtonActionKind,
    HudButtonHitRegion,
    HudComponentNode,
    HudScrollHitRegion,
    HudTheme,
    OverflowPolicy,
    ScrollConfig,
    SizeSpec,
    StatusChipShapeSpec,
    default_hud_theme,
    json_text,
    parse_overflow_policy,
    parse_scroll_config,
    parse_size_spec,
    parse_status_chip_shape,
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


@dataclass(frozen=True, slots=True)
class HudCompositionRenderResult:
    """Rendered HUD primitives plus frame-local clickable hit regions."""

    primitives: tuple[RenderPrimitive, ...]
    hit_regions: tuple[HudButtonHitRegion, ...]
    scroll_regions: tuple[HudScrollHitRegion, ...] = ()


def render_composition_profile(
    profile: HudCompositionProfile,
    *,
    viewport_width_px: int,
    viewport_height_px: int,
    component_id: str | None = None,
    theme: HudTheme | None = None,
    runtime_data: JsonObject | None = None,
    hud_layout: HudLayoutView | None = None,
    scroll_offsets: Mapping[str, tuple[float, float]] | None = None,
    include_background: bool = True,
) -> tuple[RenderPrimitive, ...]:
    """Render a composition profile or one component subtree to deterministic primitives."""

    return render_composition_profile_with_hit_regions(
        profile,
        viewport_width_px=viewport_width_px,
        viewport_height_px=viewport_height_px,
        component_id=component_id,
        theme=theme,
        runtime_data=runtime_data,
        hud_layout=hud_layout,
        scroll_offsets=scroll_offsets,
        include_background=include_background,
    ).primitives


def render_composition_profile_with_hit_regions(
    profile: HudCompositionProfile,
    *,
    viewport_width_px: int,
    viewport_height_px: int,
    component_id: str | None = None,
    theme: HudTheme | None = None,
    runtime_data: JsonObject | None = None,
    hud_layout: HudLayoutView | None = None,
    scroll_offsets: Mapping[str, tuple[float, float]] | None = None,
    include_background: bool = True,
) -> HudCompositionRenderResult:
    """Render deterministic primitives and collect clickable button hit regions."""

    if viewport_width_px <= 0:
        raise ValueError("viewport_width_px must be positive")
    if viewport_height_px <= 0:
        raise ValueError("viewport_height_px must be positive")
    render_theme = theme or default_hud_theme()
    active_data = profile.sample_data if runtime_data is None else runtime_data
    primitives: list[RenderPrimitive] = []
    hit_regions: list[HudButtonHitRegion] = []
    scroll_regions: list[HudScrollHitRegion] = []
    if include_background:
        primitives.append(
            PolygonPrimitive(
                layer="hud_preview_background",
                points=_rect_points(ScreenRect(0.0, 0.0, viewport_width_px, viewport_height_px)),
                fill_color=_PREVIEW_BACKGROUND,
                outline_color=_PREVIEW_BACKGROUND,
                line_width=0.0,
                coordinate_space="screen",
            )
        )
    if component_id is not None:
        component = find_component(profile, component_id)
        if component is None:
            raise ValueError(f"Unknown HUD component id: {component_id}")
        root_rect = ScreenRect(24.0, 24.0, viewport_width_px - 48.0, viewport_height_px - 48.0)
        result = render_component_tree_with_hit_regions(
            component,
            rect=root_rect,
            theme=render_theme,
            sample_data=active_data,
            scroll_offsets=scroll_offsets,
        )
        primitives.extend(result.primitives)
        hit_regions.extend(result.hit_regions)
        scroll_regions.extend(result.scroll_regions)
        return HudCompositionRenderResult(
            tuple(primitives), tuple(hit_regions), tuple(scroll_regions)
        )

    layout = hud_layout or _default_layout_for_profile(
        profile=profile,
        viewport_width_px=viewport_width_px,
        viewport_height_px=viewport_height_px,
    )
    for region in profile.regions:
        resolved_region = layout.region(region.region_id)
        if resolved_region is None:
            continue
        result = render_component_tree_with_hit_regions(
            region.widget,
            rect=resolved_region.rect.inset(8.0),
            theme=render_theme,
            sample_data=active_data,
            scroll_offsets=scroll_offsets,
        )
        primitives.extend(result.primitives)
        hit_regions.extend(result.hit_regions)
        scroll_regions.extend(result.scroll_regions)
    return HudCompositionRenderResult(tuple(primitives), tuple(hit_regions), tuple(scroll_regions))


def _default_layout_for_profile(
    *,
    profile: HudCompositionProfile,
    viewport_width_px: int,
    viewport_height_px: int,
) -> HudLayoutView:
    preferences = default_preferences()
    preferences = replace(
        preferences,
        hud=replace(preferences.hud, layout_preset=profile.layout_preset),
    )
    return build_hud_layout(
        preferences=preferences,
        viewport_width_px=viewport_width_px,
        viewport_height_px=viewport_height_px,
    )


def render_component_tree(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    sample_data: JsonObject,
    scroll_offsets: Mapping[str, tuple[float, float]] | None = None,
) -> tuple[RenderPrimitive, ...]:
    """Render one component subtree inside a parent-relative rectangle."""

    return render_component_tree_with_hit_regions(
        node,
        rect=rect,
        theme=theme,
        sample_data=sample_data,
        scroll_offsets=scroll_offsets,
    ).primitives


def render_component_tree_with_hit_regions(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    sample_data: JsonObject,
    scroll_offsets: Mapping[str, tuple[float, float]] | None = None,
) -> HudCompositionRenderResult:
    """Render one component subtree and collect clickable hit regions."""

    active_scroll_offsets = scroll_offsets or {}
    primitives: list[RenderPrimitive] = []
    hit_regions: list[HudButtonHitRegion] = []
    scroll_regions: list[HudScrollHitRegion] = []
    scroll = _scroll_config(node)
    node_clip = rect if _clip_enabled(node) or scroll.enabled else None
    result = _component_shell_with_hit_regions(
        node,
        rect=rect,
        theme=theme,
        sample_data=sample_data,
        scroll_offsets=active_scroll_offsets,
    )
    primitives.extend(_with_clip(result.primitives, node_clip))
    hit_regions.extend(result.hit_regions)
    scroll_regions.extend(result.scroll_regions)
    if scroll.enabled and node.children:
        content_rect = _scroll_content_rect(node, rect)
        offset_x, offset_y = _clamped_scroll_offset(
            node.widget_id,
            scroll=scroll,
            viewport_rect=rect,
            content_rect=content_rect,
            scroll_offsets=active_scroll_offsets,
        )
        scroll_region = _scroll_hit_region(
            node.widget_id,
            viewport_rect=rect,
            content_rect=content_rect,
            scroll=scroll,
            offset_x=offset_x,
            offset_y=offset_y,
        )
        scroll_regions.append(scroll_region)
        primitives.extend(_scrollbar_primitives(scroll_region, theme=theme, scroll=scroll))
        child_rects = tuple(
            _translate_rect(child_rect, dx=-offset_x, dy=-offset_y)
            for child_rect in _child_rects(node, content_rect)
        )
    else:
        child_rects = _child_rects(node, rect)
    for child, child_rect in zip(node.children, child_rects, strict=True):
        child_result = render_component_tree_with_hit_regions(
            child,
            rect=child_rect,
            theme=theme,
            sample_data=sample_data,
            scroll_offsets=active_scroll_offsets,
        )
        primitives.extend(_with_clip(child_result.primitives, node_clip))
        hit_regions.extend(
            _clip_hud_button_hit_regions(child_result.hit_regions, node_clip)
            if node_clip is not None
            else child_result.hit_regions
        )
        scroll_regions.extend(child_result.scroll_regions)
    return HudCompositionRenderResult(tuple(primitives), tuple(hit_regions), tuple(scroll_regions))


def _component_shell_with_hit_regions(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    sample_data: JsonObject,
    scroll_offsets: Mapping[str, tuple[float, float]],
) -> HudCompositionRenderResult:
    data_value = _data_value(node, sample_data)
    if node.widget_type == "CurrentActionPanel":
        return _current_action_panel(node, rect=rect, theme=theme, data_value=data_value)
    if node.widget_type == "ActionButton":
        return _action_button(node, rect=rect, theme=theme, data_value=data_value)
    if node.widget_type == "PlayerUnitsRoster":
        return _player_units_roster(
            node,
            rect=rect,
            theme=theme,
            data_value=data_value,
            scroll_offsets=scroll_offsets,
        )
    if node.widget_type == "AssignmentGroupRow":
        return _assignment_group_row(node, rect=rect, theme=theme, data_value=data_value)
    return HudCompositionRenderResult(
        _component_shell(node, rect=rect, theme=theme, sample_data=sample_data),
        (),
    )


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
    if node.widget_type == "StatusChip":
        return _status_chip(node, rect=rect, theme=theme, data_value=data_value)
    if node.widget_type == "DiceTray":
        return _dice_tray(node, rect=rect, theme=theme, data_value=data_value)
    if node.widget_type in (
        "HudPanel",
        "IconTextBar",
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
    data = _data_object(data_value)
    color_role = _attribute_text(
        node,
        "color_role",
        default=json_text(data.get("color_role")),
    )
    accent = theme.color_for_role(color_role)
    overflow = _overflow_policy(node)
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
    text_width = max(theme.compact_font_size_px, rect.right - text_x - theme.inner_padding_px)
    title_y = rect.top - theme.inner_padding_px - 2.0
    primitives.append(
        TextPrimitive(
            layer="hud_widget_text",
            text=_overflow_text(
                title, width_px=text_width, font_size_px=theme.title_font_size_px, policy=overflow
            ),
            position=(text_x, title_y),
            color=theme.text,
            font_size=_font_size_for_text(
                title,
                width_px=text_width,
                font_size_px=theme.title_font_size_px,
                policy=overflow,
            ),
            coordinate_space="screen",
            anchor_y="top",
        )
    )
    if subtitle:
        primitives.append(
            TextPrimitive(
                layer="hud_widget_text",
                text=_overflow_text(
                    subtitle,
                    width_px=text_width,
                    font_size_px=theme.compact_font_size_px,
                    policy=overflow,
                ),
                position=(text_x, title_y - theme.line_height_px),
                color=theme.muted_text,
                font_size=_font_size_for_text(
                    subtitle,
                    width_px=text_width,
                    font_size_px=theme.compact_font_size_px,
                    policy=overflow,
                ),
                coordinate_space="screen",
                anchor_y="top",
            )
        )
    return tuple(primitives)


def _current_action_panel(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    data_value: JsonValue | None,
) -> HudCompositionRenderResult:
    data = _data_object(data_value)
    overflow = _overflow_policy(node)
    title = _attribute_text(
        node,
        "title",
        default=json_text(data.get("title"), default="Current Action"),
    )
    actor = json_text(data.get("actor"), default=json_text(data.get("actor_summary")))
    request = json_text(data.get("request"), default=json_text(data.get("request_summary")))
    status = json_text(
        data.get("status"),
        default=json_text(data.get("summary"), default=json_text(data.get("advisory_status"))),
    )
    confirm_hint = _attribute_text(
        node,
        "confirm_hint",
        default=json_text(data.get("confirm_hint")),
    )
    cancel_hint = _attribute_text(
        node,
        "cancel_hint",
        default=json_text(data.get("cancel_hint")),
    )
    buttons = _object_items(data.get("buttons"))[: _attribute_int(node, "max_buttons", default=8)]
    color_role = json_text(data.get("color_role"), default="active" if buttons else "neutral")
    accent = theme.color_for_role(color_role)
    text_width = max(theme.compact_font_size_px, rect.width - (theme.inner_padding_px * 2.0))
    primitives: list[RenderPrimitive] = [
        _panel(rect, theme=theme, outline_color=_with_alpha(accent, 184))
    ]
    title_y = rect.top - theme.inner_padding_px - 2.0
    primitives.append(
        TextPrimitive(
            layer="hud_widget_text",
            text=_overflow_text(
                title,
                width_px=text_width,
                font_size_px=theme.title_font_size_px,
                policy=overflow,
            ),
            position=(rect.x + theme.inner_padding_px, title_y),
            color=theme.text,
            font_size=_font_size_for_text(
                title,
                width_px=text_width,
                font_size_px=theme.title_font_size_px,
                policy=overflow,
            ),
            coordinate_space="screen",
            anchor_y="top",
        )
    )
    meta_parts: list[str] = []
    if _attribute_bool(node, "show_actor", default=True) and actor:
        meta_parts.append(f"Actor: {actor}")
    if _attribute_bool(node, "show_request", default=True) and request:
        meta_parts.append(f"Request: {request}")
    meta = "    ".join(meta_parts)
    line_y = title_y - theme.line_height_px
    if meta:
        primitives.append(
            TextPrimitive(
                layer="hud_widget_text",
                text=_overflow_text(
                    meta,
                    width_px=text_width,
                    font_size_px=theme.compact_font_size_px,
                    policy=overflow,
                ),
                position=(rect.x + theme.inner_padding_px, line_y),
                color=theme.muted_text,
                font_size=_font_size_for_text(
                    meta,
                    width_px=text_width,
                    font_size_px=theme.compact_font_size_px,
                    policy=overflow,
                ),
                coordinate_space="screen",
                anchor_y="top",
            )
        )
        line_y -= theme.line_height_px
    if status:
        primitives.append(
            TextPrimitive(
                layer="hud_widget_text",
                text=_overflow_text(
                    status,
                    width_px=text_width,
                    font_size_px=theme.compact_font_size_px,
                    policy=overflow,
                ),
                position=(rect.x + theme.inner_padding_px, line_y),
                color=theme.muted_text,
                font_size=_font_size_for_text(
                    status,
                    width_px=text_width,
                    font_size_px=theme.compact_font_size_px,
                    policy=overflow,
                ),
                coordinate_space="screen",
                anchor_y="top",
            )
        )
        line_y -= theme.line_height_px
    hit_regions: list[HudButtonHitRegion] = []
    button_area = ScreenRect(
        rect.x + theme.inner_padding_px,
        rect.y + theme.inner_padding_px + theme.line_height_px,
        text_width,
        max(0.0, line_y - rect.y - theme.inner_padding_px - theme.line_height_px - 4.0),
    )
    button_result = _button_row(
        node,
        buttons=buttons,
        rect=button_area,
        theme=theme,
    )
    primitives.extend(button_result.primitives)
    hit_regions.extend(button_result.hit_regions)
    hint_text = " | ".join(part for part in (confirm_hint, cancel_hint) if part)
    if hint_text:
        primitives.append(
            TextPrimitive(
                layer="hud_widget_text",
                text=_overflow_text(
                    hint_text,
                    width_px=text_width,
                    font_size_px=max(8.0, theme.compact_font_size_px - 1.0),
                    policy=overflow,
                ),
                position=(rect.x + theme.inner_padding_px, rect.y + theme.inner_padding_px),
                color=theme.muted_text,
                font_size=max(8.0, theme.compact_font_size_px - 1.0),
                coordinate_space="screen",
                anchor_y="baseline",
            )
        )
    return HudCompositionRenderResult(tuple(primitives), tuple(hit_regions))


def _assignment_group_row(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    data_value: JsonValue | None,
) -> HudCompositionRenderResult:
    rows = _object_items(data_value)
    if rows:
        return _assignment_group_row_list(node, rect=rect, theme=theme, rows=rows)
    data = _data_object(data_value)
    primitives = _labelled_box(node, rect=rect, theme=theme, data_value=data_value)
    hit_region = _hit_region_for_button(
        node.widget_id,
        _assignment_group_button_data(node, data),
        rect,
    )
    return HudCompositionRenderResult(
        primitives,
        () if hit_region is None else (hit_region,),
    )


def _assignment_group_row_list(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    rows: tuple[JsonObject, ...],
) -> HudCompositionRenderResult:
    gap = max(0.0, _attribute_float(node, "button_gap", default=6.0))
    header_height = theme.line_height_px + theme.inner_padding_px + 6.0
    title = _component_title(node, data_value=None)
    row_height = min(
        max(0.0, rect.height - header_height),
        max(24.0, _attribute_float(node, "button_height", default=42.0)),
    )
    primitives: list[RenderPrimitive] = [
        _panel(rect, theme=theme),
        TextPrimitive(
            layer="hud_widget_text",
            text=title,
            position=(
                rect.x + theme.inner_padding_px,
                rect.top - theme.inner_padding_px,
            ),
            color=theme.text,
            font_size=theme.title_font_size_px,
            anchor_x="left",
            anchor_y="top",
            coordinate_space="screen",
        ),
    ]
    hit_regions: list[HudButtonHitRegion] = []
    if row_height <= 0.0:
        return HudCompositionRenderResult(tuple(primitives), ())
    y_top = rect.top - header_height
    row_x = rect.x + theme.inner_padding_px
    row_width = max(0.0, rect.width - (theme.inner_padding_px * 2.0))
    for index, row in enumerate(rows):
        row_rect = ScreenRect(row_x, y_top - row_height, row_width, row_height)
        if row_rect.y < rect.y:
            break
        row_node = replace(node, widget_id=f"{node.widget_id}_{index}")
        primitives.extend(_labelled_box(row_node, rect=row_rect, theme=theme, data_value=row))
        hit_region = _hit_region_for_button(
            row_node.widget_id,
            _assignment_group_button_data(row_node, row),
            row_rect,
        )
        if hit_region is not None:
            hit_regions.append(hit_region)
        y_top -= row_height + gap
    return HudCompositionRenderResult(tuple(primitives), tuple(hit_regions))


def _assignment_group_button_data(node: HudComponentNode, data: JsonObject) -> JsonObject:
    button_id = json_text(data.get("button_id"), default=json_text(data.get("id")))
    return {
        "button_id": button_id,
        "command_id": json_text(data.get("command_id"), default="select_assignment_group"),
        "action_kind": json_text(data.get("action_kind"), default="assignment_select"),
        "option_id": json_text(data.get("option_id"), default=button_id),
        "request_id": json_text(data.get("request_id")),
        "unit_id": json_text(data.get("unit_id")),
        "enabled": _attribute_bool(
            node,
            "enabled",
            default=_button_bool(data, "enabled", default=bool(button_id)),
        ),
        "disabled_reason": json_text(data.get("disabled_reason")),
    }


def _action_button(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    data_value: JsonValue | None,
) -> HudCompositionRenderResult:
    data = _data_object(data_value)
    label = _attribute_text(node, "label", default=json_text(data.get("label"), default="Action"))
    icon_id = node.icon_id or _attribute_text(
        node,
        "icon_id",
        default=json_text(data.get("icon_id")),
    )
    command_id = _attribute_text(
        node,
        "command_id",
        default=json_text(data.get("command_id"), default=node.widget_id),
    )
    enabled = _attribute_bool(
        node,
        "enabled",
        default=_button_bool(data, "enabled", default=True),
    )
    button_data: JsonObject = {
        "component_id": node.widget_id,
        "button_id": json_text(data.get("button_id"), default=node.widget_id),
        "label": label,
        "icon_id": icon_id,
        "command_id": command_id,
        "action_kind": "local_command",
        "enabled": enabled,
        "state": json_text(data.get("state"), default="normal"),
        "color_role": json_text(data.get("color_role"), default="neutral"),
    }
    primitives = _hud_button_primitives(button_data, rect=rect, theme=theme, node=node)
    hit_region = _hit_region_for_button(node.widget_id, button_data, rect)
    return HudCompositionRenderResult(primitives, () if hit_region is None else (hit_region,))


def _player_units_roster(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    data_value: JsonValue | None,
    scroll_offsets: Mapping[str, tuple[float, float]],
) -> HudCompositionRenderResult:
    data = _data_object(data_value)
    title = _attribute_text(
        node,
        "title",
        default=json_text(data.get("title"), default="Player Units"),
    )
    subtitle = _attribute_text(
        node,
        "subtitle",
        default=json_text(data.get("summary"), default=json_text(data.get("status"))),
    )
    buttons = _object_items(data.get("buttons"))
    overflow = _overflow_policy(node)
    scroll = _scroll_config(node)
    color_role = json_text(data.get("color_role"), default="player")
    accent = theme.color_for_role(color_role)
    primitives: list[RenderPrimitive] = [
        _panel(rect, theme=theme, outline_color=_with_alpha(accent, 184))
    ]
    text_width = max(theme.compact_font_size_px, rect.width - (theme.inner_padding_px * 2.0))
    title_y = rect.top - theme.inner_padding_px - 2.0
    primitives.append(
        TextPrimitive(
            layer="hud_widget_text",
            text=_overflow_text(
                title,
                width_px=text_width,
                font_size_px=theme.title_font_size_px,
                policy=overflow,
            ),
            position=(rect.x + theme.inner_padding_px, title_y),
            color=theme.text,
            font_size=_font_size_for_text(
                title,
                width_px=text_width,
                font_size_px=theme.title_font_size_px,
                policy=overflow,
            ),
            coordinate_space="screen",
            anchor_y="top",
        )
    )
    subtitle_y = title_y - theme.line_height_px
    header_height = theme.line_height_px + theme.inner_padding_px + 8.0
    if subtitle:
        primitives.append(
            TextPrimitive(
                layer="hud_widget_text",
                text=_overflow_text(
                    subtitle,
                    width_px=text_width,
                    font_size_px=theme.compact_font_size_px,
                    policy=overflow,
                ),
                position=(rect.x + theme.inner_padding_px, subtitle_y),
                color=theme.muted_text,
                font_size=_font_size_for_text(
                    subtitle,
                    width_px=text_width,
                    font_size_px=theme.compact_font_size_px,
                    policy=overflow,
                ),
                coordinate_space="screen",
                anchor_y="top",
            )
        )
        header_height += theme.line_height_px
    content_rect = ScreenRect(
        rect.x + theme.inner_padding_px,
        rect.y + theme.inner_padding_px,
        max(0.0, rect.width - (theme.inner_padding_px * 2.0)),
        max(0.0, rect.height - header_height - theme.inner_padding_px),
    )
    if content_rect.width <= 0.0 or content_rect.height <= 0.0:
        return HudCompositionRenderResult(tuple(primitives), ())
    button_gap = max(0.0, _attribute_float(node, "button_gap", default=6.0))
    button_height = max(20.0, _attribute_float(node, "button_height", default=34.0))
    button_min_width = max(48.0, _attribute_float(node, "button_min_width", default=120.0))
    content_height = max(
        content_rect.height,
        (len(buttons) * button_height) + (max(0, len(buttons) - 1) * button_gap),
    )
    max_button_width = max(
        (
            button_min_width,
            *(
                _estimated_text_width(json_text(button.get("label")), theme.compact_font_size_px)
                + 64.0
                for button in buttons
            ),
        )
    )
    content_width = max(content_rect.width, max_button_width)
    content_extent = ScreenRect(
        content_rect.x,
        content_rect.top - content_height,
        content_width,
        content_height,
    )
    offset_x, offset_y = _clamped_scroll_offset(
        node.widget_id,
        scroll=scroll,
        viewport_rect=content_rect,
        content_rect=content_extent,
        scroll_offsets=scroll_offsets,
    )
    scroll_region = _scroll_hit_region(
        node.widget_id,
        viewport_rect=rect,
        content_rect=ScreenRect(
            rect.x,
            rect.y,
            max(rect.width, content_width + (theme.inner_padding_px * 2.0)),
            rect.height + max(0.0, content_height - content_rect.height),
        ),
        scroll=scroll,
        offset_x=offset_x,
        offset_y=offset_y,
    )
    hit_regions: list[HudButtonHitRegion] = []
    row_y_top = content_rect.top - offset_y
    row_x = content_rect.x - offset_x
    for button in buttons:
        row_button = dict(button)
        if not json_text(row_button.get("text_icon")):
            row_button["text_icon"] = _attribute_text(node, "status_icon_text", default="UN")
        if not json_text(row_button.get("icon_id")):
            row_button["icon_id"] = "entity.unit"
        row_rect = ScreenRect(row_x, row_y_top - button_height, content_width, button_height)
        row_y_top -= button_height + button_gap
        if not _rects_intersect(row_rect, content_rect):
            continue
        primitives.extend(
            _with_clip(
                _hud_button_primitives(row_button, rect=row_rect, theme=theme, node=node),
                content_rect,
            )
        )
        hit_region = _hit_region_for_button(node.widget_id, row_button, row_rect)
        if hit_region is not None:
            clipped = _clip_hud_button_hit_region(hit_region, content_rect)
            if clipped is not None:
                hit_regions.append(clipped)
    if not buttons:
        primitives.append(
            TextPrimitive(
                layer="hud_widget_text",
                text="No projected player units",
                position=(content_rect.x, content_rect.top - 4.0),
                color=theme.muted_text,
                font_size=theme.compact_font_size_px,
                coordinate_space="screen",
                anchor_y="top",
                clip_rect=content_rect,
            )
        )
    scroll_regions = (scroll_region,) if scroll.enabled else ()
    if scroll.enabled:
        primitives.extend(_scrollbar_primitives(scroll_region, theme=theme, scroll=scroll))
    return HudCompositionRenderResult(tuple(primitives), tuple(hit_regions), scroll_regions)


def _button_row(
    node: HudComponentNode,
    *,
    buttons: tuple[JsonObject, ...],
    rect: ScreenRect,
    theme: HudTheme,
) -> HudCompositionRenderResult:
    if not buttons or rect.width <= 0.0 or rect.height <= 0.0:
        return HudCompositionRenderResult((), ())
    gap = max(0.0, _attribute_float(node, "button_gap", default=6.0))
    button_height = min(
        rect.height,
        max(20.0, _attribute_float(node, "button_height", default=34.0)),
    )
    max_per_row = max(1, min(3, _attribute_int(node, "max_buttons_per_row", default=3)))
    y_top = rect.top
    primitives: list[RenderPrimitive] = []
    hit_regions: list[HudButtonHitRegion] = []
    for row_start in range(0, len(buttons), max_per_row):
        row_buttons = buttons[row_start : row_start + max_per_row]
        if y_top - button_height < rect.y:
            break
        column_count = max(1, len(row_buttons))
        button_width = max(
            0.0,
            (rect.width - (gap * max(0, column_count - 1))) / column_count,
        )
        for column_index, button in enumerate(row_buttons):
            button_rect = ScreenRect(
                rect.x + ((button_width + gap) * column_index),
                y_top - button_height,
                button_width,
                button_height,
            )
            primitives.extend(
                _hud_button_primitives(button, rect=button_rect, theme=theme, node=node)
            )
            hit_region = _hit_region_for_button(node.widget_id, button, button_rect)
            if hit_region is not None:
                hit_regions.append(hit_region)
        y_top -= button_height + gap
    return HudCompositionRenderResult(tuple(primitives), tuple(hit_regions))


def _hud_button_primitives(
    button: JsonObject,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    node: HudComponentNode,
) -> tuple[RenderPrimitive, ...]:
    state = _button_state(button)
    enabled = _button_bool(button, "enabled", default=True)
    selected = _button_bool(button, "selected", default=False)
    role = json_text(button.get("visual_role"), default=json_text(button.get("color_role")))
    accent = _button_accent(theme=theme, state=state, role=role, selected=selected, enabled=enabled)
    fill = _button_fill(theme=theme, state=state, selected=selected, enabled=enabled)
    outline = _with_alpha(accent, 226 if enabled else 132)
    icon_id = json_text(button.get("icon_id"))
    text_icon = json_text(button.get("text_icon"))
    label = json_text(button.get("label"), default=json_text(button.get("button_id"), default=""))
    hotkey_hint = json_text(button.get("hotkey_hint"))
    shape = _attribute_text(
        node,
        "button_shape",
        default=json_text(button.get("shape"), default="rect"),
    )
    primitives: list[RenderPrimitive] = [
        _button_panel(rect, theme=theme, fill_color=fill, outline_color=outline, shape=shape)
    ]
    text_left = rect.x + 10.0
    if icon_id or text_icon:
        icon_size = min(theme.icon_size_px * 0.78, rect.height - 8.0)
        icon_rect = ScreenRect(
            rect.x + 7.0,
            rect.y + ((rect.height - icon_size) / 2.0),
            icon_size,
            icon_size,
        )
        primitives.extend(
            _icon_placeholder(icon_rect, theme=theme, label=text_icon or _icon_label(icon_id))
        )
        text_left = icon_rect.right + 7.0
    label_width = max(4.0, rect.right - text_left - 8.0)
    if hotkey_hint:
        label = f"{label}  {hotkey_hint}"
    text_color = theme.disabled if not enabled else theme.text
    primitives.append(
        TextPrimitive(
            layer="hud_widget_button_text",
            text=_truncate(label, max_chars=_max_chars(label_width, theme.compact_font_size_px)),
            position=(text_left, rect.y + (rect.height / 2.0)),
            color=text_color,
            font_size=theme.compact_font_size_px,
            coordinate_space="screen",
            anchor_y="center",
        )
    )
    return tuple(primitives)


def _button_panel(
    rect: ScreenRect,
    *,
    theme: HudTheme,
    fill_color: Color,
    outline_color: Color,
    shape: str,
) -> PolygonPrimitive | CirclePrimitive:
    if shape == "square":
        extent = min(rect.width, rect.height)
        square = ScreenRect(rect.x, rect.y + ((rect.height - extent) / 2.0), extent, extent)
        return _panel(square, theme=theme, fill_color=fill_color, outline_color=outline_color)
    if shape == "pill":
        center = (rect.x + (rect.width / 2.0), rect.y + (rect.height / 2.0))
        return CirclePrimitive(
            layer="hud_widget_button",
            center=center,
            radius=min(rect.width, rect.height) / 2.0,
            fill_color=fill_color,
            outline_color=outline_color,
            line_width=1.0,
            coordinate_space="screen",
        )
    return PolygonPrimitive(
        layer="hud_widget_button",
        points=_rect_points(rect),
        fill_color=fill_color,
        outline_color=outline_color,
        line_width=1.0,
        coordinate_space="screen",
    )


def _button_accent(
    *,
    theme: HudTheme,
    state: str,
    role: str,
    selected: bool,
    enabled: bool,
) -> Color:
    if not enabled or state == "disabled":
        return theme.disabled
    if selected or state in ("selected", "focus"):
        return theme.selected
    if state == "hover":
        return theme.active
    if state == "warning":
        return theme.warning
    if state == "invalid":
        return theme.invalid
    if state == "active":
        return theme.active
    return theme.color_for_role(role)


def _button_fill(
    *,
    theme: HudTheme,
    state: str,
    selected: bool,
    enabled: bool,
) -> Color:
    if not enabled or state == "disabled":
        return (32, 36, 36, 94)
    if selected or state in ("selected", "focus"):
        return _with_alpha(theme.selected, 78)
    if state == "hover":
        return _with_alpha(theme.active, 70)
    if state == "warning":
        return _with_alpha(theme.warning, 58)
    if state == "invalid":
        return _with_alpha(theme.invalid, 58)
    if state == "active":
        return _with_alpha(theme.active, 52)
    return (26, 32, 34, 132)


def _hit_region_for_button(
    component_id: str,
    button: JsonObject,
    rect: ScreenRect,
) -> HudButtonHitRegion | None:
    button_id = json_text(button.get("button_id"), default=json_text(button.get("id")))
    command_id = json_text(button.get("command_id"))
    action_kind = _button_action_kind(json_text(button.get("action_kind"), default="none"))
    metadata = _data_object(button.get("metadata"))
    unit_id = json_text(button.get("unit_id"), default=json_text(metadata.get("unit_id"))) or None
    if not button_id or not command_id:
        return None
    return HudButtonHitRegion(
        component_id=component_id,
        button_id=button_id,
        action_kind=action_kind,
        command_id=command_id,
        enabled=_button_bool(button, "enabled", default=True),
        bounds=(rect.x, rect.y, rect.right, rect.top),
        option_id=json_text(button.get("option_id")) or None,
        request_id=json_text(button.get("request_id")) or None,
        unit_id=unit_id,
        disabled_reason=json_text(button.get("disabled_reason")),
    )


def _button_action_kind(value: str) -> HudButtonActionKind:
    if value == "finite_option":
        return "finite_option"
    if value == "local_command":
        return "local_command"
    if value == "select_unit":
        return "select_unit"
    if value == "placement_submit":
        return "placement_submit"
    if value == "placement_clear":
        return "placement_clear"
    if value == "placement_next_model":
        return "placement_next_model"
    if value == "assignment_submit":
        return "assignment_submit"
    if value == "assignment_decline":
        return "assignment_decline"
    if value == "assignment_clear":
        return "assignment_clear"
    if value == "assignment_select":
        return "assignment_select"
    return "none"


def _button_state(button: JsonObject) -> str:
    state = json_text(button.get("state"), default="normal")
    if state in (
        "normal",
        "hover",
        "focus",
        "selected",
        "active",
        "disabled",
        "warning",
        "invalid",
    ):
        return state
    return "normal"


def _button_bool(button: JsonObject, key: str, *, default: bool) -> bool:
    value = button.get(key)
    if type(value) is bool:
        return value
    return default


def _status_chip(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    data_value: JsonValue | None,
) -> tuple[RenderPrimitive, ...]:
    shape = _status_chip_shape(node)
    if shape.shape not in ("round", "square"):
        return _labelled_box(node, rect=rect, theme=theme, data_value=data_value)
    extent = shape.square_extent_px or min(rect.width, rect.height)
    extent = max(8.0, min(extent, rect.width, rect.height))
    chip_rect = ScreenRect(
        rect.x + ((rect.width - extent) / 2.0),
        rect.y + ((rect.height - extent) / 2.0),
        extent,
        extent,
    )
    color_role = _attribute_text(node, "color_role", default=None)
    accent = theme.color_for_role(color_role)
    label = _icon_label(node.icon_id or _attribute_text(node, "icon_id", default="status.active"))
    title = _component_title(node, data_value=data_value)
    if shape.shape == "round":
        center = (chip_rect.x + (chip_rect.width / 2.0), chip_rect.y + (chip_rect.height / 2.0))
        return (
            CirclePrimitive(
                layer="hud_widget_status_chip",
                center=center,
                radius=chip_rect.width / 2.0,
                fill_color=theme.panel_fill,
                outline_color=_with_alpha(accent, 214),
                line_width=1.0,
                coordinate_space="screen",
            ),
            TextPrimitive(
                layer="hud_widget_status_chip_text",
                text=_truncate(label, max_chars=2),
                position=center,
                color=theme.text,
                font_size=max(8.0, min(theme.compact_font_size_px, chip_rect.width * 0.28)),
                coordinate_space="screen",
                anchor_x="center",
                anchor_y="center",
            ),
        )
    title_text = _truncate(title, max_chars=max(1, int(chip_rect.width / 10.0)))
    return (
        _panel(chip_rect, theme=theme, outline_color=_with_alpha(accent, 214)),
        TextPrimitive(
            layer="hud_widget_status_chip_text",
            text=title_text,
            position=(
                chip_rect.x + (chip_rect.width / 2.0),
                chip_rect.y + (chip_rect.height / 2.0),
            ),
            color=theme.text,
            font_size=max(8.0, min(theme.compact_font_size_px, chip_rect.width * 0.22)),
            coordinate_space="screen",
            anchor_x="center",
            anchor_y="center",
        ),
    )


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


def _dice_tray(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    data_value: JsonValue | None,
) -> tuple[RenderPrimitive, ...]:
    data = _data_object(data_value)
    reroll_request = _data_object(data.get("reroll_request"))
    diagnostics = _string_items(data.get("diagnostics"))
    title = _attribute_text(
        node, "title", default=json_text(data.get("title"), default="Dice Tray")
    )
    subtitle = json_text(data.get("subtitle"), default="No recent visible dice roll")
    source = json_text(data.get("source"), default="")
    total_text = json_text(data.get("total"), default="")
    color_role = "warning" if reroll_request else "active" if total_text else "neutral"
    accent = theme.color_for_role(color_role)
    overflow = _overflow_policy(node)
    primitives: list[RenderPrimitive] = [
        _panel(rect, theme=theme, outline_color=_with_alpha(accent, 194))
    ]
    title_y = rect.top - theme.inner_padding_px - 2.0
    text_width = max(theme.compact_font_size_px, rect.width - (theme.inner_padding_px * 2.0))
    primitives.append(
        TextPrimitive(
            layer="hud_widget_text",
            text=_overflow_text(
                title,
                width_px=text_width,
                font_size_px=theme.title_font_size_px,
                policy=overflow,
            ),
            position=(rect.x + theme.inner_padding_px, title_y),
            color=theme.text,
            font_size=_font_size_for_text(
                title,
                width_px=text_width,
                font_size_px=theme.title_font_size_px,
                policy=overflow,
            ),
            coordinate_space="screen",
            anchor_y="top",
        )
    )
    summary_parts = [subtitle]
    if total_text:
        summary_parts.append(f"total {total_text}")
    if _attribute_bool(node, "show_source", default=True) and source:
        summary_parts.append(source)
    summary = " | ".join(part for part in summary_parts if part)
    primitives.append(
        TextPrimitive(
            layer="hud_widget_text",
            text=_overflow_text(
                summary,
                width_px=text_width,
                font_size_px=theme.compact_font_size_px,
                policy=overflow,
            ),
            position=(rect.x + theme.inner_padding_px, title_y - theme.line_height_px),
            color=theme.muted_text,
            font_size=_font_size_for_text(
                summary,
                width_px=text_width,
                font_size_px=theme.compact_font_size_px,
                policy=overflow,
            ),
            coordinate_space="screen",
            anchor_y="top",
        )
    )
    content_rect = ScreenRect(
        rect.x + theme.inner_padding_px,
        rect.y + theme.inner_padding_px,
        max(0.0, rect.width - (theme.inner_padding_px * 2.0)),
        max(0.0, rect.height - (theme.inner_padding_px * 2.0) - (theme.line_height_px * 2.25)),
    )
    if content_rect.height <= 0.0 or content_rect.width <= 0.0:
        return tuple(primitives)
    primitives.extend(
        _dice_face_columns(
            node,
            rect=content_rect,
            theme=theme,
            data=data,
            reroll_request=reroll_request,
        )
    )
    if diagnostics:
        primitives.append(
            TextPrimitive(
                layer="hud_widget_text",
                text=_overflow_text(
                    f"Diagnostic: {diagnostics[0]}",
                    width_px=text_width,
                    font_size_px=theme.compact_font_size_px,
                    policy=overflow,
                ),
                position=(rect.x + theme.inner_padding_px, rect.y + theme.inner_padding_px),
                color=theme.warning,
                font_size=theme.compact_font_size_px,
                coordinate_space="screen",
                anchor_y="baseline",
            )
        )
    return tuple(primitives)


def _dice_face_columns(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    data: JsonObject,
    reroll_request: JsonObject,
) -> tuple[RenderPrimitive, ...]:
    faces = _face_rows(data)
    if not faces or (
        not reroll_request and all(_int_value(face.get("count"), default=0) == 0 for face in faces)
    ):
        empty_text = json_text(data.get("summary"), default="No recent visible dice roll")
        return (
            TextPrimitive(
                layer="hud_widget_text",
                text=_truncate(
                    empty_text, max_chars=_max_chars(rect.width, theme.base_font_size_px)
                ),
                position=(rect.x, rect.top - 4.0),
                color=theme.muted_text,
                font_size=theme.base_font_size_px,
                coordinate_space="screen",
                anchor_y="top",
            ),
        )
    gap = 6.0
    column_count = 7
    column_width = max(0.0, (rect.width - (gap * (column_count - 1))) / column_count)
    column_height = rect.height
    primitives: list[RenderPrimitive] = []
    face_icon_size = max(14.0, _attribute_float(node, "face_icon_size", default=28.0))
    icon_size = min(face_icon_size, max(0.0, column_width - 8.0), max(0.0, column_height * 0.45))
    for index, face in enumerate(faces):
        column_rect = ScreenRect(
            rect.x + (index * (column_width + gap)),
            rect.y,
            column_width,
            column_height,
        )
        primitives.extend(
            _dice_face_column(
                face,
                rect=column_rect,
                theme=theme,
                icon_size=icon_size,
            )
        )
    bucket_rect = ScreenRect(
        rect.x + (6 * (column_width + gap)),
        rect.y,
        column_width,
        column_height,
    )
    primitives.extend(
        _dice_bucket_column(
            node,
            rect=bucket_rect,
            theme=theme,
            reroll_request=reroll_request,
            icon_size=icon_size,
        )
    )
    return tuple(primitives)


def _dice_face_column(
    face: JsonObject,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    icon_size: float,
) -> tuple[RenderPrimitive, ...]:
    face_value = _int_value(face.get("face"), default=0)
    count = _int_value(face.get("count"), default=0)
    selectable_count = _int_value(face.get("selectable_count"), default=0)
    asset_id = json_text(face.get("asset_id"), default=f"dice.aeldari.d6.face_{face_value}")
    accent = theme.selected if selectable_count > 0 else theme.panel_border
    icon_rect = ScreenRect(
        rect.x + ((rect.width - icon_size) / 2.0),
        rect.top - icon_size - 6.0,
        icon_size,
        icon_size,
    )
    label_y = max(rect.y + 16.0, icon_rect.y - theme.line_height_px - 2.0)
    primitives: list[RenderPrimitive] = [
        _panel(
            rect, theme=theme, fill_color=(18, 24, 24, 118), outline_color=_with_alpha(accent, 172)
        ),
        *_dice_face_placeholder(icon_rect, theme=theme, asset_id=asset_id, face_value=face_value),
        TextPrimitive(
            layer="hud_widget_text",
            text=f"x{count}",
            position=(rect.x + (rect.width / 2.0), label_y),
            color=theme.text if count > 0 else theme.muted_text,
            font_size=theme.compact_font_size_px,
            coordinate_space="screen",
            anchor_x="center",
            anchor_y="top",
        ),
    ]
    if selectable_count > 0:
        primitives.append(
            TextPrimitive(
                layer="hud_widget_text",
                text=f"sel {selectable_count}",
                position=(rect.x + (rect.width / 2.0), rect.y + 6.0),
                color=theme.selected,
                font_size=max(8.0, theme.compact_font_size_px - 1.0),
                coordinate_space="screen",
                anchor_x="center",
                anchor_y="baseline",
            )
        )
    return tuple(primitives)


def _dice_face_placeholder(
    rect: ScreenRect,
    *,
    theme: HudTheme,
    asset_id: str,
    face_value: int,
) -> tuple[RenderPrimitive, ...]:
    label = str(face_value) if 1 <= face_value <= 6 else _icon_label(asset_id)
    center = (rect.x + (rect.width / 2.0), rect.y + (rect.height / 2.0))
    return (
        _panel(rect, theme=theme, fill_color=(32, 42, 44, 220), outline_color=theme.accent),
        TextPrimitive(
            layer="hud_widget_icon_text",
            text=label,
            position=center,
            color=theme.text,
            font_size=max(10.0, min(theme.title_font_size_px, rect.width * 0.48)),
            coordinate_space="screen",
            anchor_x="center",
            anchor_y="center",
        ),
    )


def _dice_bucket_column(
    node: HudComponentNode,
    *,
    rect: ScreenRect,
    theme: HudTheme,
    reroll_request: JsonObject,
    icon_size: float,
) -> tuple[RenderPrimitive, ...]:
    has_reroll = bool(reroll_request)
    options = _object_items(reroll_request.get("options")) if has_reroll else ()
    decline_option = next(
        (option for option in options if _bool_value(option.get("is_decline"), default=False)),
        None,
    )
    reroll_option = next(
        (option for option in options if not _bool_value(option.get("is_decline"), default=False)),
        None,
    )
    title = _attribute_text(
        node,
        "bucket_label",
        default="Reroll" if has_reroll else "Bucket",
    )
    subtitle = (
        json_text(reroll_option.get("label"), default=json_text(reroll_option.get("option_id")))
        if reroll_option is not None
        else "No selectable dice"
        if has_reroll
        else "Read-only"
    )
    accent = theme.warning if has_reroll else theme.neutral
    primitives: list[RenderPrimitive] = [
        _panel(
            rect, theme=theme, fill_color=(20, 22, 28, 132), outline_color=_with_alpha(accent, 188)
        )
    ]
    center_x = rect.x + (rect.width / 2.0)
    icon_rect = ScreenRect(
        rect.x + ((rect.width - icon_size) / 2.0),
        rect.top - icon_size - 6.0,
        icon_size,
        icon_size,
    )
    primitives.extend(_icon_placeholder(icon_rect, theme=theme, label="RR" if has_reroll else "RO"))
    primitives.append(
        TextPrimitive(
            layer="hud_widget_text",
            text=_truncate(
                title, max_chars=max(1, _max_chars(rect.width - 6.0, theme.compact_font_size_px))
            ),
            position=(center_x, max(rect.y + 18.0, icon_rect.y - theme.line_height_px - 2.0)),
            color=theme.text,
            font_size=theme.compact_font_size_px,
            coordinate_space="screen",
            anchor_x="center",
            anchor_y="top",
        )
    )
    primitives.append(
        TextPrimitive(
            layer="hud_widget_text",
            text=_truncate(
                subtitle,
                max_chars=max(
                    1, _max_chars(rect.width - 6.0, max(8.0, theme.compact_font_size_px - 1.0))
                ),
            ),
            position=(center_x, rect.y + 6.0),
            color=theme.warning if has_reroll else theme.muted_text,
            font_size=max(8.0, theme.compact_font_size_px - 1.0),
            coordinate_space="screen",
            anchor_x="center",
            anchor_y="baseline",
        )
    )
    if decline_option is not None:
        primitives.append(
            TextPrimitive(
                layer="hud_widget_text",
                text="decline",
                position=(center_x, rect.y + theme.line_height_px + 3.0),
                color=theme.muted_text,
                font_size=max(8.0, theme.compact_font_size_px - 2.0),
                coordinate_space="screen",
                anchor_x="center",
                anchor_y="baseline",
            )
        )
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
        widths = _allocated_axis_sizes(
            node.children,
            total_size=inner.width,
            gap_px=gap,
            axis="width",
        )
        x = inner.x
        horizontal_rects: list[ScreenRect] = []
        for width in widths:
            horizontal_rects.append(ScreenRect(x=x, y=inner.y, width=width, height=inner.height))
            x += width + gap
        return tuple(horizontal_rects)
    heights = _allocated_axis_sizes(
        node.children,
        total_size=inner.height,
        gap_px=gap,
        axis="height",
    )
    y_top = inner.top
    vertical_rects: list[ScreenRect] = []
    for height in heights:
        vertical_rects.append(
            ScreenRect(x=inner.x, y=y_top - height, width=inner.width, height=height)
        )
        y_top -= height + gap
    return tuple(vertical_rects)


def _scroll_content_rect(node: HudComponentNode, rect: ScreenRect) -> ScreenRect:
    content_width, content_height = _scroll_content_size(node, rect)
    return ScreenRect(
        x=rect.x,
        y=rect.top - content_height,
        width=content_width,
        height=content_height,
    )


def _scroll_content_size(node: HudComponentNode, rect: ScreenRect) -> tuple[float, float]:
    if not node.children:
        return (rect.width, rect.height)
    padding = max(0.0, node.layout.padding_px)
    gap = max(0.0, node.layout.gap_px)
    inner_width = max(0.0, rect.width - (padding * 2.0))
    inner_height = max(0.0, rect.height - (padding * 2.0))
    child_sizes = tuple(_estimated_scroll_child_size(child, rect) for child in node.children)
    if node.layout.kind == "grid":
        columns = max(1, node.layout.columns)
        rows = ceil(len(node.children) / columns)
        cell_width = max((width for width, _ in child_sizes), default=inner_width)
        cell_height = max((height for _, height in child_sizes), default=inner_height)
        return (
            max(rect.width, (columns * cell_width) + (gap * (columns - 1)) + (padding * 2.0)),
            max(rect.height, (rows * cell_height) + (gap * (rows - 1)) + (padding * 2.0)),
        )
    if node.layout.orientation == "horizontal":
        content_width = sum(width for width, _ in child_sizes) + (
            gap * max(0, len(child_sizes) - 1)
        )
        content_height = max((height for _, height in child_sizes), default=inner_height)
        return (
            max(rect.width, content_width + (padding * 2.0)),
            max(rect.height, content_height + (padding * 2.0)),
        )
    content_width = max((width for width, _ in child_sizes), default=inner_width)
    content_height = sum(height for _, height in child_sizes) + (gap * max(0, len(child_sizes) - 1))
    return (
        max(rect.width, content_width + (padding * 2.0)),
        max(rect.height, content_height + (padding * 2.0)),
    )


def _estimated_scroll_child_size(
    child: HudComponentNode,
    parent_rect: ScreenRect,
) -> tuple[float, float]:
    estimated_width, estimated_height = _estimated_component_size(child)
    width = _axis_size(child, axis="width", parent_size=parent_rect.width) or estimated_width
    height = _axis_size(child, axis="height", parent_size=parent_rect.height) or estimated_height
    return (max(0.0, width), max(0.0, height))


def _scroll_config(node: HudComponentNode) -> ScrollConfig:
    try:
        return parse_scroll_config(node.attributes.get("scroll"))
    except ValueError:
        return ScrollConfig()


def _clamped_scroll_offset(
    component_id: str,
    *,
    scroll: ScrollConfig,
    viewport_rect: ScreenRect,
    content_rect: ScreenRect,
    scroll_offsets: Mapping[str, tuple[float, float]],
) -> tuple[float, float]:
    offset_x, offset_y = scroll_offsets.get(component_id, (0.0, 0.0))
    max_x = max(0.0, content_rect.width - viewport_rect.width)
    max_y = max(0.0, content_rect.height - viewport_rect.height)
    if not scroll.allows_x:
        offset_x = 0.0
    if not scroll.allows_y:
        offset_y = 0.0
    if scroll.clamp_to_content:
        offset_x = min(max(0.0, offset_x), max_x)
        offset_y = min(max(0.0, offset_y), max_y)
    return (offset_x, offset_y)


def _scroll_hit_region(
    component_id: str,
    *,
    viewport_rect: ScreenRect,
    content_rect: ScreenRect,
    scroll: ScrollConfig,
    offset_x: float,
    offset_y: float,
) -> HudScrollHitRegion:
    return HudScrollHitRegion(
        component_id=component_id,
        bounds=(viewport_rect.x, viewport_rect.y, viewport_rect.right, viewport_rect.top),
        content_width=content_rect.width,
        content_height=content_rect.height,
        offset_x=offset_x,
        offset_y=offset_y,
        axes=scroll.axes,
        wheel_axis=scroll.wheel_axis,
        wheel_step_px=scroll.wheel_step_px,
        clamp_to_content=scroll.clamp_to_content,
    )


def _scrollbar_primitives(
    region: HudScrollHitRegion,
    *,
    theme: HudTheme,
    scroll: ScrollConfig,
) -> tuple[RenderPrimitive, ...]:
    if not scroll.enabled or scroll.show_scrollbars == "never":
        return ()
    if (
        scroll.show_scrollbars == "auto"
        and region.max_offset_x <= 0.0
        and region.max_offset_y <= 0.0
    ):
        return ()
    rect = ScreenRect(
        region.bounds[0],
        region.bounds[1],
        region.viewport_width,
        region.viewport_height,
    )
    primitives: list[RenderPrimitive] = []
    if region.allows_y and (scroll.show_scrollbars == "always" or region.max_offset_y > 0.0):
        track = ScreenRect(rect.right - 5.0, rect.y + 4.0, 3.0, max(0.0, rect.height - 8.0))
        thumb_height = (
            track.height
            if region.content_height <= 0.0
            else max(16.0, track.height * min(1.0, rect.height / region.content_height))
        )
        travel = max(0.0, track.height - thumb_height)
        fraction = 0.0 if region.max_offset_y <= 0.0 else region.offset_y / region.max_offset_y
        thumb_y = track.top - thumb_height - (travel * fraction)
        thumb = ScreenRect(track.x, thumb_y, track.width, thumb_height)
        primitives.append(
            _panel(track, theme=theme, fill_color=(20, 24, 24, 94), outline_color=_TRANSPARENT)
        )
        primitives.append(
            _panel(
                thumb,
                theme=theme,
                fill_color=_with_alpha(theme.selected, 132),
                outline_color=_TRANSPARENT,
            )
        )
    if region.allows_x and (scroll.show_scrollbars == "always" or region.max_offset_x > 0.0):
        track = ScreenRect(rect.x + 4.0, rect.y + 2.0, max(0.0, rect.width - 8.0), 3.0)
        thumb_width = (
            track.width
            if region.content_width <= 0.0
            else max(16.0, track.width * min(1.0, rect.width / region.content_width))
        )
        travel = max(0.0, track.width - thumb_width)
        fraction = 0.0 if region.max_offset_x <= 0.0 else region.offset_x / region.max_offset_x
        thumb = ScreenRect(track.x + (travel * fraction), track.y, thumb_width, track.height)
        primitives.append(
            _panel(track, theme=theme, fill_color=(20, 24, 24, 94), outline_color=_TRANSPARENT)
        )
        primitives.append(
            _panel(
                thumb,
                theme=theme,
                fill_color=_with_alpha(theme.selected, 132),
                outline_color=_TRANSPARENT,
            )
        )
    return tuple(primitives)


def _translate_rect(rect: ScreenRect, *, dx: float, dy: float) -> ScreenRect:
    return ScreenRect(x=rect.x + dx, y=rect.y + dy, width=rect.width, height=rect.height)


def _rects_intersect(first: ScreenRect, second: ScreenRect) -> bool:
    return not (
        first.right <= second.x
        or second.right <= first.x
        or first.top <= second.y
        or second.top <= first.y
    )


def _rect_intersection(first: ScreenRect, second: ScreenRect) -> ScreenRect | None:
    left = max(first.x, second.x)
    right = min(first.right, second.right)
    bottom = max(first.y, second.y)
    top = min(first.top, second.top)
    if left >= right or bottom >= top:
        return None
    return ScreenRect(left, bottom, right - left, top - bottom)


def _clip_hud_button_hit_regions(
    regions: tuple[HudButtonHitRegion, ...],
    clip_rect: ScreenRect,
) -> tuple[HudButtonHitRegion, ...]:
    clipped: list[HudButtonHitRegion] = []
    for region in regions:
        next_region = _clip_hud_button_hit_region(region, clip_rect)
        if next_region is not None:
            clipped.append(next_region)
    return tuple(clipped)


def _clip_hud_button_hit_region(
    region: HudButtonHitRegion,
    clip_rect: ScreenRect,
) -> HudButtonHitRegion | None:
    left, bottom, right, top = region.bounds
    region_rect = ScreenRect(left, bottom, right - left, top - bottom)
    intersection = _rect_intersection(region_rect, clip_rect)
    if intersection is None:
        return None
    return replace(
        region,
        bounds=(intersection.x, intersection.y, intersection.right, intersection.top),
    )


def _allocated_axis_sizes(
    children: tuple[HudComponentNode, ...],
    *,
    total_size: float,
    gap_px: float,
    axis: str,
) -> tuple[float, ...]:
    if not children:
        return ()
    available = max(0.0, total_size - (gap_px * (len(children) - 1)))
    explicit_sizes: list[float | None] = []
    flexible_weight = 0.0
    fixed_total = 0.0
    for child in children:
        size = _axis_size(child, axis=axis, parent_size=available)
        explicit_sizes.append(size)
        if size is None:
            flexible_weight += _axis_flex_weight(child, axis=axis)
        else:
            fixed_total += size
    remaining = max(0.0, available - fixed_total)
    fallback_size = remaining / flexible_weight if flexible_weight > 0.0 else 0.0
    allocated: list[float] = []
    for child, size in zip(children, explicit_sizes, strict=True):
        if size is None:
            size = fallback_size * _axis_flex_weight(child, axis=axis)
        allocated.append(_constrain_axis_size(child, axis=axis, size=size, parent_size=available))
    return tuple(allocated)


def _axis_size(child: HudComponentNode, *, axis: str, parent_size: float) -> float | None:
    spec = _size_spec(child.attributes.get(axis))
    if spec is None:
        status_chip_size = _status_chip_axis_size(child)
        if status_chip_size is not None:
            return status_chip_size
        return None
    if spec.unit == "px":
        return spec.value or 0.0
    if spec.unit == "percent":
        return parent_size * ((spec.value or 0.0) / 100.0)
    if spec.unit == "fit_content":
        width, height = _estimated_component_size(child)
        return width if axis == "width" else height
    return None


def _axis_flex_weight(child: HudComponentNode, *, axis: str) -> float:
    spec = _size_spec(child.attributes.get(axis))
    if spec is not None and spec.unit == "fr":
        return spec.value or 1.0
    return 1.0


def _constrain_axis_size(
    child: HudComponentNode,
    *,
    axis: str,
    size: float,
    parent_size: float,
) -> float:
    min_size = _axis_constraint(child, f"min_{axis}", parent_size=parent_size)
    max_size = _axis_constraint(child, f"max_{axis}", parent_size=parent_size)
    constrained = max(min_size or 0.0, size)
    if max_size is not None:
        constrained = min(constrained, max_size)
    return max(0.0, constrained)


def _axis_constraint(child: HudComponentNode, key: str, *, parent_size: float) -> float | None:
    spec = _size_spec(child.attributes.get(key))
    if spec is None:
        return None
    if spec.unit == "px":
        return spec.value or 0.0
    if spec.unit == "percent":
        return parent_size * ((spec.value or 0.0) / 100.0)
    return None


def _status_chip_axis_size(child: HudComponentNode) -> float | None:
    if child.widget_type != "StatusChip":
        return None
    shape = _status_chip_shape(child)
    return shape.square_extent_px


def _estimated_component_size(child: HudComponentNode) -> tuple[float, float]:
    title = _component_title(child, data_value=None)
    subtitle = _component_subtitle(child, data_value=None)
    text_width = max(_estimated_text_width(title, 16.0), _estimated_text_width(subtitle, 12.0))
    icon_bonus = 32.0 if child.icon_id or child.attributes.get("icon_id") else 0.0
    width = max(40.0, text_width + icon_bonus + 24.0)
    height = 28.0 + (18.0 if subtitle else 0.0)
    return (width, height)


def _size_spec(value: JsonValue | None) -> SizeSpec | None:
    if value is None:
        return None
    try:
        return parse_size_spec(value)
    except ValueError:
        return None


def _estimated_text_width(text: str, font_size_px: float) -> float:
    return len(text) * font_size_px * 0.58


def _clip_enabled(node: HudComponentNode) -> bool:
    value = node.attributes.get("clip_children")
    if type(value) is bool:
        return value
    return True


def _with_clip(
    primitives: tuple[RenderPrimitive, ...],
    clip_rect: ScreenRect | None,
) -> tuple[RenderPrimitive, ...]:
    if clip_rect is None:
        return primitives
    clipped: list[RenderPrimitive] = []
    for primitive in primitives:
        if primitive.clip_rect is not None:
            clipped.append(primitive)
            continue
        clipped.append(replace(primitive, clip_rect=clip_rect))
    return tuple(clipped)


def _overflow_policy(node: HudComponentNode) -> OverflowPolicy:
    try:
        return parse_overflow_policy(node.attributes.get("overflow"))
    except ValueError:
        return OverflowPolicy()


def _status_chip_shape(node: HudComponentNode) -> StatusChipShapeSpec:
    raw_shape = node.attributes.get("shape")
    if raw_shape is None:
        raw_shape = {
            "shape": "rounded_rect",
            "diameter_px": node.attributes.get("diameter_px"),
            "size_px": node.attributes.get("size_px"),
            "preserve_aspect_ratio": node.attributes.get("preserve_aspect_ratio"),
        }
    try:
        return parse_status_chip_shape(raw_shape)
    except ValueError:
        return StatusChipShapeSpec()


def _overflow_text(
    text: str,
    *,
    width_px: float,
    font_size_px: float,
    policy: OverflowPolicy,
) -> str:
    if policy.mode in ("clip", "visible", "scroll"):
        return text
    max_chars = _max_chars(width_px, font_size_px)
    if policy.mode == "wrap":
        return _truncate(text, max_chars=max_chars * max(1, policy.max_lines))
    return _truncate(text, max_chars=max_chars)


def _font_size_for_text(
    text: str,
    *,
    width_px: float,
    font_size_px: float,
    policy: OverflowPolicy,
) -> float:
    if policy.mode != "shrink_to_fit":
        return font_size_px
    if _estimated_text_width(text, font_size_px) <= width_px:
        return font_size_px
    if not text:
        return font_size_px
    estimated = width_px / (len(text) * 0.58)
    return max(policy.min_font_size_px, min(font_size_px, estimated))


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


def _data_object(value: JsonValue | None) -> JsonObject:
    if type(value) is dict:
        return value
    return {}


def _object_items(value: JsonValue | None) -> tuple[JsonObject, ...]:
    if type(value) is not list:
        return ()
    items: list[JsonObject] = []
    for item in value:
        if type(item) is dict:
            items.append(item)
    return tuple(items)


def _string_items(value: JsonValue | None) -> tuple[str, ...]:
    if type(value) is not list:
        return ()
    return tuple(item for item in value if type(item) is str and item)


def _face_rows(data: JsonObject) -> tuple[JsonObject, ...]:
    faces = _object_items(data.get("faces"))
    return tuple(face for face in faces if 1 <= _int_value(face.get("face"), default=0) <= 6)[:6]


def _int_value(value: JsonValue | None, *, default: int) -> int:
    if type(value) is int:
        return value
    return default


def _bool_value(value: JsonValue | None, *, default: bool) -> bool:
    if type(value) is bool:
        return value
    return default


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


def _attribute_int(node: HudComponentNode, key: str, *, default: int) -> int:
    value = node.attributes.get(key)
    if type(value) is int:
        return value
    return default


def _attribute_bool(node: HudComponentNode, key: str, *, default: bool) -> bool:
    value = node.attributes.get(key)
    if type(value) is bool:
        return value
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
    if max_chars <= 3:
        return text[:max_chars]
    return f"{text[: max_chars - 3]}..."


def _max_chars(width_px: float, font_size_px: float) -> int:
    if font_size_px <= 0.0:
        return 1
    return max(1, int(width_px / (font_size_px * 0.58)))
