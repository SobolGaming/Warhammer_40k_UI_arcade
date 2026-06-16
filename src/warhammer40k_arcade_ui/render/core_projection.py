"""Render view construction from core viewer projections."""

from __future__ import annotations

import math
from typing import cast

from warhammer40k_arcade_ui.core_client.protocol import JsonObject, JsonValue, UiGameView
from warhammer40k_arcade_ui.render.view_models import (
    BattlefieldView,
    DeploymentZoneView,
    HudView,
    ModelBaseView,
    ObjectiveView,
    TableView,
    TerrainFootprintView,
    UnitView,
)

_MM_PER_INCH = 25.4
_DEFAULT_PRESENTATION_BASE_RADIUS_INCHES = 32.0 / _MM_PER_INCH / 2.0
_TERRAIN_DISPLAY_SCHEMA_VERSION = "terrain-display-v1"
_TERRAIN_DISPLAY_COORDINATE_SPACE = "battlefield_inches"
_TERRAIN_DISPLAY_FOOTPRINT_KIND = "polygon"
_FOOTPRINT_BOUNDS_TOLERANCE = 1.0e-4
_FOOTPRINT_AREA_TOLERANCE = 1.0e-9


class CoreProjectionRenderError(ValueError):
    """Raised when a core projection cannot be represented by current render view models."""


def battlefield_view_from_game_view(view: UiGameView) -> BattlefieldView:
    """Build a renderable battlefield view from a core `GameViewPayload` projection."""

    mission_setup = _json_object("mission_setup", view.mission_setup)
    battlefield_state = _json_object("battlefield_state", view.battlefield_state)
    table_width = _required_positive_float(mission_setup, "battlefield_width_inches")
    table_height = _required_positive_float(mission_setup, "battlefield_depth_inches")
    return BattlefieldView(
        table=_table_from_mission_setup(
            mission_setup=mission_setup,
            width=table_width,
            height=table_height,
        ),
        deployment_zones=_deployment_zones_from_mission_setup(mission_setup),
        objectives=_objectives_from_mission_setup(mission_setup),
        terrain=_terrain_from_mission_setup(mission_setup),
        units=_units_from_battlefield_state(
            battlefield_state=battlefield_state,
            model_display_by_id=view.model_display_by_id,
        ),
        hud=HudView(
            phase_label=view.current_battle_phase or view.stage,
            active_player_id=view.active_player_id or "none",
            pending_decision_summary=_pending_decision_summary(view),
            event_log_lines=(),
        ),
    )


def _table_from_mission_setup(
    *,
    mission_setup: JsonObject,
    width: float,
    height: float,
) -> TableView:
    mission_pool_entry_id = _required_string(mission_setup, "mission_pool_entry_id")
    terrain_layout_id = _required_string(mission_setup, "terrain_layout_id")
    deployment_map_id = _required_string(mission_setup, "deployment_map_id")
    return TableView(
        width=width,
        height=height,
        label=f"Live Core {mission_pool_entry_id} / {terrain_layout_id}",
        terrain_layout_label=f"Terrain layout: {terrain_layout_id}",
        deployment_map_label=f"Deployment map: {deployment_map_id}",
    )


def _deployment_zones_from_mission_setup(
    mission_setup: JsonObject,
) -> tuple[DeploymentZoneView, ...]:
    return tuple(
        DeploymentZoneView(
            zone_id=_required_string(zone, "deployment_zone_id"),
            player_id=_required_string(zone, "player_id"),
            label=f"{_required_string(zone, 'player_id')} deployment",
            polygon=_deployment_zone_polygon(zone),
            visible=True,
        )
        for zone in (
            _json_object("deployment_zone", value)
            for value in _required_list(mission_setup, "deployment_zones")
        )
    )


