"""Command-line entry point for the Arcade UI client."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from warhammer40k_arcade_ui.app import phase_debug_enabled, run_app
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
    event_trace_level: str | None
    event_trace_file: Path | None
    crash_report_dir: Path | None


def main(argv: Sequence[str] | None = None) -> None:
    """Launch the blank Phase 0 Arcade client."""

    args = parse_args(argv)
    configure_logging()
    trace_writer = build_trace_writer(
        ForensicTraceConfig.from_runtime(
            event_trace_level=args.event_trace_level,
            event_trace_file=args.event_trace_file,
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
        event_trace_level=args.event_trace_level,
        event_trace_file=args.event_trace_file,
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
        "--crash-report-dir",
        type=Path,
        help="Write crash diagnostic bundles under this directory.",
    )
    namespace = parser.parse_args(argv)
    return CliArgs(
        ui_prefs_path=namespace.ui_prefs,
        live_core_smoke=namespace.live_core_smoke,
        event_trace_level=namespace.event_trace,
        event_trace_file=namespace.event_trace_file,
        crash_report_dir=namespace.crash_report_dir,
    )


def _runtime_mode(args: CliArgs) -> str:
    if args.live_core_smoke:
        return "live_core_smoke"
    if phase_debug_enabled():
        return "debug_fixture"
    return "fake_fixture"


if __name__ == "__main__":
    main()
