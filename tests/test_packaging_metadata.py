"""Packaging metadata regression tests."""

from __future__ import annotations

import tomllib
from importlib.resources import files
from pathlib import Path
from typing import cast


def test_pyproject_exposes_expected_console_scripts_and_package() -> None:
    pyproject_path = Path(__file__).parents[1] / "pyproject.toml"
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = cast(dict[str, object], payload["project"])
    scripts = cast(dict[str, str], project["scripts"])
    hatch = cast(dict[str, object], payload["tool"])
    hatch_build = cast(dict[str, object], hatch["hatch"])
    build = cast(dict[str, object], hatch_build["build"])
    targets = cast(dict[str, object], build["targets"])
    wheel = cast(dict[str, object], targets["wheel"])

    assert scripts == {
        "warhammer40k-arcade-ui": "warhammer40k_arcade_ui.main:main",
        "warhammer40k-export-preferences": (
            "warhammer40k_arcade_ui.preferences.export_profile:main"
        ),
        "warhammer40k-hud-preview": "warhammer40k_arcade_ui.hud.preview:main",
    }
    assert wheel["packages"] == ["src/warhammer40k_arcade_ui"]


def test_packaged_runtime_resources_are_importable() -> None:
    resources = files("warhammer40k_arcade_ui.resources")

    preference_text = resources.joinpath("preferences", "default.yaml").read_text(encoding="utf-8")
    hud_text = resources.joinpath("hud", "default-hud.yaml").read_text(encoding="utf-8")

    assert "profile_name: default" in preference_text
    assert "composition_profile: default-hud" in preference_text
    assert "profile_id: default_compass_hud" in hud_text
