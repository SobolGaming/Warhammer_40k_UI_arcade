"""Opt-in forensic event tracing for UI/core interactions."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from importlib import metadata
from os import environ
from pathlib import Path
from typing import Literal, Protocol, cast

from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    JsonValue,
    UiClientProtocolError,
    UiClientStatus,
    UiCoreClient,
    UiEventDelta,
    UiGameView,
    validate_json_value,
)

EVENT_TRACE_ENV = "EVENT_TRACE"
EVENT_TRACE_FILE_ENV = "EVENT_TRACE_FILE"
EVENT_TRACE_DIR_ENV = "EVENT_TRACE_DIR"
EVENT_TRACE_MAX_BYTES_ENV = "EVENT_TRACE_MAX_BYTES"
DEFAULT_TRACE_MAX_BYTES = 5_000_000
TRACE_SCHEMA_VERSION = "1"
REDACTED_VALUE = "[REDACTED]"
TRACE_PACKAGE_NAME = "warhammer40k-arcade-ui"

type TraceLevel = Literal["off", "summary", "payload", "render"]

_TRACE_LEVELS: tuple[TraceLevel, ...] = ("off", "summary", "payload", "render")
_SENSITIVE_KEY_PARTS = (
    "token",
    "secret",
    "authorization",
    "password",
    "credential",
    "api_key",
    "apikey",
    "access_token",
    "github_token",
)


class TraceConfigurationError(ValueError):
    """Raised when forensic trace runtime configuration is invalid."""


class TracePayloadError(ValueError):
    """Raised when a trace event cannot be represented as JSON-safe data."""


@dataclass(frozen=True, slots=True)
class TraceContext:
    """Optional per-event context included with each trace row."""

    viewer_player_id: str | None = None
    game_id: str | None = None
    request_id: str | None = None
    status_kind: str | None = None
    event_cursor: int | None = None


@dataclass(frozen=True, slots=True)
class ForensicTraceConfig:
    """Resolved forensic tracing configuration."""

    level: TraceLevel = "off"
    trace_path: Path | None = None
    max_bytes: int = DEFAULT_TRACE_MAX_BYTES
    ui_commit_sha: str | None = None
    ui_release_version: str | None = None

    @classmethod
    def from_runtime(
        cls,
        *,
        event_trace_level: str | None = None,
        event_trace_file: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> ForensicTraceConfig:
        """Resolve trace configuration from CLI overrides and environment variables."""

        environment = environ if env is None else env
        raw_level = event_trace_level
        if raw_level is None:
            raw_level = environment.get(EVENT_TRACE_ENV)
        level = parse_trace_level(raw_level)
        max_bytes = _parse_max_bytes(environment.get(EVENT_TRACE_MAX_BYTES_ENV))
        if level == "off":
            return cls(
                level=level,
                max_bytes=max_bytes,
                ui_commit_sha=_ui_commit_sha(environment),
                ui_release_version=_ui_release_version(),
            )
        trace_path = event_trace_file
        if trace_path is None:
            raw_trace_file = environment.get(EVENT_TRACE_FILE_ENV)
            if raw_trace_file is not None and raw_trace_file.strip():
                trace_path = Path(raw_trace_file)
        if trace_path is None:
            trace_dir = _trace_directory(environment)
            trace_path = trace_dir / _timestamped_trace_filename()
        return cls(
            level=level,
            trace_path=trace_path,
            max_bytes=max_bytes,
            ui_commit_sha=_ui_commit_sha(environment),
            ui_release_version=_ui_release_version(),
        )

    @property
    def enabled(self) -> bool:
        """Return whether this config should emit trace rows."""

        return self.level != "off" and self.trace_path is not None

    @property
    def includes_payload(self) -> bool:
        """Return whether full payload bodies should be emitted."""

        return self.level in ("payload", "render")

    @property
    def includes_render(self) -> bool:
        """Return whether high-level render/frame markers should be emitted."""

        return self.level == "render"


class ForensicTraceWriter(Protocol):
    """Trace sink used by UI and core-client boundary hooks."""

    @property
    def enabled(self) -> bool:
        """Return whether writes should emit rows."""

        ...

    @property
    def level(self) -> TraceLevel:
        """Current trace level."""

        ...

    @property
    def trace_path(self) -> Path | None:
        """Resolved output file path when tracing is enabled."""

        ...

    def write_event(
        self,
        *,
        category: str,
        event_name: str,
        summary: JsonObject | None = None,
        payload: JsonValue | None = None,
        context: TraceContext | None = None,
    ) -> None:
        """Write a single forensic trace event."""

        ...


class NoOpTraceWriter:
    """Trace writer used when tracing is disabled."""

    @property
    def enabled(self) -> bool:
        """Return whether writes should emit rows."""

        return False

    @property
    def level(self) -> TraceLevel:
        """Current trace level."""

        return "off"

    @property
    def trace_path(self) -> Path | None:
        """Resolved output file path when tracing is enabled."""

        return None

    def write_event(
        self,
        *,
        category: str,
        event_name: str,
        summary: JsonObject | None = None,
        payload: JsonValue | None = None,
        context: TraceContext | None = None,
    ) -> None:
        """Discard trace event data."""

        del category, event_name, summary, payload, context


@dataclass(slots=True)
class JsonLinesTraceWriter:
    """JSON Lines trace writer with deterministic redaction and simple rotation."""

    config: ForensicTraceConfig

    @property
    def enabled(self) -> bool:
        """Return whether writes should emit rows."""

        return self.config.enabled

    @property
    def level(self) -> TraceLevel:
        """Current trace level."""

        return self.config.level

    @property
    def trace_path(self) -> Path | None:
        """Resolved output file path when tracing is enabled."""

        return self.config.trace_path

    def write_event(
        self,
        *,
        category: str,
        event_name: str,
        summary: JsonObject | None = None,
        payload: JsonValue | None = None,
        context: TraceContext | None = None,
    ) -> None:
        """Write a single trace row to the configured JSON Lines file."""

        if not self.enabled:
            return
        trace_path = self.trace_path
        if trace_path is None:
            raise TraceConfigurationError("Enabled trace writer requires a trace_path.")
        row = self._trace_row(
            category=category,
            event_name=event_name,
            summary=summary,
            payload=payload,
            context=context,
        )
        line = json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        self._rotate_if_needed(trace_path=trace_path, next_line_size=len(line.encode("utf-8")))
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with trace_path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    def _trace_row(
        self,
        *,
        category: str,
        event_name: str,
        summary: JsonObject | None,
        payload: JsonValue | None,
        context: TraceContext | None,
    ) -> JsonObject:
        row: JsonObject = {
            "schema_version": TRACE_SCHEMA_VERSION,
            "category": _non_empty_trace_string("category", category),
            "event_name": _non_empty_trace_string("event_name", event_name),
            "level": self.level,
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "monotonic_seconds": time.monotonic(),
            "summary": _redacted_json_object(summary or {}),
        }
        if self.config.ui_commit_sha is not None:
            row["ui_commit_sha"] = self.config.ui_commit_sha
        if self.config.ui_release_version is not None:
            row["ui_release_version"] = self.config.ui_release_version
        if context is not None:
            _apply_context(row=row, context=context)
        if self.config.includes_payload and payload is not None:
            row["payload"] = redact_json_value(payload)
        try:
            return cast(JsonObject, validate_json_value(row))
        except UiClientProtocolError as exc:
            raise TracePayloadError(f"Trace event is not JSON-safe: {event_name}") from exc

    def _rotate_if_needed(self, *, trace_path: Path, next_line_size: int) -> None:
        if self.config.max_bytes <= 0 or not trace_path.exists():
            return
        if trace_path.stat().st_size + next_line_size <= self.config.max_bytes:
            return
        rotated_path = _rotated_trace_path(trace_path)
        rotated_path.unlink(missing_ok=True)
        trace_path.replace(rotated_path)


@dataclass(slots=True)
class TracedCoreClient:
    """Trace wrapper for the UI-facing core client facade."""

    inner: UiCoreClient
    trace_writer: ForensicTraceWriter

    def start_game(self, config: object) -> UiClientStatus:
        """Start a game session and trace the resulting status."""

        self.trace_writer.write_event(
            category="core_client",
            event_name="core.start_game.request",
            summary={"config_type": type(config).__name__},
        )
        status = self.inner.start_game(config)
        self._trace_status_response(event_name="core.start_game.response", status=status)
        return status

    def advance_until_decision_or_terminal(self) -> UiClientStatus:
        """Advance engine lifecycle and trace the resulting status."""

        self.trace_writer.write_event(
            category="core_client",
            event_name="core.advance_until_decision_or_terminal.request",
        )
        status = self.inner.advance_until_decision_or_terminal()
        self._trace_status_response(
            event_name="core.advance_until_decision_or_terminal.response",
            status=status,
        )
        return status

    def get_view(self, viewer_player_id: str) -> UiGameView:
        """Return a viewer-scoped game projection and trace the payload."""

        self.trace_writer.write_event(
            category="core_client",
            event_name="core.get_view.request",
            summary={"viewer_player_id": viewer_player_id},
            context=TraceContext(viewer_player_id=viewer_player_id),
        )
        view = self.inner.get_view(viewer_player_id)
        self.trace_writer.write_event(
            category="core_client",
            event_name="core.get_view.response",
            summary={
                "viewer_player_id": view.viewer_player_id,
                "game_id": view.game_id,
                "stage": view.stage,
                "battle_round": view.battle_round,
                "event_count": view.event_count,
                "has_pending_decision": view.pending_decision is not None,
                "has_pending_proposal": view.pending_proposal is not None,
            },
            payload=json_value_from_object(view),
            context=TraceContext(
                viewer_player_id=view.viewer_player_id,
                game_id=view.game_id,
                request_id=_view_request_id(view),
                event_cursor=view.event_count,
            ),
        )
        return view

    def get_events_since(self, cursor: int, viewer_player_id: str) -> UiEventDelta:
        """Return a viewer-scoped event delta and trace the payload."""

        self.trace_writer.write_event(
            category="core_client",
            event_name="core.get_events_since.request",
            summary={"cursor": cursor, "viewer_player_id": viewer_player_id},
            context=TraceContext(viewer_player_id=viewer_player_id, event_cursor=cursor),
        )
        delta = self.inner.get_events_since(cursor, viewer_player_id)
        self.trace_writer.write_event(
            category="core_client",
            event_name="core.get_events_since.response",
            summary={
                "cursor": delta.cursor,
                "next_cursor": delta.next_cursor,
                "event_count": len(delta.events),
                "viewer_player_id": delta.viewer_player_id,
            },
            payload=json_value_from_object(delta),
            context=TraceContext(
                viewer_player_id=delta.viewer_player_id,
                event_cursor=delta.next_cursor,
            ),
        )
        return delta

    def submit_finite(
        self,
        *,
        request_id: str,
        selected_option_id: str,
        result_id: str,
    ) -> UiClientStatus:
        """Submit an engine-provided finite option and trace request/response."""

        request_payload: JsonObject = {
            "request_id": request_id,
            "selected_option_id": selected_option_id,
            "result_id": result_id,
        }
        self.trace_writer.write_event(
            category="core_client",
            event_name="core.submit_finite.request",
            summary={
                "request_id": request_id,
                "selected_option_id": selected_option_id,
                "result_id": result_id,
            },
            payload=request_payload,
            context=TraceContext(request_id=request_id),
        )
        status = self.inner.submit_finite(
            request_id=request_id,
            selected_option_id=selected_option_id,
            result_id=result_id,
        )
        self._trace_status_response(
            event_name="core.submit_finite.response",
            status=status,
            request_id=request_id,
        )
        return status

    def submit_movement_payload(
        self,
        *,
        request_id: str,
        payload: JsonValue,
        result_id: str,
    ) -> UiClientStatus:
        """Submit a movement proposal payload and trace request/response."""

        request_payload: JsonObject = {
            "request_id": request_id,
            "result_id": result_id,
            "payload": payload,
        }
        self.trace_writer.write_event(
            category="core_client",
            event_name="core.submit_movement_payload.request",
            summary={
                "request_id": request_id,
                "result_id": result_id,
                "payload_keys": _json_payload_keys(payload),
            },
            payload=request_payload,
            context=TraceContext(request_id=request_id),
        )
        status = self.inner.submit_movement_payload(
            request_id=request_id,
            payload=payload,
            result_id=result_id,
        )
        self._trace_status_response(
            event_name="core.submit_movement_payload.response",
            status=status,
            request_id=request_id,
        )
        return status

    def _trace_status_response(
        self,
        *,
        event_name: str,
        status: UiClientStatus,
        request_id: str | None = None,
    ) -> None:
        decision_request_id = None if status.decision is None else status.decision.request_id
        self.trace_writer.write_event(
            category="core_client",
            event_name=event_name,
            summary={
                "stage": status.stage,
                "status_kind": status.status_kind,
                "message": status.message,
                "decision_request_id": decision_request_id,
                "invalid_diagnostic_count": len(status.invalid_diagnostics),
            },
            payload=json_value_from_object(status),
            context=TraceContext(
                request_id=request_id or decision_request_id,
                status_kind=status.status_kind,
            ),
        )


def build_trace_writer(config: ForensicTraceConfig) -> ForensicTraceWriter:
    """Return the writer implementation for a resolved trace config."""

    if not config.enabled:
        return NoOpTraceWriter()
    return JsonLinesTraceWriter(config=config)


def trace_core_client(
    client: UiCoreClient,
    trace_writer: ForensicTraceWriter,
) -> UiCoreClient:
    """Wrap a core client when tracing is enabled."""

    if not trace_writer.enabled:
        return client
    return TracedCoreClient(inner=client, trace_writer=trace_writer)


def parse_trace_level(value: str | None) -> TraceLevel:
    """Parse a runtime trace level value."""

    if value is None or not value.strip():
        return "off"
    lowered = value.strip().lower()
    if lowered == "1" or lowered == "true":
        return "summary"
    if lowered not in _TRACE_LEVELS:
        raise TraceConfigurationError(
            f"Unsupported EVENT_TRACE level {value!r}; expected one of {_TRACE_LEVELS}."
        )
    return lowered


def json_value_from_object(value: object) -> JsonValue:
    """Convert dataclasses and containers into strict JSON-safe trace data."""

    try:
        return validate_json_value(_jsonish_from_object(value))
    except UiClientProtocolError as exc:
        raise TracePayloadError("Trace payload value is not JSON-safe.") from exc


def redact_json_value(value: JsonValue) -> JsonValue:
    """Return a copy of JSON-safe data with token-like fields redacted."""

    if type(value) is dict:
        return {
            key: REDACTED_VALUE if _sensitive_key(key) else redact_json_value(item)
            for key, item in value.items()
        }
    if type(value) is list:
        return [redact_json_value(item) for item in value]
    return value


def _jsonish_from_object(value: object) -> object:
    if is_dataclass(value):
        if isinstance(value, type):
            raise TracePayloadError("Trace payload cannot serialize dataclass types.")
        return {
            field.name: _jsonish_from_object(getattr(value, field.name))
            for field in fields(type(value))
        }
    if type(value) is tuple:
        return [_jsonish_from_object(item) for item in cast(tuple[object, ...], value)]
    if type(value) is list:
        return [_jsonish_from_object(item) for item in cast(list[object], value)]
    if type(value) is dict:
        return {
            key: _jsonish_from_object(item)
            for key, item in cast(dict[object, object], value).items()
        }
    return value


def _redacted_json_object(value: JsonObject) -> JsonObject:
    redacted = redact_json_value(validate_json_value(value))
    if type(redacted) is not dict:
        raise TracePayloadError("Trace summary must be a JSON object.")
    return redacted


def _apply_context(*, row: JsonObject, context: TraceContext) -> None:
    if context.viewer_player_id is not None:
        row["viewer_player_id"] = context.viewer_player_id
    if context.game_id is not None:
        row["game_id"] = context.game_id
    if context.request_id is not None:
        row["request_id"] = context.request_id
    if context.status_kind is not None:
        row["status_kind"] = context.status_kind
    if context.event_cursor is not None:
        row["event_cursor"] = context.event_cursor


def _json_payload_keys(payload: JsonValue) -> list[JsonValue]:
    if type(payload) is not dict:
        return []
    return list(payload.keys())


def _view_request_id(view: UiGameView) -> str | None:
    if view.pending_decision is not None:
        return view.pending_decision.request_id
    if view.pending_proposal is not None:
        return view.pending_proposal.request_id
    return None


def _non_empty_trace_string(field_name: str, value: object) -> str:
    if type(value) is not str:
        raise TracePayloadError(f"{field_name} must be a string.")
    stripped = value.strip()
    if not stripped:
        raise TracePayloadError(f"{field_name} must not be empty.")
    return stripped


def _sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _parse_max_bytes(value: str | None) -> int:
    if value is None or not value.strip():
        return DEFAULT_TRACE_MAX_BYTES
    try:
        parsed = int(value)
    except ValueError as exc:
        raise TraceConfigurationError(f"{EVENT_TRACE_MAX_BYTES_ENV} must be an integer.") from exc
    if parsed < 0:
        raise TraceConfigurationError(f"{EVENT_TRACE_MAX_BYTES_ENV} must not be negative.")
    return parsed


def _trace_directory(environment: Mapping[str, str]) -> Path:
    raw_dir = environment.get(EVENT_TRACE_DIR_ENV)
    if raw_dir is not None and raw_dir.strip():
        return Path(raw_dir)
    return Path.home() / ".local" / "state" / TRACE_PACKAGE_NAME / "event-traces"


def _timestamped_trace_filename() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    return f"event-trace-{timestamp}.jsonl"


def _rotated_trace_path(trace_path: Path) -> Path:
    suffix = trace_path.suffix or ".jsonl"
    stem = trace_path.stem if trace_path.suffix else trace_path.name
    return trace_path.with_name(f"{stem}.1{suffix}")


def _ui_commit_sha(environment: Mapping[str, str]) -> str | None:
    for key in ("WARHAMMER40K_ARCADE_UI_COMMIT_SHA", "UI_COMMIT_SHA", "GITHUB_SHA"):
        value = environment.get(key)
        if value is not None and value.strip():
            return value.strip()
    return None


def _ui_release_version() -> str | None:
    try:
        return metadata.version(TRACE_PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return None
