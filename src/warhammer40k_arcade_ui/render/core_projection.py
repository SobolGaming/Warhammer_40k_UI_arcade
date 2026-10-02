"""Render view construction from core viewer projections."""

from __future__ import annotations

import math
from typing import cast

from warhammer40k_arcade_ui.core_client.protocol import JsonObject, JsonValue, UiGameView
from warhammer40k_arcade_ui.render.view_models import (
    BattlefieldView,
    DeploymentZoneView,
    HitRegionView,
    HudView,
    MeasurementOverlayView,
    ModelBaseView,
    ObjectiveView,
    PathOverlayView,
    RenderHintView,
    TableView,
    TerrainFootprintView,
    UnitView,
)

_MM_PER_INCH = 25.4
_DEFAULT_PRESENTATION_BASE_RADIUS_INCHES = 32.0 / _MM_PER_INCH / 2.0
_TERRAIN_DISPLAY_SCHEMA_VERSION = "terrain-display-v1"
_TERRAIN_DISPLAY_COORDINATE_SPACE = "battlefield_inches"
_TERRAIN_DISPLAY_FOOTPRINT_KIND = "polygon"
_TERRAIN_SOURCE_KIND_FEATURE = "terrain_feature"
_TERRAIN_SOURCE_KIND_AREA = "terrain_area"
_FOOTPRINT_BOUNDS_TOLERANCE = 1.0e-4
_FOOTPRINT_AREA_TOLERANCE = 1.0e-9


class CoreProjectionRenderError(ValueError):
    """Raised when a core projection cannot be represented by current render view models."""


def battlefield_view_from_game_view(view: UiGameView) -> BattlefieldView:
    """Build a renderable battlefield view from a core `GameViewPayload` projection."""

    if view.projection_schema == "ui-fixture-v1":
        return _legacy_fixture_battlefield_view(view)
    projection = view.battlefield_view
    if projection is None:
        raise CoreProjectionRenderError(
            "Current core game view is missing its canonical battlefield_view."
        )
    mission_setup = _json_object("mission_setup", view.mission_setup)
    bounds = projection.bounds
    min_x = _required_float(bounds, "min_x_inches")
    min_y = _required_float(bounds, "min_y_inches")
    if min_x != 0.0 or min_y != 0.0:
        raise CoreProjectionRenderError(
            "Current renderer requires battlefield bounds to begin at (0, 0)."
        )
    table_width = _required_float(bounds, "max_x_inches") - min_x
    table_height = _required_float(bounds, "max_y_inches") - min_y
    if table_width <= 0.0 or table_height <= 0.0:
        raise CoreProjectionRenderError("battlefield_view bounds must have positive area.")
    authoritative = projection.authoritative
    return BattlefieldView(
        table=_table_from_canonical_projection(
            mission_setup=mission_setup,
            width=table_width,
            height=table_height,
        ),
        deployment_zones=_canonical_deployment_zones(authoritative),
        objectives=_canonical_objectives(authoritative),
        terrain=_canonical_terrain(authoritative),
        units=_canonical_units(
            authoritative=authoritative,
            unit_display_by_id=view.unit_display_by_id,
            model_display_by_id=view.model_display_by_id,
        ),
        hud=_hud_from_game_view(view),
        interaction_request_id=_optional_string_value(
            projection.interaction,
            "request_id",
        ),
        selected_or_acting_entity_ids=tuple(
            _required_string_item("selected_or_acting_entity_id", value)
            for value in _required_list(
                projection.interaction,
                "selected_or_acting_entity_ids",
            )
        ),
        legal_candidate_refs=_canonical_candidate_refs(projection.interaction),
        measurement_overlays=_canonical_measurement_overlays(projection.interaction),
        path_overlays=_canonical_path_overlays(projection.interaction),
        render_hints=_canonical_render_hints(projection.render),
        hit_regions=_canonical_hit_regions(projection.render),
    )


def _legacy_fixture_battlefield_view(view: UiGameView) -> BattlefieldView:
    """Render pre-Contract-10 direct test fixtures, never engine payloads."""

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


