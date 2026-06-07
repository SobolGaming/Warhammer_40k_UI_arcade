"""Validate source import boundaries for the Arcade UI package."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

PACKAGE_ROOT = Path("src") / "warhammer40k_arcade_ui"
APPROVED_ENGINE_IMPORT_PACKAGE = "warhammer40k_arcade_ui.core_client"
ENGINE_MODULE_PREFIX = "warhammer40k_core"


@dataclass(frozen=True, slots=True)
class ImportBoundaryViolation:
    """A direct engine import outside the approved adapter boundary."""

    path: Path
    line_number: int
    module: str

    def format(self) -> str:
        """Return a stable human-readable violation line."""

        return f"{self.path}:{self.line_number}: direct engine import {self.module!r}"


def find_import_boundary_violations(
    *,
    package_root: Path = PACKAGE_ROOT,
) -> tuple[ImportBoundaryViolation, ...]:
    """Return direct core-engine imports outside ``core_client``."""

    violations: list[ImportBoundaryViolation] = []
    for path in sorted(package_root.rglob("*.py")):
        package_name = _package_name(path, package_root)
        if package_name.startswith(APPROVED_ENGINE_IMPORT_PACKAGE):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                violations.extend(_import_violations(path=path, node=node))
            elif isinstance(node, ast.ImportFrom):
                violation = _import_from_violation(path=path, node=node)
                if violation is not None:
                    violations.append(violation)
    return tuple(violations)


def main() -> int:
    """Run the import-boundary audit as a command-line tool."""

    violations = find_import_boundary_violations()
    if not violations:
        print("Import boundary check passed.")
        return 0
    print("Import boundary check failed:", file=sys.stderr)
    for violation in violations:
        print(violation.format(), file=sys.stderr)
    return 1


def _import_violations(
    *,
    path: Path,
    node: ast.Import,
) -> tuple[ImportBoundaryViolation, ...]:
    violations: list[ImportBoundaryViolation] = []
    for alias in node.names:
        if _is_engine_module(alias.name):
            violations.append(
                ImportBoundaryViolation(
                    path=path,
                    line_number=node.lineno,
                    module=alias.name,
                )
            )
    return tuple(violations)


def _import_from_violation(
    *,
    path: Path,
    node: ast.ImportFrom,
) -> ImportBoundaryViolation | None:
    if node.module is None or not _is_engine_module(node.module):
        return None
    return ImportBoundaryViolation(
        path=path,
        line_number=node.lineno,
        module=node.module,
    )


def _is_engine_module(module: str) -> bool:
    return module == ENGINE_MODULE_PREFIX or module.startswith(f"{ENGINE_MODULE_PREFIX}.")


def _package_name(path: Path, package_root: Path) -> str:
    relative = path.relative_to(package_root).with_suffix("")
    return ".".join(("warhammer40k_arcade_ui", *relative.parts))


if __name__ == "__main__":
    raise SystemExit(main())
