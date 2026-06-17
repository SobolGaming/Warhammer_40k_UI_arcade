"""Tests for converting core viewer projections into render view models."""

from __future__ import annotations

import math
from typing import cast

import pytest

from warhammer40k_arcade_ui.core_client.protocol import JsonObject, UiGameView
from warhammer40k_arcade_ui.render.core_projection import (
    CoreProjectionRenderError,
    battlefield_view_from_game_view,
)


def test_core_projection_uses_structured_terrain_display_geometry() -> None:
    expected_footprint = _rotated_rectangle_points(
        width=6.0,
        depth=4.0,
        rotation_degrees=135.0,
        origin=(26.6, 20.6),
    )
    view = battlefield_view_from_game_view(
        _game_view(
            _terrain_feature(
                center=(23.064466, 21.307107),
                size=(7.071068, 7.071068),
                display_footprint=expected_footprint,
            )
        )
    )

    footprint = view.terrain[0].footprint

    assert len(footprint) == len(expected_footprint)
    for actual_point, expected_point in zip(footprint, expected_footprint, strict=True):
        assert math.isclose(actual_point[0], expected_point[0], rel_tol=0.0, abs_tol=1.0e-9)
        assert math.isclose(actual_point[1], expected_point[1], rel_tol=0.0, abs_tol=1.0e-9)
    assert not math.isclose(footprint[1][0], footprint[0][0], rel_tol=0.0, abs_tol=1.0e-9)
    assert not math.isclose(footprint[1][1], footprint[0][1], rel_tol=0.0, abs_tol=1.0e-9)


def test_core_projection_uses_typed_terrain_areas_when_features_are_empty() -> None:
    footprint = _axis_aligned_rectangle_points(center=(20.0, 12.0), size=(6.0, 4.0))
    view = battlefield_view_from_game_view(
        _game_view(
            None,
            objective_markers=[
                {
                    "objective_marker_id": "objective-alpha",
                    "name": "Alpha",
                    "x_inches": 20.0,
                    "y_inches": 12.0,
                    "marker_diameter_mm": 40.0,
                }
            ],
            terrain_areas=[
                _terrain_area(
                    terrain_area_id="terrain-area-alpha",
                    classification="light",
                    footprint_template_id="light-6x4",
                    center=(20.0, 12.0),
                    rotation_degrees=45.0,
                    local_transform="identity",
                    footprint=footprint,
                )
            ],
            objective_terrain_areas=[
                {
                    "objective_marker_id": "objective-alpha",
                    "objective_role": "center",
                    "terrain_area_ids": ["terrain-area-alpha"],
                    "source_id": "objective-alpha-source",
                }
            ],
        )
    )

    assert view.terrain[0].terrain_id == "terrain-area-alpha"
    assert view.terrain[0].label == "light"
    assert view.terrain[0].source_kind == "terrain_area"
    assert view.terrain[0].objective_marker_ids == ("objective-alpha",)
    assert view.terrain[0].footprint == footprint


def test_core_projection_supports_mixed_terrain_areas_and_features() -> None:
    view = battlefield_view_from_game_view(
        _game_view(
            _terrain_feature(
                center=(10.0, 20.0),
                size=(6.0, 4.0),
            ),
            terrain_areas=[
                _terrain_area(
                    terrain_area_id="terrain-area-alpha",
                    classification="dense",
                    footprint_template_id="dense-10x5",
                    center=(30.0, 12.0),
                    rotation_degrees=0.0,
                    local_transform="mirror_y_axis",
                    footprint=_axis_aligned_rectangle_points(
                        center=(30.0, 12.0),
                        size=(10.0, 5.0),
                    ),
                )
            ],
        )
    )

    assert [terrain.source_kind for terrain in view.terrain] == [
        "terrain_area",
        "terrain_feature",
    ]
    assert [terrain.label for terrain in view.terrain] == ["dense", "ruins"]


