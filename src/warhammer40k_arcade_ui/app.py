"""Arcade application shell and launch path."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from importlib import import_module
from os import environ
from pathlib import Path
from typing import Any, Protocol, cast

from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.protocol import UiClientStatus
from warhammer40k_arcade_ui.diagnostics.crash_report import (
    CrashReportContext,
    CrashReportError,
    write_crash_report,
)
from warhammer40k_arcade_ui.diagnostics.forensic_trace import (
    ForensicTraceConfig,
    ForensicTraceWriter,
    build_trace_writer,
    trace_core_client,
)

logger = logging.getLogger(__name__)


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
    live_core_stop_phase: str | None = None,
    event_trace_level: str | None = None,
    event_trace_file: Path | None = None,
    event_trace_cfg_file: Path | None = None,
    event_trace_include: Sequence[str] | None = None,
    event_trace_exclude: Sequence[str] | None = None,
    event_trace_include_categories: Sequence[str] | None = None,
    event_trace_exclude_categories: Sequence[str] | None = None,
    trace_writer: ForensicTraceWriter | None = None,
    crash_report_context: CrashReportContext | None = None,
    crash_report_dir: Path | None = None,
) -> ArcadeWindow:
    """Create the application window without entering Arcade's event loop."""

    resolved_config = config or AppConfig()
    resolved_trace_writer = _resolve_trace_writer(
        event_trace_level=event_trace_level,
        event_trace_file=event_trace_file,
        event_trace_cfg_file=event_trace_cfg_file,
        event_trace_include=event_trace_include,
        event_trace_exclude=event_trace_exclude,
        event_trace_include_categories=event_trace_include_categories,
        event_trace_exclude_categories=event_trace_exclude_categories,
        trace_writer=trace_writer,
    )
    resolved_crash_context = _resolve_crash_context(
        crash_report_context=crash_report_context,
        runtime_mode=_runtime_mode(live_core_smoke, live_core_stop_phase),
        ui_prefs_path=ui_prefs_path,
        trace_writer=resolved_trace_writer,
    )
    if arcade_runtime is None:
        from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow

        if live_core_smoke:
            from warhammer40k_arcade_ui.core_client.live_smoke import (
                LiveCoreSmokeError,
                build_live_core_smoke_startup,
            )

            try:
                startup = build_live_core_smoke_startup(stop_at_phase=live_core_stop_phase)
            except LiveCoreSmokeError as exc:
                report_path = _write_startup_crash_report(
                    exception=exc,
                    context=resolved_crash_context.with_updates(
                        runtime_mode=_runtime_mode(True, live_core_stop_phase),
                        viewer_player_id="player-a",
                    ),
                    crash_report_dir=crash_report_dir,
                )
                return ArcadeWarhammerWindow(
                    config=resolved_config,
                    preferences_path=ui_prefs_path,
                    initial_status=UiClientStatus.invalid(
                        stage="setup",
                        violation_code="live_core_smoke_startup_failed",
                        message=_startup_failure_message(exc=exc, report_path=report_path),
                        field="startup",
                    ),
                    viewer_player_id="player-a",
                    trace_writer=resolved_trace_writer,
                    crash_report_context=resolved_crash_context.with_updates(
                        runtime_mode=_runtime_mode(True, live_core_stop_phase),
                        viewer_player_id="player-a",
                    ),
                    crash_report_dir=crash_report_dir,
                )
            return ArcadeWarhammerWindow(
                config=resolved_config,
                battlefield_view=startup.battlefield_view,
                preferences_path=ui_prefs_path,
                initial_status=startup.status,
                initial_game_view=startup.game_view,
                core_client=trace_core_client(startup.core_client, resolved_trace_writer),
                viewer_player_id=startup.viewer_player_id,
                event_cursor=startup.event_cursor,
                trace_writer=resolved_trace_writer,
                crash_report_context=resolved_crash_context.with_updates(
                    runtime_mode=_runtime_mode(True, live_core_stop_phase),
                    viewer_player_id=startup.viewer_player_id,
                    event_cursor=startup.event_cursor,
                ),
                crash_report_dir=crash_report_dir,
            )
        return ArcadeWarhammerWindow(
            config=resolved_config,
            preferences_path=ui_prefs_path,
            trace_writer=resolved_trace_writer,
            crash_report_context=resolved_crash_context.with_updates(runtime_mode="fake_fixture"),
            crash_report_dir=crash_report_dir,
        )

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
    live_core_stop_phase: str | None = None,
    event_trace_level: str | None = None,
    event_trace_file: Path | None = None,
    event_trace_cfg_file: Path | None = None,
    event_trace_include: Sequence[str] | None = None,
    event_trace_exclude: Sequence[str] | None = None,
    event_trace_include_categories: Sequence[str] | None = None,
    event_trace_exclude_categories: Sequence[str] | None = None,
    trace_writer: ForensicTraceWriter | None = None,
    crash_report_context: CrashReportContext | None = None,
    crash_report_dir: Path | None = None,
) -> None:
    """Create the Arcade window and start the event loop."""

    if arcade_runtime is None:
        create_window(
            config,
            ui_prefs_path=ui_prefs_path,
            live_core_smoke=live_core_smoke,
            live_core_stop_phase=live_core_stop_phase,
            event_trace_level=event_trace_level,
            event_trace_file=event_trace_file,
            event_trace_cfg_file=event_trace_cfg_file,
            event_trace_include=event_trace_include,
            event_trace_exclude=event_trace_exclude,
            event_trace_include_categories=event_trace_include_categories,
            event_trace_exclude_categories=event_trace_exclude_categories,
            trace_writer=trace_writer,
            crash_report_context=crash_report_context,
            crash_report_dir=crash_report_dir,
        )
        _load_arcade().run()
        return

    runtime = arcade_runtime
    create_window(
        config,
        runtime,
        ui_prefs_path=ui_prefs_path,
        live_core_smoke=live_core_smoke,
        live_core_stop_phase=live_core_stop_phase,
        event_trace_level=event_trace_level,
        event_trace_file=event_trace_file,
        event_trace_cfg_file=event_trace_cfg_file,
        event_trace_include=event_trace_include,
        event_trace_exclude=event_trace_exclude,
        event_trace_include_categories=event_trace_include_categories,
        event_trace_exclude_categories=event_trace_exclude_categories,
        trace_writer=trace_writer,
        crash_report_context=crash_report_context,
        crash_report_dir=crash_report_dir,
    )
    runtime.run()