def _hud_from_game_view(view: UiGameView) -> HudView:
    return HudView(
        phase_label=view.current_battle_phase or view.stage,
        active_player_id=view.active_player_id or "none",
        pending_decision_summary=_pending_decision_summary(view),
        event_log_lines=(),
    )


def _table_from_canonical_projection(
    *,
    mission_setup: JsonObject,
    width: float,
    height: float,
) -> TableView:
    mission_id = _optional_string_value(mission_setup, "mission_pool_entry_id") or "mission"
    terrain_layout_id = _optional_string_value(mission_setup, "terrain_layout_id")
    deployment_map_id = _optional_string_value(mission_setup, "deployment_map_id")
    return TableView(
        width=width,
        height=height,
        label=f"Live Core {mission_id}",
        terrain_layout_label=(
            None if terrain_layout_id is None else f"Terrain layout: {terrain_layout_id}"
        ),
        deployment_map_label=(
            None if deployment_map_id is None else f"Deployment map: {deployment_map_id}"
        ),
    )


def _canonical_deployment_zones(
    authoritative: JsonObject,
) -> tuple[DeploymentZoneView, ...]:
    zones_by_id = _json_object(
        "deployment_zones_by_id",
        authoritative.get("deployment_zones_by_id"),
    )
    zones: list[DeploymentZoneView] = []
    for zone_id, raw_zone in sorted(zones_by_id.items()):
        zone = _json_object("deployment zone", raw_zone)
        owner_player_id = _required_string(zone, "owner_player_id")
        shape = _json_object("deployment zone shape", zone.get("shape"))
        cutouts = tuple(
            tuple(
                _canonical_xy_point(_json_object("deployment zone cutout vertex", point))
                for point in _json_list_value("deployment zone polygon cutout", raw_polygon)
            )
            for raw_polygon in _required_list(shape, "polygon_cutouts")
        ) + tuple(
            _canonical_footprint(_json_object("deployment zone circle cutout", raw_circle))
            for raw_circle in _required_list(shape, "circle_cutouts")
        )
        polygons = _required_list(shape, "polygons")
        if not polygons:
            raise CoreProjectionRenderError("deployment zone must contain a polygon.")
        for index, raw_polygon in enumerate(polygons):
            polygon = tuple(
                _canonical_xy_point(_json_object("deployment zone vertex", point))
                for point in _json_list_value("deployment zone polygon", raw_polygon)
            )
            zones.append(
                DeploymentZoneView(
                    zone_id=zone_id if len(polygons) == 1 else f"{zone_id}:{index + 1}",
                    player_id=owner_player_id,
                    label=f"{owner_player_id} deployment",
                    polygon=polygon,
                    visible=True,
                    cutouts=cutouts,
                )
            )
    return tuple(zones)


def _canonical_objectives(authoritative: JsonObject) -> tuple[ObjectiveView, ...]:
    objectives_by_id = _json_object(
        "objectives_by_id",
        authoritative.get("objectives_by_id"),
    )
    return tuple(
        ObjectiveView(
            objective_id=objective_id,
            label=(
                _optional_string_value(objective, "objective_role") or _display_suffix(objective_id)
            )
            .replace("_", " ")
            .title(),
            position=_canonical_position(
                _json_object("objective position", objective.get("position"))
            ),
            radius=_required_positive_float(objective, "marker_diameter_inches") / 2.0,
        )
        for objective_id, objective in (
            (key, _json_object("objective", value))
            for key, value in sorted(objectives_by_id.items())
        )
    )


def _canonical_terrain(authoritative: JsonObject) -> tuple[TerrainFootprintView, ...]:
    terrain_areas_by_id = _json_object(
        "terrain_areas_by_id",
        authoritative.get("terrain_areas_by_id"),
    )
    terrain_features_by_id = _json_object(
        "terrain_features_by_id",
        authoritative.get("terrain_features_by_id"),
    )
    areas = tuple(
        TerrainFootprintView(
            terrain_id=terrain_id,
            label=_required_string(area, "classification"),
            footprint=_canonical_footprint(
                _json_object("terrain area footprint", area.get("footprint"))
            ),
            source_kind="terrain_area",
            logical_terrain_area_id=_required_string(area, "logical_terrain_area_id"),
        )
        for terrain_id, area in (
            (key, _json_object("terrain area", value))
            for key, value in sorted(terrain_areas_by_id.items())
        )
    )
    features = tuple(
        TerrainFootprintView(
            terrain_id=terrain_id,
            label=_required_string(feature, "terrain_feature_kind"),
            footprint=_canonical_footprint(
                _json_object("terrain feature footprint", feature.get("footprint"))
            ),
            source_kind="terrain_feature",
        )
        for terrain_id, feature in (
            (key, _json_object("terrain feature", value))
            for key, value in sorted(terrain_features_by_id.items())
        )
    )
    return areas + features


