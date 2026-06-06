"""Reusable presentation-only HUD widget toolkit models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from warhammer40k_arcade_ui.preferences.schema import JsonObject, JsonValue
from warhammer40k_arcade_ui.render.primitives import Color

type HudDensity = Literal["compact", "standard", "detailed"]
type HudState = Literal[
    "normal",
    "hover",
    "focus",
    "selected",
    "active",
    "disabled",
    "warning",
    "invalid",
]
type HudColorRole = Literal[
    "player",
    "opponent",
    "neutral",
    "active",
    "selected",
    "warning",
    "invalid",
    "disabled",
    "preview",
    "authoritative",
    "debug",
]
type HudLayoutKind = Literal["stack", "grid", "anchor", "overlay"]
type HudOrientation = Literal["vertical", "horizontal"]
type HudAlignment = Literal["start", "center", "end", "stretch"]
type HudRenderMode = Literal["none", "panel", "outline", "debug_bounds"]
type HudWidgetType = Literal[
    "HudContainer",
    "HudPanel",
    "IconSlot",
    "IconTextBar",
    "StatusChip",
    "EntityChip",
    "DonutGauge",
    "UnitRailCard",
    "DatasheetHeader",
    "DatasheetPanel",
    "StatStrip",
    "StatCell",
    "MissionCard",
    "ActionButton",
    "StratagemButton",
    "AssignmentGroupRow",
    "DicePipeline",
    "Tooltip",
    "Separator",
]


@dataclass(frozen=True, slots=True)
class HudTheme:
    """Stable visual tokens for HUD widgets."""

    theme_id: str
    density: HudDensity
    font_family: str
    base_font_size_px: float
    compact_font_size_px: float
    title_font_size_px: float
    line_height_px: float
    gap_x_px: float
    gap_y_px: float
    inner_padding_px: float
    outer_margin_px: float
    icon_size_px: float
    panel_fill: Color
    panel_border: Color
    text: Color
    muted_text: Color
    accent: Color
    player: Color
    opponent: Color
    neutral: Color
    active: Color
    selected: Color
    warning: Color
    invalid: Color
    disabled: Color
    preview: Color
    authoritative: Color
    debug: Color
    high_contrast: bool = False

    def color_for_role(self, role: str | None) -> Color:
        """Return a configured color role, defaulting to neutral for unknown local values."""

        if role == "player":
            return self.player
        if role == "opponent":
            return self.opponent
        if role == "active":
            return self.active
        if role == "selected":
            return self.selected
        if role == "warning":
            return self.warning
        if role == "invalid":
            return self.invalid
        if role == "disabled":
            return self.disabled
        if role == "preview":
            return self.preview
        if role == "authoritative":
            return self.authoritative
        if role == "debug":
            return self.debug
        return self.neutral


@dataclass(frozen=True, slots=True)
class HudLayoutSpec:
    """Parent-relative layout hints for a widget's children."""

    kind: HudLayoutKind
    orientation: HudOrientation = "vertical"
    columns: int = 1
    gap_px: float = 8.0
    padding_px: float = 8.0
    alignment: HudAlignment = "stretch"


@dataclass(frozen=True, slots=True)
class HudComponentNode:
    """One parsed widget node in a composition tree."""

    widget_type: HudWidgetType
    widget_id: str
    attributes: JsonObject
    layout: HudLayoutSpec
    children: tuple[HudComponentNode, ...] = ()
    icon_id: str | None = None
    data_ref: str | None = None


@dataclass(frozen=True, slots=True)
class HudContainerView:
    """General parent container for nesting subpanels."""

    component_id: str
    render_mode: HudRenderMode = "none"
    layout: HudLayoutSpec = HudLayoutSpec(kind="stack")
    clip_children: bool = True
    state: HudState = "normal"


@dataclass(frozen=True, slots=True)
class HudPanelView:
    """Renderable framed panel for cards, inspectors, workbenches, and popovers."""

    component_id: str
    title: str = ""
    subtitle: str = ""
    density: HudDensity = "standard"
    state: HudState = "normal"


@dataclass(frozen=True, slots=True)
class IconSlotView:
    """Single icon rendering unit using the future icon registry."""

    component_id: str
    icon_id: str
    size_px: float = 24.0
    color_role: HudColorRole = "neutral"
    opacity: float = 1.0
    badge_text: str = ""


