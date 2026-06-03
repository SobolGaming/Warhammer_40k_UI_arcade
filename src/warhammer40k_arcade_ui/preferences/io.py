"""Load and export shareable UI preferences."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import orjson
import yaml
from platformdirs import user_config_path
from yaml import YAMLError

from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.preferences.diagnostics import PreferenceDiagnostic
from warhammer40k_arcade_ui.preferences.schema import (
    UiPreferences,
    parse_preferences_payload,
)

type PreferenceFormat = Literal["json", "yaml"]

_DEFAULT_FILE_NAME = "ui-preferences.yaml"


@dataclass(frozen=True, slots=True)
class PreferencesLoadResult:
    """Result of loading a preference profile."""

    preferences: UiPreferences | None
    diagnostics: tuple[PreferenceDiagnostic, ...]
    source_path: Path | None
    used_builtin_default: bool

    @property
    def has_errors(self) -> bool:
        """Return whether loading produced any error diagnostics."""

        return any(diagnostic.severity == "error" for diagnostic in self.diagnostics)


def default_preferences_path() -> Path:
    """Return the platform default preference file path."""

    return (
        user_config_path(
            appname="warhammer40k-arcade-ui",
            appauthor=False,
            ensure_exists=False,
        )
        / _DEFAULT_FILE_NAME
    )


def load_preferences(path: Path | None = None) -> PreferencesLoadResult:
    """Load preferences from an explicit path, platform default path, or built-in defaults."""

    if path is None:
        default_path = default_preferences_path()
        if not default_path.exists():
            return PreferencesLoadResult(
                preferences=default_preferences(),
                diagnostics=(),
                source_path=None,
                used_builtin_default=True,
            )
        return _load_existing_file(default_path)
    if not path.exists():
        return PreferencesLoadResult(
            preferences=None,
            diagnostics=(
                PreferenceDiagnostic(
                    severity="error",
                    code="preferences_file_missing",
                    field="path",
                    message=f"Preference file does not exist: {path}",
                    value=str(path),
                ),
            ),
            source_path=path,
            used_builtin_default=False,
        )
    return _load_existing_file(path)


def load_preferences_from_text(
    *,
    text: str,
    preference_format: PreferenceFormat,
) -> PreferencesLoadResult:
    """Load preferences from JSON or YAML text."""

    payload = _parse_text(text=text, preference_format=preference_format)
    if isinstance(payload, PreferenceDiagnostic):
        return PreferencesLoadResult(
            preferences=None,
            diagnostics=(payload,),
            source_path=None,
            used_builtin_default=False,
        )
    result = parse_preferences_payload(payload)
    return PreferencesLoadResult(
        preferences=result.preferences,
        diagnostics=result.diagnostics,
        source_path=None,
        used_builtin_default=False,
    )


def export_preferences(
    preferences: UiPreferences,
    preference_format: PreferenceFormat,
) -> str:
    """Export preferences as deterministic JSON or YAML text."""

    payload = preferences.to_payload()
    if preference_format == "json":
        return orjson.dumps(payload, option=orjson.OPT_INDENT_2).decode("utf-8") + "\n"
    if preference_format == "yaml":
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
    raise ValueError("preference_format must be json or yaml")


def write_preferences(
    *,
    preferences: UiPreferences,
    path: Path,
    preference_format: PreferenceFormat | None = None,
) -> None:
    """Write preferences to a JSON or YAML file."""

    resolved_format = preference_format or _format_from_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        export_preferences(preferences, resolved_format),
        encoding="utf-8",
    )


def _load_existing_file(path: Path) -> PreferencesLoadResult:
    try:
        preference_format = _format_from_path(path)
    except ValueError as error:
        return PreferencesLoadResult(
            preferences=None,
            diagnostics=(
                PreferenceDiagnostic(
                    severity="error",
                    code="preferences_file_format_error",
                    field="path",
                    message=str(error),
                    value=str(path),
                ),
            ),
            source_path=path,
            used_builtin_default=False,
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        return PreferencesLoadResult(
            preferences=None,
            diagnostics=(
                PreferenceDiagnostic(
                    severity="error",
                    code="preferences_file_read_error",
                    field="path",
                    message=f"Could not read preference file: {error}",
                    value=str(path),
                ),
            ),
            source_path=path,
            used_builtin_default=False,
        )
    except UnicodeDecodeError as error:
        return PreferencesLoadResult(
            preferences=None,
            diagnostics=(
                PreferenceDiagnostic(
                    severity="error",
                    code="preferences_file_encoding_error",
                    field="path",
                    message=f"Preference file must be UTF-8: {error}",
                    value=str(path),
                ),
            ),
            source_path=path,
            used_builtin_default=False,
        )
    loaded = load_preferences_from_text(
        text=text,
        preference_format=preference_format,
    )
    return PreferencesLoadResult(
        preferences=loaded.preferences,
        diagnostics=loaded.diagnostics,
        source_path=path,
        used_builtin_default=False,
    )


def _parse_text(
    *,
    text: str,
    preference_format: PreferenceFormat,
) -> object | PreferenceDiagnostic:
    if preference_format == "json":
        try:
            return cast(object, orjson.loads(text))
        except orjson.JSONDecodeError as error:
            return PreferenceDiagnostic(
                severity="error",
                code="json_parse_error",
                field="$",
                message=f"Could not parse JSON preferences: {error}",
            )
    if preference_format == "yaml":
        try:
            loaded = cast(object, yaml.safe_load(text))
        except YAMLError as error:
            return PreferenceDiagnostic(
                severity="error",
                code="yaml_parse_error",
                field="$",
                message=f"Could not parse YAML preferences: {error}",
            )
        if loaded is None:
            return {}
        return loaded
    raise ValueError("preference_format must be json or yaml")


def _format_from_path(path: Path) -> PreferenceFormat:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix in (".yaml", ".yml"):
        return "yaml"
    raise ValueError("preference file extension must be .json, .yaml, or .yml")
