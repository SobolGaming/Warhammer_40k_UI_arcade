"""Regression tests for retiring legacy HUD render paths."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
SRC_ROOT = REPO_ROOT / "src" / "warhammer40k_arcade_ui"


def test_legacy_direct_hud_modules_stay_removed() -> None:
    """The active HUD panel path is composition/runtime data, not old direct renderers."""

    assert not (SRC_ROOT / "render" / "hud_ergonomics.py").exists()
    assert not (SRC_ROOT / "hud" / "widgets.py").exists()


def test_production_render_path_does_not_import_legacy_hud_modules() -> None:
    """Production code must not reintroduce the retired divergent HUD modules."""

    production_files = tuple(SRC_ROOT.rglob("*.py"))
    assert production_files
    forbidden_imports = (
        "warhammer40k_arcade_ui.render.hud_ergonomics",
        "warhammer40k_arcade_ui.hud.widgets",
        "build_hud_primitives",
        "build_debug_inspector",
        "DebugInspectorView",
    )

    offenders = {
        path.relative_to(REPO_ROOT).as_posix(): forbidden
        for path in production_files
        for forbidden in forbidden_imports
        if forbidden in path.read_text(encoding="utf-8")
    }

    assert offenders == {}
