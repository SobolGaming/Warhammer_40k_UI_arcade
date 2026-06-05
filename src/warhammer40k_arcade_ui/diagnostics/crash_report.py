"""Crash diagnostic bundle generation for fatal UI failures."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import traceback
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from importlib import metadata
from os import environ
from pathlib import Path
from types import TracebackType

from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    JsonValue,
    UiClientProtocolError,
    validate_json_value,
)
from warhammer40k_arcade_ui.diagnostics.forensic_trace import (
    REDACTED_VALUE,
    TRACE_PACKAGE_NAME,
    redact_json_value,
)

CRASH_REPORT_DIR_ENV = "WARHAMMER40K_ARCADE_UI_CRASH_REPORT_DIR"
RENDER_ARTIFACT_DIR_ENV = "WARHAMMER40K_ARCADE_UI_RENDER_ARTIFACT_DIR"
CRASH_REPORT_SCHEMA_VERSION = "1"
DEFAULT_TRACE_TAIL_ROWS = 25
DEFAULT_RENDER_ARTIFACT_LIMIT = 8
CRASH_REPORT_FILENAME = "crash-report.json"
COLOCATED_TRACE_FILENAME = "event-trace.jsonl"

_SENSITIVE_ARG_PARTS = (
    "token",
    "secret",
    "authorization",
    "password",
    "credential",
    "api-key",
    "api_key",
    "apikey",
    "access-token",
    "access_token",
    "github-token",
    "github_token",
)


class CrashReportError(RuntimeError):
    """Raised when a crash report cannot be written."""


@dataclass(frozen=True, slots=True)
class CrashReportContext:
    """Runtime context attached to a crash report."""

    runtime_mode: str = "unknown"
    launch_args: tuple[str, ...] = ()
    preferences_source: str | None = None
    preferences_path: Path | None = None
    viewer_player_id: str | None = None
    game_id: str | None = None
    request_id: str | None = None
    status_kind: str | None = None
    event_cursor: int | None = None
    trace_path: Path | None = None
    render_artifact_dir: Path | None = None

    def with_updates(
        self,
        *,
        runtime_mode: str | None = None,
        launch_args: tuple[str, ...] | None = None,
        preferences_source: str | None = None,
        preferences_path: Path | None = None,
        viewer_player_id: str | None = None,
        game_id: str | None = None,
        request_id: str | None = None,
        status_kind: str | None = None,
        event_cursor: int | None = None,
        trace_path: Path | None = None,
        render_artifact_dir: Path | None = None,
    ) -> CrashReportContext:
        """Return a copy with only non-None fields overridden."""

        return replace(
            self,
            runtime_mode=self.runtime_mode if runtime_mode is None else runtime_mode,
            launch_args=self.launch_args if launch_args is None else launch_args,
            preferences_source=(
                self.preferences_source if preferences_source is None else preferences_source
            ),
            preferences_path=self.preferences_path
            if preferences_path is None
            else preferences_path,
            viewer_player_id=(
                self.viewer_player_id if viewer_player_id is None else viewer_player_id
            ),
            game_id=self.game_id if game_id is None else game_id,
            request_id=self.request_id if request_id is None else request_id,
            status_kind=self.status_kind if status_kind is None else status_kind,
            event_cursor=self.event_cursor if event_cursor is None else event_cursor,
            trace_path=self.trace_path if trace_path is None else trace_path,
            render_artifact_dir=(
                self.render_artifact_dir if render_artifact_dir is None else render_artifact_dir
            ),
        )


@dataclass(frozen=True, slots=True)
class CrashReportResult:
    """Paths produced by a crash report capture."""

    bundle_dir: Path
    report_path: Path


@dataclass(frozen=True, slots=True)
class GitMetadata:
    """Best-effort Git checkout metadata."""

    commit_sha: str | None
    branch: str | None
    dirty: bool | None


@dataclass(frozen=True, slots=True)
class TraceFileCopy:
    """Best-effort colocated forensic trace file copy metadata."""

    original_path: Path | None
    copied_path: Path | None
    copy_error: str | None = None


def write_crash_report(
    *,
    exception: Exception,
    context: CrashReportContext,
    traceback_obj: TracebackType | None = None,
    report_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> CrashReportResult:
    """Write a crash diagnostic bundle and return its paths."""

    environment = environ if env is None else env
    bundle_dir = _new_bundle_dir(report_dir=_resolve_report_root(report_dir, environment))
    report_path = bundle_dir / CRASH_REPORT_FILENAME
    try:
        bundle_dir.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise CrashReportError(f"Could not create crash report bundle {bundle_dir}.") from exc
    trace_file_copy = _colocate_trace_file(
        trace_path=context.trace_path,
        bundle_dir=bundle_dir,
    )
    report = _crash_report_payload(
        exception=exception,
        context=context,
        traceback_obj=traceback_obj,
        env=environment,
        trace_file_copy=trace_file_copy,
    )
    try:
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise CrashReportError(f"Could not write crash report to {report_path}.") from exc
    return CrashReportResult(bundle_dir=bundle_dir, report_path=report_path)


def install_crash_report_excepthook(
    *,
    context: CrashReportContext,
    report_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Install a process-level hook for uncaught UI exceptions."""

    previous_hook = sys.excepthook

    def crash_report_hook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        tb: TracebackType | None,
    ) -> None:
        if isinstance(exc_value, KeyboardInterrupt | SystemExit):
            previous_hook(exc_type, exc_value, tb)
            return
        if isinstance(exc_value, Exception):
            try:
                result = write_crash_report(
                    exception=exc_value,
                    traceback_obj=tb,
                    context=context,
                    report_dir=report_dir,
                    env=env,
                )
            except CrashReportError as report_exc:
                print(f"Crash report capture failed: {report_exc}", file=sys.stderr)
            else:
                print(f"Crash report written: {result.report_path}", file=sys.stderr)
        previous_hook(exc_type, exc_value, tb)

    sys.excepthook = crash_report_hook


