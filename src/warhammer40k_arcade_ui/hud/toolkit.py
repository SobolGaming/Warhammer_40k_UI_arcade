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
type HudSizeUnit = Literal["px", "percent", "fr", "fit_content", "fill", "auto"]
type HudOverflowMode = Literal["clip", "ellipsis", "wrap", "shrink_to_fit", "scroll", "visible"]
type HudRenderMode = Literal["none", "panel", "outline", "debug_bounds"]
type HudStatusChipShape = Literal["round", "square", "rounded_rect", "pill"]
type HudScrollAxis = Literal["x", "y", "both"]
type HudWheelAxis = Literal["x", "y", "auto"]
type HudScrollbarVisibility = Literal["never", "auto", "always"]
type HudButtonActionKind = Literal[
    "none",
    "finite_option",
    "local_command",
    "select_unit",
    "placement_submit",
    "placement_clear",
    "placement_next_model",
    "assignment_submit",
    "assignment_decline",
    "assignment_clear",
]
type HudButtonShape = Literal["rect", "rounded_rect", "pill", "square"]
type HudButtonIconSide = Literal["left", "right", "both", "center", "none"]
type CurrentActionSourceKind = Literal[
    "engine_finite",
    "engine_parameterized",
    "local_gui",
    "none",
]
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
    "CurrentActionPanel",
    "StratagemButton",
    "AssignmentGroupRow",
    "DicePipeline",
    "DiceTray",
    "PlayerUnitsRoster",
    "Tooltip",
    "Separator",
]


@dataclass(frozen=True, slots=True)
class SizeSpec:
    """Parsed HUD size value for deterministic layout allocation."""

    unit: HudSizeUnit
    value: float | None = None

    @property
    def is_flexible(self) -> bool:
        """Return whether this size consumes remaining sibling space."""

        return self.unit in ("fr", "fill", "auto")


@dataclass(frozen=True, slots=True)
class OverflowPolicy:
    """Text and child overflow behavior for a component."""

    mode: HudOverflowMode = "ellipsis"
    max_lines: int = 1
    min_font_size_px: float = 10.0
    preserve_icon: bool = True
    debug_bounds: bool = False


@dataclass(frozen=True, slots=True)
class ScrollConfig:
    """Interactive child-content scroll behavior for a HUD component."""

    enabled: bool = False
    axes: HudScrollAxis = "y"
    wheel_axis: HudWheelAxis = "y"
    show_scrollbars: HudScrollbarVisibility = "auto"
    wheel_step_px: float = 48.0
    drag_scrollbars: bool = False
    clamp_to_content: bool = True

    @property
    def allows_x(self) -> bool:
        """Return whether horizontal scrolling is enabled."""

        return self.enabled and self.axes in ("x", "both")

    @property
    def allows_y(self) -> bool:
        """Return whether vertical scrolling is enabled."""

        return self.enabled and self.axes in ("y", "both")


@dataclass(frozen=True, slots=True)
class StatusChipShapeSpec:
    """Shape controls for compact status chips."""

    shape: HudStatusChipShape = "rounded_rect"
    diameter_px: float | None = None
    size_px: float | None = None
    corner_radius_px: float = 0.0
    preserve_aspect_ratio: bool = True
    content_alignment: HudAlignment = "center"

    @property
    def square_extent_px(self) -> float | None:
        """Return the configured square extent for round/square chips."""

        if self.shape == "round":
            return self.diameter_px
        if self.shape == "square":
            return self.size_px
        return None


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
class HudButtonView:
    """Reusable presentation-only HUD button with optional engine selection metadata."""

    component_id: str
    button_id: str
    command_id: str
    label: str
    action_kind: HudButtonActionKind = "none"
    option_id: str | None = None
    request_id: str | None = None
    icon_id: str | None = None
    text_icon: str = ""
    tooltip: str = ""
    hotkey_hint: str = ""
    state: HudState = "normal"
    color_role: HudColorRole = "neutral"
    selected: bool = False
    focused: bool = False
    enabled: bool = True
    disabled_reason: str = ""
    visual_role: HudColorRole = "neutral"
    unit_id: str | None = None
    metadata: JsonObject | None = None


@dataclass(frozen=True, slots=True)
class CurrentActionView:
    """Compact presentation model for the GUI user's current workflow surface."""

    component_id: str
    title: str = "Current Action"
    request_summary: str = ""
    actor_summary: str = ""
    advisory_status: str = "No active action"
    selected_action_id: str | None = None
    buttons: tuple[HudButtonView, ...] = ()
    confirm_hint: str = ""
    cancel_hint: str = ""
    source_kind: CurrentActionSourceKind = "none"


