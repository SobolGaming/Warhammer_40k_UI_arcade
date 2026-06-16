"""Local movement draft state and JSON-safe payload preview building."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Literal, cast

from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    JsonValue,
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
from warhammer40k_arcade_ui.state.selection import SelectionState

MOVEMENT_PROPOSAL_DECISION_TYPE = "submit_movement_proposal"
SCOUT_MOVE_DECISION_TYPE = "submit_scout_move"
MOVEMENT_MODE_CONTEXT_KEY = "movement_mode"
FALL_BACK_MODE_CONTEXT_KEY = "fall_back_mode"
MOVEMENT_BUDGET_CONTEXT_KEY = "movement_budget_inches"
MAXIMUM_DISTANCE_CONTEXT_KEY = "maximum_distance_inches"
SCOUT_DISTANCE_CONTEXT_KEY = "scout_distance_inches"
SUPPORTED_MOVEMENT_DRAFT_DECISION_TYPES = frozenset(
    (
        MOVEMENT_PROPOSAL_DECISION_TYPE,
        SCOUT_MOVE_DECISION_TYPE,
    )
)
SUPPORTED_MOVEMENT_DRAFT_PROPOSAL_KINDS = frozenset(
    (
        "normal_move",
        "advance",
        "fall_back",
        "surge_move",
        "charge_move",
        "pile_in",
        "consolidate",
        "scout_move",
    )
)
SAMPLED_WITNESS_PROPOSAL_KINDS = frozenset(
    (
        "charge_move",
        "pile_in",
        "consolidate",
        "scout_move",
    )
)
NO_WITNESS_NO_MOVE_PROPOSAL_KINDS = frozenset(
    (
        "charge_move",
        "pile_in",
        "consolidate",
    )
)

type MovementDraftMode = Literal["model_assignments"]
type MovementAssignmentState = Literal["active", "assigned", "unassigned"]


class MovementDraftError(ValueError):
    """Raised when a movement proposal cannot be represented as a local draft."""


@dataclass(frozen=True, slots=True)
class MovementProposalContextDiagnostic:
    """Typed diagnostic for missing adapter-visible movement proposal context."""

    violation_code: str
    field: str
    message: str

    @property
    def line(self) -> str:
        """Return a compact HUD diagnostic line."""

        return f"{self.violation_code} [{self.field}]: {self.message}"


@dataclass(frozen=True, slots=True)
class MovementProposalProfile:
    """Contract policy for one movement-shaped proposal family."""

    proposal_kind: str
    decision_type: str
    requires_sampled_witness: bool
    allows_no_witness_no_move: bool
    distance_context_key: str | None

    @property
    def submits_through_generic_parameterized_client(self) -> bool:
        """Return whether this request must bypass the movement-only client method."""

        return self.decision_type != MOVEMENT_PROPOSAL_DECISION_TYPE


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

    def uses_synthetic_payload_midpoint(self, *, requires_sampled_witness: bool) -> bool:
        """Return whether payload serialization inserts midpoint witness evidence."""

        return (
            requires_sampled_witness
            and len(self.points) == 2
            and math.dist(self.points[0], self.points[1]) > 0.0
        )

    @property
    def path_length_inches(self) -> float:
        """Return total path length in inches."""

        return _polyline_length(self.points)

    def payload_points(self, *, requires_sampled_witness: bool) -> tuple[WorldPoint, ...]:
        """Return payload points, including explicit no-op start/end for unchanged models."""

        if len(self.points) == 1:
            return (self.points[0], self.points[0])
        if self.uses_synthetic_payload_midpoint(requires_sampled_witness=requires_sampled_witness):
            # The engine needs non-endpoint path evidence even for straight moved segments.
            start, end = self.points
            midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
            return (start, midpoint, end)
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
    decision_type: str
    proposal_kind: str
    movement_phase_action: str
    movement_mode: str | None
    fall_back_mode: str | None
    game_id: str
    phase: str
    player_id: str | None
    setup_step: str | None
    action_kind: str | None
    source_rule_id: str | None
    ruleset_descriptor_hash: str | None
    scout_distance_inches: float | None
    source_decision_request_id: str
    source_decision_result_id: str
    proposal_context: JsonObject
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
            "decision_type",
            _non_empty_string("decision_type", self.decision_type),
        )
        if self.decision_type not in SUPPORTED_MOVEMENT_DRAFT_DECISION_TYPES:
            raise MovementDraftError("MovementDraft decision_type is unsupported.")
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
        object.__setattr__(self, "game_id", _non_empty_string("game_id", self.game_id))
        object.__setattr__(self, "phase", _non_empty_string("phase", self.phase))
        object.__setattr__(self, "player_id", _optional_string("player_id", self.player_id))
        object.__setattr__(self, "setup_step", _optional_string("setup_step", self.setup_step))
        object.__setattr__(self, "action_kind", _optional_string("action_kind", self.action_kind))
        object.__setattr__(
            self,
            "source_rule_id",
            _optional_string("source_rule_id", self.source_rule_id),
        )
        object.__setattr__(
            self,
            "ruleset_descriptor_hash",
            _optional_string("ruleset_descriptor_hash", self.ruleset_descriptor_hash),
        )
        if self.scout_distance_inches is not None:
            _validate_positive("scout_distance_inches", self.scout_distance_inches)
        context_diagnostic = _movement_context_diagnostic(
            decision_type=self.decision_type,
            proposal_kind=self.proposal_kind,
            movement_phase_action=self.movement_phase_action,
            movement_mode=self.movement_mode,
            fall_back_mode=self.fall_back_mode,
        )
        if context_diagnostic is not None:
            raise MovementDraftError(context_diagnostic.message)
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
        object.__setattr__(
            self,
            "proposal_context",
            _json_object("proposal_context", self.proposal_context),
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
        """Create a movement draft for the current movement proposal."""

        if pending_decision is None:
            return None
        proposal = _draftable_movement_proposal(pending_decision)
        if proposal is None:
            return None
        unit = _unit_by_id(view, proposal.unit_instance_id)
        if unit is None:
            return None
        if selection.selected_unit_id != unit.unit_id:
            return None
        if proposal.movement_phase_action is None:
            raise MovementDraftError("Movement proposal requires movement_phase_action.")
        movement_mode = _proposal_movement_mode(proposal)
        fall_back_mode = _context_string(proposal.context, FALL_BACK_MODE_CONTEXT_KEY)
        if movement_proposal_context_diagnostic(proposal) is not None:
            return None
        entity_selection = _seed_entity_selection(
            view=view,
            selection=selection,
            pending_decision=pending_decision,
            unit=unit,
        )
        draft = cls(
            selected_unit_id=unit.unit_id,
            proposal_request_id=proposal.request_id,
            decision_type=proposal.decision_type,
            proposal_kind=proposal.proposal_kind,
            movement_phase_action=proposal.movement_phase_action,
            movement_mode=movement_mode,
            fall_back_mode=fall_back_mode,
            game_id=proposal.game_id,
            phase=proposal.phase,
            player_id=proposal.player_id,
            setup_step=proposal.setup_step,
            action_kind=proposal.action_kind,
            source_rule_id=proposal.source_rule_id,
            ruleset_descriptor_hash=proposal.ruleset_descriptor_hash,
            scout_distance_inches=proposal.scout_distance_inches,
            source_decision_request_id=proposal.source_decision_request_id,
            source_decision_result_id=proposal.source_decision_result_id,
            proposal_context=proposal.context,
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
            movement_budget_inches=_proposal_movement_budget_inches(proposal),
            local_hint_lines=(),
        )
        return draft.with_recomputed_hints(view=view)

    @property
    def is_ready(self) -> bool:
        """Return whether the draft has a JSON-safe payload preview."""

        return self.ready_payload is not None

    @property
    def proposal_profile(self) -> MovementProposalProfile:
        """Return the movement-family payload policy for this draft."""

        return movement_proposal_profile(
            decision_type=self.decision_type,
            proposal_kind=self.proposal_kind,
        )

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
    def synthetic_witness_model_ids(self) -> tuple[str, ...]:
        """Return model IDs whose payload paths receive generated midpoint evidence."""

        requires_sampled_witness = self.proposal_profile.requires_sampled_witness
        return tuple(
            path.model_id
            for path in self.model_paths
            if path.uses_synthetic_payload_midpoint(
                requires_sampled_witness=requires_sampled_witness
            )
        )

    @property
    def synthetic_witness_point_count(self) -> int:
        """Return the number of generated witness points in the payload preview."""

        return len(self.synthetic_witness_model_ids)

    @property
    def payload_witness_summary_lines(self) -> tuple[str, ...]:
        """Return ready-preview path witness point summaries for debug HUD display."""

        if self.ready_payload is None:
            return ()
        lines: list[str] = []
        requires_sampled_witness = self.proposal_profile.requires_sampled_witness
        for path in self.model_paths:
            suffix = (
                ", synthetic midpoint"
                if path.uses_synthetic_payload_midpoint(
                    requires_sampled_witness=requires_sampled_witness
                )
                else ", no-op"
                if not path.has_movement
                else ""
            )
            lines.append(
                f"{path.model_id}: "
                f"{len(path.payload_points(requires_sampled_witness=requires_sampled_witness))} "
                f"witness point(s){suffix}"
            )
        return tuple(lines)

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
            and proposal.decision_type == self.decision_type
            and proposal.unit_instance_id == self.selected_unit_id
            and proposal.request_id == self.proposal_request_id
            and proposal.proposal_kind == self.proposal_kind
            and proposal.movement_phase_action == self.movement_phase_action
            and _proposal_movement_mode(proposal) == self.movement_mode
            and _context_string(proposal.context, FALL_BACK_MODE_CONTEXT_KEY) == self.fall_back_mode
        )

    def can_retry_for(self, *, pending_decision: UiDecision | None) -> bool:
        """Return whether a fresh movement request can safely reuse this draft's paths."""

        proposal = None if pending_decision is None else pending_decision.movement_proposal
        return (
            proposal is not None
            and proposal.decision_type == self.decision_type
            and proposal.unit_instance_id == self.selected_unit_id
            and proposal.proposal_kind == self.proposal_kind
            and proposal.source_decision_request_id == self.source_decision_request_id
            and proposal.source_decision_result_id == self.source_decision_result_id
            and proposal.movement_phase_action == self.movement_phase_action
            and _proposal_movement_mode(proposal) == self.movement_mode
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

        if self.ready_payload is not None:
            return self
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
            if draft.proposal_profile.allows_no_witness_no_move:
                return replace(draft, ready_payload=draft.to_payload()).with_recomputed_hints(
                    view=view
                )
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

    def clear_ready_payload(self, *, view: BattlefieldView) -> MovementDraft:
        """Return this draft to preview mode while preserving assigned paths."""

        return replace(
            self,
            cursor_preview_point=None,
            ready_payload=None,
        ).with_recomputed_hints(view=view)

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

        if not self.has_assignments and self.proposal_profile.allows_no_witness_no_move:
            return self._no_witness_no_move_payload()
        requires_sampled_witness = self.proposal_profile.requires_sampled_witness
        body: JsonObject = {
            "proposal_request_id": self.proposal_request_id,
            "proposal_kind": self.proposal_kind,
            "unit_instance_id": self.selected_unit_id,
            "movement_phase_action": self.movement_phase_action,
            "movement_mode": _non_empty_string("movement_mode", self.movement_mode),
            "witness": {
                "model_paths": [
                    {
                        "model_id": path.model_id,
                        "poses": [
                            _pose_payload(point)
                            for point in path.payload_points(
                                requires_sampled_witness=requires_sampled_witness
                            )
                        ],
                    }
                    for path in self.model_paths
                ],
            },
            "model_movements": [
                {
                    "model_instance_id": path.model_id,
                    "path": [
                        _pose_payload(point)
                        for point in path.payload_points(
                            requires_sampled_witness=requires_sampled_witness
                        )
                    ],
                    "final_pose": _pose_payload(
                        path.payload_points(requires_sampled_witness=requires_sampled_witness)[-1]
                    ),
                }
                for path in self.model_paths
            ],
        }
        self._add_family_payload_fields(body)
        if _requires_fall_back_mode(
            proposal_kind=self.proposal_kind,
            movement_phase_action=self.movement_phase_action,
        ):
            body["fall_back_mode"] = _non_empty_string("fall_back_mode", self.fall_back_mode)
        elif self.fall_back_mode is not None:
            body["fall_back_mode"] = self.fall_back_mode
        return _json_object("movement proposal payload", body)

    def _no_witness_no_move_payload(self) -> JsonObject:
        body: JsonObject = {
            "proposal_request_id": self.proposal_request_id,
            "proposal_kind": self.proposal_kind,
            "unit_instance_id": self.selected_unit_id,
            "movement_phase_action": self.movement_phase_action,
            "movement_mode": _non_empty_string("movement_mode", self.movement_mode),
        }
        self._add_family_payload_fields(body, no_move=True)
        return _json_object("movement no-move payload", body)

    def _add_family_payload_fields(self, body: JsonObject, *, no_move: bool = False) -> None:
        if self.proposal_kind == "charge_move":
            body["charge_target_unit_instance_ids"] = (
                []
                if no_move
                else _first_non_empty_context_string_list(
                    self.proposal_context,
                    (
                        "charge_target_unit_instance_ids",
                        "reachable_target_unit_instance_ids",
                    ),
                )
            )
            if "stratagem_handler_id" in self.proposal_context:
                body["stratagem_handler_id"] = self.proposal_context["stratagem_handler_id"]
        elif self.proposal_kind == "pile_in":
            body["pile_in_target_unit_instance_ids"] = (
                []
                if no_move
                else _context_string_list(
                    self.proposal_context,
                    "legal_pile_in_target_unit_instance_ids",
                )
            )
        elif self.proposal_kind == "consolidate":
            body["consolidate_target_unit_instance_ids"] = (
                []
                if no_move
                else _context_string_list(
                    self.proposal_context,
                    "legal_consolidate_target_unit_instance_ids",
                )
            )
            if not no_move:
                consolidation_mode = _first_context_string(
                    self.proposal_context,
                    "legal_consolidation_modes",
                )
                if consolidation_mode is not None:
                    body["consolidation_mode"] = consolidation_mode
        elif self.proposal_kind == "scout_move":
            body.update(
                {
                    "game_id": self.game_id,
                    "ruleset_descriptor_hash": _non_empty_string(
                        "ruleset_descriptor_hash",
                        self.ruleset_descriptor_hash,
                    ),
                    "setup_step": _non_empty_string("setup_step", self.setup_step),
                    "player_id": _non_empty_string("player_id", self.player_id),
                    "action_kind": _non_empty_string("action_kind", self.action_kind),
                    "source_rule_id": _non_empty_string("source_rule_id", self.source_rule_id),
                    "scout_distance_inches": _validated_finite_float(
                        "scout_distance_inches",
                        self.scout_distance_inches,
                    ),
                    "context": self.proposal_context,
                }
            )

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
    if proposal.decision_type not in SUPPORTED_MOVEMENT_DRAFT_DECISION_TYPES:
        return None
    if proposal.proposal_kind not in SUPPORTED_MOVEMENT_DRAFT_PROPOSAL_KINDS:
        return None
    if movement_proposal_context_diagnostic(proposal) is not None:
        return None
    if proposal.unit_instance_id != selection.selected_unit_id:
        return None
    return proposal


def movement_proposal_context_diagnostic(
    proposal: UiMovementProposalRequest,
) -> MovementProposalContextDiagnostic | None:
    """Return a typed diagnostic when movement proposal mode context is incomplete."""

    return _movement_context_diagnostic(
        decision_type=proposal.decision_type,
        proposal_kind=proposal.proposal_kind,
        movement_phase_action=proposal.movement_phase_action,
        movement_mode=_proposal_movement_mode(proposal),
        fall_back_mode=_context_string(proposal.context, FALL_BACK_MODE_CONTEXT_KEY),
    )


def movement_proposal_context_diagnostic_line(
    proposal: UiMovementProposalRequest,
) -> str | None:
    """Return a compact diagnostic line for incomplete movement proposal context."""

    diagnostic = movement_proposal_context_diagnostic(proposal)
    return None if diagnostic is None else diagnostic.line


def _draftable_movement_proposal(
    pending_decision: UiDecision,
) -> UiMovementProposalRequest | None:
    proposal = pending_decision.movement_proposal
    if proposal is None:
        return None
    if proposal.decision_type not in SUPPORTED_MOVEMENT_DRAFT_DECISION_TYPES:
        return None
    if proposal.proposal_kind not in SUPPORTED_MOVEMENT_DRAFT_PROPOSAL_KINDS:
        return None
    if movement_proposal_context_diagnostic(proposal) is not None:
        return None
    return proposal


def _movement_context_diagnostic(
    *,
    decision_type: str,
    proposal_kind: str,
    movement_phase_action: str | None,
    movement_mode: str | None,
    fall_back_mode: str | None,
) -> MovementProposalContextDiagnostic | None:
    if decision_type not in SUPPORTED_MOVEMENT_DRAFT_DECISION_TYPES:
        return MovementProposalContextDiagnostic(
            violation_code="unsupported_movement_decision_type",
            field="decision_type",
            message=(
                "Movement proposal decision type is not supported for local drafting: "
                f"{decision_type}."
            ),
        )
    if proposal_kind in SUPPORTED_MOVEMENT_DRAFT_PROPOSAL_KINDS and movement_mode is None:
        return MovementProposalContextDiagnostic(
            violation_code="movement_mode_missing_from_proposal_context",
            field=f"context.{MOVEMENT_MODE_CONTEXT_KEY}",
            message=(
                "Movement proposal context is missing required movement_mode for "
                f"{proposal_kind}; local draft submission is blocked."
            ),
        )
    if (
        _requires_fall_back_mode(
            proposal_kind=proposal_kind,
            movement_phase_action=movement_phase_action,
        )
        and fall_back_mode is None
    ):
        return MovementProposalContextDiagnostic(
            violation_code="fall_back_mode_missing_from_proposal_context",
            field=f"context.{FALL_BACK_MODE_CONTEXT_KEY}",
            message=(
                "Fall Back movement proposal context is missing required fall_back_mode; "
                "local draft submission is blocked."
            ),
        )
    return None


def _requires_fall_back_mode(
    *,
    proposal_kind: str,
    movement_phase_action: str | None,
) -> bool:
    return proposal_kind == "fall_back" or movement_phase_action == "fall_back"


def movement_proposal_profile(
    *,
    decision_type: str,
    proposal_kind: str,
) -> MovementProposalProfile:
    """Return payload policy for a supported movement-shaped proposal."""

    if proposal_kind not in SUPPORTED_MOVEMENT_DRAFT_PROPOSAL_KINDS:
        raise MovementDraftError(f"Unsupported movement proposal kind: {proposal_kind}.")
    if decision_type not in SUPPORTED_MOVEMENT_DRAFT_DECISION_TYPES:
        raise MovementDraftError(f"Unsupported movement decision type: {decision_type}.")
    if proposal_kind == "scout_move" and decision_type != SCOUT_MOVE_DECISION_TYPE:
        raise MovementDraftError("Scout Move drafts require submit_scout_move.")
    if proposal_kind != "scout_move" and decision_type != MOVEMENT_PROPOSAL_DECISION_TYPE:
        raise MovementDraftError(f"{proposal_kind} drafts require submit_movement_proposal.")
    distance_key = {
        "normal_move": MOVEMENT_BUDGET_CONTEXT_KEY,
        "advance": MOVEMENT_BUDGET_CONTEXT_KEY,
        "fall_back": MOVEMENT_BUDGET_CONTEXT_KEY,
        "surge_move": MAXIMUM_DISTANCE_CONTEXT_KEY,
        "charge_move": MAXIMUM_DISTANCE_CONTEXT_KEY,
        "pile_in": MAXIMUM_DISTANCE_CONTEXT_KEY,
        "consolidate": MAXIMUM_DISTANCE_CONTEXT_KEY,
        "scout_move": SCOUT_DISTANCE_CONTEXT_KEY,
    }.get(proposal_kind)
    return MovementProposalProfile(
        proposal_kind=proposal_kind,
        decision_type=decision_type,
        requires_sampled_witness=proposal_kind in SAMPLED_WITNESS_PROPOSAL_KINDS,
        allows_no_witness_no_move=proposal_kind in NO_WITNESS_NO_MOVE_PROPOSAL_KINDS,
        distance_context_key=distance_key,
    )


def _proposal_movement_budget_inches(proposal: UiMovementProposalRequest) -> float | None:
    profile = movement_proposal_profile(
        decision_type=proposal.decision_type,
        proposal_kind=proposal.proposal_kind,
    )
    if proposal.proposal_kind == "scout_move":
        return proposal.scout_distance_inches
    if profile.distance_context_key is None:
        return None
    return _context_positive_float(proposal.context, profile.distance_context_key)


def _proposal_movement_mode(proposal: UiMovementProposalRequest) -> str | None:
    movement_mode = _context_string(proposal.context, MOVEMENT_MODE_CONTEXT_KEY)
    if movement_mode is not None:
        return movement_mode
    if proposal.proposal_kind == "scout_move":
        return proposal.action_kind
    return None


def _unit_by_id(view: BattlefieldView, unit_id: str) -> UnitView | None:
    for unit in view.units:
        if unit.unit_id == unit_id:
            return unit
    return None


def unsupported_parameterized_tool_label(pending_decision: UiDecision | None) -> str | None:
    """Return a display label when a parameterized request is not movement-draftable."""

    if pending_decision is None or not pending_decision.is_parameterized:
        return None
    if pending_decision.placement_proposal is not None:
        return None
    proposal = pending_decision.parameterized_proposal
    if proposal is None:
        return pending_decision.decision_type
    if pending_decision.movement_proposal is not None:
        movement = pending_decision.movement_proposal
        if (
            movement.decision_type in SUPPORTED_MOVEMENT_DRAFT_DECISION_TYPES
            and movement.proposal_kind in SUPPORTED_MOVEMENT_DRAFT_PROPOSAL_KINDS
        ):
            return None
        return movement.proposal_kind
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
    if draft.synthetic_witness_model_ids:
        hints.append(
            "Preview note: "
            "UI-generated synthetic midpoint witness evidence will be inserted for "
            f"{draft.synthetic_witness_point_count} straight moved model path(s): "
            f"{_compact_model_ids(draft.synthetic_witness_model_ids)}."
        )
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


def _compact_model_ids(model_ids: tuple[str, ...], *, limit: int = 3) -> str:
    if len(model_ids) <= limit:
        return ", ".join(model_ids)
    shown = ", ".join(model_ids[:limit])
    return f"{shown}, +{len(model_ids) - limit} more"


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


def _context_string_tuple(context: JsonObject, key: str) -> tuple[str, ...]:
    value = context.get(key)
    if value is None:
        return ()
    if type(value) is not list:
        raise MovementDraftError(f"context.{key} must be a list.")
    return tuple(_non_empty_string(f"context.{key}", item) for item in value)


def _context_string_list(context: JsonObject, key: str) -> list[JsonValue]:
    values: list[JsonValue] = []
    values.extend(_context_string_tuple(context, key))
    return values


def _first_non_empty_context_string_list(
    context: JsonObject,
    keys: tuple[str, ...],
) -> list[JsonValue]:
    for key in keys:
        values = _context_string_list(context, key)
        if values:
            return values
    return []


def _first_context_string(context: JsonObject, key: str) -> str | None:
    values = _context_string_tuple(context, key)
    if not values:
        return None
    return values[0]


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
