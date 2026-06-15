"""Render view construction from core viewer projections."""

from __future__ import annotations

import math
import re
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
_SOURCE_TERRAIN_FOOTPRINT_RE = re.compile(
    r":(?P<preset>ruin_rect_(?P<width>\d+)x(?P<depth>\d+)_variant\d+):"
    r"rotation-(?P<rotation_degrees>-?\d+(?:\.\d+)?):"
    r"origin-(?P<origin_x>\d+(?:\.\d+)?)-(?P<origin_y>\d+(?:\.\d+)?)$"
)
_FOOTPRINT_BOUNDS_TOLERANCE = 1.0e-4


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
        units=_units_from_battlefield_state(battlefield_state),
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
    return TableView(
        width=width,
        height=height,
        label=f"Live Core {mission_pool_entry_id} / {terrain_layout_id}",
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


def _units_from_battlefield_state(battlefield_state: JsonObject) -> tuple[UnitView, ...]:
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
                        _model_from_placement(value)
                        for value in _required_list(unit_placement, "model_placements")
                    ),
                )
            )
    return tuple(units)


def _model_from_placement(value: JsonValue) -> ModelBaseView:
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
        base_radius=_DEFAULT_PRESENTATION_BASE_RADIUS_INCHES,
    )


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
    fallback = _centered_rectangle_polygon(
        center_x=_required_float(feature, "footprint_center_x_inches"),
        center_y=_required_float(feature, "footprint_center_y_inches"),
        width=_required_positive_float(feature, "footprint_width_inches"),
        height=_required_positive_float(feature, "footprint_depth_inches"),
    )
    source_id = _optional_string_value(feature, "source_id")
    if source_id is None:
        return fallback
    source_footprint = _rotated_source_terrain_footprint(source_id)
    if source_footprint is None:
        return fallback
    _validate_source_footprint_matches_bounds(
        feature=feature,
        source_footprint=source_footprint,
    )
    return source_footprint


def _rotated_source_terrain_footprint(
    source_id: str,
) -> tuple[tuple[float, float], ...] | None:
    match = _SOURCE_TERRAIN_FOOTPRINT_RE.search(source_id)
    if match is None:
        return None
    width = _positive_float_from_match(match.group("width"), "source terrain width")
    depth = _positive_float_from_match(match.group("depth"), "source terrain depth")
    rotation_degrees = _float_from_match(
        match.group("rotation_degrees"),
        "source terrain rotation",
    )
    origin_x = _float_from_match(match.group("origin_x"), "source terrain origin x")
    origin_y = _float_from_match(match.group("origin_y"), "source terrain origin y")
    radians = math.radians(rotation_degrees)
    cos_r = math.cos(radians)
    sin_r = math.sin(radians)
    return tuple(
        (
            origin_x + (corner_x * cos_r) - (corner_y * sin_r),
            origin_y + (corner_x * sin_r) + (corner_y * cos_r),
        )
        for corner_x, corner_y in (
            (0.0, 0.0),
            (width, 0.0),
            (width, depth),
            (0.0, depth),
        )
    )


def _validate_source_footprint_matches_bounds(
    *,
    feature: JsonObject,
    source_footprint: tuple[tuple[float, float], ...],
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
    actual_bounds = _polygon_bounds(source_footprint)
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
            "terrain source footprint does not match projected footprint bounds."
        )


def _centered_rectangle_polygon(
    *,
    center_x: float,
    center_y: float,
    width: float,
    height: float,
) -> tuple[tuple[float, float], ...]:
    half_width = width / 2.0
    half_height = height / 2.0
    return _rectangle_polygon(
        min_x=center_x - half_width,
        min_y=center_y - half_height,
        max_x=center_x + half_width,
        max_y=center_y + half_height,
    )


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
    if type(value) is int:
        return float(value)
    if type(value) is not float:
        raise CoreProjectionRenderError(f"{key} must be a number.")
    return value


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


def _float_from_match(value: str, field_name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise CoreProjectionRenderError(f"{field_name} must be finite.")
    return number


def _positive_float_from_match(value: str, field_name: str) -> float:
    number = _float_from_match(value, field_name)
    if number <= 0.0:
        raise CoreProjectionRenderError(f"{field_name} must be positive.")
    return number


def _display_suffix(value: str) -> str:
    suffix = value.rsplit(":", 1)[-1]
    return suffix if suffix else value