class IconTextureCache(Protocol):
    """Future seam for resolving icon IDs to cached Arcade textures."""

    def texture_for_icon(
        self,
        icon_id: str,
        *,
        color_role: HudColorRole,
        size_px: float,
    ) -> object | None:
        """Return a cached texture for an icon ID, or None to render a placeholder."""

        ...


@dataclass(frozen=True, slots=True)
class IconTextBarView:
    """Compact bar with an icon and one or more text fields."""

    component_id: str
    primary_label: str
    icon_id: str | None = None
    secondary_label: str = ""
    value_text: str = ""
    icon_side: Literal["left", "right", "both", "none"] = "left"
    density: HudDensity = "standard"
    state: HudState = "normal"


@dataclass(frozen=True, slots=True)
class StatusChipView:
    """Small scalar status or counter element."""

    component_id: str
    label: str
    value: str = ""
    icon_id: str | None = None
    color_role: HudColorRole = "neutral"
    state: HudState = "normal"


@dataclass(frozen=True, slots=True)
class EntityChipView:
    """Compact reference to a selectable or assignable entity."""

    component_id: str
    entity_ref: str
    display_label: str
    entity_kind_icon_id: str | None = None
    color_role: HudColorRole = "neutral"
    state: HudState = "normal"


@dataclass(frozen=True, slots=True)
class DonutGaugeView:
    """Ring/donut visual for bounded scalar values and readiness progress."""

    component_id: str
    inner_diameter_px: float
    outer_diameter_px: float
    progress_fraction: float
    label_text: str = ""
    color_role: HudColorRole = "active"
    segment_count: int = 1


@dataclass(frozen=True, slots=True)
class UnitRailCardView:
    """Compact unit tab/card for a rail or bench roster."""

    component_id: str
    unit_label: str
    short_label: str = ""
    model_count_summary: str = ""
    activation_state: str = "ready"
    color_role: HudColorRole = "player"


@dataclass(frozen=True, slots=True)
class DatasheetHeaderView:
    """Header area for selected unit or model datasheets."""

    component_id: str
    title: str
    subtitle: str = ""
    faction_icon_id: str | None = None
    color_role: HudColorRole = "player"


@dataclass(frozen=True, slots=True)
class DatasheetPanelView:
    """Composed unit/model datasheet card placeholder."""

    component_id: str
    title: str = ""
    density: HudDensity = "standard"
    stat_zone_visible: bool = True
    weapon_zone_visible: bool = True
    ability_zone_visible: bool = True
    keyword_zone_visible: bool = True


@dataclass(frozen=True, slots=True)
class StatCellView:
    """One compact labeled stat cell."""

    component_id: str
    label: str
    value: str
    icon_id: str | None = None
    emphasis_state: str = "same"


@dataclass(frozen=True, slots=True)
class StatStripView:
    """Compact row/grid of stat cells."""

    component_id: str
    cells: tuple[StatCellView, ...]
    columns: int = 3
    density: HudDensity = "compact"


@dataclass(frozen=True, slots=True)
class MissionCardView:
    """Card-like presentation for mission information."""

    component_id: str
    title: str
    subtitle: str = ""
    card_type: str = "mission"
    reveal_state: str = "revealed"


@dataclass(frozen=True, slots=True)
class ActionButtonView:
    """Clickable command element for known UI commands."""

    component_id: str
    command_id: str
    label: str
    icon_id: str | None = None
    hotkey_hint: str = ""
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class StratagemButtonView:
    """Specialized action button shape for Stratagem-like options."""

    component_id: str
    title: str
    cp_cost_text: str = ""
    eligibility_state: str = "unknown"
    icon_id: str | None = None


@dataclass(frozen=True, slots=True)
class AssignmentGroupRowView:
    """Row summarizing one generic assignment group."""

    component_id: str
    group_label: str
    operation_kind: str = ""
    state: HudState = "normal"
    summary_lines: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DicePipelineView:
    """Placeholder-ready component for future attack resolution."""

    component_id: str
    pipeline_steps: tuple[str, ...]
    current_step: str = ""
    compact: bool = True


