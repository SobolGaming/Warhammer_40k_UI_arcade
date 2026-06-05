"""Local movement draft state and JSON-safe payload preview building."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Literal, cast

from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiDecision,
    UiMovementProposalRequest,
    validate_json_value,
)
from warhammer40k_arcade_ui.render.camera import WorldPoint
from warhammer40k_arcade_ui.render.view_models import BattlefieldView, UnitView
from warhammer40k_arcade_ui.state.entity_selection import (
    EntityRef,
    EntitySelectionState,
    build_entity_selection_profile,
    entity_ref_for_model,
)
from warhammer40k_arcade_ui.state.selection import SelectionState, selected_unit

MOVEMENT_PROPOSAL_DECISION_TYPE = "submit_movement_proposal"
MOVEMENT_MODE_CONTEXT_KEY = "movement_mode"
FALL_BACK_MODE_CONTEXT_KEY = "fall_back_mode"
MOVEMENT_BUDGET_CONTEXT_KEY = "movement_budget_inches"

type MovementDraftMode = Literal["model_assignments"]
type MovementAssignmentState = Literal["active", "assigned", "unassigned"]


class MovementDraftError(ValueError):
    """Raised when a movement proposal cannot be represented as a local draft."""


@dataclass(frozen=True, slots=True)
class MovementModelPath:
    """Path points for one model in a local movement draft."""

    model_id: str
    base_radius: float
    points: tuple[WorldPoint, ...]
    assignment_group_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", _non_empty_string("model_id", self.model_id))
        _validate_positive("base_radius", self.base_radius)
        if type(self.points) is not tuple or not self.points:
            raise MovementDraftError("MovementModelPath points must be a non-empty tuple.")
        object.__setattr__(
            self,
            "points",
            tuple(_validate_world_point("path point", point) for point in self.points),
        )
        object.__setattr__(
            self,
            "assignment_group_id",
            _optional_string("assignment_group_id", self.assignment_group_id),
        )

    @property
    def final_point(self) -> WorldPoint:
        """Return the current final point for this model path."""

        return self.points[-1]

    @property
    def has_movement(self) -> bool:
        """Return whether this path includes a non-zero movement segment."""

        return any(math.dist(start, end) > 0.0 for start, end in pairwise(self.points))

    @property
    def path_length_inches(self) -> float:
        """Return total path length in inches."""

        return _polyline_length(self.points)

    def payload_points(self) -> tuple[WorldPoint, ...]:
        """Return payload points, including explicit no-op start/end for unchanged models."""

        if len(self.points) == 1:
            return (self.points[0], self.points[0])
        return self.points

    def with_translated_waypoint(
        self,
        *,
        delta_x: float,
        delta_y: float,
        assignment_group_id: str,
    ) -> MovementModelPath:
        """Append a waypoint translated from the current final point."""

        _validate_finite("delta_x", delta_x)
        _validate_finite("delta_y", delta_y)
        final_x, final_y = self.final_point
        return replace(
            self,
            points=(*self.points, (final_x + delta_x, final_y + delta_y)),
            assignment_group_id=assignment_group_id,
        )

    def with_preview_waypoint(self, *, delta_x: float, delta_y: float) -> MovementModelPath:
        """Return a non-mutating preview path translated from the current final point."""

        _validate_finite("delta_x", delta_x)
        _validate_finite("delta_y", delta_y)
        final_x, final_y = self.final_point
        return replace(self, points=(*self.points, (final_x + delta_x, final_y + delta_y)))

    def with_removed_last_waypoint(self) -> MovementModelPath:
        """Remove the most recent waypoint while preserving the starting point."""

        if len(self.points) <= 1:
            return self
        points = self.points[:-1]
        return replace(
            self,
            points=points,
            assignment_group_id=self.assignment_group_id if len(points) > 1 else None,
        )


@dataclass(frozen=True, slots=True)
class MovementAssignmentView:
    """Summary-friendly view of one model's local movement assignment."""

    model_id: str
    base_radius: float
    points: tuple[WorldPoint, ...]
    final_point: WorldPoint
    assignment_group_id: str | None
    state: MovementAssignmentState
    path_length_inches: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", _non_empty_string("model_id", self.model_id))
        _validate_positive("base_radius", self.base_radius)
        if type(self.points) is not tuple or not self.points:
            raise MovementDraftError("MovementAssignmentView points must be a non-empty tuple.")
        object.__setattr__(
            self,
            "points",
            tuple(_validate_world_point("assignment point", point) for point in self.points),
        )
        object.__setattr__(
            self,
            "final_point",
            _validate_world_point("final_point", self.final_point),
        )
        object.__setattr__(
            self,
            "assignment_group_id",
            _optional_string("assignment_group_id", self.assignment_group_id),
        )
        if self.state not in ("active", "assigned", "unassigned"):
            raise MovementDraftError("MovementAssignmentView state is unsupported.")
        _validate_non_negative("path_length_inches", self.path_length_inches)

    @property
    def has_movement(self) -> bool:
        """Return whether this assignment includes a non-zero movement segment."""

        return self.path_length_inches > 0.0


