"""Command-line export helper for built-in UI preference profiles."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from warhammer40k_arcade_ui.preferences.defaults import (
    default_preferences,
    dense_debug_preferences,
    keyboard_heavy_preferences,
)
from warhammer40k_arcade_ui.preferences.io import PreferenceFormat, export_preferences
from warhammer40k_arcade_ui.preferences.schema import UiPreferences


def main(argv: Sequence[str] | None = None) -> None:
    """Export a built-in preference profile to stdout or a file."""

    parser = argparse.ArgumentParser(description="Export Warhammer 40k Arcade UI preferences.")
    parser.add_argument(
        "--profile",
        choices=("default", "dense-debug", "keyboard-heavy"),
        default="default",
    )
    parser.add_argument("--format", choices=("json", "yaml"), default="yaml")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    text = export_preferences(
        _profile_from_name(args.profile),
        _preference_format(args.format),
    )
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")


def _profile_from_name(name: str) -> UiPreferences:
    if name == "default":
        return default_preferences()
    if name == "dense-debug":
        return dense_debug_preferences()
    if name == "keyboard-heavy":
        return keyboard_heavy_preferences()
    raise ValueError("unknown profile")


def _preference_format(value: str) -> PreferenceFormat:
    if value == "json":
        return "json"
    if value == "yaml":
        return "yaml"
    raise ValueError("unknown preference format")
