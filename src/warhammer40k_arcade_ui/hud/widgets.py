"""Arcade GUI widgets for HUD zone placeholders."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import arcade.gui
from arcade.types import Color

from warhammer40k_arcade_ui.hud.layouts import HudLayoutView

PANEL_BACKGROUND = Color(14, 18, 20, 122)
PANEL_BORDER = Color(164, 177, 170, 148)


def layout_signature(layout: HudLayoutView) -> tuple[object, ...]:
    """Return a stable signature for deciding when the widget shell must rebuild."""

    return (
        layout.preset_id,
        layout.viewport_width_px,
        layout.viewport_height_px,
        tuple(
            (
                region.zone_id,
                region.rect.x,
                region.rect.y,
                region.rect.width,
                region.rect.height,
                region.collapsed,
            )
            for region in layout.regions
        ),
    )


def install_hud_zone_widgets(
    *,
    manager: arcade.gui.UIManager,
    layout: HudLayoutView,
) -> None:
    """Replace a UI manager's contents with placeholder widgets for HUD zones."""

    clear_manager = cast(Callable[[], None], getattr(manager, "clear"))  # noqa: B009
    add_widget = cast(Callable[..., object], getattr(manager, "add"))  # noqa: B009
    clear_manager()
    for region in layout.regions:
        panel = arcade.gui.UIWidget(
            x=region.rect.x,
            y=region.rect.y,
            width=region.rect.width,
            height=region.rect.height,
        ).with_background(color=PANEL_BACKGROUND)
        panel = panel.with_border(width=1, color=PANEL_BORDER)
        add_widget(panel, layer=0)
