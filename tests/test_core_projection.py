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


def test_core_projection_uses_source_rotated_terrain_footprint() -> None:
    view = battlefield_view_from_game_view(
        _game_view(
            _terrain_feature(
                center=(23.064466, 21.307107),
                size=(7.071068, 7.071068),
                source_id=(
                    "gw-11e-chapter-approved-2025-26:layout-1:slot-09:"
                    "ruin_rect_6x4_variant1:rotation-135.000000:origin-26.600-20.600"
                ),
            )
        )
    )

    footprint = view.terrain[0].footprint

    expected_footprint = _rotated_rectangle_points(
        width=6.0,
        depth=4.0,
        rotation_degrees=135.0,
        origin=(26.6, 20.6),
    )
    assert len(footprint) == len(expected_footprint)
    for actual_point, expected_point in zip(footprint, expected_footprint, strict=True):
        assert math.isclose(actual_point[0], expected_point[0], rel_tol=0.0, abs_tol=1.0e-9)
        assert math.isclose(actual_point[1], expected_point[1], rel_tol=0.0, abs_tol=1.0e-9)
    assert not math.isclose(footprint[1][0], footprint[0][0], rel_tol=0.0, abs_tol=1.0e-9)
    assert not math.isclose(footprint[1][1], footprint[0][1], rel_tol=0.0, abs_tol=1.0e-9)


def test_core_projection_falls_back_to_axis_aligned_terrain_footprint() -> None:
    view = battlefield_view_from_game_view(
        _game_view(
            _terrain_feature(
                center=(10.0, 20.0),
                size=(6.0, 4.0),
                source_id="custom-terrain-source",
            )
        )
    )

    assert view.terrain[0].footprint == (
        (7.0, 18.0),
        (13.0, 18.0),
        (13.0, 22.0),
        (7.0, 22.0),
    )


def test_core_projection_rejects_source_terrain_footprint_bound_mismatch() -> None:
    with pytest.raises(
        CoreProjectionRenderError,
        match="terrain source footprint does not match projected footprint bounds",
    ):
        battlefield_view_from_game_view(
            _game_view(
                _terrain_feature(
                    center=(22.0, 21.0),
                    size=(7.071068, 7.071068),
                    source_id=(
                        "gw-11e-chapter-approved-2025-26:layout-1:slot-09:"
                        "ruin_rect_6x4_variant1:rotation-135.000000:origin-26.600-20.600"
                    ),
                )
            )
        )


def _game_view(terrain_feature: JsonObject) -> UiGameView:
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
                "placed_armies": [
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
                "removed_model_ids": [],
            },
        ),
        mission_setup=cast(
            JsonObject,
            {
                "mission_pool_entry_id": "mission-a",
                "terrain_layout_id": "layout-1",
                "battlefield_width_inches": 60.0,
                "battlefield_depth_inches": 44.0,
                "deployment_zones": [],
                "objective_markers": [],
                "terrain_features": [terrain_feature],
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
    )


def _terrain_feature(
    *,
    center: tuple[float, float],
    size: tuple[float, float],
    source_id: str,
) -> JsonObject:
    return cast(
        JsonObject,
        {
            "feature_id": "layout-1-slot-09-ruin-rect-6x4-variant1",
            "feature_kind": "ruins",
            "footprint_center_x_inches": center[0],
            "footprint_center_y_inches": center[1],
            "footprint_width_inches": size[0],
            "footprint_depth_inches": size[1],
            "walls": [],
            "floors": [],
            "source_id": source_id,
        },
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
