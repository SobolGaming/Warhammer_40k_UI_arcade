"""Tests for opt-in forensic event tracing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import arcade
import pytest

from tests.support.gui_driver import GuiTestDriver
from warhammer40k_arcade_ui.core_client.protocol import JsonValue, validate_json_value
from warhammer40k_arcade_ui.debug_fixtures import phase6_debug_core_client
from warhammer40k_arcade_ui.diagnostics.forensic_trace import (
    ForensicTraceConfig,
    JsonLinesTraceWriter,
    TraceConfigurationError,
    TracePayloadError,
    build_trace_writer,
    trace_core_client,
)


def test_disabled_trace_produces_no_file(tmp_path: Path) -> None:
    trace_path = tmp_path / "event-trace.jsonl"
    writer = build_trace_writer(
        ForensicTraceConfig(level="off", trace_path=trace_path, ui_commit_sha="test-sha")
    )

    writer.write_event(category="test", event_name="test.disabled")

    assert not trace_path.exists()


def test_summary_trace_records_status_without_payload_body(tmp_path: Path) -> None:
    trace_path = tmp_path / "summary-trace.jsonl"
    writer = JsonLinesTraceWriter(
        ForensicTraceConfig(level="summary", trace_path=trace_path, ui_commit_sha="test-sha")
    )
    traced_client = trace_core_client(phase6_debug_core_client(), writer)

    traced_client.submit_finite(
        request_id="decision-request-phase6-debug-000001",
        selected_option_id="normal_move",
        result_id="ui-result-000001",
    )

    rows = _trace_rows(trace_path)
    response = _row_by_name(rows, "core.submit_finite.response")
    assert response["summary"] == {
        "decision_request_id": "decision-request-phase6-debug-000002",
        "invalid_diagnostic_count": 0,
        "message": None,
        "stage": "battle",
        "status_kind": "waiting_for_decision",
    }
    assert "payload" not in response


def test_payload_trace_records_json_safe_ui_core_payloads(tmp_path: Path) -> None:
    trace_path = tmp_path / "payload-trace.jsonl"
    writer = JsonLinesTraceWriter(
        ForensicTraceConfig(level="payload", trace_path=trace_path, ui_commit_sha="test-sha")
    )
    traced_client = trace_core_client(phase6_debug_core_client(), writer)

    view = traced_client.get_view("player_1")
    traced_client.submit_finite(
        request_id="decision-request-phase6-debug-000001",
        selected_option_id="advance",
        result_id="ui-result-000001",
    )

    rows = _trace_rows(trace_path)
    get_view_response = _row_by_name(rows, "core.get_view.response")
    submit_request = _row_by_name(rows, "core.submit_finite.request")
    get_view_payload = get_view_response["payload"]
    assert type(get_view_payload) is dict
    assert get_view_payload["game_id"] == view.game_id
    assert get_view_payload["viewer_player_id"] == "player_1"
    assert submit_request["payload"] == {
        "request_id": "decision-request-phase6-debug-000001",
        "result_id": "ui-result-000001",
        "selected_option_id": "advance",
    }


def test_trace_writer_rejects_non_json_safe_payload(tmp_path: Path) -> None:
    writer = JsonLinesTraceWriter(
        ForensicTraceConfig(level="payload", trace_path=tmp_path / "bad-trace.jsonl")
    )

    with pytest.raises(TracePayloadError):
        writer.write_event(
            category="test",
            event_name="test.bad_payload",
            payload=cast(JsonValue, {"bad": object()}),
        )


def test_trace_redacts_token_like_fields_and_does_not_emit_secret_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_should_not_appear")
    trace_path = tmp_path / "redacted-trace.jsonl"
    writer = JsonLinesTraceWriter(ForensicTraceConfig(level="payload", trace_path=trace_path))

    writer.write_event(
        category="test",
        event_name="test.redaction",
        summary={"github_token": "ghp_summary_secret"},
        payload={"nested": {"access_token": "payload-secret"}, "safe": "visible"},
    )

    trace_text = trace_path.read_text(encoding="utf-8")
    assert "ghp_should_not_appear" not in trace_text
    assert "ghp_summary_secret" not in trace_text
    assert "payload-secret" not in trace_text
    assert "visible" in trace_text


def test_trace_writer_rotates_when_size_limit_is_reached(tmp_path: Path) -> None:
    trace_path = tmp_path / "rotating-trace.jsonl"
    writer = JsonLinesTraceWriter(
        ForensicTraceConfig(level="summary", trace_path=trace_path, max_bytes=1)
    )

    writer.write_event(category="test", event_name="test.first")
    writer.write_event(category="test", event_name="test.second")

    assert trace_path.exists()
    assert (tmp_path / "rotating-trace.1.jsonl").exists()


def test_trace_exclude_filter_suppresses_named_events(tmp_path: Path) -> None:
    trace_path = tmp_path / "filtered-trace.jsonl"
    writer = JsonLinesTraceWriter(
        ForensicTraceConfig(
            level="summary",
            trace_path=trace_path,
            excluded_event_names=frozenset({"ui.mouse_motion"}),
        )
    )

    writer.write_event(category="ui_input", event_name="ui.mouse_motion")
    writer.write_event(category="ui_input", event_name="ui.key_press")

    event_names = {_required_trace_string(row, "event_name") for row in _trace_rows(trace_path)}
    assert event_names == {"ui.key_press"}


def test_trace_include_filter_allows_only_named_events(tmp_path: Path) -> None:
    trace_path = tmp_path / "included-trace.jsonl"
    writer = JsonLinesTraceWriter(
        ForensicTraceConfig(
            level="summary",
            trace_path=trace_path,
            included_event_names=frozenset({"ui.key_press"}),
        )
    )

    writer.write_event(category="ui_input", event_name="ui.mouse_motion")
    writer.write_event(category="ui_input", event_name="ui.key_press")

    event_names = {_required_trace_string(row, "event_name") for row in _trace_rows(trace_path)}
    assert event_names == {"ui.key_press"}


def test_trace_category_filters_apply_after_event_include(tmp_path: Path) -> None:
    trace_path = tmp_path / "category-trace.jsonl"
    writer = JsonLinesTraceWriter(
        ForensicTraceConfig(
            level="summary",
            trace_path=trace_path,
            included_categories=frozenset({"core_client"}),
            excluded_event_names=frozenset({"core.get_view.request"}),
        )
    )

    writer.write_event(category="ui_input", event_name="ui.key_press")
    writer.write_event(category="core_client", event_name="core.get_view.request")
    writer.write_event(category="core_client", event_name="core.get_view.response")

    event_names = {_required_trace_string(row, "event_name") for row in _trace_rows(trace_path)}
    assert event_names == {"core.get_view.response"}


def test_trace_config_file_supplies_filters_and_output_options(tmp_path: Path) -> None:
    trace_path = tmp_path / "cfg-trace.jsonl"
    config_path = tmp_path / "event-trace-cfg.json"
    config_path.write_text(
        json.dumps(
            {
                "event_trace_cfg": {
                    "level": "summary",
                    "file": str(trace_path),
                    "max_bytes": 1234,
                    "include": ["ui.key_press", "ui.key_release"],
                    "exclude": ["ui.key_release"],
                    "include_categories": ["core_client"],
                    "exclude_categories": ["render"],
                }
            }
        ),
        encoding="utf-8",
    )

    config = ForensicTraceConfig.from_runtime(event_trace_cfg_file=config_path, env={})

    assert config.level == "summary"
    assert config.trace_path == trace_path
    assert config.max_bytes == 1234
    assert config.included_event_names == frozenset({"ui.key_press", "ui.key_release"})
    assert config.excluded_event_names == frozenset({"ui.key_release"})
    assert config.included_categories == frozenset({"core_client"})
    assert config.excluded_categories == frozenset({"render"})


def test_trace_config_file_rejects_non_string_filter_values(tmp_path: Path) -> None:
    config_path = tmp_path / "event-trace-cfg.json"
    config_path.write_text(
        json.dumps({"event_trace_cfg": {"level": "summary", "include": ["ui.key_press", 3]}}),
        encoding="utf-8",
    )

    with pytest.raises(TraceConfigurationError):
        ForensicTraceConfig.from_runtime(event_trace_cfg_file=config_path, env={})


def test_window_and_core_events_are_traced_through_gui_driver(tmp_path: Path) -> None:
    trace_path = tmp_path / "gui-trace.jsonl"
    writer = JsonLinesTraceWriter(
        ForensicTraceConfig(level="payload", trace_path=trace_path, ui_commit_sha="test-sha")
    )
    driver = GuiTestDriver.launch(core_mode="phase6_debug", trace_writer=writer)
    try:
        driver.click_world((7.0, 18.0))
        driver.press_key(arcade.key.ENTER)
        driver.release_key(arcade.key.ENTER)
    finally:
        driver.close()

    event_names = {_required_trace_string(row, "event_name") for row in _trace_rows(trace_path)}
    assert "ui.mouse_press" in event_names
    assert "ui.key_press" in event_names
    assert "ui.key_release" in event_names
    assert "ui.command_dispatch" in event_names
    assert "ui.finite_submission_attempt" in event_names
    assert "core.submit_finite.request" in event_names
    assert "core.get_view.response" in event_names


def _trace_rows(trace_path: Path) -> list[dict[str, JsonValue]]:
    rows: list[dict[str, JsonValue]] = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = validate_json_value(json.loads(line))
        assert type(value) is dict
        rows.append(value)
    return rows


def _row_by_name(rows: list[dict[str, JsonValue]], event_name: str) -> dict[str, JsonValue]:
    for row in rows:
        if row["event_name"] == event_name:
            return row
    raise AssertionError(f"Trace row not found: {event_name}")


def _required_trace_string(row: dict[str, JsonValue], key: str) -> str:
    value = row[key]
    assert type(value) is str
    return value