def _canonical_candidate_refs(interaction: JsonObject) -> tuple[tuple[str, str], ...]:
    return tuple(
        (
            _required_string(reference, "reference_kind"),
            _required_string(reference, "reference_id"),
        )
        for reference in (
            _json_object("legal candidate reference", value)
            for value in _required_list(interaction, "legal_candidate_refs")
        )
    )


def _canonical_measurement_overlays(
    interaction: JsonObject,
) -> tuple[MeasurementOverlayView, ...]:
    return tuple(
        MeasurementOverlayView(
            overlay_id=_required_string(overlay, "overlay_id"),
            start=_canonical_position(_json_object("measurement start", overlay.get("start"))),
            end=_canonical_position(_json_object("measurement end", overlay.get("end"))),
            distance_inches=_required_non_negative_float(overlay, "distance_inches"),
        )
        for overlay in (
            _json_object("measurement overlay", value)
            for value in _required_list(interaction, "measurement_overlays")
        )
    )


def _canonical_path_overlays(interaction: JsonObject) -> tuple[PathOverlayView, ...]:
    overlays: list[PathOverlayView] = []
    for value in _required_list(interaction, "path_overlays"):
        overlay = _json_object("path overlay", value)
        segments = tuple(
            _json_object("path segment", segment) for segment in _required_list(overlay, "segments")
        )
        if not segments:
            raise CoreProjectionRenderError("path overlay must contain a segment.")
        points = [
            _canonical_pose_position(_json_object("path segment start", segments[0].get("start")))
        ]
        for index, segment in enumerate(segments):
            if _required_string(segment, "segment_kind") != "line":
                raise CoreProjectionRenderError("Only line path overlay segments are supported.")
            start = _canonical_pose_position(
                _json_object("path segment start", segment.get("start"))
            )
            if start != points[-1]:
                raise CoreProjectionRenderError(
                    f"path overlay segment {index} does not continue the prior segment."
                )
            points.append(
                _canonical_pose_position(_json_object("path segment end", segment.get("end")))
            )
        overlays.append(
            PathOverlayView(
                overlay_id=_required_string(overlay, "overlay_id"),
                model_id=_required_string(overlay, "model_instance_id"),
                points=tuple(points),
            )
        )
    return tuple(overlays)


def _canonical_render_hints(render: JsonObject) -> tuple[RenderHintView, ...]:
    hints = _json_object("hints_by_entity_id", render.get("hints_by_entity_id"))
    return tuple(
        RenderHintView(
            entity_id=_required_matching_string(hint, "entity_id", entity_id),
            asset_id=_optional_string_value(hint, "asset_id"),
        )
        for entity_id, hint in (
            (key, _json_object("render hint", value)) for key, value in sorted(hints.items())
        )
    )


def _canonical_hit_regions(render: JsonObject) -> tuple[HitRegionView, ...]:
    regions = _json_object(
        "hit_regions_by_entity_id",
        render.get("hit_regions_by_entity_id"),
    )
    return tuple(
        HitRegionView(
            entity_id=_required_matching_string(region, "entity_id", entity_id),
            footprint=_canonical_footprint(_json_object("hit region shape", region.get("shape"))),
        )
        for entity_id, region in (
            (key, _json_object("hit region", value)) for key, value in sorted(regions.items())
        )
    )


