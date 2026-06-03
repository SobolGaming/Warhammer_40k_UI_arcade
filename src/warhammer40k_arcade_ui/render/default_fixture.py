"""Deterministic fixture battlefield used before engine projections drive rendering."""

from __future__ import annotations

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


def default_battlefield_view() -> BattlefieldView:
    """Return a small Strike Force table fixture for launch-time inspection."""

    return BattlefieldView(
        table=TableView(width=60.0, height=44.0, label="Strike Force 60 x 44"),
        deployment_zones=(
            DeploymentZoneView(
                zone_id="player_1_deployment",
                player_id="player_1",
                label="Player 1 Deployment",
                polygon=((0.0, 0.0), (10.0, 0.0), (10.0, 44.0), (0.0, 44.0)),
                visible=True,
            ),
            DeploymentZoneView(
                zone_id="player_2_deployment",
                player_id="player_2",
                label="Player 2 Deployment",
                polygon=((50.0, 0.0), (60.0, 0.0), (60.0, 44.0), (50.0, 44.0)),
                visible=True,
            ),
        ),
        objectives=(
            ObjectiveView(
                objective_id="objective_alpha",
                label="A",
                position=(30.0, 22.0),
                radius=3.0,
            ),
            ObjectiveView(
                objective_id="objective_bravo",
                label="B",
                position=(18.0, 12.0),
                radius=3.0,
            ),
            ObjectiveView(
                objective_id="objective_charlie",
                label="C",
                position=(42.0, 32.0),
                radius=3.0,
            ),
        ),
        terrain=(
            TerrainFootprintView(
                terrain_id="ruin_west",
                label="Ruin",
                footprint=((13.0, 24.0), (24.0, 24.0), (24.0, 36.0), (13.0, 36.0)),
            ),
            TerrainFootprintView(
                terrain_id="crater_east",
                label="Crater",
                footprint=((37.0, 8.0), (48.0, 9.0), (46.0, 18.0), (36.0, 17.0)),
            ),
            TerrainFootprintView(
                terrain_id="shipping_container",
                label="Container",
                footprint=((27.0, 5.0), (34.0, 5.0), (34.0, 9.0), (27.0, 9.0)),
            ),
        ),
        units=(
            UnitView(
                unit_id="intercessor_squad",
                player_id="player_1",
                label="Intercessors",
                models=(
                    ModelBaseView(
                        model_id="intercessor_1",
                        label="I1",
                        position=(7.0, 18.0),
                        base_radius=0.63,
                    ),
                    ModelBaseView(
                        model_id="intercessor_2",
                        label="I2",
                        position=(7.0, 22.0),
                        base_radius=0.63,
                    ),
                    ModelBaseView(
                        model_id="intercessor_3",
                        label="I3",
                        position=(7.0, 26.0),
                        base_radius=0.63,
                    ),
                ),
            ),
            UnitView(
                unit_id="guardian_squad",
                player_id="player_2",
                label="Guardians",
                models=(
                    ModelBaseView(
                        model_id="guardian_1",
                        label="G1",
                        position=(53.0, 18.0),
                        base_radius=0.63,
                    ),
                    ModelBaseView(
                        model_id="guardian_2",
                        label="G2",
                        position=(53.0, 22.0),
                        base_radius=0.63,
                    ),
                    ModelBaseView(
                        model_id="guardian_3",
                        label="G3",
                        position=(53.0, 26.0),
                        base_radius=0.63,
                    ),
                ),
            ),
        ),
        hud=HudView(
            phase_label="Fixture: Command Phase",
            active_player_id="player_1",
            pending_decision_summary="No pending engine decision",
            event_log_lines=("Fixture battlefield loaded", "Awaiting core projection integration"),
        ),
    )
