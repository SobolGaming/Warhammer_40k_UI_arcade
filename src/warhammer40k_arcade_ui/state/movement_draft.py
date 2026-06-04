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
from warhammer40k_arcade_ui.state.selection import SelectionState, selected_unit, unit_center

MOVEMENT_PROPOSAL_DECISION_TYPE = "submit_movement_proposal"
MOVEMENT_MODE_CONTEXT_KEY = "movement_mode"
FALL_BACK_MODE_CONTEXT_KEY = "fall_back_mode"
MOVEMENT_BUDGET_CONTEXT_KEY = "movement_budget_inches"

type MovementDraftMode = Literal["unit_simple", "model_edit_deferred"]


class MovementDraftError(ValueError):
    """Raised when a movement proposal cannot be represented as a local draft."""


@dataclass(frozen=True, slots=True)
class MovementModelPath:
    """Path points for one model in a local movement draft."""

    model_id: str
    base_radius: float
    points: tuple[WorldPoint, ...]

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

    @property
    def final_point(self) -> WorldPoint:
        """Return the current final point for this model path."""

        return self.points[-1]

    def with_translated_waypoint(self, *, delta_x: float, delta_y: float) -> MovementModelPath:
        """Append a waypoint translated from the current final point."""

        _validate_finite("delta_x", delta_x)
        _validate_finite("delta_y", delta_y)
        final_x, final_y = self.final_point
        return replace(self, points=(*self.points, (final_x + delta_x, final_y + delta_y)))

    def with_removed_last_waypoint(self) -> MovementModelPath:
        """Remove the most recent waypoint while preserving the starting point."""

        if len(self.points) <= 1:
            return self
        return replace(self, points=self.points[:-1])


@dataclass(frozen=True, slots=True)
class MovementDraft:
    """Local movement draft for a pending movement proposal request."""

    selected_unit_id: str
    proposal_request_id: str
    proposal_kind: str
    movement_phase_action: str
    movement_mode: str | None
    fall_back_mode: str | None
    source_decision_request_id: str
    source_decision_result_id: str
    mode: MovementDraftMode
    anchor_points: tuple[WorldPoint, ...]
    model_paths: tuple[MovementModelPath, ...]
    cursor_preview_point: WorldPoint | None
    movement_budget_inches: float | None
    local_hint_lines: tuple[str, ...]
    ready_payload: JsonObject | None = None

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
        if self.mode not in ("unit_simple", "model_edit_deferred"):
            raise MovementDraftError("Unsupported movement draft mode.")
        if type(self.anchor_points) is not tuple or not self.anchor_points:
            raise MovementDraftError("MovementDraft anchor_points must be a non-empty tuple.")
        object.__setattr__(
            self,
            "anchor_points",
            tuple(_validate_world_point("anchor point", point) for point in self.anchor_points),
        )
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
        if proposal is None:
            return None
        unit = selected_unit(view, selection)
        if unit is None:
            return None
        if proposal.movement_phase_action is None:
            raise MovementDraftError("Movement proposal requires movement_phase_action.")
        draft = cls(
            selected_unit_id=unit.unit_id,
            proposal_request_id=proposal.request_id,
            proposal_kind=proposal.proposal_kind,
            movement_phase_action=proposal.movement_phase_action,
            movement_mode=_context_string(proposal.context, MOVEMENT_MODE_CONTEXT_KEY),
            fall_back_mode=_context_string(proposal.context, FALL_BACK_MODE_CONTEXT_KEY),
            source_decision_request_id=proposal.source_decision_request_id,
            source_decision_result_id=proposal.source_decision_result_id,
            mode=_draft_mode_for_unit(unit),
            anchor_points=(unit_center(unit),),
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
    def current_segment_length(self) -> float:
        """Return the current preview segment length in inches."""

        if self.cursor_preview_point is not None:
            return math.dist(self.anchor_points[-1], self.cursor_preview_point)
        if len(self.anchor_points) < 2:
            return 0.0
        return math.dist(self.anchor_points[-2], self.anchor_points[-1])

    @property
    def total_path_length(self) -> float:
        """Return total anchor-path length including the live preview point."""

        total = _polyline_length(self.anchor_points)
        if self.cursor_preview_point is not None:
            total += math.dist(self.anchor_points[-1], self.cursor_preview_point)
        return total

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

        proposal = None if pending_decision is None else pending_decision.movement_proposal
        return (
            proposal is not None
            and proposal.decision_type == MOVEMENT_PROPOSAL_DECISION_TYPE
            and selection.selected_unit_id == self.selected_unit_id
            and proposal.unit_instance_id == self.selected_unit_id
            and proposal.request_id == self.proposal_request_id
            and proposal.proposal_kind == self.proposal_kind
            and proposal.movement_phase_action == self.movement_phase_action
            and _context_string(proposal.context, MOVEMENT_MODE_CONTEXT_KEY) == self.movement_mode
            and _context_string(proposal.context, FALL_BACK_MODE_CONTEXT_KEY) == self.fall_back_mode
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
        """Commit a waypoint in unit-level simple path mode."""

        point = _validate_world_point("world_point", world_point)
        last_x, last_y = self.anchor_points[-1]
        point_x, point_y = point
        delta_x = point_x - last_x
        delta_y = point_y - last_y
        return replace(
            self,
            anchor_points=(*self.anchor_points, point),
            model_paths=tuple(
                path.with_translated_waypoint(delta_x=delta_x, delta_y=delta_y)
                for path in self.model_paths
            ),
            cursor_preview_point=None,
            ready_payload=None,
        ).with_recomputed_hints(view=view)

    def remove_last_waypoint(self, *, view: BattlefieldView) -> MovementDraft:
        """Remove the most recent committed waypoint without submitting anything."""

        if len(self.anchor_points) <= 1:
            return replace(
                self, cursor_preview_point=None, ready_payload=None
            ).with_recomputed_hints(view=view)
        return replace(
            self,
            anchor_points=self.anchor_points[:-1],
            model_paths=tuple(path.with_removed_last_waypoint() for path in self.model_paths),
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
        if len(draft.anchor_points) < 2:
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
        """Recompute local advisory hints for the current path geometry."""

        return replace(self, local_hint_lines=_local_hint_lines(view=view, draft=self))

    def preview_model_paths(self) -> tuple[MovementModelPath, ...]:
        """Return model paths including the current cursor preview, if any."""

        if self.cursor_preview_point is None:
            return self.model_paths
        last_x, last_y = self.anchor_points[-1]
        point_x, point_y = self.cursor_preview_point
        delta_x = point_x - last_x
        delta_y = point_y - last_y
        return tuple(
            path.with_translated_waypoint(delta_x=delta_x, delta_y=delta_y)
            for path in self.model_paths
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
                        "poses": [_pose_payload(point) for point in path.points],
                    }
                    for path in self.model_paths
                ],
            },
            "model_movements": [
                {
                    "model_instance_id": path.model_id,
                    "path": [_pose_payload(point) for point in path.points],
                    "final_pose": _pose_payload(path.final_point),
                }
                for path in self.model_paths
            ],
        }
        if self.movement_mode is not None:
            body["movement_mode"] = self.movement_mode
        if self.fall_back_mode is not None:
            body["fall_back_mode"] = self.fall_back_mode
        return _json_object("movement proposal payload", body)


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


