"""Arcade application shell and launch path."""

from __future__ import annotations

from importlib import import_module
from os import environ
from pathlib import Path
from typing import Any, Protocol, cast

from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.protocol import UiClientStatus

PHASE6_DEBUG_ENV_VAR = "WARHAMMER40K_ARCADE_UI_DEBUG_PHASE6"
PHASE7_DEBUG_ENV_VAR = "WARHAMMER40K_ARCADE_UI_DEBUG_PHASE7"


class ArcadeWindow(Protocol):
    """Small protocol for the Arcade window surface used by tests and launch code."""

    background_color: Any


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
    ui_prefs_path: Path | None = None,
    live_core_smoke: bool = False,
) -> ArcadeWindow:
    """Create the application window without entering Arcade's event loop."""

    resolved_config = config or AppConfig()
    if arcade_runtime is None:
        from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow

        if live_core_smoke:
            from warhammer40k_arcade_ui.core_client.live_smoke import (
                LiveCoreSmokeError,
                build_live_core_smoke_startup,
            )

            try:
                startup = build_live_core_smoke_startup()
            except LiveCoreSmokeError as exc:
                return ArcadeWarhammerWindow(
                    config=resolved_config,
                    preferences_path=ui_prefs_path,
                    initial_status=UiClientStatus.invalid(
                        stage="setup",
                        violation_code="live_core_smoke_startup_failed",
                        message=str(exc),
                        field="startup",
                    ),
                    viewer_player_id="player-a",
                )
            return ArcadeWarhammerWindow(
                config=resolved_config,
                battlefield_view=startup.battlefield_view,
                preferences_path=ui_prefs_path,
                initial_status=startup.status,
                core_client=startup.core_client,
                viewer_player_id=startup.viewer_player_id,
                event_cursor=startup.event_cursor,
            )
        if phase_debug_enabled():
            from warhammer40k_arcade_ui.debug_fixtures import (
                phase6_debug_core_client,
                phase6_debug_pending_decision,
            )

            return ArcadeWarhammerWindow(
                config=resolved_config,
                preferences_path=ui_prefs_path,
                pending_decision=phase6_debug_pending_decision(),
                core_client=phase6_debug_core_client(),
                viewer_player_id="player_1",
            )
        return ArcadeWarhammerWindow(config=resolved_config, preferences_path=ui_prefs_path)

    runtime = arcade_runtime
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
    ui_prefs_path: Path | None = None,
    live_core_smoke: bool = False,
) -> None:
    """Create the Arcade window and start the event loop."""

    if arcade_runtime is None:
        create_window(config, ui_prefs_path=ui_prefs_path, live_core_smoke=live_core_smoke)
        _load_arcade().run()
        return

    runtime = arcade_runtime
    create_window(config, runtime, ui_prefs_path=ui_prefs_path, live_core_smoke=live_core_smoke)
    runtime.run()


def phase_debug_enabled() -> bool:
    """Return whether any deterministic phase debug fixture is enabled."""

    return environ.get(PHASE6_DEBUG_ENV_VAR) == "1" or environ.get(PHASE7_DEBUG_ENV_VAR) == "1"
