"""HUD view models for selection, context actions, and debug inspection."""

from __future__ import annotations

from dataclasses import dataclass

from warhammer40k_arcade_ui.core_client.protocol import JsonValue, UiDecision, UiFiniteOption
from warhammer40k_arcade_ui.render.camera import WorldPoint
from warhammer40k_arcade_ui.render.view_models import BattlefieldView, UnitView
from warhammer40k_arcade_ui.state.selection import (
    SelectionState,
    selected_model,
    selected_unit,
    unit_center,
)


@dataclass(frozen=True, slots=True)
class ContextMenuAction:
    """A finite option displayed in the local context menu."""

    option_id: str
    label: str
    disabled_reason: str | None

    @property
    def enabled(self) -> bool:
        """Return whether the option is display-enabled."""

        return self.disabled_reason is None


@dataclass(frozen=True, slots=True)
class ContextMenuView:
    """Display model for the selected-unit context menu."""

    request_id: str
    unit_id: str
    anchor_world: WorldPoint
    actions: tuple[ContextMenuAction, ...]


@dataclass(frozen=True, slots=True)
class UnitPanelView:
    """Display model for the selected-unit information panel."""

    unit_id: str
    unit_label: str
    model_count: int
    selected_model_id: str | None
    position_summary: str
    pending_request_id: str | None
    available_actions: tuple[ContextMenuAction, ...]


@dataclass(frozen=True, slots=True)
class DebugInspectorView:
    """Debug inspector content derived from viewer-scoped state."""

    request_id: str
    selected_unit_id: str | None
    proposal_kind: str | None
    cursor_position: WorldPoint | None
    event_cursor: int

    @property
    def lines(self) -> tuple[str, ...]:
        """Return deterministic text lines for display."""

        cursor = (
            "none"
            if self.cursor_position is None
            else f"{self.cursor_position[0]:.2f}, {self.cursor_position[1]:.2f} in"
        )
        return (
            f"Request: {self.request_id}",
            f"Selected unit: {self.selected_unit_id or 'none'}",
            f"Proposal kind: {self.proposal_kind or 'none'}",
            f"Cursor: {cursor}",
            f"Event cursor: {self.event_cursor}",
        )


def build_unit_panel(
    *,
    view: BattlefieldView,
    selection: SelectionState,
    pending_decision: UiDecision | None,
) -> UnitPanelView | None:
    """Build selected-unit panel content, if a selected unit is present."""

    unit = selected_unit(view, selection)
    if unit is None:
        return None
    model = selected_model(view, selection)
    actions = finite_actions_for_unit(pending_decision=pending_decision, unit_id=unit.unit_id)
    return UnitPanelView(
        unit_id=unit.unit_id,
        unit_label=unit.label,
        model_count=len(unit.models),
        selected_model_id=model.model_id
        if selection.selected_model_panel_visible and model
        else None,
        position_summary=_position_summary(unit),
        pending_request_id=(
            pending_decision.request_id if actions and pending_decision is not None else None
        ),
        available_actions=actions,
    )


def build_context_menu(
    *,
    view: BattlefieldView,
    selection: SelectionState,
    pending_decision: UiDecision | None,
    fallback_anchor_world: WorldPoint | None = None,
) -> ContextMenuView | None:
    """Build a context menu from the current finite request without inventing options."""

    unit = selected_unit(view, selection)
    if unit is None or pending_decision is None or not selection.context_menu_open:
        return None
    actions = finite_actions_for_unit(
        pending_decision=pending_decision,
        unit_id=unit.unit_id,
    )
    if not actions:
        return None
    anchor_world = selection.context_menu_anchor_world or fallback_anchor_world or unit_center(unit)
    return ContextMenuView(
        request_id=pending_decision.request_id,
        unit_id=unit.unit_id,
        anchor_world=anchor_world,
        actions=actions,
    )


def build_debug_inspector(
    *,
    selection: SelectionState,
    pending_decision: UiDecision | None,
    cursor_position: WorldPoint | None,
    event_cursor: int,
) -> DebugInspectorView | None:
    """Build debug inspector content when enabled by state/preferences."""

    if not selection.debug_inspector_visible:
        return None
    proposal = None if pending_decision is None else pending_decision.movement_proposal
    return DebugInspectorView(
        request_id="none" if pending_decision is None else pending_decision.request_id,
        selected_unit_id=selection.selected_unit_id,
        proposal_kind=None if proposal is None else proposal.proposal_kind,
        cursor_position=cursor_position,
        event_cursor=event_cursor,
    )


def finite_actions_for_unit(
    *,
    pending_decision: UiDecision | None,
    unit_id: str,
) -> tuple[ContextMenuAction, ...]:
    """Return finite actions for a selected unit from engine-provided options only."""

    if (
        pending_decision is None
        or pending_decision.is_parameterized
        or not decision_targets_unit(pending_decision, unit_id)
    ):
        return ()
    return tuple(_action_from_option(option) for option in pending_decision.options)


def decision_targets_unit(decision: UiDecision, unit_id: str) -> bool:
    """Return whether a pending decision payload names the selected unit."""

    proposal = decision.movement_proposal
    if proposal is not None and proposal.unit_instance_id == unit_id:
        return True
    return _payload_targets_unit(decision.payload, unit_id)


def _action_from_option(option: UiFiniteOption) -> ContextMenuAction:
    return ContextMenuAction(
        option_id=option.option_id,
        label=option.label,
        disabled_reason=_disabled_reason(option.payload),
    )


def _disabled_reason(payload: JsonValue) -> str | None:
    if type(payload) is not dict:
        return None
    reason = payload.get("disabled_reason")
    if type(reason) is str and reason:
        return reason
    unavailable_reason = payload.get("unavailable_reason")
    if type(unavailable_reason) is str and unavailable_reason:
        return unavailable_reason
    return None


def _payload_targets_unit(payload: JsonValue, unit_id: str) -> bool:
    if type(payload) is not dict:
        return False
    for key in ("unit_instance_id", "unit_id", "selected_unit_id", "target_unit_id"):
        if payload.get(key) == unit_id:
            return True
    return False


def _position_summary(unit: UnitView) -> str:
    center_x, center_y = unit_center(unit)
    return f"Center {center_x:.2f}, {center_y:.2f} in"