def _deployment_zone_polygon(zone: JsonObject) -> tuple[tuple[float, float], ...]:
    if {"min_x", "min_y", "max_x", "max_y"}.issubset(zone):
        return _rectangle_polygon(
            min_x=_required_float(zone, "min_x"),
            min_y=_required_float(zone, "min_y"),
            max_x=_required_float(zone, "max_x"),
            max_y=_required_float(zone, "max_y"),
        )
    shape = _json_object("deployment_zone.shape", zone.get("shape"))
    polygons = _required_list(shape, "polygons")
    if len(polygons) != 1:
        raise CoreProjectionRenderError(
            "deployment_zone.shape must contain exactly one polygon for rendering."
        )
    polygon = _json_object("deployment_zone.shape.polygons[0]", polygons[0])
    return tuple(
        _xy_point_from_payload(_json_object("deployment_zone.shape.vertex", value))
        for value in _required_list(polygon, "vertices")
    )


def _xy_point_from_payload(payload: JsonObject) -> tuple[float, float]:
    return (_required_float(payload, "x"), _required_float(payload, "y"))


def _objectives_from_mission_setup(mission_setup: JsonObject) -> tuple[ObjectiveView, ...]:
    return tuple(
        ObjectiveView(
            objective_id=_required_string(marker, "objective_marker_id"),
            label=_required_string(marker, "name"),
            position=(
                _required_float(marker, "x_inches"),
                _required_float(marker, "y_inches"),
            ),
            radius=_marker_radius_inches(marker),
        )
        for marker in (
            _json_object("objective_marker", value)
            for value in _required_list(mission_setup, "objective_markers")
        )
    )


def _terrain_from_mission_setup(mission_setup: JsonObject) -> tuple[TerrainFootprintView, ...]:
    return tuple(
        TerrainFootprintView(
            terrain_id=_required_string(feature, "feature_id"),
            label=_required_string(feature, "feature_kind"),
            footprint=_terrain_display_footprint(feature),
        )
        for feature in (
            _json_object("terrain_feature", value)
            for value in _required_list(mission_setup, "terrain_features")
        )
    )


def _units_from_battlefield_state(
    *,
    battlefield_state: JsonObject,
    model_display_by_id: JsonObject,
) -> tuple[UnitView, ...]:
    units: list[UnitView] = []
    for placed_army_value in _required_list(battlefield_state, "placed_armies"):
        placed_army = _json_object("placed_army", placed_army_value)
        for unit_placement_value in _required_list(placed_army, "unit_placements"):
            unit_placement = _json_object("unit_placement", unit_placement_value)
            unit_id = _required_string(unit_placement, "unit_instance_id")
            units.append(
                UnitView(
                    unit_id=unit_id,
                    player_id=_required_string(unit_placement, "player_id"),
                    label=_display_suffix(unit_id),
                    models=tuple(
                        _model_from_placement(
                            value=value,
                            model_display_by_id=model_display_by_id,
                        )
                        for value in _required_list(unit_placement, "model_placements")
                    ),
                )
            )
    return tuple(units)


def _model_from_placement(
    *,
    value: JsonValue,
    model_display_by_id: JsonObject,
) -> ModelBaseView:
    model_placement = _json_object("model_placement", value)
    model_id = _required_string(model_placement, "model_instance_id")
    pose = _json_object("pose", model_placement.get("pose"))
    position = _json_object("pose.position", pose.get("position"))
    return ModelBaseView(
        model_id=model_id,
        label=_display_suffix(model_id),
        position=(
            _required_float(position, "x"),
            _required_float(position, "y"),
        ),
        base_radius=_model_base_radius_inches(
            model_id=model_id,
            model_display_by_id=model_display_by_id,
        ),
        base_movement_inches=_model_base_movement_inches(
            model_id=model_id,
            model_display_by_id=model_display_by_id,
        ),
    )


def _model_base_radius_inches(*, model_id: str, model_display_by_id: JsonObject) -> float:
    display = _optional_model_display(model_id=model_id, model_display_by_id=model_display_by_id)
    if display is None:
        return _DEFAULT_PRESENTATION_BASE_RADIUS_INCHES
    base_size = _json_object("model_display.base_size", display.get("base_size"))
    kind = _required_string(base_size, "kind")
    if kind == "circular":
        return _required_positive_float(base_size, "diameter_mm") / _MM_PER_INCH / 2.0
    if kind == "oval":
        length = _required_positive_float(base_size, "length_mm")
        width = _required_positive_float(base_size, "width_mm")
        return max(length, width) / _MM_PER_INCH / 2.0
    raise CoreProjectionRenderError(f"model_display base_size kind is unsupported: {kind}.")


