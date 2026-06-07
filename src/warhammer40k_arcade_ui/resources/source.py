"""Safe access helpers for packaged and filesystem resource sources."""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path, PurePosixPath
from typing import Literal

RESOURCE_PACKAGE = "warhammer40k_arcade_ui.resources"

type ConfigSourceKind = Literal["builtin", "user_default", "explicit_path"]
type ResourceSourceKind = Literal["builtin", "user_default", "explicit_path"]


@dataclass(frozen=True, slots=True)
class ConfigSource:
    """Origin metadata for a loaded UI configuration profile."""

    kind: ConfigSourceKind
    name: str
    path: Path | None = None

    @property
    def display_name(self) -> str:
        """Return a compact user/debug-facing source label."""

        if self.kind == "builtin":
            return f"builtin:{self.name}"
        if self.path is not None:
            return str(self.path)
        return self.name


@dataclass(frozen=True, slots=True)
class ResourceSource:
    """Origin metadata for a loaded non-preference resource."""

    kind: ResourceSourceKind
    name: str
    path: Path | None = None

    @property
    def display_name(self) -> str:
        """Return a compact user/debug-facing source label."""

        if self.kind == "builtin":
            return f"builtin:{self.name}"
        if self.path is not None:
            return str(self.path)
        return self.name


type GenericSource = ConfigSource | ResourceSource


def read_builtin_text(relative_resource: str) -> str:
    """Read a packaged text resource by safe package-relative path."""

    rel = validate_builtin_resource_path(relative_resource)
    return files(RESOURCE_PACKAGE).joinpath(*rel.parts).read_text(encoding="utf-8")


def resolve_resource_reference(
    reference: str,
    *,
    relative_to: GenericSource | None = None,
    known_builtins: Mapping[str, str] | None = None,
) -> ResourceSource:
    """Resolve a resource reference against an optional generic source context."""

    builtin_resource = (known_builtins or {}).get(reference)
    if builtin_resource is not None:
        return ResourceSource(kind="builtin", name=builtin_resource)
    if reference.startswith("builtin:"):
        return ResourceSource(kind="builtin", name=reference.removeprefix("builtin:"))

    candidate = Path(reference)
    if candidate.is_absolute():
        return ResourceSource(kind="explicit_path", name=str(candidate), path=candidate)

    if relative_to is not None and relative_to.path is not None:
        path = relative_to.path.parent / candidate
        return ResourceSource(kind=_resource_kind(relative_to), name=str(path), path=path)
    if relative_to is not None and relative_to.kind == "builtin":
        return ResourceSource(
            kind="builtin",
            name=resolve_builtin_relative_resource(relative_to.name, reference),
        )
    return ResourceSource(kind="explicit_path", name=reference, path=Path(reference))


@contextmanager
def builtin_resource_path(relative_resource: str) -> Generator[Path]:
    """Yield a real filesystem path for a packaged resource when an API needs one."""

    rel = validate_builtin_resource_path(relative_resource)
    traversable = files(RESOURCE_PACKAGE).joinpath(*rel.parts)
    with as_file(traversable) as real_path:
        yield real_path


def validate_builtin_resource_path(relative_resource: str) -> PurePosixPath:
    """Validate and normalize a package-relative resource path."""

    rel = PurePosixPath(relative_resource)
    if rel.is_absolute() or ".." in rel.parts or "" in rel.parts:
        raise ValueError(f"unsafe resource path: {relative_resource!r}")
    if not rel.parts:
        raise ValueError("resource path must not be empty")
    return rel


def resolve_builtin_relative_resource(base_resource: str, reference: str) -> str:
    """Resolve a package-relative reference against a built-in package resource."""

    base = validate_builtin_resource_path(base_resource)
    relative = PurePosixPath(reference)
    if relative.is_absolute() or not relative.parts:
        raise ValueError(f"unsafe resource path: {reference!r}")
    parts: list[str] = list(base.parent.parts)
    for part in relative.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise ValueError(f"unsafe resource path: {reference!r}")
            parts.pop()
            continue
        parts.append(part)
    if not parts:
        raise ValueError("resource path must not be empty")
    return "/".join(parts)


def _resource_kind(source: GenericSource) -> ResourceSourceKind:
    if source.kind == "builtin":
        return "builtin"
    if source.kind == "user_default":
        return "user_default"
    return "explicit_path"