def _crash_report_payload(
    *,
    exception: Exception,
    context: CrashReportContext,
    traceback_obj: TracebackType | None,
    env: Mapping[str, str],
    trace_file_copy: TraceFileCopy,
) -> JsonObject:
    repo_root = _repo_root()
    git = _git_metadata(repo_root)
    report: JsonObject = {
        "schema_version": CRASH_REPORT_SCHEMA_VERSION,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "exception": _exception_payload(exception=exception, traceback_obj=traceback_obj),
        "ui": {
            "package_name": TRACE_PACKAGE_NAME,
            "release_version": _ui_release_version(repo_root),
            "commit_sha": git.commit_sha,
            "branch": git.branch,
            "dirty": git.dirty,
        },
        "core_engine": {
            "release_version": None,
            "commit_sha": None,
            "note": "Not currently exposed by the UI/core adapter contract.",
        },
        "runtime": _runtime_payload(context),
        "environment": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "arcade_version": _dependency_version("arcade"),
            "pyglet_version": _dependency_version("pyglet"),
        },
        "forensic_trace": _trace_tail_payload(trace_file_copy),
        "render_artifacts": _render_artifacts_payload(
            artifact_dir=_resolve_render_artifact_dir(context.render_artifact_dir, env)
        ),
    }
    try:
        validated = validate_json_value(redact_json_value(report))
    except UiClientProtocolError as exc:
        raise CrashReportError("Crash report payload is not JSON-safe.") from exc
    if type(validated) is not dict:
        raise CrashReportError("Crash report payload must be a JSON object.")
    return validated


def _exception_payload(
    *,
    exception: Exception,
    traceback_obj: TracebackType | None,
) -> JsonObject:
    tb = exception.__traceback__ if traceback_obj is None else traceback_obj
    stack_trace: list[JsonValue] = list(traceback.format_exception(type(exception), exception, tb))
    return {
        "type": type(exception).__name__,
        "message": str(exception),
        "stack_trace": stack_trace,
    }


def _runtime_payload(context: CrashReportContext) -> JsonObject:
    return {
        "runtime_mode": context.runtime_mode,
        "launch_args": _redacted_launch_args(context.launch_args),
        "preferences_source": context.preferences_source,
        "preferences_path": None
        if context.preferences_path is None
        else str(context.preferences_path),
        "viewer_player_id": context.viewer_player_id,
        "game_id": context.game_id,
        "request_id": context.request_id,
        "status_kind": context.status_kind,
        "event_cursor": context.event_cursor,
    }


def _redacted_launch_args(args: Sequence[str]) -> list[JsonValue]:
    redacted: list[JsonValue] = []
    redact_next = False
    for arg in args:
        if redact_next:
            redacted.append(REDACTED_VALUE)
            redact_next = False
            continue
        if arg.startswith("--"):
            key, separator, _value = arg.partition("=")
            if _sensitive_arg_key(key):
                redacted.append(f"{key}={REDACTED_VALUE}" if separator else key)
                if not separator:
                    redact_next = True
                continue
        redacted.append(arg)
    return redacted


def _sensitive_arg_key(value: str) -> bool:
    normalized = value.lower()
    return any(part in normalized for part in _SENSITIVE_ARG_PARTS)


