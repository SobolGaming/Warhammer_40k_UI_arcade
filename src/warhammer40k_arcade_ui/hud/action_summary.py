"""Advisory action visual summary view models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from warhammer40k_arcade_ui.core_client.protocol import UiDecision, UiInvalidDiagnostic
from warhammer40k_arcade_ui.preferences.schema import ActionSummaryDefault
from warhammer40k_arcade_ui.render.camera import WorldPoint
from warhammer40k_arcade_ui.state.movement_draft import (
    MovementDraft,
    unsupported_parameterized_tool_label,
)

type ActionSummaryIntensity = Literal["hidden", "dim", "review"]
type ActionSummaryOperationKind = Literal["movement", "unsupported"]
type ActionSummaryGroupState = Literal["active", "assigned", "unassigned", "warning", "invalid"]
type ActionSummaryColorRole = Literal["movement", "warning", "unsupported"]


@dataclass(frozen=True, slots=True)
class ActionVisualSummaryGroup:
    """One visual group in a request-scoped advisory battlefield summary."""

    group_id: str
    label: str
    state: ActionSummaryGroupState
    source_ref_keys: tuple[str, ...]
    target_ref_keys: tuple[str, ...]
    path_points: tuple[WorldPoint, ...]
    ghost_center: WorldPoint | None
    ghost_radius: float | None
    icon_id: str | None
    color_role: ActionSummaryColorRole
    summary_lines: tuple[str, ...]

    @property
    def has_path(self) -> bool:
        """Return whether this summary group includes a drawable path."""

        return len(self.path_points) >= 2


@dataclass(frozen=True, slots=True)
class ActionVisualSummary:
    """Generic advisory battlefield summary for the current request workspace."""

    request_id: str | None
    operation_kind: ActionSummaryOperationKind
    intensity: ActionSummaryIntensity
    groups: tuple[ActionVisualSummaryGroup, ...]
    diagnostic_lines: tuple[str, ...]
    ready: bool
    max_labels: int

    @property
    def has_drawable_groups(self) -> bool:
        """Return whether this summary contains map geometry."""

        return any(group.has_path or group.ghost_center is not None for group in self.groups)


def build_action_visual_summary(
    *,
    movement_draft: MovementDraft | None,
    pending_decision: UiDecision | None,
    diagnostics: tuple[UiInvalidDiagnostic, ...],
    intensity: ActionSummaryDefault,
    max_labels: int,
) -> ActionVisualSummary | None:
    """Build an advisory visual summary without adding a second rules path."""

    if intensity == "hidden":
        return None
    if movement_draft is not None:
        return _movement_visual_summary(
            movement_draft=movement_draft,
            diagnostics=diagnostics,
            intensity=intensity,
            max_labels=max_labels,
        )
    unsupported_label = unsupported_parameterized_tool_label(pending_decision)
    if unsupported_label is not None:
        return _unsupported_summary(
            pending_decision=pending_decision,
            label=unsupported_label,
            intensity=intensity,
            max_labels=max_labels,
        )
    if _is_fight_order_decision(pending_decision):
        return _unsupported_summary(
            pending_decision=pending_decision,
            label=None if pending_decision is None else pending_decision.decision_type,
            intensity=intensity,
            max_labels=max_labels,
        )
    return None


def _movement_visual_summary(
    *,
    movement_draft: MovementDraft,
    diagnostics: tuple[UiInvalidDiagnostic, ...],
    intensity: ActionSummaryDefault,
    max_labels: int,
) -> ActionVisualSummary:
    diagnostic_lines = _diagnostic_lines(diagnostics)
    warning = bool(diagnostic_lines) or any(
        "warning" in hint.lower() for hint in movement_draft.local_hint_lines
    )
    groups: list[ActionVisualSummaryGroup] = []
    for assignment in movement_draft.assignment_views():
        if not assignment.has_movement:
            continue
        state = "warning" if warning else assignment.state
        group_id = assignment.assignment_group_id or f"model:{assignment.model_id}"
        groups.append(
            ActionVisualSummaryGroup(
                group_id=group_id,
                label=f"{assignment.model_id} movement path",
                state=state,
                source_ref_keys=(f"model:{assignment.model_id}",),
                target_ref_keys=(),
                path_points=assignment.points,
                ghost_center=assignment.final_point,
                ghost_radius=assignment.base_radius,
                icon_id=None,
                color_role="warning" if warning else "movement",
                summary_lines=(f"Path: {assignment.path_length_inches:.2f} in",),
            )
        )
    return ActionVisualSummary(
        request_id=movement_draft.proposal_request_id,
        operation_kind="movement",
        intensity=intensity,
        groups=tuple(groups),
        diagnostic_lines=(*movement_draft.local_hint_lines, *diagnostic_lines),
        ready=movement_draft.is_ready,
        max_labels=max_labels,
    )


def _unsupported_summary(
    *,
    pending_decision: UiDecision | None,
    label: str | None,
    intensity: ActionSummaryDefault,
    max_labels: int,
) -> ActionVisualSummary:
    diagnostic_label = label or "unknown"
    return ActionVisualSummary(
        request_id=None if pending_decision is None else pending_decision.request_id,
        operation_kind="unsupported",
        intensity=intensity,
        groups=(),
        diagnostic_lines=(
            f"No action visual summary adapter is available for {diagnostic_label}.",
        ),
        ready=False,
        max_labels=max_labels,
    )


def _diagnostic_lines(diagnostics: tuple[UiInvalidDiagnostic, ...]) -> tuple[str, ...]:
    lines: list[str] = []
    for diagnostic in diagnostics:
        field = f" [{diagnostic.field}]" if diagnostic.field else ""
        lines.append(f"{diagnostic.violation_code}{field}: {diagnostic.message}")
    return tuple(lines)


def _is_fight_order_decision(pending_decision: UiDecision | None) -> bool:
    if pending_decision is None or pending_decision.is_parameterized:
        return False
    return pending_decision.decision_type in {
        "select_fight_activation",
        "resolve_fight_interrupt",
    }
