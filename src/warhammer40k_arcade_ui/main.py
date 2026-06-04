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


def main(argv: Sequence[str] | None = None) -> None:
    """Launch the blank Phase 0 Arcade client."""

    args = parse_args(argv)
    configure_logging()
    run_app(ui_prefs_path=args.ui_prefs_path)


def parse_args(argv: Sequence[str] | None) -> CliArgs:
    parser = argparse.ArgumentParser(description="Launch the Warhammer 40k Arcade UI.")
    parser.add_argument(
        "--ui-prefs",
        type=Path,
        help="Path to a JSON/YAML UI preferences profile.",
    )
    namespace = parser.parse_args(argv)
    return CliArgs(ui_prefs_path=namespace.ui_prefs)


if __name__ == "__main__":
    main()
