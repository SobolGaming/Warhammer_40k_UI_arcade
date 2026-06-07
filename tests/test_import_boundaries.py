"""Tests for repository import-boundary hardening."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.check_import_boundaries import find_import_boundary_violations


def test_import_boundary_script_passes_current_source_tree() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_import_boundaries.py"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "Import boundary check passed." in completed.stdout
    assert completed.stderr == ""


def test_import_boundary_script_allows_only_core_client_engine_imports(
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "warhammer40k_arcade_ui"
    approved_dir = package_root / "core_client"
    render_dir = package_root / "render"
    approved_dir.mkdir(parents=True)
    render_dir.mkdir()
    (approved_dir / "local_session_client.py").write_text(
        "from warhammer40k_core.engine.game_state import GameConfig\n",
        encoding="utf-8",
    )
    offender = render_dir / "arcade_window.py"
    offender.write_text(
        "import warhammer40k_core.engine.game_state\n",
        encoding="utf-8",
    )

    violations = find_import_boundary_violations(package_root=package_root)

    assert len(violations) == 1
    assert violations[0].path == offender
    assert violations[0].line_number == 1
    assert violations[0].module == "warhammer40k_core.engine.game_state"
