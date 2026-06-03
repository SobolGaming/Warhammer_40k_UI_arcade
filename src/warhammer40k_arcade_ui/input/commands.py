"""Preference-backed local command matching."""

from __future__ import annotations

from dataclasses import dataclass

from warhammer40k_arcade_ui.preferences.schema import UiPreferences


@dataclass(frozen=True, slots=True)
class CommandInvocation:
    """A matched local UI command from a configured hotkey."""

    command_id: str
    overlay_id: str | None = None


def command_for_key(
    *,
    preferences: UiPreferences,
    key: str,
    modifiers: tuple[str, ...] = (),
) -> CommandInvocation | None:
    """Return the configured command for a normalized key/modifier input."""

    normalized_key = key.lower()
    normalized_modifiers = tuple(sorted(modifier.lower() for modifier in modifiers))
    for binding in preferences.hotkeys:
        if binding.normalized_input == (normalized_modifiers, normalized_key):
            return CommandInvocation(
                command_id=binding.command_id,
                overlay_id=binding.overlay_id,
            )
    return None
