"""HUD view models for selection, context actions, and debug inspection."""

from __future__ import annotations

from dataclasses import dataclass

from warhammer40k_arcade_ui.core_client.protocol import (
    JsonValue,
    UiDecision,
    UiFiniteOption,
    UiInvalidDiagnostic,
)
from warhammer40k_arcade_ui.render.camera import WorldPoint
from warhammer40k_arcade_ui.render.view_models import BattlefieldView, UnitView
from warhammer40k_arcade_ui.state.movement_draft import (
    MovementDraft,
    unsupported_parameterized_tool_label,
)
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
class FiniteDecisionOptionView:
    """HUD display model for one finite option."""

    option_id: str
    label: str
    highlighted: bool
    disabled_reason: str | None


@dataclass(frozen=True, slots=True)
class FiniteDecisionPanelView:
    """HUD display model for the current finite-decision surface."""

    request_id: str | None
    decision_type: str | None
    actor_id: str | None
    status_line: str
    proposal_kind: str | None
    options: tuple[FiniteDecisionOptionView, ...]
    diagnostic_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MovementDraftPanelView:
    """HUD display model for the local movement draft preview."""

    status_line: str
    request_id: str | None
    unit_id: str | None
    proposal_kind: str | None
    movement_phase_action: str | None
    movement_mode: str | None
    fall_back_mode: str | None
    current_segment_inches: float | None
    total_path_inches: float | None
    remaining_budget_inches: float | None
    ready: bool
    hint_lines: tuple[str, ...]


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
    preference_source_label: str

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
            f"UI prefs: {self.preference_source_label}",
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


def build_finite_decision_panel(
    *,
    pending_decision: UiDecision | None,
    highlighted_option_index: int,
    status_message: str,
    diagnostics: tuple[UiInvalidDiagnostic, ...],
) -> FiniteDecisionPanelView:
    """Build a generic finite-decision HUD panel from the current client status."""

    if pending_decision is None:
        return FiniteDecisionPanelView(
            request_id=None,
            decision_type=None,
            actor_id=None,
            status_line=status_message,
            proposal_kind=None,
            options=(),
            diagnostic_lines=_diagnostic_lines(diagnostics),
        )
    if pending_decision.is_parameterized:
        proposal = pending_decision.parameterized_proposal
        proposal_kind = (
            proposal.proposal_kind
            if proposal is not None and proposal.proposal_kind is not None
            else pending_decision.decision_type
        )
        return FiniteDecisionPanelView(
            request_id=pending_decision.request_id,
            decision_type=pending_decision.decision_type,
            actor_id=pending_decision.actor_id,
            status_line=status_message,
            proposal_kind=proposal_kind,
            options=(),
            diagnostic_lines=_diagnostic_lines(diagnostics),
        )
    return FiniteDecisionPanelView(
        request_id=pending_decision.request_id,
        decision_type=pending_decision.decision_type,
        actor_id=pending_decision.actor_id,
        status_line=status_message,
        proposal_kind=None,
        options=tuple(
            FiniteDecisionOptionView(
                option_id=option.option_id,
                label=option.label,
                highlighted=index == highlighted_option_index,
                disabled_reason=_disabled_reason(option.payload),
            )
            for index, option in enumerate(pending_decision.options)
        ),
        diagnostic_lines=_diagnostic_lines(diagnostics),
    )


def build_movement_draft_panel(
    *,
    movement_draft: MovementDraft | None,
    pending_decision: UiDecision | None,
) -> MovementDraftPanelView | None:
    """Build movement draft HUD content without treating previews as authoritative."""

    if movement_draft is not None:
        return MovementDraftPanelView(
            status_line="Movement draft ready"
            if movement_draft.is_ready
            else "Movement draft preview",
            request_id=movement_draft.proposal_request_id,
            unit_id=movement_draft.selected_unit_id,
            proposal_kind=movement_draft.proposal_kind,
            movement_phase_action=movement_draft.movement_phase_action,
            movement_mode=movement_draft.movement_mode,
            fall_back_mode=movement_draft.fall_back_mode,
            current_segment_inches=movement_draft.current_segment_length,
            total_path_inches=movement_draft.total_path_length,
            remaining_budget_inches=movement_draft.remaining_budget_inches,
            ready=movement_draft.is_ready,
            hint_lines=movement_draft.local_hint_lines,
        )
    unsupported_label = unsupported_parameterized_tool_label(pending_decision)
    if unsupported_label is not None:
        return MovementDraftPanelView(
            status_line=f"Unsupported proposal tool: {unsupported_label}",
            request_id=None if pending_decision is None else pending_decision.request_id,
            unit_id=None,
            proposal_kind=unsupported_label,
            movement_phase_action=None,
            movement_mode=None,
            fall_back_mode=None,
            current_segment_inches=None,
            total_path_inches=None,
            remaining_budget_inches=None,
            ready=False,
            hint_lines=("Proposal visible; movement draft tool is not applicable.",),
        )
    movement_proposal = None if pending_decision is None else pending_decision.movement_proposal
    if movement_proposal is None:
        return None
    return MovementDraftPanelView(
        status_line="Movement proposal pending",
        request_id=movement_proposal.request_id,
        unit_id=movement_proposal.unit_instance_id,
        proposal_kind=movement_proposal.proposal_kind,
        movement_phase_action=movement_proposal.movement_phase_action,
        movement_mode=None,
        fall_back_mode=None,
        current_segment_inches=None,
        total_path_inches=None,
        remaining_budget_inches=None,
        ready=False,
        hint_lines=("Requested unit is not selected.",),
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
    preference_source_label: str,
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
        preference_source_label=preference_source_label,
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


def _diagnostic_lines(diagnostics: tuple[UiInvalidDiagnostic, ...]) -> tuple[str, ...]:
    return tuple(f"{diagnostic.violation_code}: {diagnostic.message}" for diagnostic in diagnostics)


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
