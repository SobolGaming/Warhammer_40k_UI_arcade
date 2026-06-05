"""Smoke tests for the command-line entry point."""

from __future__ import annotations

from pathlib import Path

import pytest

from warhammer40k_arcade_ui import app, main
from warhammer40k_arcade_ui.config import AppConfig


class FakeWindow:
    """Test double for an Arcade window."""

    def __init__(self) -> None:
        self.background_color: object | None = None


class FakeColorPalette:
    """Test double for Arcade color constants."""

    def __init__(self) -> None:
        self.dark_slate_gray = object()

    @property
    def DARK_SLATE_GRAY(self) -> object:
        return self.dark_slate_gray


class FakeArcadeRuntime:
    """Test double for the Arcade module surface used by the app."""

    def __init__(self) -> None:
        self.color = FakeColorPalette()
        self.calls: list[str] = []
        self.window: FakeWindow | None = None

    def Window(self, *, width: int, height: int, title: str, resizable: bool) -> FakeWindow:
        assert width == 1280
        assert height == 800
        assert title == "Warhammer 40k Arcade UI"
        assert resizable is True
        self.calls.append("Window")
        self.window = FakeWindow()
        return self.window

    def run(self) -> None:
        self.calls.append("run")


def test_main_configures_logging_then_runs_app(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, Path | None, bool | None, str | None, Path | None, Path | None]] = []

    def fake_configure_logging() -> None:
        calls.append(("configure_logging", None, None, None, None, None))

    def fake_run_app(
        *,
        ui_prefs_path: Path | None = None,
        live_core_smoke: bool = False,
        event_trace_level: str | None = None,
        event_trace_file: Path | None = None,
        trace_writer: object | None = None,
        crash_report_context: object | None = None,
        crash_report_dir: Path | None = None,
    ) -> None:
        assert trace_writer is not None
        assert crash_report_context is not None
        calls.append(
            (
                "run_app",
                ui_prefs_path,
                live_core_smoke,
                event_trace_level,
                event_trace_file,
                crash_report_dir,
            )
        )

    monkeypatch.setattr(main, "configure_logging", fake_configure_logging)
    monkeypatch.setattr(main, "run_app", fake_run_app)

    main.main(
        [
            "--ui-prefs",
            "docs/preferences/keyboard-heavy.yaml",
            "--live-core-smoke",
            "--event-trace",
            "payload",
            "--event-trace-file",
            "/tmp/ui-trace.jsonl",
            "--crash-report-dir",
            "/tmp/ui-crashes",
        ]
    )

    assert calls == [
        ("configure_logging", None, None, None, None, None),
        (
            "run_app",
            Path("docs/preferences/keyboard-heavy.yaml"),
            True,
            "payload",
            Path("/tmp/ui-trace.jsonl"),
            Path("/tmp/ui-crashes"),
        ),
    ]


def test_run_app_creates_window_then_starts_arcade() -> None:
    runtime = FakeArcadeRuntime()

    app.run_app(arcade_runtime=runtime, ui_prefs_path=Path("docs/preferences/default.yaml"))

    assert runtime.calls == ["Window", "run"]
    assert runtime.window is not None
    assert runtime.window.background_color is runtime.color.DARK_SLATE_GRAY


def test_create_window_accepts_explicit_config() -> None:
    runtime = FakeArcadeRuntime()
    config = AppConfig()

    created_window = app.create_window(config=config, arcade_runtime=runtime)

    assert runtime.calls == ["Window"]
    assert created_window is runtime.window


def test_parse_args_accepts_optional_ui_preferences_path() -> None:
    parsed = main.parse_args(
        [
            "--ui-prefs",
            "/tmp/profile.yaml",
            "--live-core-smoke",
            "--event-trace",
            "summary",
            "--event-trace-file",
            "/tmp/trace.jsonl",
            "--crash-report-dir",
            "/tmp/crashes",
        ]
    )

    assert parsed.ui_prefs_path == Path("/tmp/profile.yaml")
    assert parsed.live_core_smoke is True
    assert parsed.event_trace_level == "summary"
    assert parsed.event_trace_file == Path("/tmp/trace.jsonl")
    assert parsed.crash_report_dir == Path("/tmp/crashes")


def test_phase7_debug_env_alias_enables_debug_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(app.PHASE6_DEBUG_ENV_VAR, raising=False)
    monkeypatch.setenv(app.PHASE7_DEBUG_ENV_VAR, "1")

    assert app.phase_debug_enabled() is True