@dataclass(frozen=True, slots=True)
class TooltipView:
    """Transient hover/detail text container."""

    component_id: str
    title: str
    body: str = ""


@dataclass(frozen=True, slots=True)
class SeparatorView:
    """Visual separator between sibling widget groups."""

    component_id: str
    orientation: HudOrientation = "horizontal"
    color_role: HudColorRole = "neutral"


@dataclass(frozen=True, slots=True)
class HudWidgetDefinition:
    """Registry entry for a supported widget type."""

    widget_type: HudWidgetType
    allowed_attributes: frozenset[str]


_COMMON_ATTRIBUTES = frozenset(
    (
        "alignment",
        "alpha",
        "background_alpha",
        "border_alpha",
        "border_color_role",
        "border_width",
        "clip_children",
        "color_role",
        "debug_label_visible",
        "density",
        "fill_color_role",
        "height",
        "max_width",
        "min_width",
        "opacity",
        "padding",
        "state",
        "tooltip_key",
        "width",
        "z_order",
    )
)

_WIDGET_ATTRIBUTES: dict[HudWidgetType, frozenset[str]] = {
    "HudContainer": frozenset(
        (
            "anchor",
            "gap",
            "max_size",
            "min_size",
            "offset",
            "rect",
            "render_mode",
            "scroll_policy",
            "size_policy",
        )
    ),
    "HudPanel": frozenset(
        (
            "collapse_state",
            "collapsed_size",
            "content_gap",
            "footer_visible",
            "header_visible",
            "subtitle",
            "title",
            "title_padding",
        )
    ),
    "IconSlot": frozenset(("badge_text", "fallback_glyph", "icon_size", "shape", "size")),
    "IconTextBar": frozenset(
        (
            "height",
            "hotkey_hint",
            "icon_side",
            "icon_size",
            "primary_label",
            "secondary_label",
            "text_alignment",
            "truncation_policy",
            "underline_style",
            "value_text",
        )
    ),
    "StatusChip": frozenset(
        ("icon_id", "label", "min_width", "progress_fraction", "shape", "value")
    ),
    "EntityChip": frozenset(
        (
            "badge_count",
            "compact_mode",
            "display_label",
            "entity_ref",
            "expanded_mode",
            "warning_marker",
        )
    ),
    "DonutGauge": frozenset(
        (
            "background_ring_alpha",
            "center_icon_id",
            "gap_between_segments",
            "inner_diameter",
            "label_text",
            "outer_diameter",
            "progress_fraction",
            "segment_count",
            "start_angle",
            "sweep_angle",
        )
    ),
    "UnitRailCard": frozenset(
        (
            "activation_state",
            "compact",
            "expanded",
            "model_count_summary",
            "short_label",
            "status_summary",
            "unit_label",
        )
    ),
    "DatasheetHeader": frozenset(
        (
            "badges",
            "collapse_control_visible",
            "faction_icon_id",
            "status_chips",
            "subtitle",
            "title",
        )
    ),
    "DatasheetPanel": frozenset(
        (
            "ability_zone_visible",
            "comparison_mode",
            "debug_source_fields_visible",
            "footer_action_row_visible",
            "keyword_zone_visible",
            "stat_zone_visible",
            "title",
            "weapon_zone_visible",
            "zone_order",
        )
    ),
    "StatStrip": frozenset(("cells", "columns", "stat_labels", "stat_values")),
    "StatCell": frozenset(("delta_state", "emphasis_state", "icon_id", "label", "value")),
    "MissionCard": frozenset(
        (
            "card_type",
            "compact",
            "expanded",
            "owner_color_role",
            "progress_chips",
            "reveal_state",
            "score",
            "subtitle",
            "title",
        )
    ),
    "ActionButton": frozenset(
        (
            "command_id",
            "confirmation_required",
            "disabled_reason",
            "enabled",
            "hotkey_hint",
            "icon_side",
            "label",
        )
    ),
    "StratagemButton": frozenset(
        (
            "cp_cost_badge",
            "eligibility_state",
            "hotkey_hint",
            "phase_badge",
            "target_summary",
            "title",
        )
    ),
    "AssignmentGroupRow": frozenset(
        (
            "detailed",
            "expanded",
            "group_label",
            "operation_kind",
            "source_entity_chips",
            "summary_lines",
            "target_entity_chips",
        )
    ),
    "DicePipeline": frozenset(
        (
            "compact",
            "current_step",
            "dice_pool_summaries",
            "history_visible",
            "modifier_chips",
            "pipeline_steps",
        )
    ),
    "Tooltip": frozenset(("body", "title")),
    "Separator": frozenset(("orientation",)),
}


