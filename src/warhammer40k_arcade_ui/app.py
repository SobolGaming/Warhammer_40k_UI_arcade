"""Arcade application shell for the Phase 0 bootstrap."""

from __future__ import annotations

from importlib import import_module
from typing import Protocol, cast

from warhammer40k_arcade_ui.config import AppConfig


class ArcadeWindow(Protocol):
    """Small protocol for the Arcade window surface used by Phase 0."""

    background_color: object


class ArcadeWindowFactory(Protocol):
    """Callable shape for `arcade.Window`."""

    def __call__(self, *, width: int, height: int, title: str, resizable: bool) -> ArcadeWindow:
        """Create an Arcade window."""

        ...


class ArcadeColorPalette(Protocol):
    """Color constants consumed by the blank window."""

    @property
    def DARK_SLATE_GRAY(self) -> object:
        """Dark slate gray color constant."""

        ...


class ArcadeRuntime(Protocol):
    """Minimal Arcade module surface needed by this bootstrap app."""

    @property
    def Window(self) -> ArcadeWindowFactory:
        """Window constructor."""

        ...

    @property
    def color(self) -> ArcadeColorPalette:
        """Arcade color palette."""

        ...

    def run(self) -> None:
        """Start Arcade's event loop."""

        ...


def _load_arcade() -> ArcadeRuntime:
    """Load Arcade lazily so non-rendering tests remain headless-safe."""

    return cast(ArcadeRuntime, import_module("arcade"))


def create_window(
    config: AppConfig | None = None,
    arcade_runtime: ArcadeRuntime | None = None,
) -> ArcadeWindow:
    """Create the application window without entering Arcade's event loop."""

    resolved_config = config or AppConfig()
    runtime = arcade_runtime or _load_arcade()
    window = runtime.Window(
        width=resolved_config.window_width,
        height=resolved_config.window_height,
        title=resolved_config.title,
        resizable=resolved_config.resizable,
    )
    window.background_color = runtime.color.DARK_SLATE_GRAY
    return window


def run_app(
    config: AppConfig | None = None,
    arcade_runtime: ArcadeRuntime | None = None,
) -> None:
    """Create a blank Arcade window and start the event loop."""

    runtime = arcade_runtime or _load_arcade()
    create_window(config, runtime)
    runtime.run()