def _canonical_units(
    *,
    authoritative: JsonObject,
    unit_display_by_id: JsonObject,
    model_display_by_id: JsonObject,
) -> tuple[UnitView, ...]:
    models_by_id = _json_object("models_by_id", authoritative.get("models_by_id"))
    grouped: dict[str, list[ModelBaseView]] = {}
    owner_by_unit_id: dict[str, str] = {}
    for model_id, raw_model in sorted(models_by_id.items()):
        model = _json_object("battlefield model", raw_model)
        state = _required_string(model, "state")
        if model.get("pose") is None:
            continue
        if state not in {"placed", "destroyed"}:
            raise CoreProjectionRenderError(f"Unsupported canonical model state: {state}.")
        unit_id = _required_string(model, "unit_instance_id")
        owner_by_unit_id[unit_id] = _required_string(model, "owner_player_id")
        grouped.setdefault(unit_id, []).append(
            _canonical_model(
                model_id=model_id,
                model=model,
                model_display_by_id=model_display_by_id,
            )
        )
    units: list[UnitView] = []
    for unit_id, models in sorted(grouped.items()):
        display = _json_object_if_present(unit_display_by_id, unit_id)
        label = (
            _optional_string_value(display, "unit_display_name") if display is not None else None
        )
        units.append(
            UnitView(
                unit_id=unit_id,
                player_id=owner_by_unit_id[unit_id],
                label=label or _display_suffix(unit_id),
                models=tuple(models),
            )
        )
    return tuple(units)


def _canonical_model(
    *,
    model_id: str,
    model: JsonObject,
    model_display_by_id: JsonObject,
) -> ModelBaseView:
    pose = _json_object("model pose", model.get("pose"))
    position = _json_object("model position", pose.get("position"))
    geometry = _json_object("model geometry", model.get("geometry"))
    support_shape = _json_object("model support shape", geometry.get("support_shape"))
    measurement_shapes = tuple(
        _json_object("model measurement shape", value)
        for value in _required_list(geometry, "measurement_shapes")
    )
    world_position = _canonical_position(position)
    facing_degrees = _required_float(pose, "facing_degrees")
    display = _json_object_if_present(model_display_by_id, model_id)
    return ModelBaseView(
        model_id=model_id,
        label=(
            _optional_string_value(display, "model_display_name") if display is not None else None
        )
        or _display_suffix(model_id),
        position=world_position,
        base_radius=_shape_display_radius(support_shape),
        base_movement_inches=_display_movement_inches(display),
        support_footprint=_model_shape_footprint(
            support_shape,
            world_position=world_position,
            facing_degrees=facing_degrees,
        ),
        measurement_footprints=tuple(
            _model_shape_footprint(
                shape,
                world_position=world_position,
                facing_degrees=facing_degrees,
            )
            for shape in measurement_shapes
        ),
    )


def _display_movement_inches(display: JsonObject | None) -> float | None:
    if display is None:
        return None
    characteristics = _json_object_if_present(display, "current_characteristics")
    if characteristics is None:
        return None
    movement = _json_object_if_present(characteristics, "M")
    if movement is None:
        return None
    value = movement.get("final")
    if type(value) not in {int, float}:
        return None
    movement_inches = float(cast(int | float, value))
    return movement_inches if movement_inches > 0.0 else None


def _shape_display_radius(shape: JsonObject) -> float:
    kind = _required_string(shape, "kind")
    if kind == "circle":
        return _required_positive_float(shape, "radius_inches")
    if kind in {"rectangle", "ellipse", "capsule"}:
        width = _required_positive_float(shape, "width_inches")
        length = _required_positive_float(shape, "length_inches")
        return math.hypot(width / 2.0, length / 2.0)
    if kind == "polygon":
        vertices = tuple(
            _canonical_xy_point(_json_object("shape vertex", value))
            for value in _required_list(shape, "vertices")
        )
        if not vertices:
            raise CoreProjectionRenderError("polygon support shape must contain vertices.")
        center = _shape_center(shape)
        return max(math.dist(center, point) for point in vertices)
    raise CoreProjectionRenderError(f"Unsupported canonical model support shape: {kind}.")


def _model_shape_footprint(
    shape: JsonObject,
    *,
    world_position: tuple[float, float],
    facing_degrees: float,
) -> tuple[tuple[float, float], ...]:
    """Transform one model-local physical shape into battlefield coordinates."""

    local_points = _model_local_shape_points(shape)
    facing = math.radians(facing_degrees)
    return tuple(
        (
            world_position[0] + (x * math.cos(facing)) - (y * math.sin(facing)),
            world_position[1] + (x * math.sin(facing)) + (y * math.cos(facing)),
        )
        for x, y in local_points
    )