def default_hud_theme(*, density: HudDensity = "standard", high_contrast: bool = False) -> HudTheme:
    """Return the built-in HUD theme tokens."""

    text = (248, 250, 242, 255) if high_contrast else (238, 241, 233, 255)
    panel_alpha = 214 if high_contrast else 156
    return HudTheme(
        theme_id="default-high-contrast" if high_contrast else "default",
        density=density,
        font_family="Arial",
        base_font_size_px=14.0,
        compact_font_size_px=12.0,
        title_font_size_px=16.0,
        line_height_px=18.0,
        gap_x_px=8.0,
        gap_y_px=8.0,
        inner_padding_px=10.0,
        outer_margin_px=12.0,
        icon_size_px=24.0,
        panel_fill=(14, 18, 20, panel_alpha),
        panel_border=(164, 177, 170, 180 if high_contrast else 148),
        text=text,
        muted_text=(178, 190, 184, 255),
        accent=(255, 222, 135, 255),
        player=(80, 155, 235, 255),
        opponent=(235, 110, 95, 255),
        neutral=(152, 165, 176, 255),
        active=(132, 232, 255, 255),
        selected=(255, 225, 96, 255),
        warning=(255, 168, 94, 255),
        invalid=(248, 92, 92, 255),
        disabled=(130, 136, 132, 150),
        preview=(102, 220, 180, 150),
        authoritative=(122, 214, 156, 255),
        debug=(202, 156, 255, 255),
        high_contrast=high_contrast,
    )


def widget_registry() -> dict[str, HudWidgetDefinition]:
    """Return known widget types and their tunable attributes."""

    return {
        widget_type: HudWidgetDefinition(
            widget_type=widget_type,
            allowed_attributes=_COMMON_ATTRIBUTES | attributes,
        )
        for widget_type, attributes in _WIDGET_ATTRIBUTES.items()
    }


def known_widget_types() -> frozenset[str]:
    """Return all supported composition widget types."""

    return frozenset(widget_registry())


def component_allowed_attributes(widget_type: str) -> frozenset[str]:
    """Return tunable attributes for a widget type, or an empty set for unknown values."""

    definition = widget_registry().get(widget_type)
    if definition is None:
        return frozenset()
    return definition.allowed_attributes


def known_icon_ids() -> frozenset[str]:
    """Return the placeholder-safe icon IDs currently supported by preview validation."""

    return frozenset(
        (
            "action.cancel",
            "action.confirm",
            "action.inspect",
            "action.measure",
            "action.movement",
            "action.summary",
            "dice.damage",
            "dice.hit",
            "dice.save",
            "dice.wound",
            "entity.model",
            "entity.objective",
            "entity.terrain",
            "entity.unit",
            "mission.primary",
            "mission.secondary",
            "phase.movement",
            "status.active",
            "status.invalid",
            "status.selected",
            "status.warning",
            "stratagem.generic",
            "unit.battleline",
        )
    )


def known_data_refs() -> frozenset[str]:
    """Return safe runtime/preview data reference keys."""

    return frozenset(
        (
            "active_player",
            "assignment_groups",
            "command_points",
            "current_action",
            "current_assignment",
            "debug_status",
            "mission_summary",
            "movement_budget",
            "opponent_roster",
            "phase_state",
            "player_roster",
            "selected_model",
            "selected_unit",
            "selection_status",
        )
    )


def widget_type_from_string(raw_type: str) -> HudWidgetType | None:
    """Return a typed widget identifier for a validated registry value."""

    if raw_type in _WIDGET_ATTRIBUTES:
        return raw_type
    return None


def json_text(value: JsonValue | None, *, default: str = "") -> str:
    """Return a compact display string for YAML sample/runtime values."""

    if type(value) is str:
        return value
    if type(value) is int or type(value) is float or type(value) is bool:
        return str(value)
    return default
