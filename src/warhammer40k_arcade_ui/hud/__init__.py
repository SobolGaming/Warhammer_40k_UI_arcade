"""HUD view models derived from viewer-scoped UI state."""

from warhammer40k_arcade_ui.hud.action_summary import (
    ActionVisualSummary,
    ActionVisualSummaryGroup,
    build_action_visual_summary,
)
from warhammer40k_arcade_ui.hud.layouts import (
    HudLayoutView,
    HudRegionView,
    ScreenRect,
    build_hud_layout,
)
from warhammer40k_arcade_ui.hud.view_models import (
    ContextMenuAction,
    ContextMenuView,
    DebugInspectorView,
    FiniteDecisionOptionView,
    FiniteDecisionPanelView,
    MovementDraftPanelView,
    UnitPanelView,
    build_context_menu,
    build_debug_inspector,
    build_finite_decision_panel,
    build_movement_draft_panel,
    build_unit_panel,
    decision_targets_unit,
)

__all__ = [
    "ActionVisualSummary",
    "ActionVisualSummaryGroup",
    "ContextMenuAction",
    "ContextMenuView",
    "DebugInspectorView",
    "FiniteDecisionOptionView",
    "FiniteDecisionPanelView",
    "HudLayoutView",
    "HudRegionView",
    "MovementDraftPanelView",
    "ScreenRect",
    "UnitPanelView",
    "build_action_visual_summary",
    "build_context_menu",
    "build_debug_inspector",
    "build_finite_decision_panel",
    "build_hud_layout",
    "build_movement_draft_panel",
    "build_unit_panel",
    "decision_targets_unit",
]
