"""Local placement proposal draft state and JSON-safe payload building."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, cast

from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    JsonValue,
    UiDecision,
    UiPlacementProposalRequest,
    validate_json_value,
)
from warhammer40k_arcade_ui.render.camera import WorldPoint
from warhammer40k_arcade_ui.render.view_models import BattlefieldView, ModelBaseView, UnitView
from warhammer40k_arcade_ui.state.selection import SelectionState

_MM_PER_INCH = 25.4
_DEFAULT_PRESENTATION_BASE_RADIUS_INCHES = 0.75

PLACEMENT_PROPOSAL_DECISION_TYPES = frozenset(
    (
        "submit_placement_proposal",
        "submit_deployment_placement",
        "submit_redeploy_placement",
        "submit_scout_reserve_setup",
    )
)
SUPPORTED_PLACEMENT_PROPOSAL_KINDS = frozenset(
    (
        "reinforcement_placement",
        "deep_strike_placement",
        "strategic_reserves_placement",
        "disembark_placement",
        "deployment_placement",
        "redeploy_placement",
        "scout_reserve_setup",
    )
)

type PlacementModelState = Literal["current", "placed", "unplaced"]


class PlacementDraftError(ValueError):
    """Raised when a placement proposal cannot be represented as a local draft."""


@dataclass(frozen=True, slots=True)
class PlacementModelPose:
    """Local final pose for one required placement model."""

    model_id: str
    base_radius: float
    position: WorldPoint | None
    facing_degrees: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", _non_empty_string("model_id", self.model_id))
        _validate_positive("base_radius", self.base_radius)
        object.__setattr__(
            self,
            "position",
            None if self.position is None else _validate_world_point("position", self.position),
        )
        _validate_finite("facing_degrees", self.facing_degrees)

    @property
    def placed(self) -> bool:
        """Return whether this model has a drafted final pose."""

        return self.position is not None

    def with_position(self, position: WorldPoint) -> PlacementModelPose:
        """Return this model placed at a new world position."""

        return replace(self, position=_validate_world_point("position", position))


@dataclass(frozen=True, slots=True)
class PlacementAssignmentView:
    """Summary-friendly view of one placement model."""

    model_id: str
    base_radius: float
    position: WorldPoint | None
    state: PlacementModelState

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", _non_empty_string("model_id", self.model_id))
        _validate_positive("base_radius", self.base_radius)
        object.__setattr__(
            self,
            "position",
            None if self.position is None else _validate_world_point("position", self.position),
        )
        if self.state not in ("current", "placed", "unplaced"):
            raise PlacementDraftError("PlacementAssignmentView state is unsupported.")


@dataclass(frozen=True, slots=True)
class PlacementDraft:
    """Local per-model placement workspace for a pending placement proposal request."""

    selected_unit_id: str
    proposal_request_id: str
    decision_type: str
    proposal_kind: str
    placement_kind: str
    game_id: str
    player_id: str
    source_decision_request_id: str
    source_decision_result_id: str
    model_poses: tuple[PlacementModelPose, ...]
    selected_model_id: str
    cursor_preview_point: WorldPoint | None
    local_hint_lines: tuple[str, ...]
    ready_payload: JsonObject | None = None
    ruleset_descriptor_hash: str | None = None
    setup_step: str | None = None
    action_kind: str | None = None
    source_rule_id: str | None = None
    context: JsonObject | None = None

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
        if self.decision_type not in PLACEMENT_PROPOSAL_DECISION_TYPES:
            raise PlacementDraftError("Unsupported placement proposal decision_type.")
        object.__setattr__(self, "decision_type", self.decision_type)
        if self.proposal_kind not in SUPPORTED_PLACEMENT_PROPOSAL_KINDS:
            raise PlacementDraftError("Unsupported placement proposal kind.")
        object.__setattr__(self, "proposal_kind", self.proposal_kind)
        object.__setattr__(
            self,
            "placement_kind",
            _non_empty_string("placement_kind", self.placement_kind),
        )
        object.__setattr__(self, "game_id", _non_empty_string("game_id", self.game_id))
        object.__setattr__(self, "player_id", _non_empty_string("player_id", self.player_id))
        object.__setattr__(
            self,
            "source_decision_request_id",
            _non_empty_string("source_decision_request_id", self.source_decision_request_id),
        )
        object.__setattr__(
            self,
            "source_decision_result_id",
            _non_empty_string("source_decision_result_id", self.source_decision_result_id),
        )
        if type(self.model_poses) is not tuple or not self.model_poses:
            raise PlacementDraftError("PlacementDraft model_poses must be a non-empty tuple.")
        if any(type(pose) is not PlacementModelPose for pose in self.model_poses):
            raise PlacementDraftError("PlacementDraft model_poses must contain PlacementModelPose.")
        _validate_unique_model_poses(self.model_poses)
        model_ids = {pose.model_id for pose in self.model_poses}
        if self.selected_model_id not in model_ids:
            raise PlacementDraftError("selected_model_id must name a placement model.")
        object.__setattr__(
            self,
            "cursor_preview_point",
            None
            if self.cursor_preview_point is None
            else _validate_world_point("cursor_preview_point", self.cursor_preview_point),
        )
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
        object.__setattr__(
            self,
            "ruleset_descriptor_hash",
            _optional_string("ruleset_descriptor_hash", self.ruleset_descriptor_hash),
        )
        object.__setattr__(self, "setup_step", _optional_string("setup_step", self.setup_step))
        object.__setattr__(self, "action_kind", _optional_string("action_kind", self.action_kind))
        object.__setattr__(
            self,
            "source_rule_id",
            _optional_string("source_rule_id", self.source_rule_id),
        )
        object.__setattr__(
            self,
            "context",
            {} if self.context is None else _json_object("context", self.context),
        )

    @classmethod
    def start_for_pending(
        cls,
        *,
        view: BattlefieldView,
        selection: SelectionState,
        pending_decision: UiDecision | None,
        model_display_by_id: JsonObject | None = None,
    ) -> PlacementDraft | None:
        """Create a placement draft for the current placement proposal."""

        del selection
        proposal = _draftable_placement_proposal(pending_decision)
        if proposal is None:
            return None
        unit = _unit_by_id(view, proposal.unit_instance_id)
        model_ids = proposal.required_model_ids or (
            tuple(model.model_id for model in unit.models) if unit is not None else ()
        )
        if not model_ids:
            return None
        models_by_id = _models_by_id(unit)
        model_poses = tuple(
            PlacementModelPose(
                model_id=model_id,
                base_radius=_model_base_radius(
                    models_by_id.get(model_id),
                    model_id=model_id,
                    model_display_by_id=model_display_by_id,
                ),
                position=None,
            )
            for model_id in model_ids
        )
        return cls(
            selected_unit_id=proposal.unit_instance_id,
            proposal_request_id=proposal.request_id,
            decision_type=proposal.decision_type,
            proposal_kind=proposal.proposal_kind,
            placement_kind=proposal.placement_kind,
            game_id=proposal.game_id,
            player_id=proposal.player_id,
            source_decision_request_id=proposal.source_decision_request_id,
            source_decision_result_id=proposal.source_decision_result_id,
            model_poses=model_poses,
            selected_model_id=model_poses[0].model_id,
            cursor_preview_point=None,
            local_hint_lines=("Placement preview only until submitted.",),
            ruleset_descriptor_hash=proposal.ruleset_descriptor_hash,
            setup_step=proposal.setup_step,
            action_kind=proposal.action_kind,
            source_rule_id=proposal.source_rule_id,
            context=proposal.context,
        )

    @property
    def is_ready(self) -> bool:
        """Return whether the draft has a JSON-safe payload preview."""

        return self.ready_payload is not None

    @property
    def total_model_count(self) -> int:
        """Return required placement model count."""

        return len(self.model_poses)

    @property
    def placed_model_count(self) -> int:
        """Return models with drafted final poses."""

        return sum(1 for pose in self.model_poses if pose.placed)

    @property
    def unplaced_model_count(self) -> int:
        """Return models still missing a drafted final pose."""

        return self.total_model_count - self.placed_model_count

    @property
    def selected_model_pose(self) -> PlacementModelPose:
        """Return the current placement model pose."""

        for pose in self.model_poses:
            if pose.model_id == self.selected_model_id:
                return pose
        raise PlacementDraftError("Selected placement model disappeared.")

    @property
    def payload_preview(self) -> JsonObject | None:
        """Return the ready payload preview, if Enter has marked the draft ready."""

        return self.ready_payload

    @property
    def status_line(self) -> str:
        """Return compact HUD status text."""

        state = "ready" if self.is_ready else "preview"
        return (
            f"Placement draft {state}: {self.placed_model_count}/"
            f"{self.total_model_count} model(s) placed"
        )

    def is_for(self, *, pending_decision: UiDecision | None) -> bool:
        """Return whether this draft still matches the pending placement request."""

        return self.matches_proposal_context(pending_decision=pending_decision)

    def matches_proposal_context(self, *, pending_decision: UiDecision | None) -> bool:
        """Return whether this draft matches the current placement proposal context."""

        proposal = None if pending_decision is None else pending_decision.placement_proposal
        return (
            proposal is not None
            and proposal.request_id == self.proposal_request_id
            and proposal.decision_type == self.decision_type
            and proposal.unit_instance_id == self.selected_unit_id
            and proposal.proposal_kind == self.proposal_kind
            and proposal.placement_kind == self.placement_kind
            and proposal.source_decision_request_id == self.source_decision_request_id
            and proposal.source_decision_result_id == self.source_decision_result_id
        )

    def with_cursor_preview(self, world_point: WorldPoint) -> PlacementDraft:
        """Update the current local placement cursor preview."""

        if self.ready_payload is not None:
            return self
        return replace(
            self,
            cursor_preview_point=_validate_world_point("world_point", world_point),
            ready_payload=None,
        )

    def place_current_model(self, world_point: WorldPoint) -> PlacementDraft:
        """Place the current model at the supplied point and advance to the next unplaced model."""

        point = _validate_world_point("world_point", world_point)
        model_poses = tuple(
            pose.with_position(point) if pose.model_id == self.selected_model_id else pose
            for pose in self.model_poses
        )
        next_model_id = _next_unplaced_model_id(model_poses, self.selected_model_id)
        return replace(
            self,
            model_poses=model_poses,
            selected_model_id=next_model_id,
            cursor_preview_point=None,
            ready_payload=None,
        ).with_recomputed_hints()

    def mark_ready(self) -> PlacementDraft:
        """Mark the current draft ready by building a payload preview without submitting."""

        if self.unplaced_model_count > 0:
            return replace(
                self,
                ready_payload=None,
                local_hint_lines=(
                    "Placement warning: place every required model before submitting.",
                ),
            )
        return replace(self, ready_payload=self.to_payload()).with_recomputed_hints()

    def clear_ready(self) -> PlacementDraft:
        """Clear a ready payload after local focus changes."""

        return replace(self, ready_payload=None)

    def select_next_model(self) -> PlacementDraft:
        """Advance local focus to the next required placement model."""

        model_ids = tuple(pose.model_id for pose in self.model_poses)
        current_index = model_ids.index(self.selected_model_id)
        return replace(
            self,
            selected_model_id=model_ids[(current_index + 1) % len(model_ids)],
            cursor_preview_point=None,
            ready_payload=None,
        ).with_recomputed_hints()

    def with_recomputed_hints(self) -> PlacementDraft:
        """Recompute local advisory hints."""

        hints = ["Placement preview only until submitted."]
        if self.unplaced_model_count:
            hints.append(f"{self.unplaced_model_count} model(s) still need placement.")
        if self.is_ready:
            hints.append("Press confirm again to submit this placement proposal.")
        return replace(self, local_hint_lines=tuple(hints))

    def assignment_views(self) -> tuple[PlacementAssignmentView, ...]:
        """Return summary-friendly assignment rows for rendering and HUD status."""

        return tuple(
            PlacementAssignmentView(
                model_id=pose.model_id,
                base_radius=pose.base_radius,
                position=self.cursor_preview_point
                if pose.model_id == self.selected_model_id and pose.position is None
                else pose.position,
                state="current"
                if pose.model_id == self.selected_model_id
                else "placed"
                if pose.placed
                else "unplaced",
            )
            for pose in self.model_poses
        )

    def to_payload(self) -> JsonObject:
        """Build the JSON-safe placement proposal payload for the committed draft."""

        model_placements: list[JsonValue] = [
            _model_placement_payload(self, pose) for pose in self.model_poses
        ]
        body: JsonObject
        if self.decision_type == "submit_deployment_placement":
            body = {
                "proposal_request_id": self.proposal_request_id,
                "proposal_kind": self.proposal_kind,
                "game_id": self.game_id,
                "ruleset_descriptor_hash": _required_string_value(
                    "ruleset_descriptor_hash",
                    self.ruleset_descriptor_hash,
                ),
                "setup_step": _required_string_value("setup_step", self.setup_step),
                "player_id": self.player_id,
                "unit_instance_id": self.selected_unit_id,
                "placement_kind": self.placement_kind,
                "model_placements": model_placements,
            }
            if self.context:
                body["context"] = self.context
            return _json_object("deployment placement payload", body)
        if self.decision_type in ("submit_redeploy_placement", "submit_scout_reserve_setup"):
            body = {
                "proposal_request_id": self.proposal_request_id,
                "proposal_kind": self.proposal_kind,
                "game_id": self.game_id,
                "ruleset_descriptor_hash": _required_string_value(
                    "ruleset_descriptor_hash",
                    self.ruleset_descriptor_hash,
                ),
                "setup_step": _required_string_value("setup_step", self.setup_step),
                "player_id": self.player_id,
                "unit_instance_id": self.selected_unit_id,
                "action_kind": _required_string_value("action_kind", self.action_kind),
                "source_rule_id": _required_string_value("source_rule_id", self.source_rule_id),
                "placement_kind": self.placement_kind,
                "model_placements": model_placements,
            }
            if self.context:
                body["context"] = self.context
            return _json_object("pre-battle placement payload", body)
        attempted_placement: JsonObject = {
            "army_id": _army_id_from_unit_instance_id(self.selected_unit_id, self.player_id),
            "player_id": self.player_id,
            "unit_instance_id": self.selected_unit_id,
            "model_placements": model_placements,
        }
        body = {
            "proposal_request_id": self.proposal_request_id,
            "proposal_kind": self.proposal_kind,
            "unit_instance_id": self.selected_unit_id,
            "placement_kind": self.placement_kind,
            "attempted_placement": attempted_placement,
        }
        for key in (
            "transport_unit_instance_id",
            "disembark_mode",
            "transport_movement_status",
            "large_model_exceptions",
            "restriction_overrides",
        ):
            value = (self.context or {}).get(key)
            if value not in (None, (), []):
                body[key] = validate_json_value(value)
        return _json_object("placement proposal payload", body)


def placement_proposal_for_selected_unit(
    *,
    selection: SelectionState,
    pending_decision: UiDecision | None,
) -> UiPlacementProposalRequest | None:
    """Return the placement proposal matching the selected unit, if any."""

    if selection.selected_unit_id is None or pending_decision is None:
        return None
    proposal = pending_decision.placement_proposal
    if proposal is None:
        return None
    if proposal.unit_instance_id != selection.selected_unit_id:
        return None
    return proposal


def _draftable_placement_proposal(
    pending_decision: UiDecision | None,
) -> UiPlacementProposalRequest | None:
    proposal = None if pending_decision is None else pending_decision.placement_proposal
    if proposal is None:
        return None
    if proposal.decision_type not in PLACEMENT_PROPOSAL_DECISION_TYPES:
        return None
    if proposal.proposal_kind not in SUPPORTED_PLACEMENT_PROPOSAL_KINDS:
        return None
    return proposal


def _model_placement_payload(draft: PlacementDraft, pose: PlacementModelPose) -> JsonObject:
    if pose.position is None:
        raise PlacementDraftError("Cannot serialize unplaced placement model.")
    return {
        "army_id": _army_id_from_unit_instance_id(draft.selected_unit_id, draft.player_id),
        "player_id": draft.player_id,
        "unit_instance_id": draft.selected_unit_id,
        "model_instance_id": pose.model_id,
        "pose": _pose_payload(pose.position, pose.facing_degrees),
    }


def _pose_payload(point: WorldPoint, facing_degrees: float) -> JsonObject:
    return {
        "position": {"x": point[0], "y": point[1], "z": 0.0},
        "facing": {"degrees": facing_degrees},
    }


def _next_unplaced_model_id(
    model_poses: tuple[PlacementModelPose, ...],
    current_model_id: str,
) -> str:
    unplaced = tuple(pose.model_id for pose in model_poses if not pose.placed)
    if not unplaced:
        return current_model_id
    if current_model_id in unplaced:
        current_index = unplaced.index(current_model_id)
        return unplaced[(current_index + 1) % len(unplaced)]
    return unplaced[0]


def _unit_by_id(view: BattlefieldView, unit_id: str) -> UnitView | None:
    for unit in view.units:
        if unit.unit_id == unit_id:
            return unit
    return None


def _models_by_id(unit: UnitView | None) -> dict[str, ModelBaseView]:
    if unit is None:
        return {}
    return {model.model_id: model for model in unit.models}


def _model_base_radius(
    model: ModelBaseView | None,
    *,
    model_id: str,
    model_display_by_id: JsonObject | None,
) -> float:
    if model is not None:
        return model.base_radius
    display = _optional_model_display(
        model_id=model_id,
        model_display_by_id=model_display_by_id,
    )
    if display is None:
        return _DEFAULT_PRESENTATION_BASE_RADIUS_INCHES
    base_size = _json_object("model_display.base_size", display.get("base_size"))
    kind = _non_empty_string("model_display.base_size.kind", base_size.get("kind"))
    if kind == "circular":
        return _positive_float_field(base_size, "diameter_mm") / _MM_PER_INCH / 2.0
    if kind == "oval":
        length = _positive_float_field(base_size, "length_mm")
        width = _positive_float_field(base_size, "width_mm")
        return max(length, width) / _MM_PER_INCH / 2.0
    raise PlacementDraftError(f"model_display base_size kind is unsupported: {kind}.")


def _optional_model_display(
    *,
    model_id: str,
    model_display_by_id: JsonObject | None,
) -> JsonObject | None:
    if model_display_by_id is None:
        return None
    display_value = model_display_by_id.get(model_id)
    if display_value is None:
        return None
    return _json_object("model_display", display_value)


def _army_id_from_unit_instance_id(unit_instance_id: str, player_id: str) -> str:
    if ":" in unit_instance_id:
        return unit_instance_id.split(":", 1)[0]
    return player_id


def _validate_unique_model_poses(model_poses: tuple[PlacementModelPose, ...]) -> None:
    model_ids = [pose.model_id for pose in model_poses]
    if len(model_ids) != len(set(model_ids)):
        raise PlacementDraftError("PlacementDraft model IDs must be unique.")


def _validate_world_point(field_name: str, value: object) -> WorldPoint:
    if type(value) is not tuple:
        raise PlacementDraftError(f"{field_name} must be a 2D point tuple.")
    point = cast(tuple[object, ...], value)
    if len(point) != 2:
        raise PlacementDraftError(f"{field_name} must be a 2D point tuple.")
    x, y = point
    return (
        _validate_finite(f"{field_name}.x", x),
        _validate_finite(f"{field_name}.y", y),
    )


def _validate_positive(field_name: str, value: float) -> None:
    _validate_finite(field_name, value)
    if value <= 0.0:
        raise PlacementDraftError(f"{field_name} must be positive.")


def _positive_float_field(payload: JsonObject, key: str) -> float:
    try:
        value = payload[key]
    except KeyError as exc:
        raise PlacementDraftError(f"{key} is required.") from exc
    number = _validate_finite(key, value)
    if number <= 0.0:
        raise PlacementDraftError(f"{key} must be positive.")
    return number


def _validate_finite(field_name: str, value: object) -> float:
    if type(value) is int:
        numeric = float(value)
    elif type(value) is float:
        numeric = value
    else:
        raise PlacementDraftError(f"{field_name} must be numeric.")
    if not -float("inf") < numeric < float("inf"):
        raise PlacementDraftError(f"{field_name} must be finite.")
    return numeric


def _non_empty_string(field_name: str, value: object) -> str:
    if type(value) is not str:
        raise PlacementDraftError(f"{field_name} must be a string.")
    stripped = value.strip()
    if not stripped:
        raise PlacementDraftError(f"{field_name} must not be empty.")
    return stripped


def _required_string_value(field_name: str, value: str | None) -> str:
    if value is None:
        raise PlacementDraftError(f"{field_name} is required for this placement payload.")
    return _non_empty_string(field_name, value)


def _optional_string(field_name: str, value: object | None) -> str | None:
    if value is None:
        return None
    return _non_empty_string(field_name, value)


def _json_object(field_name: str, value: object) -> JsonObject:
    json_value = validate_json_value(value)
    if type(json_value) is not dict:
        raise PlacementDraftError(f"{field_name} must be a JSON object.")
    return json_value
