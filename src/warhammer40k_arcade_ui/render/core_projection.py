"""Render view construction from core viewer projections."""

from __future__ import annotations

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
            polygon=_rectangle_polygon(
                min_x=_required_float(zone, "min_x"),
                min_y=_required_float(zone, "min_y"),
                max_x=_required_float(zone, "max_x"),
                max_y=_required_float(zone, "max_y"),
            ),
            visible=True,
        )
        for zone in (
            _json_object("deployment_zone", value)
            for value in _required_list(mission_setup, "deployment_zones")
        )
    )


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
            footprint=_centered_rectangle_polygon(
                center_x=_required_float(feature, "footprint_center_x_inches"),
                center_y=_required_float(feature, "footprint_center_y_inches"),
                width=_required_positive_float(feature, "footprint_width_inches"),
                height=_required_positive_float(feature, "footprint_depth_inches"),
            ),
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
    if not units:
        raise CoreProjectionRenderError("battlefield_state must contain at least one unit.")
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


def _display_suffix(value: str) -> str:
    suffix = value.rsplit(":", 1)[-1]
    return suffix if suffix else value
