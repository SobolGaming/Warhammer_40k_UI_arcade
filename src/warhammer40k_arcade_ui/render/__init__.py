"""Rendering foundation for the Arcade UI client."""

from warhammer40k_arcade_ui.render.camera import WorldCamera
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.render.primitives import (
    CirclePrimitive,
    PolygonPrimitive,
    RenderPrimitive,
    TextPrimitive,
    build_hud_primitives,
    build_world_primitives,
)
from warhammer40k_arcade_ui.render.view_models import (
    BattlefieldView,
    DeploymentZoneView,
    HudView,
    ModelBaseView,
    ObjectiveView,
    RenderViewModelError,
    TableView,
    TerrainFootprintView,
    UnitView,
)

__all__ = [
    "BattlefieldView",
    "CirclePrimitive",
    "DeploymentZoneView",
    "HudView",
    "ModelBaseView",
    "ObjectiveView",
    "PolygonPrimitive",
    "RenderPrimitive",
    "RenderViewModelError",
    "TableView",
    "TerrainFootprintView",
    "TextPrimitive",
    "UnitView",
    "WorldCamera",
    "build_hud_primitives",
    "build_world_primitives",
    "default_battlefield_view",
]