@dataclass(frozen=True, slots=True)
class MovementDraft:
    """Local per-model assignment workspace for a pending movement proposal request."""

    selected_unit_id: str
    proposal_request_id: str
    proposal_kind: str
    movement_phase_action: str
    movement_mode: str | None
    fall_back_mode: str | None
    source_decision_request_id: str
    source_decision_result_id: str
    mode: MovementDraftMode
    entity_selection: EntitySelectionState
    model_paths: tuple[MovementModelPath, ...]
    cursor_preview_point: WorldPoint | None
    movement_budget_inches: float | None
    local_hint_lines: tuple[str, ...]
    ready_payload: JsonObject | None = None
    next_assignment_group_index: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "selected_unit_id",
            _non_empty_string("selected_unit_id", self.selected_unit_id),
        )
        object.__setattr__(
            self,
            "proposal_request_id",
            _non_empty_string("proposal_request_id", self.proposal_request_id),
        )
        object.__setattr__(
            self,
            "proposal_kind",
            _non_empty_string("proposal_kind", self.proposal_kind),
        )
        object.__setattr__(
            self,
            "movement_phase_action",
            _non_empty_string("movement_phase_action", self.movement_phase_action),
        )
        object.__setattr__(
            self,
            "movement_mode",
            _optional_string("movement_mode", self.movement_mode),
        )
        object.__setattr__(
            self,
            "fall_back_mode",
            _optional_string("fall_back_mode", self.fall_back_mode),
        )
        object.__setattr__(
            self,
            "source_decision_request_id",
            _non_empty_string(
                "source_decision_request_id",
                self.source_decision_request_id,
            ),
        )
        object.__setattr__(
            self,
            "source_decision_result_id",
            _non_empty_string(
                "source_decision_result_id",
                self.source_decision_result_id,
            ),
        )
        if self.mode != "model_assignments":
            raise MovementDraftError("Unsupported movement draft mode.")
        if type(self.entity_selection) is not EntitySelectionState:
            raise MovementDraftError("entity_selection must be an EntitySelectionState.")
        if type(self.model_paths) is not tuple or not self.model_paths:
            raise MovementDraftError("MovementDraft model_paths must be a non-empty tuple.")
        if any(type(path) is not MovementModelPath for path in self.model_paths):
            raise MovementDraftError("MovementDraft model_paths must contain MovementModelPath.")
        _validate_unique_model_paths(self.model_paths)
        object.__setattr__(
            self,
            "cursor_preview_point",
            _optional_world_point("cursor_preview_point", self.cursor_preview_point),
        )
        if self.movement_budget_inches is not None:
            _validate_positive("movement_budget_inches", self.movement_budget_inches)
        if type(self.local_hint_lines) is not tuple:
            raise MovementDraftError("MovementDraft local_hint_lines must be a tuple.")
        object.__setattr__(
            self,
            "local_hint_lines",
            tuple(_non_empty_string("hint", hint) for hint in self.local_hint_lines),
        )
        if self.ready_payload is not None:
            object.__setattr__(
                self,
                "ready_payload",
                _json_object("ready_payload", self.ready_payload),
            )
        if (
            type(self.next_assignment_group_index) is not int
            or self.next_assignment_group_index < 1
        ):
            raise MovementDraftError("next_assignment_group_index must be a positive integer.")

    @classmethod
    def start_for_pending(
        cls,
        *,
        view: BattlefieldView,
        selection: SelectionState,
        pending_decision: UiDecision | None,
    ) -> MovementDraft | None:
        """Create a movement draft for the selected unit and current movement proposal."""

        proposal = movement_proposal_for_selected_unit(
            view=view,
            selection=selection,
            pending_decision=pending_decision,
        )
        if proposal is None or pending_decision is None:
            return None
        unit = selected_unit(view, selection)
        if unit is None:
            return None
        if proposal.movement_phase_action is None:
            raise MovementDraftError("Movement proposal requires movement_phase_action.")
        entity_selection = _seed_entity_selection(
            view=view,
            selection=selection,
            pending_decision=pending_decision,
            unit=unit,
        )
        draft = cls(
            selected_unit_id=unit.unit_id,
            proposal_request_id=proposal.request_id,
            proposal_kind=proposal.proposal_kind,
            movement_phase_action=proposal.movement_phase_action,
            movement_mode=_context_string(proposal.context, MOVEMENT_MODE_CONTEXT_KEY),
            fall_back_mode=_context_string(proposal.context, FALL_BACK_MODE_CONTEXT_KEY),
            source_decision_request_id=proposal.source_decision_request_id,
            source_decision_result_id=proposal.source_decision_result_id,
            mode="model_assignments",
            entity_selection=entity_selection,
            model_paths=tuple(
                MovementModelPath(
                    model_id=model.model_id,
                    base_radius=model.base_radius,
                    points=(model.position,),
                )
                for model in unit.models
            ),
            cursor_preview_point=None,
            movement_budget_inches=_context_positive_float(
                proposal.context,
                MOVEMENT_BUDGET_CONTEXT_KEY,
            ),
            local_hint_lines=(),
        )
        return draft.with_recomputed_hints(view=view)

    @property
    def is_ready(self) -> bool:
        """Return whether the draft has a JSON-safe payload preview."""

        return self.ready_payload is not None

    @property
    def has_assignments(self) -> bool:
        """Return whether any model has a non-zero drafted movement path."""

        return any(path.has_movement for path in self.model_paths)

    @property
    def total_model_count(self) -> int:
        """Return the number of models in the proposal unit."""

        return len(self.model_paths)

    @property
    def assigned_model_count(self) -> int:
        """Return the number of models with drafted non-zero movement."""

        return sum(1 for path in self.model_paths if path.has_movement)

    @property
    def unchanged_model_count(self) -> int:
        """Return the number of models represented as no-op paths."""

        return self.total_model_count - self.assigned_model_count

    @property
    def selected_model_ids(self) -> tuple[str, ...]:
        """Return active model IDs after applying unit aliases to the model layer."""

        ids: list[str] = []
        all_model_ids = tuple(path.model_id for path in self.model_paths)
        for ref in self.entity_selection.selected_refs:
            if ref.kind == "model" and ref.entity_id in all_model_ids and ref.entity_id not in ids:
                ids.append(ref.entity_id)
            elif ref.kind == "unit" and ref.entity_id == self.selected_unit_id:
                ids.extend(model_id for model_id in all_model_ids if model_id not in ids)
        return tuple(ids)

    @property
    def active_layer(self) -> str | None:
        """Return the active entity-selection layer."""

        return self.entity_selection.active_layer

    @property
    def current_segment_length(self) -> float:
        """Return the current preview segment length in inches."""

        if self.cursor_preview_point is None:
            return 0.0
        anchor = self._active_anchor_point()
        if anchor is None:
            return 0.0
        return math.dist(anchor, self.cursor_preview_point)

    @property
    def total_path_length(self) -> float:
        """Return the longest active selected model path length."""

        active_ids = set(self.selected_model_ids)
        if not active_ids:
            return 0.0
        paths = [path for path in self.preview_model_paths() if path.model_id in active_ids]
        if not paths:
            return 0.0
        return max(path.path_length_inches for path in paths)

    @property
    def remaining_budget_inches(self) -> float | None:
        """Return remaining advisory movement budget, when the proposal provided one."""

        if self.movement_budget_inches is None:
            return None
        return self.movement_budget_inches - self.total_path_length

    @property
    def payload_preview(self) -> JsonObject | None:
        """Return the ready payload preview, if Enter has marked the draft ready."""

        return self.ready_payload

    def is_for(self, *, selection: SelectionState, pending_decision: UiDecision | None) -> bool:
        """Return whether this draft still matches the selected unit and pending request."""

        if selection.selected_unit_id != self.selected_unit_id:
            return False
        return self.matches_proposal_context(pending_decision=pending_decision)

    def matches_proposal_context(self, *, pending_decision: UiDecision | None) -> bool:
        """Return whether this draft matches the current movement proposal context."""

        proposal = None if pending_decision is None else pending_decision.movement_proposal
        return (
            proposal is not None
            and proposal.decision_type == MOVEMENT_PROPOSAL_DECISION_TYPE
            and proposal.unit_instance_id == self.selected_unit_id
            and proposal.request_id == self.proposal_request_id
            and proposal.proposal_kind == self.proposal_kind
            and proposal.movement_phase_action == self.movement_phase_action
            and _context_string(proposal.context, MOVEMENT_MODE_CONTEXT_KEY) == self.movement_mode
            and _context_string(proposal.context, FALL_BACK_MODE_CONTEXT_KEY) == self.fall_back_mode
        )

    def can_retry_for(self, *, pending_decision: UiDecision | None) -> bool:
        """Return whether a fresh movement request can safely reuse this draft's paths."""

        proposal = None if pending_decision is None else pending_decision.movement_proposal
        return (
            proposal is not None
            and proposal.decision_type == MOVEMENT_PROPOSAL_DECISION_TYPE
            and proposal.unit_instance_id == self.selected_unit_id
            and proposal.proposal_kind == self.proposal_kind
            and proposal.source_decision_request_id == self.source_decision_request_id
            and proposal.source_decision_result_id == self.source_decision_result_id
            and proposal.movement_phase_action == self.movement_phase_action
            and _context_string(proposal.context, MOVEMENT_MODE_CONTEXT_KEY) == self.movement_mode
            and _context_string(proposal.context, FALL_BACK_MODE_CONTEXT_KEY) == self.fall_back_mode
        )

    def with_retry_request(
        self,
        *,
        view: BattlefieldView,
        pending_decision: UiDecision,
    ) -> MovementDraft:
        """Retarget drafted paths to a fresh same-context retry proposal request."""

        if not self.can_retry_for(pending_decision=pending_decision):
            raise MovementDraftError("Retry movement draft must match the new proposal context.")
        proposal = pending_decision.movement_proposal
        if proposal is None:
            raise MovementDraftError("Retry movement draft requires a movement proposal.")
        return replace(
            self,
            proposal_request_id=proposal.request_id,
            ready_payload=None,
            cursor_preview_point=None,
        ).with_recomputed_hints(view=view)

    def replace_model_selection(
        self,
        *,
        view: BattlefieldView,
        ref: EntityRef,
    ) -> MovementDraft:
        """Replace the active request-scoped movement model selection."""

        return self._with_entity_selection(
            view=view,
            entity_selection=self.entity_selection.replace_selection(ref),
        )

    def add_model_selection(
        self,
        *,
        view: BattlefieldView,
        ref: EntityRef,
    ) -> MovementDraft:
        """Add a model or alias target to the active movement selection."""

        return self._with_entity_selection(
            view=view,
            entity_selection=self.entity_selection.add_selection(ref),
        )

    def subtract_model_selection(
        self,
        *,
        view: BattlefieldView,
        ref: EntityRef,
    ) -> MovementDraft:
        """Remove a model or alias target from the active movement selection."""

        return self._with_entity_selection(
            view=view,
            entity_selection=self.entity_selection.subtract_selection(ref),
        )

    def toggle_model_selection(
        self,
        *,
        view: BattlefieldView,
        ref: EntityRef,
    ) -> MovementDraft:
        """Toggle a model or alias target in the active movement selection."""

        return self._with_entity_selection(
            view=view,
            entity_selection=self.entity_selection.toggle_selection(ref),
        )

    def clear_active_selection(self, *, view: BattlefieldView) -> MovementDraft:
        """Clear the active request-scoped selection while keeping drafted paths."""

        return self._with_entity_selection(
            view=view,
            entity_selection=self.entity_selection.clear_selection(),
        )

    def cycle_entity_focus(self, *, view: BattlefieldView) -> MovementDraft:
        """Cycle focus through the active entity layer."""

        return self._with_entity_selection(
            view=view,
            entity_selection=self.entity_selection.cycle_focus(),
        )

    def cycle_entity_layer(self, *, view: BattlefieldView) -> MovementDraft:
        """Cycle the active entity-selection layer."""

        return self._with_entity_selection(
            view=view,
            entity_selection=self.entity_selection.cycle_active_layer(),
        )

    def select_current_group(self, *, view: BattlefieldView) -> MovementDraft:
        """Expand the focused model to its current selectable group."""

        return self._with_entity_selection(
            view=view,
            entity_selection=self.entity_selection.select_current_group(),
        )

    def with_cursor_preview(
        self,
        *,
        view: BattlefieldView,
        world_point: WorldPoint,
    ) -> MovementDraft:
        """Update the current local endpoint preview."""

        return replace(
            self,
            cursor_preview_point=_validate_world_point("world_point", world_point),
            ready_payload=None,
        ).with_recomputed_hints(view=view)

    def add_waypoint(self, *, view: BattlefieldView, world_point: WorldPoint) -> MovementDraft:
        """Commit a waypoint to the active selected model subset."""

        point = _validate_world_point("world_point", world_point)
        active_ids = self.selected_model_ids
        anchor = self._active_anchor_point()
        if not active_ids or anchor is None:
            return replace(
                self,
                cursor_preview_point=None,
                ready_payload=None,
                local_hint_lines=(
                    *self.local_hint_lines,
                    "Preview warning: select one or more moving models before adding a waypoint.",
                ),
            )
        anchor_x, anchor_y = anchor
        point_x, point_y = point
        delta_x = point_x - anchor_x
        delta_y = point_y - anchor_y
        group_id, next_index = self._assignment_group_for_active_selection(active_ids)
        return replace(
            self,
            model_paths=tuple(
                path.with_translated_waypoint(
                    delta_x=delta_x,
                    delta_y=delta_y,
                    assignment_group_id=group_id,
                )
                if path.model_id in active_ids
                else path
                for path in self.model_paths
            ),
            cursor_preview_point=None,
            ready_payload=None,
            next_assignment_group_index=next_index,
        ).with_recomputed_hints(view=view)

    def remove_last_waypoint(self, *, view: BattlefieldView) -> MovementDraft:
        """Remove the most recent waypoint for the active selected model subset."""

        active_ids = set(self.selected_model_ids)
        if not active_ids:
            return replace(self, cursor_preview_point=None, ready_payload=None)
        return replace(
            self,
            model_paths=tuple(
                path.with_removed_last_waypoint() if path.model_id in active_ids else path
                for path in self.model_paths
            ),
            cursor_preview_point=None,
            ready_payload=None,
        ).with_recomputed_hints(view=view)

    def mark_ready(self, *, view: BattlefieldView) -> MovementDraft:
        """Mark the current draft ready by building a payload preview without submitting."""

        draft = (
            self.add_waypoint(view=view, world_point=self.cursor_preview_point)
            if self.cursor_preview_point is not None
            else self
        )
        if not draft.has_assignments:
            return replace(
                draft,
                ready_payload=None,
                local_hint_lines=(
                    *draft.local_hint_lines,
                    "Preview warning: add an endpoint before marking the movement draft ready.",
                ),
            )
        return replace(draft, ready_payload=draft.to_payload()).with_recomputed_hints(view=view)

    def with_recomputed_hints(self, *, view: BattlefieldView) -> MovementDraft:
        """Recompute local advisory hints for the current assignment geometry."""

        return replace(self, local_hint_lines=_local_hint_lines(view=view, draft=self))

    def preview_model_paths(self) -> tuple[MovementModelPath, ...]:
        """Return model paths including the current cursor preview, if any."""

        if self.cursor_preview_point is None:
            return self.model_paths
        active_ids = self.selected_model_ids
        anchor = self._active_anchor_point()
        if not active_ids or anchor is None:
            return self.model_paths
        anchor_x, anchor_y = anchor
        point_x, point_y = self.cursor_preview_point
        delta_x = point_x - anchor_x
        delta_y = point_y - anchor_y
        return tuple(
            path.with_preview_waypoint(delta_x=delta_x, delta_y=delta_y)
            if path.model_id in active_ids
            else path
            for path in self.model_paths
        )

    def assignment_views(self) -> tuple[MovementAssignmentView, ...]:
        """Return summary-friendly assignment rows for render, HUD, and later visual summaries."""

        active_ids = set(self.selected_model_ids)
        return tuple(
            MovementAssignmentView(
                model_id=path.model_id,
                base_radius=path.base_radius,
                points=path.points,
                final_point=path.final_point,
                assignment_group_id=path.assignment_group_id,
                state="active"
                if path.model_id in active_ids
                else "assigned"
                if path.has_movement
                else "unassigned",
                path_length_inches=path.path_length_inches,
            )
            for path in self.preview_model_paths()
        )

    def to_payload(self) -> JsonObject:
        """Build the JSON-safe movement proposal payload for the committed draft."""

        body: JsonObject = {
            "proposal_request_id": self.proposal_request_id,
            "proposal_kind": self.proposal_kind,
            "unit_instance_id": self.selected_unit_id,
            "movement_phase_action": self.movement_phase_action,
            "witness": {
                "model_paths": [
                    {
                        "model_id": path.model_id,
                        "poses": [_pose_payload(point) for point in path.payload_points()],
                    }
                    for path in self.model_paths
                ],
            },
            "model_movements": [
                {
                    "model_instance_id": path.model_id,
                    "path": [_pose_payload(point) for point in path.payload_points()],
                    "final_pose": _pose_payload(path.payload_points()[-1]),
                }
                for path in self.model_paths
            ],
        }
        if self.movement_mode is not None:
            body["movement_mode"] = self.movement_mode
        if self.fall_back_mode is not None:
            body["fall_back_mode"] = self.fall_back_mode
        return _json_object("movement proposal payload", body)

    def _with_entity_selection(
        self,
        *,
        view: BattlefieldView,
        entity_selection: EntitySelectionState,
    ) -> MovementDraft:
        return replace(
            self,
            entity_selection=entity_selection,
            cursor_preview_point=None,
            ready_payload=None,
        ).with_recomputed_hints(view=view)

    def _active_anchor_point(self) -> WorldPoint | None:
        active_ids = set(self.selected_model_ids)
        if not active_ids:
            return None
        points = tuple(path.final_point for path in self.model_paths if path.model_id in active_ids)
        if not points:
            return None
        return _mean_point(points)

    def _assignment_group_for_active_selection(
        self,
        active_ids: tuple[str, ...],
    ) -> tuple[str, int]:
        active_paths = tuple(path for path in self.model_paths if path.model_id in active_ids)
        group_ids = {
            path.assignment_group_id
            for path in active_paths
            if path.assignment_group_id is not None
        }
        if len(group_ids) == 1 and all(
            path.assignment_group_id in group_ids for path in active_paths
        ):
            group_id = next(iter(group_ids))
            return group_id, self.next_assignment_group_index
        group_id = f"assignment-group-{self.next_assignment_group_index:06d}"
        return group_id, self.next_assignment_group_index + 1


