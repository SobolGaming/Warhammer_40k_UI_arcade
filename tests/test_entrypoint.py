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
    calls: list[tuple[str, Path | None]] = []

    def fake_configure_logging() -> None:
        calls.append(("configure_logging", None))

    def fake_run_app(*, ui_prefs_path: Path | None = None) -> None:
        calls.append(("run_app", ui_prefs_path))

    monkeypatch.setattr(main, "configure_logging", fake_configure_logging)
    monkeypatch.setattr(main, "run_app", fake_run_app)

    main.main(["--ui-prefs", "docs/preferences/keyboard-heavy.yaml"])

    assert calls == [
        ("configure_logging", None),
        ("run_app", Path("docs/preferences/keyboard-heavy.yaml")),
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
    parsed = main.parse_args(["--ui-prefs", "/tmp/profile.yaml"])

    assert parsed.ui_prefs_path == Path("/tmp/profile.yaml")


def test_phase7_debug_env_alias_enables_debug_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(app.PHASE6_DEBUG_ENV_VAR, raising=False)
    monkeypatch.setenv(app.PHASE7_DEBUG_ENV_VAR, "1")

    assert app.phase_debug_enabled() is True
