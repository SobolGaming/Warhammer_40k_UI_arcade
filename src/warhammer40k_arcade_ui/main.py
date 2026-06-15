"""Command-line entry point for the Arcade UI client."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from warhammer40k_arcade_ui.app import run_app
from warhammer40k_arcade_ui.diagnostics.crash_report import (
    CrashReportContext,
    install_crash_report_excepthook,
)
from warhammer40k_arcade_ui.diagnostics.forensic_trace import (
    ForensicTraceConfig,
    build_trace_writer,
)
from warhammer40k_arcade_ui.logging_config import configure_logging


@dataclass(frozen=True, slots=True)
class CliArgs:
    """Parsed command-line options for the Arcade UI."""

    ui_prefs_path: Path | None
    live_core_smoke: bool
    stop_at_phase: str | None
    event_trace_level: str | None
    event_trace_file: Path | None
    event_trace_cfg_file: Path | None
    event_trace_include: tuple[str, ...]
    event_trace_exclude: tuple[str, ...]
    event_trace_include_categories: tuple[str, ...]
    event_trace_exclude_categories: tuple[str, ...]
    crash_report_dir: Path | None


def main(argv: Sequence[str] | None = None) -> None:
    """Launch the blank Phase 0 Arcade client."""

    args = parse_args(argv)
    configure_logging()
    trace_writer = build_trace_writer(
        ForensicTraceConfig.from_runtime(
            event_trace_level=args.event_trace_level,
            event_trace_file=args.event_trace_file,
            event_trace_cfg_file=args.event_trace_cfg_file,
            event_trace_include=args.event_trace_include,
            event_trace_exclude=args.event_trace_exclude,
            event_trace_include_categories=args.event_trace_include_categories,
            event_trace_exclude_categories=args.event_trace_exclude_categories,
        )
    )
    crash_context = CrashReportContext(
        runtime_mode=_runtime_mode(args),
        launch_args=tuple(sys.argv[1:] if argv is None else argv),
        preferences_path=args.ui_prefs_path,
        trace_path=trace_writer.trace_path,
    )
    install_crash_report_excepthook(
        context=crash_context,
        report_dir=args.crash_report_dir,
    )
    run_app(
        ui_prefs_path=args.ui_prefs_path,
        live_core_smoke=args.live_core_smoke,
        live_core_stop_phase=args.stop_at_phase,
        event_trace_level=args.event_trace_level,
        event_trace_file=args.event_trace_file,
        event_trace_cfg_file=args.event_trace_cfg_file,
        event_trace_include=args.event_trace_include,
        event_trace_exclude=args.event_trace_exclude,
        event_trace_include_categories=args.event_trace_include_categories,
        event_trace_exclude_categories=args.event_trace_exclude_categories,
        trace_writer=trace_writer,
        crash_report_context=crash_context,
        crash_report_dir=args.crash_report_dir,
    )


def parse_args(argv: Sequence[str] | None) -> CliArgs:
    parser = argparse.ArgumentParser(description="Launch the Warhammer 40k Arcade UI.")
    parser.add_argument(
        "--ui-prefs",
        type=Path,
        help="Path to a JSON/YAML UI preferences profile.",
    )
    parser.add_argument(
        "--live-core-smoke",
        action="store_true",
        help="Launch an opt-in real local core movement smoke session.",
    )
    parser.add_argument(
        "--stop-at-phase",
        choices=("deployment", "movement"),
        help=(
            "Live-core smoke pause point. Defaults to movement; use deployment to open the "
            "Arcade window at the first deployment placement proposal."
        ),
    )
    parser.add_argument(
        "--event-trace",
        choices=("off", "summary", "payload", "render"),
        help="Enable a forensic UI/core event trace level for this run.",
    )
    parser.add_argument(
        "--event-trace-file",
        type=Path,
        help="Write the forensic event trace JSON Lines file to this path.",
    )
    parser.add_argument(
        "--event-trace-cfg",
        type=Path,
        help="Path to an event trace JSON config file.",
    )
    parser.add_argument(
        "--event-trace-include",
        action="append",
        nargs="+",
        metavar="EVENT",
        help=(
            "Only emit matching event names. Accepts repeated values, space-separated values, "
            "or comma-separated values."
        ),
    )
    parser.add_argument(
        "--event-trace-exclude",
        action="append",
        nargs="+",
        metavar="EVENT",
        help=(
            "Suppress matching event names. Accepts repeated values, space-separated values, "
            "or comma-separated values."
        ),
    )
    parser.add_argument(
        "--event-trace-include-category",
        action="append",
        nargs="+",
        metavar="CATEGORY",
        help=(
            "Only emit matching event categories. Accepts repeated values, space-separated values, "
            "or comma-separated values."
        ),
    )
    parser.add_argument(
        "--event-trace-exclude-category",
        action="append",
        nargs="+",
        metavar="CATEGORY",
        help=(
            "Suppress matching event categories. Accepts repeated values, space-separated values, "
            "or comma-separated values."
        ),
    )
    parser.add_argument(
        "--crash-report-dir",
        type=Path,
        help="Write crash diagnostic bundles under this directory.",
    )
    namespace = parser.parse_args(argv)
    if namespace.stop_at_phase is not None and not namespace.live_core_smoke:
        parser.error("--stop-at-phase requires --live-core-smoke.")
    return CliArgs(
        ui_prefs_path=namespace.ui_prefs,
        live_core_smoke=namespace.live_core_smoke,
        stop_at_phase=namespace.stop_at_phase,
        event_trace_level=namespace.event_trace,
        event_trace_file=namespace.event_trace_file,
        event_trace_cfg_file=namespace.event_trace_cfg,
        event_trace_include=_flatten_filter_args(namespace.event_trace_include),
        event_trace_exclude=_flatten_filter_args(namespace.event_trace_exclude),
        event_trace_include_categories=_flatten_filter_args(namespace.event_trace_include_category),
        event_trace_exclude_categories=_flatten_filter_args(namespace.event_trace_exclude_category),
        crash_report_dir=namespace.crash_report_dir,
    )


def _runtime_mode(args: CliArgs) -> str:
    if args.live_core_smoke:
        return "live_core_smoke"
    return "fake_fixture"


def _flatten_filter_args(raw_values: list[list[str]] | None) -> tuple[str, ...]:
    if raw_values is None:
        return ()
    return tuple(
        candidate
        for group in raw_values
        for value in group
        for candidate in _split_filter_arg(value)
    )


def _split_filter_arg(value: str) -> tuple[str, ...]:
    return tuple(candidate.strip() for candidate in value.split(",") if candidate.strip())


if __name__ == "__main__":
    main()
