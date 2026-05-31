"""Command-line entry point for the Arcade UI client."""

from __future__ import annotations

from warhammer40k_arcade_ui.app import run_app
from warhammer40k_arcade_ui.logging_config import configure_logging


def main() -> None:
    """Launch the blank Phase 0 Arcade client."""

    configure_logging()
    run_app()


if __name__ == "__main__":
    main()