def movement_proposal_for_selected_unit(
    *,
    view: BattlefieldView,
    selection: SelectionState,
    pending_decision: UiDecision | None,
) -> UiMovementProposalRequest | None:
    """Return the movement proposal that can activate drafting for the selected unit."""

    del view
    if selection.selected_unit_id is None or pending_decision is None:
        return None
    proposal = pending_decision.movement_proposal
    if proposal is None:
        return None
    if proposal.decision_type != MOVEMENT_PROPOSAL_DECISION_TYPE:
        return None
    if proposal.unit_instance_id != selection.selected_unit_id:
        return None
    return proposal


def unsupported_parameterized_tool_label(pending_decision: UiDecision | None) -> str | None:
    """Return a display label when a parameterized request is not movement-draftable."""

    if pending_decision is None or not pending_decision.is_parameterized:
        return None
    proposal = pending_decision.parameterized_proposal
    if proposal is None:
        return pending_decision.decision_type
    if pending_decision.movement_proposal is not None:
        movement = pending_decision.movement_proposal
        if movement.decision_type == MOVEMENT_PROPOSAL_DECISION_TYPE:
            return None
    return proposal.proposal_kind or proposal.decision_type


def _seed_entity_selection(
    *,
    view: BattlefieldView,
    selection: SelectionState,
    pending_decision: UiDecision,
    unit: UnitView,
) -> EntitySelectionState:
    profile = build_entity_selection_profile(view=view, pending_decision=pending_decision)
    state = EntitySelectionState.initial(profile)
    seed_ref = (
        entity_ref_for_model(
            view=view,
            unit_id=unit.unit_id,
            model_id=selection.selected_model_id,
        )
        if selection.selected_model_id is not None
        else None
    )
    if seed_ref is None:
        seed_ref = entity_ref_for_model(
            view=view,
            unit_id=unit.unit_id,
            model_id=unit.models[0].model_id,
        )
    if seed_ref is None:
        return state
    return state.replace_selection(seed_ref)