def _model_local_shape_points(shape: JsonObject) -> tuple[tuple[float, float], ...]:
    kind = _required_string(shape, "kind")
    center = _optional_shape_center(shape)
    rotation = math.radians(_required_float(shape, "rotation_degrees"))
    if kind == "polygon":
        raw_points = tuple(
            _canonical_xy_point(_json_object("shape vertex", value))
            for value in _required_list(shape, "vertices")
        )
        if len(raw_points) < 3:
            raise CoreProjectionRenderError("polygon model shape must contain three vertices.")
        return tuple(
            _rotated_offset(center, point[0] - center[0], point[1] - center[1], rotation)
            for point in raw_points
        )
    if kind == "circle":
        radius = _required_positive_float(shape, "radius_inches")
        return tuple(
            (
                center[0] + radius * math.cos((2.0 * math.pi * index) / 32.0),
                center[1] + radius * math.sin((2.0 * math.pi * index) / 32.0),
            )
            for index in range(32)
        )
    width = _required_positive_float(shape, "width_inches")
    length = _required_positive_float(shape, "length_inches")
    unrotated: tuple[tuple[float, float], ...]
    if kind == "rectangle":
        unrotated = (
            (-width / 2.0, -length / 2.0),
            (width / 2.0, -length / 2.0),
            (width / 2.0, length / 2.0),
            (-width / 2.0, length / 2.0),
        )
    elif kind == "ellipse":
        unrotated = tuple(
            (
                (width / 2.0) * math.cos((2.0 * math.pi * index) / 32.0),
                (length / 2.0) * math.sin((2.0 * math.pi * index) / 32.0),
            )
            for index in range(32)
        )
    elif kind == "capsule":
        radius = width / 2.0
        straight_half = max(0.0, (length / 2.0) - radius)
        unrotated = tuple(
            (
                radius * math.cos(math.pi + (math.pi * index / 16.0)),
                -straight_half + radius * math.sin(math.pi + (math.pi * index / 16.0)),
            )
            for index in range(17)
        ) + tuple(
            (
                radius * math.cos(math.pi * index / 16.0),
                straight_half + radius * math.sin(math.pi * index / 16.0),
            )
            for index in range(17)
        )
    else:
        raise CoreProjectionRenderError(f"Unsupported canonical model shape: {kind}.")
    return tuple(_rotated_offset(center, x, y, rotation) for x, y in unrotated)


def _optional_shape_center(shape: JsonObject) -> tuple[float, float]:
    value = shape.get("center")
    if value is None:
        return (0.0, 0.0)
    return _canonical_xy_point(_json_object("shape center", value))


def _canonical_footprint(shape: JsonObject) -> tuple[tuple[float, float], ...]:
    kind = _required_string(shape, "kind")
    if kind == "polygon":
        footprint = tuple(
            _canonical_xy_point(_json_object("footprint vertex", value))
            for value in _required_list(shape, "vertices")
        )
        _validate_terrain_area_footprint(footprint)
        return footprint
    center = _shape_center(shape)
    rotation = math.radians(_required_float(shape, "rotation_degrees"))
    if kind == "circle":
        radius = _required_positive_float(shape, "radius_inches")
        return tuple(
            (
                center[0] + radius * math.cos((2.0 * math.pi * index) / 32.0),
                center[1] + radius * math.sin((2.0 * math.pi * index) / 32.0),
            )
            for index in range(32)
        )
    if kind == "rectangle":
        half_width = _required_positive_float(shape, "width_inches") / 2.0
        half_length = _required_positive_float(shape, "length_inches") / 2.0
        return tuple(
            _rotated_offset(center, x, y, rotation)
            for x, y in (
                (-half_width, -half_length),
                (half_width, -half_length),
                (half_width, half_length),
                (-half_width, half_length),
            )
        )
    if kind == "ellipse":
        half_width = _required_positive_float(shape, "width_inches") / 2.0
        half_length = _required_positive_float(shape, "length_inches") / 2.0
        return tuple(
            _rotated_offset(
                center,
                half_width * math.cos((2.0 * math.pi * index) / 32.0),
                half_length * math.sin((2.0 * math.pi * index) / 32.0),
                rotation,
            )
            for index in range(32)
        )
    raise CoreProjectionRenderError(f"Unsupported canonical terrain footprint: {kind}.")