def test_core_projection_rejects_malformed_terrain_area_footprint() -> None:
    with pytest.raises(
        CoreProjectionRenderError,
        match="terrain area footprint_polygon must be unclosed",
    ):
        battlefield_view_from_game_view(
            _game_view(
                None,
                terrain_areas=[
                    _terrain_area(
                        terrain_area_id="terrain-area-alpha",
                        classification="light",
                        footprint_template_id="light-6x4",
                        center=(20.0, 12.0),
                        rotation_degrees=0.0,
                        local_transform="identity",
                        footprint=((17.0, 10.0), (23.0, 10.0), (17.0, 10.0)),
                    )
                ],
            )
        )


def test_core_projection_rejects_unknown_objective_terrain_area_link() -> None:
    with pytest.raises(
        CoreProjectionRenderError,
        match="objective_terrain_areas references unknown terrain area: terrain-area-missing",
    ):
        battlefield_view_from_game_view(
            _game_view(
                None,
                terrain_areas=[
                    _terrain_area(
                        terrain_area_id="terrain-area-alpha",
                        classification="light",
                        footprint_template_id="light-6x4",
                        center=(20.0, 12.0),
                        rotation_degrees=0.0,
                        local_transform="identity",
                        footprint=_axis_aligned_rectangle_points(
                            center=(20.0, 12.0),
                            size=(6.0, 4.0),
                        ),
                    )
                ],
                objective_terrain_areas=[
                    {
                        "objective_marker_id": "objective-alpha",
                        "objective_role": "center",
                        "terrain_area_ids": ["terrain-area-missing"],
                        "source_id": "objective-alpha-source",
                    }
                ],
            )
        )


def test_core_projection_rejects_missing_terrain_display_geometry() -> None:
    terrain_feature = _terrain_feature(
        center=(10.0, 20.0),
        size=(6.0, 4.0),
    )
    del terrain_feature["display_geometry"]

    with pytest.raises(
        CoreProjectionRenderError,
        match=r"terrain_feature\.display_geometry must be a JSON object",
    ):
        battlefield_view_from_game_view(_game_view(terrain_feature))


def test_core_projection_rejects_malformed_terrain_display_geometry() -> None:
    terrain_feature = _terrain_feature(
        center=(10.0, 20.0),
        size=(6.0, 4.0),
    )
    terrain_feature["display_geometry"] = {
        "schema_version": "terrain-display-v1",
        "coordinate_space": "battlefield_inches",
        "display_template_id": "custom-template",
        "footprint_kind": "circle",
        "footprint_polygon": [
            {"x_inches": 7.0, "y_inches": 18.0},
            {"x_inches": 13.0, "y_inches": 18.0},
            {"x_inches": 13.0, "y_inches": 22.0},
        ],
    }

    with pytest.raises(
        CoreProjectionRenderError,
        match="terrain display geometry footprint_kind is unsupported",
    ):
        battlefield_view_from_game_view(_game_view(terrain_feature))


def test_core_projection_uses_axis_aligned_display_geometry_when_provided() -> None:
    view = battlefield_view_from_game_view(
        _game_view(
            _terrain_feature(
                center=(10.0, 20.0),
                size=(6.0, 4.0),
            )
        )
    )

    assert view.terrain[0].footprint == (
        (7.0, 18.0),
        (13.0, 18.0),
        (13.0, 22.0),
        (7.0, 22.0),
    )


def test_core_projection_uses_structured_deployment_zone_shape() -> None:
    view = battlefield_view_from_game_view(
        _game_view(
            _terrain_feature(
                center=(10.0, 20.0),
                size=(6.0, 4.0),
            ),
            deployment_zones=[
                {
                    "deployment_zone_id": "deployment-zone-alpha",
                    "player_id": "player-a",
                    "shape": {
                        "polygons": [
                            {
                                "vertices": [
                                    {"x": 0.0, "y": 0.0},
                                    {"x": 18.0, "y": 0.0},
                                    {"x": 18.0, "y": 44.0},
                                    {"x": 0.0, "y": 44.0},
                                ]
                            }
                        ],
                        "cutouts": [],
                    },
                }
            ],
        )
    )

    assert view.deployment_zones[0].polygon == (
        (0.0, 0.0),
        (18.0, 0.0),
        (18.0, 44.0),
        (0.0, 44.0),
    )


