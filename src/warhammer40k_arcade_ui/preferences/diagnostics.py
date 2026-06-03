"""Diagnostics for shareable UI preferences."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type Severity = Literal["info", "warning", "error"]


@dataclass(frozen=True, slots=True)
class PreferenceDiagnostic:
    """Typed config diagnostic safe to surface in the UI."""

    severity: Severity
    code: str
    message: str
    field: str
    value: str | None = None

    def __post_init__(self) -> None:
        if self.severity not in ("info", "warning", "error"):
            raise ValueError("severity must be info, warning, or error")
        object.__setattr__(self, "code", _non_empty_string("code", self.code))
        object.__setattr__(self, "message", _non_empty_string("message", self.message))
        object.__setattr__(self, "field", _non_empty_string("field", self.field))
        if self.value is not None:
            object.__setattr__(self, "value", _non_empty_string("value", self.value))


def _non_empty_string(name: str, value: str) -> str:
    if not value:
        raise ValueError(f"{name} must be non-empty")
    return value
