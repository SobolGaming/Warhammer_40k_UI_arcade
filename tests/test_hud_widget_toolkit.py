"""Tests for the configurable HUD widget toolkit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from warhammer40k_arcade_ui.hud import preview as hud_preview
from warhammer40k_arcade_ui.hud.composition import (
    HudCompositionValidationResult,
    load_hud_composition,
    load_hud_composition_for_preferences,
    parse_hud_composition_payload,
)
from warhammer40k_arcade_ui.hud.preview import main as hud_preview_main
from warhammer40k_arcade_ui.hud.toolkit import (
    DonutGaugeView,
    HudContainerView,
    HudLayoutSpec,
    component_allowed_attributes,
    default_hud_theme,
    known_data_refs,
    known_icon_ids,
    known_widget_types,
)
from warhammer40k_arcade_ui.hud.toolkit_render import render_composition_profile
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.primitives import (
    CirclePrimitive,
    PolygonPrimitive,
    TextPrimitive,
)


def test_widget_registry_exposes_expected_phase19_inventory() -> None:
    assert {
        "HudContainer",
        "IconTextBar",
        "DonutGauge",
        "DatasheetPanel",
        "AssignmentGroupRow",
    }.issubset(known_widget_types())
    assert {"render_mode", "clip_children"}.issubset(component_allowed_attributes("HudContainer"))
    assert {"inner_diameter", "outer_diameter", "progress_fraction"}.issubset(
        component_allowed_attributes("DonutGauge")
    )
    assert "action.movement" in known_icon_ids()
    assert "selected_unit" in known_data_refs()


def test_toolkit_view_models_preserve_tunable_widget_attributes() -> None:
    theme = default_hud_theme(density="compact", high_contrast=True)
    container = HudContainerView(
        component_id="root",
        render_mode="panel",
        layout=HudLayoutSpec(kind="grid", columns=2),
    )
    gauge = DonutGaugeView(
        component_id="move_ring",
        inner_diameter_px=48.0,
        outer_diameter_px=92.0,
        progress_fraction=0.5,
        label_text="Move",
    )

    assert theme.high_contrast is True
    assert container.layout.columns == 2
    assert gauge.inner_diameter_px == 48.0
    assert gauge.outer_diameter_px == 92.0


def test_documented_production_hud_compositions_load() -> None:
    docs_dir = Path(__file__).parents[1] / "docs" / "hud"
    for filename in ("default-hud.yaml", "command-bench-hud.yaml"):
        result = load_hud_composition(docs_dir / filename)

        assert result.profile is not None, result.diagnostics
        assert result.diagnostics == ()
        assert result.profile.sample_data == {}


def test_preview_composition_supports_sample_data_and_component_lookup() -> None:
    path = Path(__file__).parents[1] / "docs" / "hud" / "examples" / "unit-datasheet-preview.yaml"

    result = load_hud_composition(path, preview=True)

    assert result.profile is not None, result.diagnostics
    assert result.profile.profile_id == "unit_datasheet_preview"
    assert "selected_unit" in result.profile.sample_data


def test_preferences_composition_reference_loads_and_missing_path_is_diagnostic() -> None:
    preferences = default_preferences()

    result = load_hud_composition_for_preferences(preferences)

    assert result.profile is not None, result.diagnostics
    assert result.profile.source_path == Path("docs/hud/default-hud.yaml")

    missing_preferences = replace(
        preferences,
        hud=replace(preferences.hud, composition_profile="docs/hud/missing.yaml"),
    )
    missing_result = load_hud_composition_for_preferences(missing_preferences)

    assert missing_result.profile is None
    assert "composition_file_error" in _codes(missing_result)


def test_composition_rejects_unknown_widget_type_and_attribute() -> None:
    payload = {
        "schema_version": 1,
        "profile_id": "bad_profile",
        "layout_preset": "compass_ring",
        "theme": "default",
        "regions": {
            "right_inspector": {
                "widget": {
                    "type": "MysteryBox",
                    "id": "mystery",
                    "rule_validation": "not allowed",
                }
            }
        },
    }

    result = parse_hud_composition_payload(payload)

    assert result.profile is None
    assert {"unknown_widget_type", "unknown_widget_attribute"}.issubset(_codes(result))


def test_preview_composition_reports_missing_sample_data_and_unsafe_includes() -> None:
    payload = {
        "schema_version": 1,
        "profile_id": "bad_preview",
        "layout_preset": "compass_ring",
        "theme": "default",
        "include": "../shared.yaml",
        "regions": {
            "right_inspector": {
                "widget": {
                    "type": "DatasheetPanel",
                    "id": "selected_unit_datasheet",
                    "data_ref": "selected_unit",
                    "title": "Selected Unit",
                }
            }
        },
    }

    result = parse_hud_composition_payload(payload, preview=True)

    assert result.profile is None
    assert {"unsafe_include", "missing_sample_data"}.issubset(_codes(result))


def test_runtime_composition_rejects_preview_sample_data() -> None:
    payload = {
        "schema_version": 1,
        "profile_id": "runtime_with_preview_data",
        "layout_preset": "compass_ring",
        "theme": "default",
        "sample_data": {"selected_unit": {"name": "Unit"}},
        "regions": {
            "right_inspector": {
                "widget": {"type": "DatasheetPanel", "id": "selected_unit_datasheet"}
            }
        },
    }

    result = parse_hud_composition_payload(payload)

    assert result.profile is None
    assert "production_sample_data_not_allowed" in _codes(result)


def test_composition_renderer_builds_component_primitives() -> None:
    path = Path(__file__).parents[1] / "docs" / "hud" / "examples" / "workbench-preview.yaml"
    result = load_hud_composition(path, preview=True)
    assert result.profile is not None, result.diagnostics

    primitives = render_composition_profile(
        result.profile,
        viewport_width_px=640,
        viewport_height_px=360,
        component_id="movement_budget_ring",
    )

    assert any(type(primitive) is PolygonPrimitive for primitive in primitives)
    assert any(type(primitive) is CirclePrimitive for primitive in primitives)
    assert any(
        type(primitive) is TextPrimitive and primitive.text == "Move" for primitive in primitives
    )


def test_datasheet_preview_stat_labels_do_not_overlap_values() -> None:
    path = Path(__file__).parents[1] / "docs" / "hud" / "examples" / "unit-datasheet-preview.yaml"
    result = load_hud_composition(path, preview=True)
    assert result.profile is not None, result.diagnostics

    primitives = render_composition_profile(
        result.profile,
        viewport_width_px=1280,
        viewport_height_px=800,
    )
    label = _exact_text_primitive(primitives, "M")
    value = _exact_text_primitive(primitives, "6")

    assert label.anchor_y == "top"
    assert value.anchor_y == "center"
    label_bottom = label.position[1] - label.font_size
    value_top = value.position[1] + (value.font_size / 2.0)

    assert label_bottom - value_top >= 2.0


def test_non_renderable_container_positions_children_without_own_panel() -> None:
    payload = {
        "schema_version": 1,
        "profile_id": "container_preview",
        "layout_preset": "compass_ring",
        "theme": "default",
        "sample_data": {
            "current_action": {"label": "Normal Move"},
            "movement_budget": {"progress_fraction": 0.5},
        },
        "regions": {
            "bottom_workbench": {
                "widget": {
                    "type": "HudContainer",
                    "id": "root",
                    "render_mode": "none",
                    "layout": {
                        "kind": "grid",
                        "columns": 2,
                        "gap_px": 4,
                        "padding_px": 4,
                    },
                    "children": [
                        {
                            "type": "IconTextBar",
                            "id": "action",
                            "data_ref": "current_action",
                            "primary_label": "Action",
                        },
                        {
                            "type": "DonutGauge",
                            "id": "ring",
                            "data_ref": "movement_budget",
                            "inner_diameter": 16,
                            "outer_diameter": 32,
                            "label_text": "Move",
                        },
                    ],
                }
            }
        },
    }
    result = parse_hud_composition_payload(payload, preview=True)
    assert result.profile is not None, result.diagnostics

    primitives = render_composition_profile(
        result.profile,
        viewport_width_px=400,
        viewport_height_px=220,
        component_id="root",
    )
    panel_count = sum(1 for primitive in primitives if type(primitive) is PolygonPrimitive)

    assert panel_count >= 2
    assert any(type(primitive) is CirclePrimitive for primitive in primitives)


def test_hud_preview_headless_writes_png_and_metadata(tmp_path: Path) -> None:
    path = Path(__file__).parents[1] / "docs" / "hud" / "examples" / "workbench-preview.yaml"

    hud_preview_main(
        [
            str(path),
            "--component",
            "movement_budget_ring",
            "--headless",
            "--artifact-dir",
            str(tmp_path),
            "--width",
            "320",
            "--height",
            "240",
        ]
    )

    assert (tmp_path / "workbench_preview-movement_budget_ring.png").exists()
    assert (tmp_path / "workbench_preview-movement_budget_ring.json").exists()


def test_interactive_preview_clears_each_frame_without_start_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = FakePreviewRuntime()
    monkeypatch.setattr(hud_preview, "_load_arcade", lambda: runtime)

    hud_preview.run_interactive_preview(primitives=(), width=320, height=240, title="HUD Preview")

    assert runtime.window is not None
    assert runtime.window.clear_calls == 2
    assert runtime.run_calls == 1
    assert runtime.start_render_calls == 0


def test_hud_preview_reports_invalid_yaml_with_exit_code() -> None:
    payload = {
        "schema_version": 1,
        "profile_id": "bad_preview",
        "layout_preset": "compass_ring",
        "theme": "default",
        "regions": {
            "right_inspector": {"widget": {"type": "Nope", "id": "bad"}},
        },
    }

    result = parse_hud_composition_payload(payload, preview=True)

    assert result.profile is None
    assert "unknown_widget_type" in _codes(result)


class FakePreviewWindow:
    """Test double for the interactive HUD preview window."""

    def __init__(self) -> None:
        self.clear_calls = 0
        self.on_draw: Callable[[], None] | None = None

    def clear(self) -> None:
        self.clear_calls += 1

    def push_handlers(self, *, on_draw: Callable[[], None]) -> None:
        self.on_draw = on_draw


class FakePreviewRuntime:
    """Test double for the Arcade runtime used by interactive preview."""

    def __init__(self) -> None:
        self.window: FakePreviewWindow | None = None
        self.run_calls = 0
        self.start_render_calls = 0

    def Window(self, **_kwargs: object) -> FakePreviewWindow:
        self.window = FakePreviewWindow()
        return self.window

    def run(self) -> None:
        self.run_calls += 1
        assert self.window is not None
        assert self.window.on_draw is not None
        self.window.on_draw()
        self.window.on_draw()

    def start_render(self) -> None:
        self.start_render_calls += 1
        raise AssertionError("interactive preview must use window.clear(), not start_render()")

    def draw_polygon_filled(
        self,
        _points: tuple[tuple[float, float], ...],
        _color: tuple[int, int, int, int],
    ) -> None:
        return None

    def draw_polygon_outline(
        self,
        _points: tuple[tuple[float, float], ...],
        _color: tuple[int, int, int, int],
        _line_width: float,
    ) -> None:
        return None

    def draw_circle_filled(
        self,
        _x: float,
        _y: float,
        _radius: float,
        _color: tuple[int, int, int, int],
    ) -> None:
        return None

    def draw_circle_outline(
        self,
        _x: float,
        _y: float,
        _radius: float,
        _color: tuple[int, int, int, int],
        _line_width: float,
    ) -> None:
        return None

    def draw_line(
        self,
        _start_x: float,
        _start_y: float,
        _end_x: float,
        _end_y: float,
        _color: tuple[int, int, int, int],
        _line_width: float,
    ) -> None:
        return None

    def draw_text(self, *_args: object, **_kwargs: object) -> None:
        return None


def _codes(result: HudCompositionValidationResult) -> set[str]:
    return {diagnostic.code for diagnostic in result.diagnostics}


def _exact_text_primitive(
    primitives: tuple[object, ...],
    text: str,
) -> TextPrimitive:
    matches = [
        primitive
        for primitive in primitives
        if type(primitive) is TextPrimitive and primitive.text == text
    ]
    assert len(matches) == 1
    return matches[0]