def test_core_projection_allows_empty_unit_list_during_deployment() -> None:
    view = battlefield_view_from_game_view(
        _game_view(
            _terrain_feature(
                center=(10.0, 20.0),
                size=(6.0, 4.0),
            ),
            placed_armies=[],
        )
    )

    assert view.units == ()
    assert view.table.width == 60.0
    assert view.table.height == 44.0


def test_core_projection_preserves_terrain_and_deployment_layout_labels() -> None:
    view = battlefield_view_from_game_view(
        _game_view(
            _terrain_feature(
                center=(10.0, 20.0),
                size=(6.0, 4.0),
            )
        )
    )

    assert view.table.terrain_layout_label == "Terrain layout: layout-1"
    assert view.table.deployment_map_label == "Deployment map: deployment-map-a"


def test_core_projection_uses_model_display_base_size_and_movement_hint() -> None:
    view = battlefield_view_from_game_view(
        _game_view(
            _terrain_feature(
                center=(10.0, 20.0),
                size=(6.0, 4.0),
            ),
            model_display_by_id={
                "unit-alpha:model-001": {
                    "model_instance_id": "unit-alpha:model-001",
                    "base_size": {
                        "base_size_id": "base-size:core-vehicle-monster",
                        "kind": "circular",
                        "diameter_mm": 120.0,
                        "length_mm": None,
                        "width_mm": None,
                    },
                    "base_characteristics": {
                        "M": {
                            "label": "M",
                            "characteristic": "movement",
                            "final": 10,
                            "base": 10,
                            "raw": 10,
                            "display_value": '10"',
                        }
                    },
                }
            },
        )
    )

    model = view.units[0].models[0]

    assert math.isclose(model.base_radius, 120.0 / 25.4 / 2.0)
    assert model.base_movement_inches == 10.0


def test_core_projection_rejects_source_terrain_footprint_bound_mismatch() -> None:
    with pytest.raises(
        CoreProjectionRenderError,
        match="terrain display footprint does not match projected footprint bounds",
    ):
        battlefield_view_from_game_view(
            _game_view(
                _terrain_feature(
                    center=(22.0, 21.0),
                    size=(7.071068, 7.071068),
                    display_footprint=_rotated_rectangle_points(
                        width=6.0,
                        depth=4.0,
                        rotation_degrees=135.0,
                        origin=(26.6, 20.6),
                    ),
                )
            )
        )


def _game_view(
    terrain_feature: JsonObject | None,
    *,
    deployment_zones: list[JsonObject] | None = None,
    objective_markers: list[JsonObject] | None = None,
    terrain_areas: list[JsonObject] | None = None,
    objective_terrain_areas: list[JsonObject] | None = None,
    placed_armies: list[JsonObject] | None = None,
    model_display_by_id: JsonObject | None = None,
) -> UiGameView:
    terrain_features = [] if terrain_feature is None else [terrain_feature]
    return UiGameView(
        viewer_player_id="player-a",
        game_id="projection-test-game",
        stage="battle",
        battle_round=1,
        active_player_id="player-a",
        current_setup_step=None,
        current_battle_phase="movement",
        player_ids=("player-a", "player-b"),
        battlefield_state=cast(
            JsonObject,
            {
                "battlefield_id": "projection-test-battlefield",
                "placed_armies": _default_placed_armies()
                if placed_armies is None
                else placed_armies,
                "removed_model_ids": [],
            },
        ),
        mission_setup=cast(
            JsonObject,
            {
                "mission_pool_entry_id": "mission-a",
                "terrain_layout_id": "layout-1",
                "deployment_map_id": "deployment-map-a",
                "battlefield_width_inches": 60.0,
                "battlefield_depth_inches": 44.0,
                "deployment_zones": [] if deployment_zones is None else deployment_zones,
                "objective_markers": [] if objective_markers is None else objective_markers,
                "terrain_areas": [] if terrain_areas is None else terrain_areas,
                "objective_terrain_areas": []
                if objective_terrain_areas is None
                else objective_terrain_areas,
                "terrain_features": terrain_features,
            },
        ),
        public_secondary_mission_choices=(),
        public_secondary_mission_card_states=(),
        public_command_point_ledgers=(),
        public_victory_point_ledgers=(),
        public_stratagem_use_records=(),
        pending_decision=None,
        pending_proposal=None,
        event_count=1,
        model_display_by_id={} if model_display_by_id is None else model_display_by_id,
    )