def _model_base_movement_inches(
    *,
    model_id: str,
    model_display_by_id: JsonObject,
) -> float | None:
    display = _optional_model_display(model_id=model_id, model_display_by_id=model_display_by_id)
    if display is None:
        return None
    return _movement_characteristic_inches(display.get("base_characteristics")) or (
        _movement_characteristic_inches(display.get("current_characteristics"))
    )


def _optional_model_display(
    *,
    model_id: str,
    model_display_by_id: JsonObject,
) -> JsonObject | None:
    display_value = model_display_by_id.get(model_id)
    if display_value is None:
        return None
    return _json_object("model_display", display_value)


def _movement_characteristic_inches(characteristics_value: JsonValue) -> float | None:
    if characteristics_value is None:
        return None
    characteristics = _json_object("model_display.characteristics", characteristics_value)
    movement_value = characteristics.get("M")
    if movement_value is None:
        return None
    movement = _json_object("model_display.characteristics.M", movement_value)
    for key in ("final", "base", "raw"):
        value = movement.get(key)
        if value is None:
            continue
        number = _number_to_float(f"model_display.characteristics.M.{key}", value)
        if number > 0.0:
            return number
    return None


def _pending_decision_summary(view: UiGameView) -> str:
    decision = view.pending_decision
    if decision is None:
        return "No pending decision"
    if decision.is_parameterized:
        proposal = decision.parameterized_proposal
        label = (
            proposal.proposal_kind
            if proposal is not None and proposal.proposal_kind is not None
            else decision.decision_type
        )
        return f"Proposal required: {label}"
    return f"Waiting: {decision.decision_type}"


def _marker_radius_inches(marker: JsonObject) -> float:
    return _required_positive_float(marker, "marker_diameter_mm") / _MM_PER_INCH / 2.0


def _terrain_display_footprint(feature: JsonObject) -> tuple[tuple[float, float], ...]:
    display_geometry = _json_object(
        "terrain_feature.display_geometry",
        feature.get("display_geometry"),
    )
    schema_version = _required_string(display_geometry, "schema_version")
    if schema_version != _TERRAIN_DISPLAY_SCHEMA_VERSION:
        raise CoreProjectionRenderError("terrain display geometry schema_version is unsupported.")
    coordinate_space = _required_string(display_geometry, "coordinate_space")
    if coordinate_space != _TERRAIN_DISPLAY_COORDINATE_SPACE:
        raise CoreProjectionRenderError("terrain display geometry coordinate_space is unsupported.")
    footprint_kind = _required_string(display_geometry, "footprint_kind")
    if footprint_kind != _TERRAIN_DISPLAY_FOOTPRINT_KIND:
        raise CoreProjectionRenderError("terrain display geometry footprint_kind is unsupported.")
    _optional_string_field(display_geometry, "display_template_id")
    footprint = tuple(
        _terrain_display_point_from_payload(value)
        for value in _required_list(display_geometry, "footprint_polygon")
    )
    _validate_terrain_display_footprint(footprint)
    _validate_display_footprint_matches_bounds(
        feature=feature,
        display_footprint=footprint,
    )
    return footprint


def _terrain_display_point_from_payload(value: JsonValue) -> tuple[float, float]:
    point = _json_object("terrain display point", value)
    return (
        _required_float(point, "x_inches"),
        _required_float(point, "y_inches"),
    )


def _validate_terrain_display_footprint(footprint: tuple[tuple[float, float], ...]) -> None:
    if len(footprint) < 3:
        raise CoreProjectionRenderError(
            "terrain display geometry footprint_polygon must contain at least three points."
        )
    if footprint[0] == footprint[-1]:
        raise CoreProjectionRenderError(
            "terrain display geometry footprint_polygon must be unclosed."
        )
    if abs(_polygon_area(footprint)) <= _FOOTPRINT_AREA_TOLERANCE:
        raise CoreProjectionRenderError(
            "terrain display geometry footprint_polygon must have non-zero area."
        )