def _local_hint_lines(*, view: BattlefieldView, draft: MovementDraft) -> tuple[str, ...]:
    hints: list[str] = ["Preview/advisory only; engine validates movement."]
    selected_count = len(draft.selected_model_ids)
    hints.append(f"Active movement selection: {selected_count} model(s).")
    if draft.unchanged_model_count:
        hints.append(
            "Preview note: "
            f"{draft.unchanged_model_count} unchanged model(s) remain explicit no-op paths."
        )
    if draft.movement_budget_inches is None:
        hints.append("Preview warning: movement budget is unavailable in the proposal context.")
    elif _has_over_budget_path(draft):
        hints.append("Preview warning: at least one path exceeds the displayed movement budget.")
    if _has_out_of_bounds_endpoint(view=view, draft=draft):
        hints.append("Preview warning: final ghost base is outside table bounds.")
    if _has_self_overlap(draft):
        hints.append("Preview warning: final ghost bases overlap each other.")
    return tuple(hints)


def _has_over_budget_path(draft: MovementDraft) -> bool:
    if draft.movement_budget_inches is None:
        return False
    return any(path.path_length_inches > draft.movement_budget_inches for path in draft.model_paths)


def _has_out_of_bounds_endpoint(*, view: BattlefieldView, draft: MovementDraft) -> bool:
    for path in draft.preview_model_paths():
        final_x, final_y = path.final_point
        if (
            final_x - path.base_radius < 0.0
            or final_y - path.base_radius < 0.0
            or final_x + path.base_radius > view.table.width
            or final_y + path.base_radius > view.table.height
        ):
            return True
    return False