def _draft_mode_for_unit(unit: UnitView) -> MovementDraftMode:
    if len(unit.models) > 12:
        return "model_edit_deferred"
    return "unit_simple"


def _local_hint_lines(*, view: BattlefieldView, draft: MovementDraft) -> tuple[str, ...]:
    hints: list[str] = ["Preview/advisory only; engine validates movement."]
    if draft.mode == "model_edit_deferred":
        hints.append("Preview warning: model-level editing is deferred for this large unit.")
    if draft.movement_budget_inches is None:
        hints.append("Preview warning: movement budget is unavailable in the proposal context.")
    elif draft.remaining_budget_inches is not None and draft.remaining_budget_inches < 0.0:
        hints.append("Preview warning: estimated path exceeds the displayed movement budget.")
    if _has_out_of_bounds_endpoint(view=view, draft=draft):
        hints.append("Preview warning: final ghost base is outside table bounds.")
    if _has_self_overlap(draft):
        hints.append("Preview warning: final ghost bases overlap each other.")
    return tuple(hints)


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


def _non_empty_string(field_name: str, value: object) -> str:
    if type(value) is not str:
        raise MovementDraftError(f"{field_name} must be a string.")
    stripped = value.strip()
    if not stripped:
        raise MovementDraftError(f"{field_name} must not be empty.")
    return stripped


def _optional_string(field_name: str, value: object) -> str | None:
    if value is None:
        return None
    return _non_empty_string(field_name, value)


def _validate_positive(field_name: str, value: float) -> None:
    if type(value) is not float and type(value) is not int:
        raise MovementDraftError(f"{field_name} must be a number.")
    if value <= 0.0 or not math.isfinite(value):
        raise MovementDraftError(f"{field_name} must be finite and positive.")


def _validate_finite(field_name: str, value: object) -> None:
    _validated_finite_float(field_name, value)


def _validated_finite_float(field_name: str, value: object) -> float:
    if type(value) is not float and type(value) is not int:
        raise MovementDraftError(f"{field_name} must be a number.")
    float_value = float(value)
    if not math.isfinite(float_value):
        raise MovementDraftError(f"{field_name} must be finite.")
    return float_value