def _resolve_trace_writer(
    *,
    event_trace_level: str | None,
    event_trace_file: Path | None,
    event_trace_cfg_file: Path | None,
    event_trace_include: Sequence[str] | None,
    event_trace_exclude: Sequence[str] | None,
    event_trace_include_categories: Sequence[str] | None,
    event_trace_exclude_categories: Sequence[str] | None,
    trace_writer: ForensicTraceWriter | None,
) -> ForensicTraceWriter:
    if trace_writer is not None:
        return trace_writer
    return build_trace_writer(
        ForensicTraceConfig.from_runtime(
            event_trace_level=event_trace_level,
            event_trace_file=event_trace_file,
            event_trace_cfg_file=event_trace_cfg_file,
            event_trace_include=event_trace_include,
            event_trace_exclude=event_trace_exclude,
            event_trace_include_categories=event_trace_include_categories,
            event_trace_exclude_categories=event_trace_exclude_categories,
            env=environ,
        )
    )


def _runtime_mode(live_core_smoke: bool, live_core_stop_phase: str | None) -> str:
    if live_core_smoke:
        if live_core_stop_phase is not None:
            return f"live_core_smoke:{live_core_stop_phase}"
        return "live_core_smoke"
    return "fake_fixture"


def _resolve_crash_context(
    *,
    crash_report_context: CrashReportContext | None,
    runtime_mode: str,
    ui_prefs_path: Path | None,
    trace_writer: ForensicTraceWriter,
) -> CrashReportContext:
    base = crash_report_context or CrashReportContext(runtime_mode=runtime_mode)
    return base.with_updates(
        runtime_mode=runtime_mode,
        preferences_path=ui_prefs_path,
        trace_path=trace_writer.trace_path,
    )


def _write_startup_crash_report(
    *,
    exception: Exception,
    context: CrashReportContext,
    crash_report_dir: Path | None,
) -> Path | None:
    try:
        return write_crash_report(
            exception=exception,
            context=context,
            report_dir=crash_report_dir,
        ).report_path
    except CrashReportError:
        logger.exception("Startup crash report capture failed.")
        return None


def _startup_failure_message(*, exc: Exception, report_path: Path | None) -> str:
    if report_path is None:
        return str(exc)
    return f"{exc} Crash report: {report_path}"