def _has_self_overlap(draft: MovementDraft) -> bool:
    paths = draft.preview_model_paths()
    for index, left in enumerate(paths):
        for right in paths[index + 1 :]:
            if math.dist(left.final_point, right.final_point) < (
                left.base_radius + right.base_radius
            ):
                return True
    return False


def _polyline_length(points: tuple[WorldPoint, ...]) -> float:
    if len(points) < 2:
        return 0.0
    return sum(math.dist(start, end) for start, end in pairwise(points))


def _pose_payload(point: WorldPoint) -> JsonObject:
    x, y = point
    return {
        "position": {
            "x": x,
            "y": y,
            "z": 0.0,
        },
        "facing": {"degrees": 0.0},
    }


def _context_string(context: JsonObject, key: str) -> str | None:
    value = context.get(key)
    if value is None:
        return None
    return _non_empty_string(key, value)


def _context_positive_float(context: JsonObject, key: str) -> float | None:
    value = context.get(key)
    if value is None:
        return None
    if type(value) is int:
        value = float(value)
    if type(value) is not float:
        raise MovementDraftError(f"{key} must be a number.")
    _validate_positive(key, value)
    return value


def _json_object(field_name: str, value: object) -> JsonObject:
    json_value = validate_json_value(value)
    if type(json_value) is not dict:
        raise MovementDraftError(f"{field_name} must be a JSON object.")
    return json_value