def _shape_center(shape: JsonObject) -> tuple[float, float]:
    center = _json_object("shape center", shape.get("center"))
    return _canonical_xy_point(center)


def _rotated_offset(
    center: tuple[float, float],
    x: float,
    y: float,
    rotation: float,
) -> tuple[float, float]:
    return (
        center[0] + (x * math.cos(rotation)) - (y * math.sin(rotation)),
        center[1] + (x * math.sin(rotation)) + (y * math.cos(rotation)),
    )


def _canonical_position(payload: JsonObject) -> tuple[float, float]:
    return (_required_float(payload, "x_inches"), _required_float(payload, "y_inches"))


def _canonical_pose_position(payload: JsonObject) -> tuple[float, float]:
    return _canonical_position(_json_object("pose position", payload.get("position")))


def _canonical_xy_point(payload: JsonObject) -> tuple[float, float]:
    return (_required_float(payload, "x_inches"), _required_float(payload, "y_inches"))


def _json_list_value(name: str, payload: object) -> list[JsonValue]:
    if type(payload) is not list:
        raise CoreProjectionRenderError(f"{name} must be a JSON list.")
    return cast(list[JsonValue], payload)


def _json_object_if_present(payload: JsonObject, key: str) -> JsonObject | None:
    value = payload.get(key)
    if value is None:
        return None
    return _json_object(key, value)


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
    objective_marker_ids_by_area_id = _objective_marker_ids_by_terrain_area_id(mission_setup)
    terrain_areas = tuple(
        _terrain_area_from_payload(
            _json_object("terrain_area", value),
            objective_marker_ids_by_area_id=objective_marker_ids_by_area_id,
        )
        for value in _optional_list(mission_setup, "terrain_areas")
    )
    _validate_objective_links_reference_terrain_areas(
        objective_marker_ids_by_area_id=objective_marker_ids_by_area_id,
        terrain_areas=terrain_areas,
    )
    terrain_features = tuple(
        TerrainFootprintView(
            terrain_id=_required_string(feature, "feature_id"),
            label=_required_string(feature, "feature_kind"),
            footprint=_terrain_display_footprint(feature),
            source_kind=_TERRAIN_SOURCE_KIND_FEATURE,
        )
        for feature in (
            _json_object("terrain_feature", value)
            for value in _optional_list(mission_setup, "terrain_features")
        )
    )
    return terrain_areas + terrain_features


def _terrain_area_from_payload(
    area: JsonObject,
    *,
    objective_marker_ids_by_area_id: dict[str, tuple[str, ...]],
) -> TerrainFootprintView:
    terrain_area_id = _required_string(area, "terrain_area_id")
    classification = _required_string(area, "classification")
    footprint_template_id = _required_string(area, "footprint_template_id")
    _required_string(area, "terrain_feature_kind")
    _required_float(area, "center_x_inches")
    _required_float(area, "center_y_inches")
    _required_float(area, "rotation_degrees")
    _required_string(area, "local_transform")
    _required_string(area, "source_layout_id")
    _required_string(area, "source_id")
    return TerrainFootprintView(
        terrain_id=terrain_area_id,
        label=classification or footprint_template_id,
        footprint=_terrain_area_footprint(area),
        source_kind=_TERRAIN_SOURCE_KIND_AREA,
        objective_marker_ids=objective_marker_ids_by_area_id.get(terrain_area_id, ()),
    )