@dataclass(frozen=True, slots=True)
class HudButtonHitRegion:
    """Frame-local hit-test metadata for a rendered HUD button."""

    component_id: str
    button_id: str
    action_kind: HudButtonActionKind
    command_id: str
    enabled: bool
    bounds: tuple[float, float, float, float]
    option_id: str | None = None
    request_id: str | None = None
    unit_id: str | None = None
    disabled_reason: str = ""

    def contains(self, screen_x: float, screen_y: float) -> bool:
        """Return whether a screen-space point is inside this hit region."""

        left, bottom, right, top = self.bounds
        return left <= screen_x <= right and bottom <= screen_y <= top


@dataclass(frozen=True, slots=True)
class HudScrollHitRegion:
    """Frame-local hit-test metadata for a scrollable HUD viewport."""

    component_id: str
    bounds: tuple[float, float, float, float]
    content_width: float
    content_height: float
    offset_x: float
    offset_y: float
    axes: HudScrollAxis
    wheel_axis: HudWheelAxis
    wheel_step_px: float
    clamp_to_content: bool = True

    @property
    def viewport_width(self) -> float:
        """Return viewport width in screen pixels."""

        left, _, right, _ = self.bounds
        return max(0.0, right - left)

    @property
    def viewport_height(self) -> float:
        """Return viewport height in screen pixels."""

        _, bottom, _, top = self.bounds
        return max(0.0, top - bottom)

    @property
    def max_offset_x(self) -> float:
        """Return the largest horizontal scroll offset allowed by current content."""

        return max(0.0, self.content_width - self.viewport_width)

    @property
    def max_offset_y(self) -> float:
        """Return the largest vertical scroll offset allowed by current content."""

        return max(0.0, self.content_height - self.viewport_height)

    @property
    def allows_x(self) -> bool:
        """Return whether this scroll region accepts horizontal scroll input."""

        return self.axes in ("x", "both")

    @property
    def allows_y(self) -> bool:
        """Return whether this scroll region accepts vertical scroll input."""

        return self.axes in ("y", "both")

    def contains(self, screen_x: float, screen_y: float) -> bool:
        """Return whether a screen-space point is inside this scroll region."""

        left, bottom, right, top = self.bounds
        return left <= screen_x <= right and bottom <= screen_y <= top


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
        "icons",
        "aspect_ratio",
        "max_width",
        "max_height",
        "min_width",
        "min_height",
        "opacity",
        "overflow",
        "padding",
        "scroll",
        "shape",
        "state",
        "slots",
        "text",
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
        (
            "diameter_px",
            "icon_id",
            "label",
            "preserve_aspect_ratio",
            "progress_fraction",
            "size_px",
            "value",
        )
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
            "stat_cell_gap",
            "stat_cell_height",
            "stat_cell_min_width",
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
    "CurrentActionPanel": frozenset(
        (
            "button_gap",
            "button_height",
            "button_min_width",
            "max_buttons_per_row",
            "button_shape",
            "cancel_hint",
            "confirm_hint",
            "max_buttons",
            "show_actor",
            "show_request",
            "title",
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
    "DiceTray": frozenset(
        (
            "bucket_label",
            "compact",
            "count_only_threshold",
            "dice_face_asset_ids",
            "face_icon_size",
            "history_visible",
            "max_visible_dice_per_face",
            "show_source",
            "title",
        )
    ),
    "PlayerUnitsRoster": frozenset(
        (
            "button_gap",
            "button_height",
            "button_min_width",
            "button_shape",
            "max_visible_rows",
            "status_icon_text",
            "subtitle",
            "title",
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
            "decision.attack_resolution",
            "decision.complete_phase",
            "decision.melee",
            "decision.stratagem",
            "dice.damage",
            "dice.aeldari.d6.face_1",
            "dice.aeldari.d6.face_2",
            "dice.aeldari.d6.face_3",
            "dice.aeldari.d6.face_4",
            "dice.aeldari.d6.face_5",
            "dice.aeldari.d6.face_6",
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
            "phase.command",
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
            "hud.selected_unit.card",
            "hud.selected_unit.rows",
            "hud.status_chips",
            "hud.status_chips.active_player",
            "hud.status_chips.pending",
            "hud.status_chips.phase",
            "hud.workbench.actions",
            "hud.workbench.assignments.groups",
            "hud.workbench.assignments.notices",
            "hud.dice_tray.active",
            "hud.workbench.review.diagnostics",
            "hud.workbench.review.events",
            "hud.workbench.review.hotkeys",
            "hud.player_units.roster",
            "mission_summary",
            "movement_budget",
            "dice_tray",
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


def parse_size_spec(value: JsonValue) -> SizeSpec:
    """Parse a JSON-safe size value into a typed size specification."""

    if type(value) is int or type(value) is float:
        size = float(value)
        if size < 0.0:
            raise ValueError("size values must not be negative")
        return SizeSpec(unit="px", value=size)
    if type(value) is not str:
        raise ValueError("size values must be numbers or strings")
    text = value.strip()
    if not text:
        raise ValueError("size values must not be empty")
    if text in ("fit-content", "fit_content"):
        return SizeSpec(unit="fit_content")
    if text == "fill":
        return SizeSpec(unit="fill")
    if text == "auto":
        return SizeSpec(unit="auto")
    if text.endswith("px"):
        return SizeSpec(unit="px", value=_positive_float(text[:-2], "px size"))
    if text.endswith("%"):
        percent = _positive_float(text[:-1], "percentage size")
        if percent > 100.0:
            raise ValueError("percentage sizes must not exceed 100%")
        return SizeSpec(unit="percent", value=percent)
    if text.endswith("fr"):
        fraction = _positive_float(text[:-2], "fraction size")
        if fraction <= 0.0:
            raise ValueError("fraction sizes must be greater than zero")
        return SizeSpec(unit="fr", value=fraction)
    raise ValueError(f"unsupported size unit: {text}")


def parse_overflow_policy(value: JsonValue | None) -> OverflowPolicy:
    """Parse a JSON-safe overflow value into a typed overflow policy."""

    if value is None:
        return OverflowPolicy()
    if type(value) is str:
        return OverflowPolicy(mode=_overflow_mode(value))
    if type(value) is not dict:
        raise ValueError("overflow must be a string or object")
    raw_mode = value.get("mode", "ellipsis")
    mode = _overflow_mode(raw_mode) if type(raw_mode) is str else _invalid_overflow_mode()
    max_lines = _positive_int(value.get("max_lines"), default=1, label="overflow.max_lines")
    min_font_size_px = _positive_float_value(
        value.get("min_font_size_px"),
        default=10.0,
        label="overflow.min_font_size_px",
    )
    preserve_icon = _bool_value(value.get("preserve_icon"), default=True, label="preserve_icon")
    debug_bounds = _bool_value(value.get("debug_bounds"), default=False, label="debug_bounds")
    return OverflowPolicy(
        mode=mode,
        max_lines=max_lines,
        min_font_size_px=min_font_size_px,
        preserve_icon=preserve_icon,
        debug_bounds=debug_bounds,
    )


def parse_scroll_config(value: JsonValue | None) -> ScrollConfig:
    """Parse a JSON-safe scroll config into typed scroll behavior."""

    if value is None:
        return ScrollConfig()
    if type(value) is bool:
        return ScrollConfig(enabled=value)
    if type(value) is str:
        return ScrollConfig(enabled=True, axes=_scroll_axis(value))
    if type(value) is not dict:
        raise ValueError("scroll must be a boolean, axis string, or object")
    enabled = _bool_value(value.get("enabled"), default=False, label="scroll.enabled")
    raw_axes = value.get("axes", "y")
    axes = _scroll_axis(raw_axes) if type(raw_axes) is str else _invalid_scroll_axis()
    raw_wheel_axis = value.get("wheel_axis", "y")
    wheel_axis = (
        _wheel_axis(raw_wheel_axis) if type(raw_wheel_axis) is str else _invalid_wheel_axis()
    )
    raw_scrollbars = value.get("show_scrollbars", "auto")
    show_scrollbars = (
        _scrollbar_visibility(raw_scrollbars)
        if type(raw_scrollbars) is str
        else _invalid_scrollbar_visibility()
    )
    wheel_step_px = _positive_float_value(
        value.get("wheel_step_px"),
        default=48.0,
        label="scroll.wheel_step_px",
    )
    if wheel_step_px <= 0.0:
        raise ValueError("scroll.wheel_step_px must be greater than zero")
    drag_scrollbars = _bool_value(
        value.get("drag_scrollbars"),
        default=False,
        label="scroll.drag_scrollbars",
    )
    clamp_to_content = _bool_value(
        value.get("clamp_to_content"),
        default=True,
        label="scroll.clamp_to_content",
    )
    return ScrollConfig(
        enabled=enabled,
        axes=axes,
        wheel_axis=wheel_axis,
        show_scrollbars=show_scrollbars,
        wheel_step_px=wheel_step_px,
        drag_scrollbars=drag_scrollbars,
        clamp_to_content=clamp_to_content,
    )


def parse_status_chip_shape(value: JsonValue | None) -> StatusChipShapeSpec:
    """Parse status-chip shape controls from JSON-safe YAML data."""

    if value is None:
        return StatusChipShapeSpec()
    if type(value) is str:
        return StatusChipShapeSpec(shape=_status_chip_shape(value))
    if type(value) is not dict:
        raise ValueError("status chip shape must be a string or object")
    raw_shape = value.get("shape", "rounded_rect")
    shape = _status_chip_shape(raw_shape) if type(raw_shape) is str else _invalid_status_shape()
    diameter_px = _optional_positive_float(value.get("diameter_px"), label="shape.diameter_px")
    size_px = _optional_positive_float(value.get("size_px"), label="shape.size_px")
    corner_radius_px = _positive_float_value(
        value.get("corner_radius_px"),
        default=0.0,
        label="shape.corner_radius_px",
    )
    preserve_aspect_ratio = _bool_value(
        value.get("preserve_aspect_ratio"),
        default=True,
        label="shape.preserve_aspect_ratio",
    )
    raw_alignment = value.get("content_alignment", "center")
    content_alignment: HudAlignment = "center"
    if raw_alignment == "start":
        content_alignment = "start"
    elif raw_alignment == "center":
        content_alignment = "center"
    elif raw_alignment == "end":
        content_alignment = "end"
    elif raw_alignment == "stretch":
        content_alignment = "stretch"
    elif raw_alignment is not None:
        raise ValueError("shape.content_alignment must be start, center, end, or stretch")
    return StatusChipShapeSpec(
        shape=shape,
        diameter_px=diameter_px,
        size_px=size_px,
        corner_radius_px=corner_radius_px,
        preserve_aspect_ratio=preserve_aspect_ratio,
        content_alignment=content_alignment,
    )


def json_text(value: JsonValue | None, *, default: str = "") -> str:
    """Return a compact display string for YAML sample/runtime values."""

    if type(value) is str:
        return value
    if type(value) is int or type(value) is float or type(value) is bool:
        return str(value)
    return default


def _overflow_mode(value: str) -> HudOverflowMode:
    if value == "clip":
        return "clip"
    if value == "ellipsis":
        return "ellipsis"
    if value == "wrap":
        return "wrap"
    if value == "shrink_to_fit":
        return "shrink_to_fit"
    if value == "scroll":
        return "scroll"
    if value == "visible":
        return "visible"
    raise ValueError(
        "overflow.mode must be clip, ellipsis, wrap, shrink_to_fit, scroll, or visible"
    )


def _invalid_overflow_mode() -> HudOverflowMode:
    raise ValueError("overflow.mode must be a string")


def _status_chip_shape(value: str) -> HudStatusChipShape:
    if value == "round":
        return "round"
    if value == "square":
        return "square"
    if value == "rounded_rect":
        return "rounded_rect"
    if value == "pill":
        return "pill"
    raise ValueError("status chip shape must be round, square, rounded_rect, or pill")


def _invalid_status_shape() -> HudStatusChipShape:
    raise ValueError("shape.shape must be a string")


def _scroll_axis(value: str) -> HudScrollAxis:
    if value == "x":
        return "x"
    if value == "y":
        return "y"
    if value == "both":
        return "both"
    raise ValueError("scroll.axes must be x, y, or both")


def _invalid_scroll_axis() -> HudScrollAxis:
    raise ValueError("scroll.axes must be a string")


def _wheel_axis(value: str) -> HudWheelAxis:
    if value == "x":
        return "x"
    if value == "y":
        return "y"
    if value == "auto":
        return "auto"
    raise ValueError("scroll.wheel_axis must be x, y, or auto")


def _invalid_wheel_axis() -> HudWheelAxis:
    raise ValueError("scroll.wheel_axis must be a string")


def _scrollbar_visibility(value: str) -> HudScrollbarVisibility:
    if value == "never":
        return "never"
    if value == "auto":
        return "auto"
    if value == "always":
        return "always"
    raise ValueError("scroll.show_scrollbars must be never, auto, or always")


def _invalid_scrollbar_visibility() -> HudScrollbarVisibility:
    raise ValueError("scroll.show_scrollbars must be a string")


def _positive_float(text: str, label: str) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise ValueError(f"{label} must contain a number") from exc
    if value < 0.0:
        raise ValueError(f"{label} must not be negative")
    return value


def _optional_positive_float(value: JsonValue | None, *, label: str) -> float | None:
    if value is None:
        return None
    return _positive_float_value(value, default=0.0, label=label)


def _positive_float_value(value: JsonValue | None, *, default: float, label: str) -> float:
    if value is None:
        return default
    if type(value) is not int and type(value) is not float:
        raise ValueError(f"{label} must be numeric")
    numeric = float(value)
    if numeric < 0.0:
        raise ValueError(f"{label} must not be negative")
    return numeric


def _positive_int(value: JsonValue | None, *, default: int, label: str) -> int:
    if value is None:
        return default
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer")
    if value < 1:
        raise ValueError(f"{label} must be at least 1")
    return value


def _bool_value(value: JsonValue | None, *, default: bool, label: str) -> bool:
    if value is None:
        return default
    if type(value) is not bool:
        raise ValueError(f"{label} must be true or false")
    return value