def _default_placed_armies() -> list[JsonObject]:
    return cast(
        list[JsonObject],
        [
            {
                "army_id": "army-alpha",
                "player_id": "player-a",
                "unit_placements": [
                    {
                        "army_id": "army-alpha",
                        "player_id": "player-a",
                        "unit_instance_id": "unit-alpha",
                        "model_placements": [
                            {
                                "army_id": "army-alpha",
                                "player_id": "player-a",
                                "unit_instance_id": "unit-alpha",
                                "model_instance_id": "unit-alpha:model-001",
                                "pose": {
                                    "position": {"x": 6.0, "y": 6.0, "z": 0.0},
                                    "facing": {"degrees": 0.0},
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    )


def _terrain_feature(
    *,
    center: tuple[float, float],
    size: tuple[float, float],
    display_footprint: tuple[tuple[float, float], ...] | None = None,
) -> JsonObject:
    footprint = (
        _axis_aligned_rectangle_points(center=center, size=size)
        if display_footprint is None
        else display_footprint
    )
    return cast(
        JsonObject,
        {
            "feature_id": "layout-1-slot-09-ruin-rect-6x4-variant1",
            "feature_kind": "ruins",
            "footprint_center_x_inches": center[0],
            "footprint_center_y_inches": center[1],
            "footprint_width_inches": size[0],
            "footprint_depth_inches": size[1],
            "display_geometry": {
                "schema_version": "terrain-display-v1",
                "coordinate_space": "battlefield_inches",
                "display_template_id": "test-terrain-template",
                "footprint_kind": "polygon",
                "footprint_polygon": [
                    {"x_inches": point[0], "y_inches": point[1]} for point in footprint
                ],
            },
            "walls": [],
            "floors": [],
            "source_id": "custom-terrain-source",
        },
    )


def _terrain_area(
    *,
    terrain_area_id: str,
    classification: str,
    footprint_template_id: str,
    center: tuple[float, float],
    rotation_degrees: float,
    local_transform: str,
    footprint: tuple[tuple[float, float], ...],
) -> JsonObject:
    return cast(
        JsonObject,
        {
            "terrain_area_id": terrain_area_id,
            "classification": classification,
            "footprint_template_id": footprint_template_id,
            "terrain_feature_kind": "ruins",
            "center_x_inches": center[0],
            "center_y_inches": center[1],
            "rotation_degrees": rotation_degrees,
            "local_transform": local_transform,
            "footprint_polygon": [
                {"x_inches": point[0], "y_inches": point[1]} for point in footprint
            ],
            "source_layout_id": "layout-1",
            "source_id": f"source:{terrain_area_id}",
            "source_transform": "identity",
            "symmetry_axis": "none",
        },
    )


def _axis_aligned_rectangle_points(
    *,
    center: tuple[float, float],
    size: tuple[float, float],
) -> tuple[tuple[float, float], ...]:
    half_width = size[0] / 2.0
    half_height = size[1] / 2.0
    return (
        (center[0] - half_width, center[1] - half_height),
        (center[0] + half_width, center[1] - half_height),
        (center[0] + half_width, center[1] + half_height),
        (center[0] - half_width, center[1] + half_height),
    )


def _rotated_rectangle_points(
    *,
    width: float,
    depth: float,
    rotation_degrees: float,
    origin: tuple[float, float],
) -> tuple[tuple[float, float], ...]:
    radians = math.radians(rotation_degrees)
    cos_r = math.cos(radians)
    sin_r = math.sin(radians)
    origin_x, origin_y = origin
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