def _objective_marker_ids_by_terrain_area_id(
    mission_setup: JsonObject,
) -> dict[str, tuple[str, ...]]:
    marker_ids_by_area_id: dict[str, tuple[str, ...]] = {}
    for value in _optional_list(mission_setup, "objective_terrain_areas"):
        objective_terrain_area = _json_object("objective_terrain_area", value)
        objective_marker_id = _required_string(objective_terrain_area, "objective_marker_id")
        _required_string(objective_terrain_area, "objective_role")
        _required_string(objective_terrain_area, "source_id")
        terrain_area_ids = tuple(
            _non_empty_string("terrain_area_id", terrain_area_id_value)
            for terrain_area_id_value in _required_list(
                objective_terrain_area,
                "terrain_area_ids",
            )
        )
        if not terrain_area_ids:
            raise CoreProjectionRenderError(
                "objective_terrain_areas terrain_area_ids must not be empty."
            )
        for terrain_area_id in terrain_area_ids:
            if terrain_area_id in marker_ids_by_area_id:
                raise CoreProjectionRenderError(
                    "objective_terrain_areas must not link a terrain area to multiple "
                    "objective markers."
                )
            marker_ids_by_area_id[terrain_area_id] = (objective_marker_id,)
    return marker_ids_by_area_id


def _validate_objective_links_reference_terrain_areas(
    *,
    objective_marker_ids_by_area_id: dict[str, tuple[str, ...]],
    terrain_areas: tuple[TerrainFootprintView, ...],
) -> None:
    terrain_area_ids = {area.terrain_id for area in terrain_areas}
    unknown_area_ids = sorted(set(objective_marker_ids_by_area_id) - terrain_area_ids)
    if unknown_area_ids:
        raise CoreProjectionRenderError(
            f"objective_terrain_areas references unknown terrain area: {unknown_area_ids[0]}."
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
    if kind in {"oval", "rectangular"}:
        length = _required_positive_float(base_size, "length_mm")
        width = _required_positive_float(base_size, "width_mm")
        if kind == "rectangular":
            # The current renderer draws a circle; contain every rectangle corner.
            return math.hypot(length / 2.0, width / 2.0) / _MM_PER_INCH
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


def _terrain_area_footprint(area: JsonObject) -> tuple[tuple[float, float], ...]:
    footprint = tuple(
        _terrain_area_point_from_payload(value)
        for value in _required_list(area, "footprint_polygon")
    )
    _validate_terrain_area_footprint(footprint)
    return footprint


def _terrain_display_point_from_payload(value: JsonValue) -> tuple[float, float]:
    point = _json_object("terrain display point", value)
    return (
        _required_float(point, "x_inches"),
        _required_float(point, "y_inches"),
    )


def _terrain_area_point_from_payload(value: JsonValue) -> tuple[float, float]:
    point = _json_object("terrain area point", value)
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


def _validate_terrain_area_footprint(footprint: tuple[tuple[float, float], ...]) -> None:
    if len(footprint) < 3:
        raise CoreProjectionRenderError(
            "terrain area footprint_polygon must contain at least three points."
        )
    if footprint[0] == footprint[-1]:
        raise CoreProjectionRenderError("terrain area footprint_polygon must be unclosed.")
    if abs(_polygon_area(footprint)) <= _FOOTPRINT_AREA_TOLERANCE:
        raise CoreProjectionRenderError("terrain area footprint_polygon must have non-zero area.")


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


def _optional_list(payload: JsonObject, key: str) -> list[JsonValue]:
    value = payload.get(key)
    if value is None:
        return []
    if type(value) is not list:
        raise CoreProjectionRenderError(f"{key} must be a JSON list.")
    return value


def _required_string(payload: JsonObject, key: str) -> str:
    return _non_empty_string(key, payload.get(key))


def _non_empty_string(name: str, value: object) -> str:
    if type(value) is not str or not value:
        raise CoreProjectionRenderError(f"{name} must be a non-empty string.")
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


def _required_non_negative_float(payload: JsonObject, key: str) -> float:
    value = _required_float(payload, key)
    if value < 0.0:
        raise CoreProjectionRenderError(f"{key} must be non-negative.")
    return value


def _required_string_item(name: str, value: object) -> str:
    return _non_empty_string(name, value)


def _required_matching_string(payload: JsonObject, key: str, expected: str) -> str:
    actual = _required_string(payload, key)
    if actual != expected:
        raise CoreProjectionRenderError(f"{key} must match its map key {expected!r}.")
    return actual


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