def _validate_display_footprint_matches_bounds(
    *,
    feature: JsonObject,
    display_footprint: tuple[tuple[float, float], ...],
) -> None:
    center_x = _required_float(feature, "footprint_center_x_inches")
    center_y = _required_float(feature, "footprint_center_y_inches")
    width = _required_positive_float(feature, "footprint_width_inches")
    height = _required_positive_float(feature, "footprint_depth_inches")
    expected_bounds = (
        center_x - (width / 2.0),
        center_y - (height / 2.0),
        center_x + (width / 2.0),
        center_y + (height / 2.0),
    )
    actual_bounds = _polygon_bounds(display_footprint)
    if any(
        not math.isclose(
            actual,
            expected,
            rel_tol=0.0,
            abs_tol=_FOOTPRINT_BOUNDS_TOLERANCE,
        )
        for actual, expected in zip(actual_bounds, expected_bounds, strict=True)
    ):
        raise CoreProjectionRenderError(
            "terrain display footprint does not match projected footprint bounds."
        )


def _polygon_area(polygon: tuple[tuple[float, float], ...]) -> float:
    total = 0.0
    for index, point in enumerate(polygon):
        next_point = polygon[(index + 1) % len(polygon)]
        total += (point[0] * next_point[1]) - (next_point[0] * point[1])
    return total / 2.0


def _rectangle_polygon(
    *,
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
) -> tuple[tuple[float, float], ...]:
    if min_x >= max_x or min_y >= max_y:
        raise CoreProjectionRenderError("rectangle bounds must have positive area.")
    return (
        (min_x, min_y),
        (max_x, min_y),
        (max_x, max_y),
        (min_x, max_y),
    )


def _polygon_bounds(polygon: tuple[tuple[float, float], ...]) -> tuple[float, float, float, float]:
    return (
        min(point[0] for point in polygon),
        min(point[1] for point in polygon),
        max(point[0] for point in polygon),
        max(point[1] for point in polygon),
    )


def _json_object(name: str, payload: object) -> JsonObject:
    if type(payload) is not dict:
        raise CoreProjectionRenderError(f"{name} must be a JSON object.")
    return cast(JsonObject, payload)


def _required_list(payload: JsonObject, key: str) -> list[JsonValue]:
    value = payload.get(key)
    if type(value) is not list:
        raise CoreProjectionRenderError(f"{key} must be a JSON list.")
    return value


def _required_string(payload: JsonObject, key: str) -> str:
    value = payload.get(key)
    if type(value) is not str or not value:
        raise CoreProjectionRenderError(f"{key} must be a non-empty string.")
    return value


def _required_float(payload: JsonObject, key: str) -> float:
    value = payload.get(key)
    number = _number_to_float(key, value)
    if not math.isfinite(number):
        raise CoreProjectionRenderError(f"{key} must be finite.")
    return number


def _number_to_float(name: str, value: object) -> float:
    if type(value) is int:
        return float(value)
    if type(value) is float:
        return value
    raise CoreProjectionRenderError(f"{name} must be a number.")


def _required_positive_float(payload: JsonObject, key: str) -> float:
    value = _required_float(payload, key)
    if value <= 0.0:
        raise CoreProjectionRenderError(f"{key} must be positive.")
    return value


def _optional_string_value(payload: JsonObject, key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if type(value) is not str:
        raise CoreProjectionRenderError(f"{key} must be a string.")
    stripped = value.strip()
    if not stripped:
        raise CoreProjectionRenderError(f"{key} must not be empty.")
    return stripped


def _optional_string_field(payload: JsonObject, key: str) -> str | None:
    if key not in payload:
        raise CoreProjectionRenderError(f"{key} is required.")
    return _optional_string_value(payload, key)


def _display_suffix(value: str) -> str:
    suffix = value.rsplit(":", 1)[-1]
    return suffix if suffix else value
