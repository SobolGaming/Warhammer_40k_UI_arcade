"""Tests for crash diagnostic bundle generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import arcade

from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonValue,
    UiClientProtocolError,
    UiClientStatus,
    UiEventDelta,
    UiGameView,
)
from warhammer40k_arcade_ui.debug_fixtures import phase6_debug_pending_decision
from warhammer40k_arcade_ui.diagnostics.crash_report import (
    CrashReportContext,
    CrashReportResult,
    write_crash_report,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow


def test_crash_report_captures_schema_stack_metadata_and_trace_tail(tmp_path: Path) -> None:
    trace_path = tmp_path / "event-trace.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps({"event_name": "ui.key_press", "request_id": "request-1"}),
                json.dumps({"event_name": "core.get_view.response", "status_kind": "waiting"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = _write_report_for_value_error(tmp_path=tmp_path, trace_path=trace_path)

    report = _read_report(result.report_path)
    assert report["schema_version"] == "1"
    assert report["exception"]["type"] == "ValueError"
    assert report["runtime"]["runtime_mode"] == "test_mode"
    assert report["runtime"]["preferences_source"] == "default.yaml"
    assert report["runtime"]["request_id"] == "request-1"
    assert report["ui"]["package_name"] == "warhammer40k-arcade-ui"
    stack_trace = cast(list[object], report["exception"]["stack_trace"])
    assert any("controlled crash" in str(line) for line in stack_trace)
    trace_tail = cast(dict[str, Any], report["forensic_trace"])
    assert trace_tail["path"] == str(trace_path)
    colocated_trace_path = result.bundle_dir / "event-trace.jsonl"
    assert trace_tail["colocated_path"] == str(colocated_trace_path)
    assert colocated_trace_path.exists()
    assert colocated_trace_path.read_text(encoding="utf-8") == trace_path.read_text(
        encoding="utf-8"
    )
    rows = cast(list[dict[str, Any]], trace_tail["rows"])
    assert rows[-1]["event_name"] == "core.get_view.response"


def test_crash_report_redacts_token_like_launch_args(tmp_path: Path) -> None:
    result = _write_report_for_runtime_error(tmp_path)

    text = result.report_path.read_text(encoding="utf-8")
    assert "ghp_should_not_appear" not in text
    assert "plain_secret" not in text
    assert "env_secret_should_not_appear" not in text
    assert "visible" in text


def test_fatal_window_error_writes_report_and_exposes_report_path(tmp_path: Path) -> None:
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=640, window_height=480),
        preferences=default_preferences(),
        pending_decision=phase6_debug_pending_decision(),
        core_client=FailingCoreClient(),
        crash_report_context=CrashReportContext(
            runtime_mode="test_window",
            preferences_source="injected preferences",
        ),
        crash_report_dir=tmp_path / "crashes",
    )
    try:
        window.on_key_press(arcade.key.ENTER, 0)

        report_path = window.last_crash_report_path
        assert report_path is not None
        assert report_path.exists()
        assert str(report_path) in window.finite_state.status_message
        report = _read_report(report_path)
        assert report["exception"]["type"] == "UiClientProtocolError"
        assert report["runtime"]["runtime_mode"] == "test_window"
        assert report["runtime"]["preferences_source"] == "injected preferences"
    finally:
        window.close()


def test_ordinary_authoritative_invalid_diagnostic_does_not_create_report(tmp_path: Path) -> None:
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=640, window_height=480),
        preferences=default_preferences(),
        pending_decision=phase6_debug_pending_decision(),
        crash_report_dir=tmp_path / "crashes",
    )
    try:
        window.on_key_press(arcade.key.ENTER, 0)

        assert window.last_crash_report_path is None
        assert not list((tmp_path / "crashes").glob("crash-*"))
        assert window.finite_state.status_kind == "invalid"
        assert window.finite_state.diagnostics[0].violation_code == "no_core_client"
    finally:
        window.close()


def _read_report(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert type(value) is dict
    return cast(dict[str, Any], value)


def _write_report_for_value_error(*, tmp_path: Path, trace_path: Path) -> CrashReportResult:
    try:
        _raise_value_error()
    except ValueError as exc:
        return write_crash_report(
            exception=exc,
            context=CrashReportContext(
                runtime_mode="test_mode",
                launch_args=("--ui-prefs", "docs/preferences/default.yaml"),
                preferences_source="default.yaml",
                viewer_player_id="player_1",
                request_id="request-1",
                status_kind="waiting",
                event_cursor=7,
                trace_path=trace_path,
            ),
            report_dir=tmp_path / "crashes",
            env={},
        )
    raise AssertionError("Expected controlled ValueError.")


def _write_report_for_runtime_error(tmp_path: Path) -> CrashReportResult:
    try:
        _raise_runtime_error()
    except RuntimeError as exc:
        return write_crash_report(
            exception=exc,
            context=CrashReportContext(
                launch_args=(
                    "--github-token",
                    "ghp_should_not_appear",
                    "--password=plain_secret",
                    "--safe",
                    "visible",
                )
            ),
            report_dir=tmp_path / "crashes",
            env={"GITHUB_TOKEN": "env_secret_should_not_appear"},
        )
    raise AssertionError("Expected controlled RuntimeError.")


def _raise_value_error() -> None:
    raise ValueError("controlled crash")


def _raise_runtime_error() -> None:
    raise RuntimeError("redaction check")


class FailingCoreClient:
    """Core client that fails at the finite submission boundary."""

    def start_game(self, config: object) -> UiClientStatus:
        del config
        raise AssertionError("start_game should not be called.")

    def advance_until_decision_or_terminal(self) -> UiClientStatus:
        raise AssertionError("advance_until_decision_or_terminal should not be called.")

    def get_view(self, viewer_player_id: str) -> UiGameView:
        del viewer_player_id
        raise AssertionError("get_view should not be called.")

    def get_events_since(self, cursor: int, viewer_player_id: str) -> UiEventDelta:
        del cursor, viewer_player_id
        raise AssertionError("get_events_since should not be called.")

    def submit_finite(
        self,
        *,
        request_id: str,
        selected_option_id: str,
        result_id: str | None = None,
    ) -> UiClientStatus:
        del request_id, selected_option_id, result_id
        raise UiClientProtocolError("missing required request_id")

    def submit_movement_payload(
        self,
        *,
        request_id: str,
        payload: JsonValue,
        result_id: str | None = None,
    ) -> UiClientStatus:
        del request_id, payload, result_id
        raise AssertionError("submit_movement_payload should not be called.")