def _trace_tail_payload(trace_file_copy: TraceFileCopy) -> JsonObject:
    trace_path = trace_file_copy.original_path
    if trace_path is None:
        return {"path": None, "colocated_path": None, "rows": []}
    read_path = trace_file_copy.copied_path or trace_path
    payload: JsonObject = {
        "path": str(trace_path),
        "colocated_path": None
        if trace_file_copy.copied_path is None
        else str(trace_file_copy.copied_path),
        "rows": [],
    }
    if trace_file_copy.copy_error is not None:
        payload["copy_error"] = trace_file_copy.copy_error
    if not read_path.exists():
        payload["missing"] = True
        return payload
    try:
        lines = read_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        payload["read_error"] = str(exc)
        return payload
    rows: list[JsonValue] = []
    decode_errors: list[JsonValue] = []
    for line_number, line in _tail_numbered_lines(lines, DEFAULT_TRACE_TAIL_ROWS):
        try:
            raw_row = json.loads(line)
            rows.append(validate_json_value(raw_row))
        except json.JSONDecodeError as exc:
            decode_errors.append(
                {
                    "line_number": line_number,
                    "message": exc.msg,
                }
            )
        except UiClientProtocolError as exc:
            decode_errors.append(
                {
                    "line_number": line_number,
                    "message": str(exc),
                }
            )
    payload["rows"] = rows
    if len(lines) > DEFAULT_TRACE_TAIL_ROWS:
        payload["truncated_before_line"] = len(lines) - DEFAULT_TRACE_TAIL_ROWS + 1
    if decode_errors:
        payload["decode_errors"] = decode_errors
    return payload


def _colocate_trace_file(*, trace_path: Path | None, bundle_dir: Path) -> TraceFileCopy:
    if trace_path is None:
        return TraceFileCopy(original_path=None, copied_path=None)
    try:
        trace_exists = trace_path.exists()
    except OSError as exc:
        return TraceFileCopy(
            original_path=trace_path,
            copied_path=None,
            copy_error=str(exc),
        )
    if not trace_exists:
        return TraceFileCopy(original_path=trace_path, copied_path=None)
    copied_path = bundle_dir / COLOCATED_TRACE_FILENAME
    try:
        shutil.copy2(trace_path, copied_path)
    except OSError as exc:
        return TraceFileCopy(
            original_path=trace_path,
            copied_path=None,
            copy_error=str(exc),
        )
    return TraceFileCopy(original_path=trace_path, copied_path=copied_path)


def _tail_numbered_lines(lines: Sequence[str], max_lines: int) -> list[tuple[int, str]]:
    start_index = max(0, len(lines) - max_lines)
    return [(index + 1, line) for index, line in enumerate(lines[start_index:], start_index)]


def _render_artifacts_payload(artifact_dir: Path | None) -> JsonObject:
    payload: JsonObject = {"directory": None if artifact_dir is None else str(artifact_dir)}
    if artifact_dir is None:
        payload["latest"] = []
        return payload
    if not artifact_dir.exists():
        payload["missing"] = True
        payload["latest"] = []
        return payload
    try:
        entries = [
            child
            for child in artifact_dir.iterdir()
            if child.is_file() and child.suffix.lower() in (".png", ".json")
        ]
        latest = sorted(entries, key=lambda path: path.stat().st_mtime, reverse=True)[
            :DEFAULT_RENDER_ARTIFACT_LIMIT
        ]
        payload["latest"] = [
            {
                "path": str(path),
                "size_bytes": path.stat().st_size,
            }
            for path in latest
        ]
    except OSError as exc:
        payload["read_error"] = str(exc)
        payload["latest"] = []
    return payload


def _resolve_render_artifact_dir(
    context_dir: Path | None,
    env: Mapping[str, str],
) -> Path | None:
    if context_dir is not None:
        return context_dir
    raw_dir = env.get(RENDER_ARTIFACT_DIR_ENV)
    if raw_dir is not None and raw_dir.strip():
        return Path(raw_dir)
    return _repo_root() / ".test-artifacts" / "render"


def _resolve_report_root(report_dir: Path | None, env: Mapping[str, str]) -> Path:
    if report_dir is not None:
        return report_dir
    raw_dir = env.get(CRASH_REPORT_DIR_ENV)
    if raw_dir is not None and raw_dir.strip():
        return Path(raw_dir)
    return Path.home() / ".local" / "state" / TRACE_PACKAGE_NAME / "crash-bundles"


def _new_bundle_dir(*, report_dir: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    return report_dir / f"crash-{timestamp}"


def _dependency_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def _ui_release_version(repo_root: Path) -> str | None:
    installed = _dependency_version(TRACE_PACKAGE_NAME)
    if installed is not None:
        return installed
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return None
    marker = 'version = "'
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(marker) and stripped.endswith('"'):
            return stripped.removeprefix(marker).removesuffix('"')
    return None


def _git_metadata(repo_root: Path) -> GitMetadata:
    commit_sha = _git_output(repo_root, ("rev-parse", "HEAD"))
    branch = _git_output(repo_root, ("rev-parse", "--abbrev-ref", "HEAD"))
    dirty_output = _git_output(repo_root, ("status", "--porcelain"))
    dirty = None if dirty_output is None else bool(dirty_output)
    return GitMetadata(commit_sha=commit_sha, branch=branch, dirty=dirty)


def _git_output(repo_root: Path, args: tuple[str, ...]) -> str | None:
    try:
        result = subprocess.run(
            ("git", *args),
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except OSError, subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
