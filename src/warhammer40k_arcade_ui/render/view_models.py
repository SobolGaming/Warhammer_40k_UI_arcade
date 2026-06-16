"""Typed, read-only battlefield view models for rendering."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Self, cast

type Point = tuple[float, float]
type Polygon = tuple[Point, ...]


class RenderViewModelError(ValueError):
    """Raised when fixture or projection data cannot be rendered safely."""


@dataclass(frozen=True, slots=True)
class TableView:
    """Table dimensions in world-space inches."""

    width: float
    height: float
    label: str
    terrain_layout_label: str | None = None
    deployment_map_label: str | None = None

    def __post_init__(self) -> None:
        _validate_positive_float("width", self.width)
        _validate_positive_float("height", self.height)
        object.__setattr__(self, "label", _non_empty_string("label", self.label))
        object.__setattr__(
            self,
            "terrain_layout_label",
            _optional_non_empty_string("terrain_layout_label", self.terrain_layout_label),
        )
        object.__setattr__(
            self,
            "deployment_map_label",
            _optional_non_empty_string("deployment_map_label", self.deployment_map_label),
        )

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        table = _required_object("table", payload)
        return cls(
            width=_required_positive_float(table, "width"),
            height=_required_positive_float(table, "height"),
            label=_required_string(table, "label"),
            terrain_layout_label=_optional_string(table, "terrain_layout_label"),
            deployment_map_label=_optional_string(table, "deployment_map_label"),
        )


@dataclass(frozen=True, slots=True)
class DeploymentZoneView:
    """Optional deployment-zone overlay in table coordinates."""

    zone_id: str
    player_id: str
    label: str
    polygon: Polygon
    visible: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "zone_id", _non_empty_string("zone_id", self.zone_id))
        object.__setattr__(self, "player_id", _non_empty_string("player_id", self.player_id))
        object.__setattr__(self, "label", _non_empty_string("label", self.label))
        object.__setattr__(self, "polygon", _validate_polygon("polygon", self.polygon))
        if type(self.visible) is not bool:
            raise RenderViewModelError("visible must be a bool.")

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        zone = _required_object("deployment zone", payload)
        return cls(
            zone_id=_required_string(zone, "zone_id"),
            player_id=_required_string(zone, "player_id"),
            label=_required_string(zone, "label"),
            polygon=_required_polygon(zone, "polygon"),
            visible=_required_bool(zone, "visible"),
        )


@dataclass(frozen=True, slots=True)
class ObjectiveView:
    """Objective marker in table coordinates."""

    objective_id: str
    label: str
    position: Point
    radius: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "objective_id",
            _non_empty_string("objective_id", self.objective_id),
        )
        object.__setattr__(self, "label", _non_empty_string("label", self.label))
        object.__setattr__(self, "position", _validate_point("position", self.position))
        _validate_positive_float("radius", self.radius)

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        objective = _required_object("objective", payload)
        return cls(
            objective_id=_required_string(objective, "objective_id"),
            label=_required_string(objective, "label"),
            position=_required_point(objective, "position"),
            radius=_required_positive_float(objective, "radius"),
        )


@dataclass(frozen=True, slots=True)
class TerrainFootprintView:
    """Simple terrain footprint in table coordinates."""

    terrain_id: str
    label: str
    footprint: Polygon
    source_kind: str = "terrain_feature"
    objective_marker_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "terrain_id", _non_empty_string("terrain_id", self.terrain_id))
        object.__setattr__(self, "label", _non_empty_string("label", self.label))
        object.__setattr__(self, "footprint", _validate_polygon("footprint", self.footprint))
        if self.source_kind not in {"terrain_feature", "terrain_area"}:
            raise RenderViewModelError("source_kind must be terrain_feature or terrain_area.")
        if type(self.objective_marker_ids) is not tuple:
            raise RenderViewModelError("objective_marker_ids must be a tuple.")
        object.__setattr__(
            self,
            "objective_marker_ids",
            tuple(
                _non_empty_string("objective_marker_id", marker_id)
                for marker_id in self.objective_marker_ids
            ),
        )

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        terrain = _required_object("terrain", payload)
        return cls(
            terrain_id=_required_string(terrain, "terrain_id"),
            label=_required_string(terrain, "label"),
            footprint=_required_polygon(terrain, "footprint"),
            source_kind=_optional_string(terrain, "source_kind") or "terrain_feature",
            objective_marker_ids=tuple(
                _required_string_item("objective_marker_id", marker_id)
                for marker_id in _optional_list(terrain, "objective_marker_ids")
            ),
        )


@dataclass(frozen=True, slots=True)
class ModelBaseView:
    """Model base rendered as a circular footprint."""

    model_id: str
    label: str
    position: Point
    base_radius: float
    base_movement_inches: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", _non_empty_string("model_id", self.model_id))
        object.__setattr__(self, "label", _non_empty_string("label", self.label))
        object.__setattr__(self, "position", _validate_point("position", self.position))
        _validate_positive_float("base_radius", self.base_radius)
        if self.base_movement_inches is not None:
            _validate_positive_float("base_movement_inches", self.base_movement_inches)

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        model = _required_object("model", payload)
        return cls(
            model_id=_required_string(model, "model_id"),
            label=_required_string(model, "label"),
            position=_required_point(model, "position"),
            base_radius=_required_positive_float(model, "base_radius"),
            base_movement_inches=_optional_positive_float(model, "base_movement_inches"),
        )


@dataclass(frozen=True, slots=True)
class UnitView:
    """Unit placeholder plus its model bases."""

    unit_id: str
    player_id: str
    label: str
    models: tuple[ModelBaseView, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "unit_id", _non_empty_string("unit_id", self.unit_id))
        object.__setattr__(self, "player_id", _non_empty_string("player_id", self.player_id))
        object.__setattr__(self, "label", _non_empty_string("label", self.label))
        if type(self.models) is not tuple or not self.models:
            raise RenderViewModelError("models must be a non-empty tuple.")
        if any(type(model) is not ModelBaseView for model in self.models):
            raise RenderViewModelError("models must contain ModelBaseView items.")

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        unit = _required_object("unit", payload)
        return cls(
            unit_id=_required_string(unit, "unit_id"),
            player_id=_required_string(unit, "player_id"),
            label=_required_string(unit, "label"),
            models=tuple(
                ModelBaseView.from_payload(model) for model in _required_list(unit, "models")
            ),
        )


@dataclass(frozen=True, slots=True)
class HudView:
    """HUD labels derived from viewer-scoped UI state."""

    phase_label: str
    active_player_id: str
    pending_decision_summary: str
    event_log_lines: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "phase_label",
            _non_empty_string("phase_label", self.phase_label),
        )
        object.__setattr__(
            self,
            "active_player_id",
            _non_empty_string("active_player_id", self.active_player_id),
        )
        object.__setattr__(
            self,
            "pending_decision_summary",
            _non_empty_string(
                "pending_decision_summary",
                self.pending_decision_summary,
            ),
        )
        if type(self.event_log_lines) is not tuple:
            raise RenderViewModelError("event_log_lines must be a tuple.")
        object.__setattr__(
            self,
            "event_log_lines",
            tuple(_non_empty_string("event_log_line", line) for line in self.event_log_lines),
        )

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        hud = _required_object("hud", payload)
        return cls(
            phase_label=_required_string(hud, "phase_label"),
            active_player_id=_required_string(hud, "active_player_id"),
            pending_decision_summary=_required_string(hud, "pending_decision_summary"),
            event_log_lines=tuple(
                _required_string_item("event_log_line", line)
                for line in _required_list(hud, "event_log_lines")
            ),
        )


@dataclass(frozen=True, slots=True)
class BattlefieldView:
    """Complete renderable battlefield projection."""

    table: TableView
    deployment_zones: tuple[DeploymentZoneView, ...]
    objectives: tuple[ObjectiveView, ...]
    terrain: tuple[TerrainFootprintView, ...]
    units: tuple[UnitView, ...]
    hud: HudView

    def __post_init__(self) -> None:
        if type(self.table) is not TableView:
            raise RenderViewModelError("table must be a TableView.")
        if type(self.deployment_zones) is not tuple:
            raise RenderViewModelError("deployment_zones must be a tuple.")
        if type(self.objectives) is not tuple:
            raise RenderViewModelError("objectives must be a tuple.")
        if type(self.terrain) is not tuple:
            raise RenderViewModelError("terrain must be a tuple.")
        if type(self.units) is not tuple:
            raise RenderViewModelError("units must be a tuple.")
        if type(self.hud) is not HudView:
            raise RenderViewModelError("hud must be a HudView.")

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        view = _required_object("battlefield view", payload)
        return cls(
            table=TableView.from_payload(view["table"]),
            deployment_zones=tuple(
                DeploymentZoneView.from_payload(zone)
                for zone in _required_list(view, "deployment_zones")
            ),
            objectives=tuple(
                ObjectiveView.from_payload(objective)
                for objective in _required_list(view, "objectives")
            ),
            terrain=tuple(
                TerrainFootprintView.from_payload(terrain)
                for terrain in _required_list(view, "terrain")
            ),
            units=tuple(UnitView.from_payload(unit) for unit in _required_list(view, "units")),
            hud=HudView.from_payload(view["hud"]),
        )

    def with_hud(
        self,
        *,
        phase_label: str,
        active_player_id: str,
        pending_decision_summary: str,
        event_log_lines: tuple[str, ...],
    ) -> BattlefieldView:
        """Return this battlefield view with refreshed HUD labels."""

        return replace(
            self,
            hud=HudView(
                phase_label=phase_label,
                active_player_id=active_player_id,
                pending_decision_summary=pending_decision_summary,
                event_log_lines=event_log_lines,
            ),
        )

    def with_model_positions(self, positions_by_model_id: dict[str, Point]) -> BattlefieldView:
        """Return this view with matching model positions refreshed from a projection."""

        if not positions_by_model_id:
            return self
        return replace(
            self,
            units=tuple(
                replace(
                    unit,
                    models=tuple(
                        replace(model, position=positions_by_model_id[model.model_id])
                        if model.model_id in positions_by_model_id
                        else model
                        for model in unit.models
                    ),
                )
                for unit in self.units
            ),
        )

    def refreshed_from_projection(
        self,
        *,
        battlefield_state: object,
        phase_label: str,
        active_player_id: str,
        pending_decision_summary: str,
        event_log_lines: tuple[str, ...],
    ) -> BattlefieldView:
        """Return a render view refreshed from supported UI/core projection shapes."""

        updated_view = self
        if battlefield_state is None:
            updated_view = self
        elif _looks_like_render_battlefield_view_payload(battlefield_state):
            updated_view = BattlefieldView.from_payload(battlefield_state)
        elif _looks_like_core_battlefield_runtime_payload(battlefield_state):
            updated_view = self.with_model_positions(
                _model_positions_from_core_battlefield_payload(battlefield_state)
            )
        else:
            raise RenderViewModelError(
                "Unsupported battlefield_state projection shape: "
                f"{_projection_shape_description(battlefield_state)}."
            )
        return updated_view.with_hud(
            phase_label=phase_label,
            active_player_id=active_player_id,
            pending_decision_summary=pending_decision_summary,
            event_log_lines=event_log_lines,
        )


def _required_object(name: str, payload: object) -> dict[str, object]:
    if type(payload) is not dict:
        raise RenderViewModelError(f"{name} must be an object.")
    return cast(dict[str, object], payload)


def _looks_like_render_battlefield_view_payload(payload: object) -> bool:
    return type(payload) is dict and "table" in payload and "units" in payload and "hud" in payload


def _looks_like_core_battlefield_runtime_payload(payload: object) -> bool:
    return type(payload) is dict and "placed_armies" in payload


def _projection_shape_description(payload: object) -> str:
    if type(payload) is dict:
        object_payload = cast(dict[object, object], payload)
        keys = sorted(str(key) for key in object_payload)
        return f"object keys={keys}"
    return type(payload).__name__


def _model_positions_from_core_battlefield_payload(payload: object) -> dict[str, Point]:
    battlefield = _required_object("battlefield_state", payload)
    positions: dict[str, Point] = {}
    for placed_army in _required_list(battlefield, "placed_armies"):
        placed_army_payload = _required_object("placed_army", placed_army)
        for unit_placement in _required_list(placed_army_payload, "unit_placements"):
            unit_placement_payload = _required_object("unit_placement", unit_placement)
            for model_placement in _required_list(unit_placement_payload, "model_placements"):
                model_placement_payload = _required_object("model_placement", model_placement)
                model_id = _required_string(model_placement_payload, "model_instance_id")
                positions[model_id] = _pose_position(
                    _required_value(model_placement_payload, "pose")
                )
    return positions


def _pose_position(payload: object) -> Point:
    pose = _required_object("pose", payload)
    position = _required_object("position", _required_value(pose, "position"))
    point = (
        _numeric_to_float("pose.position.x", _required_value(position, "x")),
        _numeric_to_float("pose.position.y", _required_value(position, "y")),
    )
    _validate_finite_float("pose.position.x", point[0])
    _validate_finite_float("pose.position.y", point[1])
    return point


def _required_list(payload: dict[str, object], key: str) -> list[object]:
    value = _required_value(payload, key)
    if type(value) is not list:
        raise RenderViewModelError(f"{key} must be a list.")
    return cast(list[object], value)


def _optional_list(payload: dict[str, object], key: str) -> list[object]:
    value = payload.get(key)
    if value is None:
        return []
    if type(value) is not list:
        raise RenderViewModelError(f"{key} must be a list.")
    return cast(list[object], value)


def _required_value(payload: dict[str, object], key: str) -> object:
    if key not in payload:
        raise RenderViewModelError(f"{key} is required.")
    return payload[key]


def _required_string(payload: dict[str, object], key: str) -> str:
    return _required_string_item(key, _required_value(payload, key))


def _required_string_item(name: str, value: object) -> str:
    return _non_empty_string(name, value)


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return _optional_non_empty_string(key, value)


def _optional_non_empty_string(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _non_empty_string(name, value)


def _non_empty_string(name: str, value: object) -> str:
    if type(value) is not str or not value:
        raise RenderViewModelError(f"{name} must be a non-empty string.")
    return value


def _required_bool(payload: dict[str, object], key: str) -> bool:
    value = _required_value(payload, key)
    if type(value) is not bool:
        raise RenderViewModelError(f"{key} must be a bool.")
    return value


def _required_positive_float(payload: dict[str, object], key: str) -> float:
    value = _required_value(payload, key)
    numeric_value = _numeric_to_float(key, value)
    _validate_positive_float(key, numeric_value)
    return numeric_value


def _optional_positive_float(payload: dict[str, object], key: str) -> float | None:
    value = payload.get(key)
    if value is None:
        return None
    numeric_value = _numeric_to_float(key, value)
    _validate_positive_float(key, numeric_value)
    return numeric_value


def _required_point(payload: dict[str, object], key: str) -> Point:
    return _validate_point(key, _required_value(payload, key))


def _required_polygon(payload: dict[str, object], key: str) -> Polygon:
    return _validate_polygon(key, _required_value(payload, key))


def _validate_polygon(name: str, value: object) -> Polygon:
    if type(value) not in (list, tuple):
        raise RenderViewModelError(f"{name} must be a list of points.")
    points = tuple(
        _validate_point(name, point) for point in cast(list[object] | tuple[object, ...], value)
    )
    if len(points) < 3:
        raise RenderViewModelError(f"{name} must contain at least three points.")
    return points


def _validate_point(name: str, value: object) -> Point:
    if type(value) not in (list, tuple):
        raise RenderViewModelError(f"{name} point must be a two-item list.")
    coordinates = cast(list[object] | tuple[object, ...], value)
    if len(coordinates) != 2:
        raise RenderViewModelError(f"{name} point must contain exactly two values.")
    x_value, y_value = coordinates
    point = (
        _numeric_to_float(f"{name}.x", x_value),
        _numeric_to_float(f"{name}.y", y_value),
    )
    _validate_finite_float(f"{name}.x", point[0])
    _validate_finite_float(f"{name}.y", point[1])
    return point


def _numeric_to_float(name: str, value: object) -> float:
    if type(value) is int:
        return float(value)
    if type(value) is float:
        return value
    raise RenderViewModelError(f"{name} must be numeric.")


def _validate_positive_float(name: str, value: float) -> None:
    if value <= 0 or not math.isfinite(value):
        raise RenderViewModelError(f"{name} must be finite and positive.")


def _validate_finite_float(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise RenderViewModelError(f"{name} must be finite.")