def _validate_unique_model_paths(paths: tuple[MovementModelPath, ...]) -> None:
    seen: set[str] = set()
    for path in paths:
        if path.model_id in seen:
            raise MovementDraftError("MovementDraft model_paths must not contain duplicates.")
        seen.add(path.model_id)


def _optional_world_point(field_name: str, value: WorldPoint | None) -> WorldPoint | None:
    if value is None:
        return None
    return _validate_world_point(field_name, value)


def _validate_world_point(field_name: str, value: object) -> WorldPoint:
    if type(value) is not tuple:
        raise MovementDraftError(f"{field_name} must be a 2D world point.")
    point = cast(tuple[object, ...], value)
    if len(point) != 2:
        raise MovementDraftError(f"{field_name} must be a 2D world point.")
    x = point[0]
    y = point[1]
    return (
        _validated_finite_float(f"{field_name}.x", x),
        _validated_finite_float(f"{field_name}.y", y),
    )


def _mean_point(points: tuple[WorldPoint, ...]) -> WorldPoint:
    x_total = sum(point[0] for point in points)
    y_total = sum(point[1] for point in points)
    return (x_total / len(points), y_total / len(points))


def _non_empty_string(field_name: str, value: object) -> str:
    if type(value) is not str:
        raise MovementDraftError(f"{field_name} must be a string.")
    stripped = value.strip()
    if not stripped:
        raise MovementDraftError(f"{field_name} must not be empty.")
    return stripped


def _optional_string(field_name: str, value: object | None) -> str | None:
    if value is None:
        return None
    return _non_empty_string(field_name, value)


def _validate_positive(field_name: str, value: float) -> None:
    if type(value) is not float and type(value) is not int:
        raise MovementDraftError(f"{field_name} must be a number.")
    if value <= 0.0 or not math.isfinite(value):
        raise MovementDraftError(f"{field_name} must be finite and positive.")


def _validate_non_negative(field_name: str, value: float) -> None:
    if type(value) is not float and type(value) is not int:
        raise MovementDraftError(f"{field_name} must be a number.")
    if value < 0.0 or not math.isfinite(value):
        raise MovementDraftError(f"{field_name} must be finite and non-negative.")


def _validate_finite(field_name: str, value: object) -> None:
    _validated_finite_float(field_name, value)


def _validated_finite_float(field_name: str, value: object) -> float:
    if type(value) is not float and type(value) is not int:
        raise MovementDraftError(f"{field_name} must be a number.")
    float_value = float(value)
    if not math.isfinite(float_value):
        raise MovementDraftError(f"{field_name} must be finite.")
    return float_value
