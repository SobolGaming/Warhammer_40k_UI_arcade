"""HUD view models for selection, context actions, and debug inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from warhammer40k_arcade_ui.core_client.protocol import (
    JsonValue,
    UiDecision,
    UiFiniteOption,
    UiInvalidDiagnostic,
    UiMovementProposalRequest,
)
from warhammer40k_arcade_ui.preferences.schema import AssignmentHudMode, UiPreferences
from warhammer40k_arcade_ui.render.camera import WorldPoint
from warhammer40k_arcade_ui.render.view_models import BattlefieldView, UnitView
from warhammer40k_arcade_ui.state.assignment_workspace import AssignmentWorkspace
from warhammer40k_arcade_ui.state.entity_selection import EntityRef
from warhammer40k_arcade_ui.state.movement_draft import (
    MovementDraft,
    movement_proposal_context_diagnostic_line,
    unsupported_parameterized_tool_label,
)
from warhammer40k_arcade_ui.state.placement_draft import PlacementDraft
from warhammer40k_arcade_ui.state.selection import (
    SelectionState,
    selected_model,
    selected_unit,
    unit_center,
)

type AssignmentGroupState = Literal["active", "assigned", "unassigned", "warning", "invalid"]
type AssignmentReadinessState = Literal[
    "empty",
    "incomplete",
    "ready",
    "invalid",
    "unsupported",
    "finite",
]
_PROPOSAL_UNIT_MISSING_CODE = "proposal_unit_missing_from_projection"


@dataclass(frozen=True, slots=True)
class ContextMenuAction:
    """A finite option displayed in the local context menu."""

    option_id: str
    label: str
    disabled_reason: str | None = None
    highlighted: bool = False

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
    active_layer: str | None
    active_model_ids: tuple[str, ...]
    assigned_model_count: int
    total_model_count: int
    unchanged_model_count: int
    current_segment_inches: float | None
    total_path_inches: float | None
    remaining_budget_inches: float | None
    synthetic_witness_model_ids: tuple[str, ...]
    synthetic_witness_point_count: int
    payload_witness_lines: tuple[str, ...]
    ready: bool
    hint_lines: tuple[str, ...]
    diagnostic_lines: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PlacementDraftPanelView:
    """HUD display model for the local placement draft preview."""

    status_line: str
    request_id: str | None
    unit_id: str | None
    proposal_kind: str | None
    placement_kind: str | None
    selected_model_id: str | None
    placed_model_count: int
    total_model_count: int
    unplaced_model_count: int
    ready: bool
    hint_lines: tuple[str, ...]
    diagnostic_lines: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AssignmentHudGroupView:
    """One stable request-scoped assignment group for HUD and future visual summaries."""

    group_id: str
    label: str
    state: AssignmentGroupState
    source_ref_keys: tuple[str, ...]
    target_ref_keys: tuple[str, ...]
    summary_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssignmentHudPanelView:
    """Generic request-scoped assignment review HUD view model."""

    request_id: str | None
    decision_type: str | None
    actor_id: str | None
    operation_kind: str
    proposal_kind: str | None
    active_layer: str | None
    active_selection_ref_keys: tuple[str, ...]
    assigned_ref_keys: tuple[str, ...]
    unassigned_ref_keys: tuple[str, ...]
    readiness_state: AssignmentReadinessState
    groups: tuple[AssignmentHudGroupView, ...]
    advisory_lines: tuple[str, ...]
    diagnostic_lines: tuple[str, ...]
    display_mode: AssignmentHudMode
    warning_markers_visible: bool
    chain_breadcrumbs_visible: bool
    chain_lines: tuple[str, ...]
    preference_source_label: str | None
    decline_available: bool = False


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


def build_unit_panel(
    *,
    view: BattlefieldView,
    selection: SelectionState,
    pending_decision: UiDecision | None,
    highlighted_option_id: str | None = None,
) -> UnitPanelView | None:
    """Build selected-unit panel content, if a selected unit is present."""

    unit = selected_unit(view, selection)
    if unit is None:
        return None
    model = selected_model(view, selection)
    actions = finite_actions_for_unit(
        pending_decision=pending_decision,
        unit_id=unit.unit_id,
        highlighted_option_id=highlighted_option_id,
    )
    return UnitPanelView(
        unit_id=unit.unit_id,
        unit_label=unit.label,
        model_count=len(unit.models),
        selected_model_id=model.model_id if model else None,
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
    view: BattlefieldView | None = None,
    status_message: str | None = None,
    diagnostics: tuple[UiInvalidDiagnostic, ...] = (),
) -> MovementDraftPanelView | None:
    """Build movement draft HUD content without treating previews as authoritative."""

    if movement_draft is not None:
        status_line = (
            status_message
            if diagnostics and status_message is not None
            else "Movement draft ready"
            if movement_draft.is_ready
            else "Movement draft preview"
        )
        return MovementDraftPanelView(
            status_line=status_line,
            request_id=movement_draft.proposal_request_id,
            unit_id=movement_draft.selected_unit_id,
            proposal_kind=movement_draft.proposal_kind,
            movement_phase_action=movement_draft.movement_phase_action,
            movement_mode=movement_draft.movement_mode,
            fall_back_mode=movement_draft.fall_back_mode,
            active_layer=movement_draft.active_layer,
            active_model_ids=movement_draft.selected_model_ids,
            assigned_model_count=movement_draft.assigned_model_count,
            total_model_count=movement_draft.total_model_count,
            unchanged_model_count=movement_draft.unchanged_model_count,
            current_segment_inches=movement_draft.current_segment_length,
            total_path_inches=movement_draft.total_path_length,
            remaining_budget_inches=movement_draft.remaining_budget_inches,
            synthetic_witness_model_ids=movement_draft.synthetic_witness_model_ids,
            synthetic_witness_point_count=movement_draft.synthetic_witness_point_count,
            payload_witness_lines=movement_draft.payload_witness_summary_lines,
            ready=movement_draft.is_ready,
            hint_lines=movement_draft.local_hint_lines,
            diagnostic_lines=_diagnostic_lines(diagnostics),
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
            active_layer=None,
            active_model_ids=(),
            assigned_model_count=0,
            total_model_count=0,
            unchanged_model_count=0,
            current_segment_inches=None,
            total_path_inches=None,
            remaining_budget_inches=None,
            synthetic_witness_model_ids=(),
            synthetic_witness_point_count=0,
            payload_witness_lines=(),
            ready=False,
            hint_lines=("Proposal visible; movement draft tool is not applicable.",),
            diagnostic_lines=_diagnostic_lines(diagnostics),
        )
    movement_proposal = None if pending_decision is None else pending_decision.movement_proposal
    if movement_proposal is None:
        if not diagnostics:
            return None
        return MovementDraftPanelView(
            status_line=status_message or "Movement submission diagnostic",
            request_id=None if pending_decision is None else pending_decision.request_id,
            unit_id=None,
            proposal_kind=None,
            movement_phase_action=None,
            movement_mode=None,
            fall_back_mode=None,
            active_layer=None,
            active_model_ids=(),
            assigned_model_count=0,
            total_model_count=0,
            unchanged_model_count=0,
            current_segment_inches=None,
            total_path_inches=None,
            remaining_budget_inches=None,
            synthetic_witness_model_ids=(),
            synthetic_witness_point_count=0,
            payload_witness_lines=(),
            ready=False,
            hint_lines=(),
            diagnostic_lines=_diagnostic_lines(diagnostics),
        )
    status_line = (
        status_message
        if diagnostics and status_message is not None
        else "Movement proposal pending"
    )
    context_diagnostic = movement_proposal_context_diagnostic_line(movement_proposal)
    if context_diagnostic is not None:
        return MovementDraftPanelView(
            status_line="Movement proposal context incomplete" if not diagnostics else status_line,
            request_id=movement_proposal.request_id,
            unit_id=movement_proposal.unit_instance_id,
            proposal_kind=movement_proposal.proposal_kind,
            movement_phase_action=movement_proposal.movement_phase_action,
            movement_mode=None,
            fall_back_mode=None,
            active_layer=None,
            active_model_ids=(),
            assigned_model_count=0,
            total_model_count=0,
            unchanged_model_count=0,
            current_segment_inches=None,
            total_path_inches=None,
            remaining_budget_inches=None,
            synthetic_witness_model_ids=(),
            synthetic_witness_point_count=0,
            payload_witness_lines=(),
            ready=False,
            hint_lines=(
                "Movement proposal mode context is incomplete.",
                "Adapter-visible movement semantics are missing; submission is blocked.",
            ),
            diagnostic_lines=_append_unique_line(
                _diagnostic_lines(diagnostics),
                context_diagnostic,
            ),
        )
    missing_unit_diagnostic = _missing_proposal_unit_diagnostic_line(
        view=view,
        proposal=movement_proposal,
    )
    if missing_unit_diagnostic is not None:
        return MovementDraftPanelView(
            status_line="Movement proposal projection mismatch" if not diagnostics else status_line,
            request_id=movement_proposal.request_id,
            unit_id=movement_proposal.unit_instance_id,
            proposal_kind=movement_proposal.proposal_kind,
            movement_phase_action=movement_proposal.movement_phase_action,
            movement_mode=None,
            fall_back_mode=None,
            active_layer=None,
            active_model_ids=(),
            assigned_model_count=0,
            total_model_count=0,
            unchanged_model_count=0,
            current_segment_inches=None,
            total_path_inches=None,
            remaining_budget_inches=None,
            synthetic_witness_model_ids=(),
            synthetic_witness_point_count=0,
            payload_witness_lines=(),
            ready=False,
            hint_lines=(
                "Proposal unit is absent from the current viewer projection.",
                "Projection/request drift; movement cannot be drafted locally.",
            ),
            diagnostic_lines=_append_unique_line(
                _diagnostic_lines(diagnostics),
                missing_unit_diagnostic,
            ),
        )
    return MovementDraftPanelView(
        status_line=status_line,
        request_id=movement_proposal.request_id,
        unit_id=movement_proposal.unit_instance_id,
        proposal_kind=movement_proposal.proposal_kind,
        movement_phase_action=movement_proposal.movement_phase_action,
        movement_mode=None,
        fall_back_mode=None,
        active_layer=None,
        active_model_ids=(),
        assigned_model_count=0,
        total_model_count=0,
        unchanged_model_count=0,
        current_segment_inches=None,
        total_path_inches=None,
        remaining_budget_inches=None,
        synthetic_witness_model_ids=(),
        synthetic_witness_point_count=0,
        payload_witness_lines=(),
        ready=False,
        hint_lines=("Requested unit is not selected.",),
        diagnostic_lines=_diagnostic_lines(diagnostics),
    )


def build_placement_draft_panel(
    *,
    placement_draft: PlacementDraft | None,
    pending_decision: UiDecision | None,
    status_message: str | None = None,
    diagnostics: tuple[UiInvalidDiagnostic, ...] = (),
) -> PlacementDraftPanelView | None:
    """Build placement draft HUD content without treating previews as authoritative."""

    if placement_draft is not None:
        status_line = (
            status_message
            if diagnostics and status_message is not None
            else "Placement draft ready"
            if placement_draft.is_ready
            else "Placement draft preview"
        )
        return PlacementDraftPanelView(
            status_line=status_line,
            request_id=placement_draft.proposal_request_id,
            unit_id=placement_draft.selected_unit_id,
            proposal_kind=placement_draft.proposal_kind,
            placement_kind=placement_draft.placement_kind,
            selected_model_id=placement_draft.selected_model_id,
            placed_model_count=placement_draft.placed_model_count,
            total_model_count=placement_draft.total_model_count,
            unplaced_model_count=placement_draft.unplaced_model_count,
            ready=placement_draft.is_ready,
            hint_lines=placement_draft.local_hint_lines,
            diagnostic_lines=_diagnostic_lines(diagnostics),
        )
    proposal = None if pending_decision is None else pending_decision.placement_proposal
    if proposal is None:
        return None
    return PlacementDraftPanelView(
        status_line=status_message or "Placement proposal pending",
        request_id=proposal.request_id,
        unit_id=proposal.unit_instance_id,
        proposal_kind=proposal.proposal_kind,
        placement_kind=proposal.placement_kind,
        selected_model_id=None,
        placed_model_count=0,
        total_model_count=len(proposal.required_model_ids),
        unplaced_model_count=len(proposal.required_model_ids),
        ready=False,
        hint_lines=("Select the requested unit to begin placement drafting.",),
        diagnostic_lines=_diagnostic_lines(diagnostics),
    )


def build_assignment_hud_panel(
    *,
    movement_draft: MovementDraft | None,
    pending_decision: UiDecision | None,
    view: BattlefieldView | None = None,
    highlighted_option_index: int,
    diagnostics: tuple[UiInvalidDiagnostic, ...],
    preferences: UiPreferences,
    preference_source_label: str,
    event_log_lines: tuple[str, ...] = (),
    placement_draft: PlacementDraft | None = None,
    assignment_workspace: AssignmentWorkspace | None = None,
) -> AssignmentHudPanelView | None:
    """Build the generic request-scoped assignment HUD without adding rules semantics."""

    if not preferences.hud.show_assignment_hud:
        return None
    diagnostic_lines = _diagnostic_lines(diagnostics)
    if movement_draft is not None:
        return _movement_assignment_hud_panel(
            movement_draft=movement_draft,
            pending_decision=pending_decision,
            diagnostic_lines=diagnostic_lines,
            preferences=preferences,
            preference_source_label=preference_source_label,
            chain_lines=_chain_lines(preferences, event_log_lines),
        )
    if placement_draft is not None:
        return _placement_assignment_hud_panel(
            placement_draft=placement_draft,
            pending_decision=pending_decision,
            diagnostic_lines=diagnostic_lines,
            preferences=preferences,
            preference_source_label=preference_source_label,
            chain_lines=_chain_lines(preferences, event_log_lines),
        )
    if assignment_workspace is not None:
        return _generic_assignment_hud_panel(
            assignment_workspace=assignment_workspace,
            pending_decision=pending_decision,
            diagnostic_lines=diagnostic_lines,
            preferences=preferences,
            preference_source_label=preference_source_label,
            chain_lines=_chain_lines(preferences, event_log_lines),
        )
    unsupported_label = unsupported_parameterized_tool_label(pending_decision)
    if unsupported_label is not None:
        return _unsupported_assignment_hud_panel(
            pending_decision=pending_decision,
            unsupported_label=unsupported_label,
            diagnostic_lines=diagnostic_lines,
            preferences=preferences,
            preference_source_label=preference_source_label,
            chain_lines=_chain_lines(preferences, event_log_lines),
        )
    context_diagnostic = _movement_proposal_context_diagnostic_line(pending_decision)
    if context_diagnostic is not None:
        return _movement_proposal_context_assignment_hud_panel(
            pending_decision=pending_decision,
            diagnostic_line=context_diagnostic,
            diagnostic_lines=diagnostic_lines,
            preferences=preferences,
            preference_source_label=preference_source_label,
            chain_lines=_chain_lines(preferences, event_log_lines),
        )
    missing_unit_diagnostic = _missing_movement_proposal_unit_diagnostic_line(
        view=view,
        pending_decision=pending_decision,
    )
    if missing_unit_diagnostic is not None:
        return _missing_movement_proposal_unit_assignment_hud_panel(
            pending_decision=pending_decision,
            diagnostic_line=missing_unit_diagnostic,
            diagnostic_lines=diagnostic_lines,
            preferences=preferences,
            preference_source_label=preference_source_label,
            chain_lines=_chain_lines(preferences, event_log_lines),
        )
    if _is_fight_order_decision(pending_decision):
        return _finite_assignment_hud_panel(
            pending_decision=pending_decision,
            highlighted_option_index=highlighted_option_index,
            diagnostic_lines=diagnostic_lines,
            preferences=preferences,
            preference_source_label=preference_source_label,
            chain_lines=_chain_lines(preferences, event_log_lines),
        )
    return None


def _placement_assignment_hud_panel(
    *,
    placement_draft: PlacementDraft,
    pending_decision: UiDecision | None,
    diagnostic_lines: tuple[str, ...],
    preferences: UiPreferences,
    preference_source_label: str | None,
    chain_lines: tuple[str, ...],
) -> AssignmentHudPanelView:
    assignment_views = placement_draft.assignment_views()
    placed_ref_keys = tuple(
        f"model:{assignment.model_id}"
        for assignment in assignment_views
        if assignment.state == "placed"
    )
    unplaced_ref_keys = tuple(
        f"model:{assignment.model_id}"
        for assignment in assignment_views
        if assignment.state == "unplaced"
    )
    active_ref_keys = tuple(
        f"model:{assignment.model_id}"
        for assignment in assignment_views
        if assignment.state == "current"
    )
    groups = tuple(
        AssignmentHudGroupView(
            group_id=f"placement:{assignment.model_id}",
            label=f"{assignment.model_id}: {assignment.state}",
            state=_placement_assignment_state(assignment.state),
            source_ref_keys=(f"model:{assignment.model_id}",),
            target_ref_keys=(),
            summary_lines=(
                "Draft pose assigned."
                if assignment.position is not None
                else "No draft pose assigned yet.",
            ),
        )
        for assignment in assignment_views[:5]
    )
    return AssignmentHudPanelView(
        request_id=placement_draft.proposal_request_id,
        decision_type=None if pending_decision is None else pending_decision.decision_type,
        actor_id=None if pending_decision is None else pending_decision.actor_id,
        operation_kind="placement",
        proposal_kind=placement_draft.proposal_kind,
        active_layer="model",
        active_selection_ref_keys=active_ref_keys,
        assigned_ref_keys=placed_ref_keys,
        unassigned_ref_keys=unplaced_ref_keys,
        readiness_state=_placement_readiness_state(placement_draft, diagnostic_lines),
        groups=groups,
        advisory_lines=placement_draft.local_hint_lines,
        diagnostic_lines=diagnostic_lines,
        display_mode=preferences.hud.assignment_hud_mode,
        warning_markers_visible=preferences.hud.show_assignment_warning_markers,
        chain_breadcrumbs_visible=preferences.hud.show_chain_breadcrumbs,
        chain_lines=chain_lines,
        preference_source_label=preference_source_label,
    )


def _generic_assignment_hud_panel(
    *,
    assignment_workspace: AssignmentWorkspace,
    pending_decision: UiDecision | None,
    diagnostic_lines: tuple[str, ...],
    preferences: UiPreferences,
    preference_source_label: str | None,
    chain_lines: tuple[str, ...],
) -> AssignmentHudPanelView:
    combined_diagnostics = _append_unique_lines(
        diagnostic_lines,
        assignment_workspace.diagnostic_lines,
    )
    return AssignmentHudPanelView(
        request_id=assignment_workspace.request_id,
        decision_type=None if pending_decision is None else pending_decision.decision_type,
        actor_id=assignment_workspace.actor_id,
        operation_kind=assignment_workspace.proposal_kind,
        proposal_kind=assignment_workspace.proposal_kind,
        active_layer="assignment",
        active_selection_ref_keys=assignment_workspace.assigned_ref_keys,
        assigned_ref_keys=assignment_workspace.assigned_ref_keys,
        unassigned_ref_keys=(),
        readiness_state=_assignment_workspace_readiness_state(
            assignment_workspace,
            combined_diagnostics,
        ),
        groups=tuple(
            AssignmentHudGroupView(
                group_id=row.row_id,
                label=row.label,
                state="assigned" if assignment_workspace.is_ready else "warning",
                source_ref_keys=row.source_ref_keys,
                target_ref_keys=row.target_ref_keys,
                summary_lines=row.summary_lines,
            )
            for row in assignment_workspace.rows[:5]
        )
        or (
            AssignmentHudGroupView(
                group_id=f"assignment:{assignment_workspace.request_id}",
                label=_assignment_empty_label(assignment_workspace),
                state="warning",
                source_ref_keys=(),
                target_ref_keys=(),
                summary_lines=assignment_workspace.local_hint_lines[:2],
            ),
        ),
        advisory_lines=assignment_workspace.local_hint_lines,
        diagnostic_lines=combined_diagnostics,
        display_mode=preferences.hud.assignment_hud_mode,
        warning_markers_visible=preferences.hud.show_assignment_warning_markers,
        chain_breadcrumbs_visible=preferences.hud.show_chain_breadcrumbs,
        chain_lines=chain_lines,
        preference_source_label=preference_source_label,
        decline_available=assignment_workspace.declinable,
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


def _movement_assignment_hud_panel(
    *,
    movement_draft: MovementDraft,
    pending_decision: UiDecision | None,
    diagnostic_lines: tuple[str, ...],
    preferences: UiPreferences,
    preference_source_label: str | None,
    chain_lines: tuple[str, ...],
) -> AssignmentHudPanelView:
    assigned_ref_keys = tuple(
        f"model:{assignment.model_id}"
        for assignment in movement_draft.assignment_views()
        if assignment.has_movement
    )
    unassigned_ref_keys = tuple(
        f"model:{assignment.model_id}"
        for assignment in movement_draft.assignment_views()
        if not assignment.has_movement
    )
    advisory_lines = movement_draft.local_hint_lines
    return AssignmentHudPanelView(
        request_id=movement_draft.proposal_request_id,
        decision_type=None if pending_decision is None else pending_decision.decision_type,
        actor_id=None if pending_decision is None else pending_decision.actor_id,
        operation_kind="movement",
        proposal_kind=movement_draft.proposal_kind,
        active_layer=movement_draft.active_layer,
        active_selection_ref_keys=_ref_keys(movement_draft.entity_selection.selected_refs),
        assigned_ref_keys=assigned_ref_keys,
        unassigned_ref_keys=unassigned_ref_keys,
        readiness_state=_movement_readiness_state(movement_draft, diagnostic_lines),
        groups=_movement_assignment_groups(movement_draft),
        advisory_lines=advisory_lines,
        diagnostic_lines=diagnostic_lines,
        display_mode=preferences.hud.assignment_hud_mode,
        warning_markers_visible=preferences.hud.show_assignment_warning_markers,
        chain_breadcrumbs_visible=preferences.hud.show_chain_breadcrumbs,
        chain_lines=chain_lines,
        preference_source_label=preference_source_label,
    )


def _unsupported_assignment_hud_panel(
    *,
    pending_decision: UiDecision | None,
    unsupported_label: str,
    diagnostic_lines: tuple[str, ...],
    preferences: UiPreferences,
    preference_source_label: str | None,
    chain_lines: tuple[str, ...],
) -> AssignmentHudPanelView:
    proposal = None if pending_decision is None else pending_decision.parameterized_proposal
    request_id = (
        proposal.request_id
        if proposal is not None
        else None
        if pending_decision is None
        else pending_decision.request_id
    )
    decision_type = (
        proposal.decision_type
        if proposal is not None
        else None
        if pending_decision is None
        else pending_decision.decision_type
    )
    actor_id = (
        proposal.actor_id
        if proposal is not None
        else None
        if pending_decision is None
        else pending_decision.actor_id
    )
    proposal_kind = proposal.proposal_kind if proposal is not None else unsupported_label
    return AssignmentHudPanelView(
        request_id=request_id,
        decision_type=decision_type,
        actor_id=actor_id,
        operation_kind="unsupported",
        proposal_kind=proposal_kind or unsupported_label,
        active_layer=None,
        active_selection_ref_keys=(),
        assigned_ref_keys=(),
        unassigned_ref_keys=(),
        readiness_state="unsupported" if not diagnostic_lines else "invalid",
        groups=(
            AssignmentHudGroupView(
                group_id=f"unsupported:{unsupported_label}",
                label=f"Unsupported proposal tool: {unsupported_label}",
                state="warning" if not diagnostic_lines else "invalid",
                source_ref_keys=(),
                target_ref_keys=(),
                summary_lines=("No assignment adapter is available for this request family.",),
            ),
        ),
        advisory_lines=("Visible request only; no local assignment payload will be built.",),
        diagnostic_lines=diagnostic_lines,
        display_mode=preferences.hud.assignment_hud_mode,
        warning_markers_visible=preferences.hud.show_assignment_warning_markers,
        chain_breadcrumbs_visible=preferences.hud.show_chain_breadcrumbs,
        chain_lines=chain_lines,
        preference_source_label=preference_source_label,
    )


def _finite_assignment_hud_panel(
    *,
    pending_decision: UiDecision | None,
    highlighted_option_index: int,
    diagnostic_lines: tuple[str, ...],
    preferences: UiPreferences,
    preference_source_label: str | None,
    chain_lines: tuple[str, ...],
) -> AssignmentHudPanelView:
    if pending_decision is None:
        raise AssertionError("Fight-order assignment HUD requires a pending decision.")
    groups = tuple(
        _finite_option_assignment_group(
            option=option,
            highlighted=index == highlighted_option_index,
        )
        for index, option in enumerate(pending_decision.options)
    )
    selected_ref_keys = (
        groups[highlighted_option_index].source_ref_keys
        if 0 <= highlighted_option_index < len(groups)
        else ()
    )
    return AssignmentHudPanelView(
        request_id=pending_decision.request_id,
        decision_type=pending_decision.decision_type,
        actor_id=pending_decision.actor_id,
        operation_kind="finite",
        proposal_kind=None,
        active_layer="unit",
        active_selection_ref_keys=selected_ref_keys,
        assigned_ref_keys=(),
        unassigned_ref_keys=(),
        readiness_state="finite" if not diagnostic_lines else "invalid",
        groups=groups,
        advisory_lines=("Finite request; submit one engine-provided option ID.",),
        diagnostic_lines=diagnostic_lines,
        display_mode=preferences.hud.assignment_hud_mode,
        warning_markers_visible=preferences.hud.show_assignment_warning_markers,
        chain_breadcrumbs_visible=preferences.hud.show_chain_breadcrumbs,
        chain_lines=chain_lines,
        preference_source_label=preference_source_label,
    )


def _missing_movement_proposal_unit_assignment_hud_panel(
    *,
    pending_decision: UiDecision | None,
    diagnostic_line: str,
    diagnostic_lines: tuple[str, ...],
    preferences: UiPreferences,
    preference_source_label: str | None,
    chain_lines: tuple[str, ...],
) -> AssignmentHudPanelView:
    if pending_decision is None or pending_decision.movement_proposal is None:
        raise AssertionError("Missing proposal-unit assignment HUD requires a movement proposal.")
    proposal = pending_decision.movement_proposal
    unit_ref_key = f"unit:{proposal.unit_instance_id}"
    return AssignmentHudPanelView(
        request_id=proposal.request_id,
        decision_type=proposal.decision_type,
        actor_id=proposal.actor_id,
        operation_kind="movement",
        proposal_kind=proposal.proposal_kind,
        active_layer=None,
        active_selection_ref_keys=(),
        assigned_ref_keys=(),
        unassigned_ref_keys=(),
        readiness_state="invalid",
        groups=(
            AssignmentHudGroupView(
                group_id=f"missing-proposal-unit:{proposal.unit_instance_id}",
                label="Proposal unit missing from projection",
                state="invalid",
                source_ref_keys=(unit_ref_key,),
                target_ref_keys=(),
                summary_lines=(
                    f"Requested unit: {proposal.unit_instance_id}",
                    "Projection/request drift; movement cannot be drafted locally.",
                ),
            ),
        ),
        advisory_lines=(
            "Engine movement request names a unit missing from this viewer projection.",
        ),
        diagnostic_lines=_append_unique_line(diagnostic_lines, diagnostic_line),
        display_mode=preferences.hud.assignment_hud_mode,
        warning_markers_visible=preferences.hud.show_assignment_warning_markers,
        chain_breadcrumbs_visible=preferences.hud.show_chain_breadcrumbs,
        chain_lines=chain_lines,
        preference_source_label=preference_source_label,
    )


def _movement_proposal_context_assignment_hud_panel(
    *,
    pending_decision: UiDecision | None,
    diagnostic_line: str,
    diagnostic_lines: tuple[str, ...],
    preferences: UiPreferences,
    preference_source_label: str | None,
    chain_lines: tuple[str, ...],
) -> AssignmentHudPanelView:
    if pending_decision is None or pending_decision.movement_proposal is None:
        raise AssertionError("Movement-context assignment HUD requires a movement proposal.")
    proposal = pending_decision.movement_proposal
    return AssignmentHudPanelView(
        request_id=proposal.request_id,
        decision_type=proposal.decision_type,
        actor_id=proposal.actor_id,
        operation_kind="movement",
        proposal_kind=proposal.proposal_kind,
        active_layer=None,
        active_selection_ref_keys=(),
        assigned_ref_keys=(),
        unassigned_ref_keys=(),
        readiness_state="invalid",
        groups=(
            AssignmentHudGroupView(
                group_id=f"invalid-movement-context:{proposal.request_id}",
                label="Movement proposal context incomplete",
                state="invalid",
                source_ref_keys=(f"unit:{proposal.unit_instance_id}",),
                target_ref_keys=(),
                summary_lines=(
                    f"Requested unit: {proposal.unit_instance_id}",
                    "Missing adapter-visible mode context; submission is blocked.",
                ),
            ),
        ),
        advisory_lines=("Engine movement request is missing required movement mode context.",),
        diagnostic_lines=_append_unique_line(diagnostic_lines, diagnostic_line),
        display_mode=preferences.hud.assignment_hud_mode,
        warning_markers_visible=preferences.hud.show_assignment_warning_markers,
        chain_breadcrumbs_visible=preferences.hud.show_chain_breadcrumbs,
        chain_lines=chain_lines,
        preference_source_label=preference_source_label,
    )


def _movement_assignment_groups(
    movement_draft: MovementDraft,
) -> tuple[AssignmentHudGroupView, ...]:
    assignment_views = movement_draft.assignment_views()
    groups: list[AssignmentHudGroupView] = []
    assigned_group_ids = tuple(
        group_id
        for group_id in dict.fromkeys(
            assignment.assignment_group_id
            for assignment in assignment_views
            if assignment.assignment_group_id is not None and assignment.has_movement
        )
    )
    for group_id in assigned_group_ids:
        group_assignments = tuple(
            assignment
            for assignment in assignment_views
            if assignment.assignment_group_id == group_id and assignment.has_movement
        )
        if not group_assignments:
            continue
        state: AssignmentGroupState = (
            "active"
            if any(assignment.state == "active" for assignment in group_assignments)
            else "assigned"
        )
        longest_path = max(assignment.path_length_inches for assignment in group_assignments)
        groups.append(
            AssignmentHudGroupView(
                group_id=group_id,
                label=f"{group_id}: {len(group_assignments)} model(s)",
                state=state,
                source_ref_keys=tuple(
                    f"model:{assignment.model_id}" for assignment in group_assignments
                ),
                target_ref_keys=(),
                summary_lines=(f"Longest path: {longest_path:.2f} in",),
            )
        )
    active_without_path = tuple(
        assignment
        for assignment in assignment_views
        if assignment.state == "active" and not assignment.has_movement
    )
    if active_without_path:
        groups.append(
            AssignmentHudGroupView(
                group_id="active-selection",
                label=f"Active selection: {len(active_without_path)} model(s)",
                state="active",
                source_ref_keys=tuple(
                    f"model:{assignment.model_id}" for assignment in active_without_path
                ),
                target_ref_keys=(),
                summary_lines=("No path assigned to the active selection yet.",),
            )
        )
    unassigned = tuple(
        assignment
        for assignment in assignment_views
        if assignment.state != "active" and not assignment.has_movement
    )
    if unassigned:
        label = (
            f"No-op ready: {len(unassigned)} model(s)"
            if movement_draft.is_ready
            else f"Unassigned: {len(unassigned)} model(s)"
        )
        groups.append(
            AssignmentHudGroupView(
                group_id="unassigned-or-no-op",
                label=label,
                state="unassigned",
                source_ref_keys=tuple(f"model:{assignment.model_id}" for assignment in unassigned),
                target_ref_keys=(),
                summary_lines=(
                    "Unchanged models are submitted as explicit start/end no-op paths."
                    if movement_draft.is_ready
                    else "These models still have no movement path assignment.",
                ),
            )
        )
    return tuple(groups)


def _chain_lines(
    preferences: UiPreferences,
    event_log_lines: tuple[str, ...],
) -> tuple[str, ...]:
    if not preferences.hud.show_chain_breadcrumbs:
        return ()
    return event_log_lines[-3:]


def _finite_option_assignment_group(
    *,
    option: UiFiniteOption,
    highlighted: bool,
) -> AssignmentHudGroupView:
    fight_ref_key = _fight_option_ref_key(option.option_id)
    state: AssignmentGroupState = "active" if highlighted else "assigned"
    summary = _finite_option_summary(option.option_id)
    return AssignmentHudGroupView(
        group_id=f"finite:{option.option_id}",
        label=option.label,
        state=state,
        source_ref_keys=() if fight_ref_key is None else (fight_ref_key,),
        target_ref_keys=(),
        summary_lines=(summary,),
    )


def _movement_readiness_state(
    movement_draft: MovementDraft,
    diagnostic_lines: tuple[str, ...],
) -> AssignmentReadinessState:
    if diagnostic_lines:
        return "invalid"
    if movement_draft.is_ready:
        return "ready"
    if movement_draft.has_assignments:
        return "incomplete"
    return "empty"


def _placement_readiness_state(
    placement_draft: PlacementDraft,
    diagnostic_lines: tuple[str, ...],
) -> AssignmentReadinessState:
    if diagnostic_lines:
        return "invalid"
    if placement_draft.is_ready:
        return "ready"
    if placement_draft.placed_model_count:
        return "incomplete"
    return "empty"


def _placement_assignment_state(state: str) -> AssignmentGroupState:
    if state == "current":
        return "active"
    if state == "placed":
        return "assigned"
    return "unassigned"


def _missing_movement_proposal_unit_diagnostic_line(
    *,
    view: BattlefieldView | None,
    pending_decision: UiDecision | None,
) -> str | None:
    proposal = None if pending_decision is None else pending_decision.movement_proposal
    if proposal is None:
        return None
    return _missing_proposal_unit_diagnostic_line(view=view, proposal=proposal)


def _movement_proposal_context_diagnostic_line(
    pending_decision: UiDecision | None,
) -> str | None:
    proposal = None if pending_decision is None else pending_decision.movement_proposal
    if proposal is None:
        return None
    return movement_proposal_context_diagnostic_line(proposal)


def _missing_proposal_unit_diagnostic_line(
    *,
    view: BattlefieldView | None,
    proposal: UiMovementProposalRequest,
) -> str | None:
    if view is None or _unit_by_id(view, proposal.unit_instance_id) is not None:
        return None
    return (
        f"{_PROPOSAL_UNIT_MISSING_CODE} [unit_instance_id]: "
        "Movement proposal unit is not available in the current viewer projection: "
        f"{proposal.unit_instance_id}."
    )


def _unit_by_id(view: BattlefieldView, unit_id: str) -> UnitView | None:
    for unit in view.units:
        if unit.unit_id == unit_id:
            return unit
    return None


def _append_unique_line(lines: tuple[str, ...], line: str) -> tuple[str, ...]:
    if line in lines:
        return lines
    return (*lines, line)


def _append_unique_lines(
    lines: tuple[str, ...],
    extra_lines: tuple[str, ...],
) -> tuple[str, ...]:
    result = lines
    for line in extra_lines:
        result = _append_unique_line(result, line)
    return result


def _assignment_workspace_readiness_state(
    assignment_workspace: AssignmentWorkspace,
    diagnostic_lines: tuple[str, ...],
) -> AssignmentReadinessState:
    if diagnostic_lines:
        return "invalid"
    if assignment_workspace.is_ready:
        return "ready"
    if assignment_workspace.rows:
        return "incomplete"
    return "empty"


def _assignment_empty_label(assignment_workspace: AssignmentWorkspace) -> str:
    return f"{assignment_workspace.proposal_kind.replace('_', ' ').title()} needs input"


def _is_fight_order_decision(pending_decision: UiDecision | None) -> bool:
    return (
        pending_decision is not None
        and not pending_decision.is_parameterized
        and pending_decision.decision_type in ("select_fight_activation", "resolve_fight_interrupt")
    )


def _fight_option_ref_key(option_id: str) -> str | None:
    parts = option_id.split(":")
    if len(parts) != 3 or parts[0] != "fight":
        return None
    return f"unit:{parts[2]}"


def _finite_option_summary(option_id: str) -> str:
    parts = option_id.split(":")
    if len(parts) == 3 and parts[0] == "fight":
        return f"Fight type: {parts[1]}; unit: {parts[2]}"
    if option_id == "eligible_to_fight_pass":
        return "Engine-issued pass option."
    if option_id == "decline_fight_interrupt":
        return "Engine-issued interrupt decline option."
    return f"Option ID: {option_id}"


def _ref_keys(refs: tuple[EntityRef, ...]) -> tuple[str, ...]:
    return tuple(ref.selection_key for ref in refs)


def finite_actions_for_unit(
    *,
    pending_decision: UiDecision | None,
    unit_id: str,
    highlighted_option_id: str | None = None,
) -> tuple[ContextMenuAction, ...]:
    """Return finite actions for a selected unit from engine-provided options only."""

    if (
        pending_decision is None
        or pending_decision.is_parameterized
        or not decision_targets_unit(pending_decision, unit_id)
    ):
        return ()
    return tuple(
        _action_from_option(
            option,
            highlighted=option.option_id == highlighted_option_id,
        )
        for option in pending_decision.options
    )


def decision_targets_unit(decision: UiDecision, unit_id: str) -> bool:
    """Return whether a pending decision payload names the selected unit."""

    proposal = decision.movement_proposal
    if proposal is not None and proposal.unit_instance_id == unit_id:
        return True
    placement_proposal = decision.placement_proposal
    if placement_proposal is not None and placement_proposal.unit_instance_id == unit_id:
        return True
    return _payload_targets_unit(decision.payload, unit_id)


def _action_from_option(
    option: UiFiniteOption,
    *,
    highlighted: bool = False,
) -> ContextMenuAction:
    return ContextMenuAction(
        option_id=option.option_id,
        label=option.label,
        disabled_reason=_disabled_reason(option.payload),
        highlighted=highlighted,
    )


def _diagnostic_lines(diagnostics: tuple[UiInvalidDiagnostic, ...]) -> tuple[str, ...]:
    return tuple(_diagnostic_line(diagnostic) for diagnostic in diagnostics)


def _diagnostic_line(diagnostic: UiInvalidDiagnostic) -> str:
    field = "" if diagnostic.field is None else f" [{diagnostic.field}]"
    return f"{diagnostic.violation_code}{field}: {diagnostic.message}"


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
