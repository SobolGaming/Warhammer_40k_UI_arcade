"""Command-line entry point for the Arcade UI client."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from warhammer40k_arcade_ui.app import run_app
from warhammer40k_arcade_ui.logging_config import configure_logging


@dataclass(frozen=True, slots=True)
class CliArgs:
    """Parsed command-line options for the Arcade UI."""

    ui_prefs_path: Path | None
    live_core_smoke: bool
    event_trace_level: str | None
    event_trace_file: Path | None


def main(argv: Sequence[str] | None = None) -> None:
    """Launch the blank Phase 0 Arcade client."""

    args = parse_args(argv)
    configure_logging()
    run_app(
        ui_prefs_path=args.ui_prefs_path,
        live_core_smoke=args.live_core_smoke,
        event_trace_level=args.event_trace_level,
        event_trace_file=args.event_trace_file,
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
    namespace = parser.parse_args(argv)
    return CliArgs(
        ui_prefs_path=namespace.ui_prefs,
        live_core_smoke=namespace.live_core_smoke,
        event_trace_level=namespace.event_trace,
        event_trace_file=namespace.event_trace_file,
    )


if __name__ == "__main__":
    main()
