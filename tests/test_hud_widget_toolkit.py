"""Tests for the configurable HUD widget toolkit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Protocol, cast

import pytest

from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.hud import preview as hud_preview
from warhammer40k_arcade_ui.hud.composition import (
    HudCompositionProfile,
    HudCompositionValidationResult,
    load_hud_composition,
    load_hud_composition_for_preferences,
    load_hud_composition_reference,
    parse_hud_composition_payload,
)
from warhammer40k_arcade_ui.hud.layouts import ScreenRect
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
    parse_overflow_policy,
    parse_scroll_config,
    parse_size_spec,
    parse_status_chip_shape,
)
from warhammer40k_arcade_ui.hud.toolkit_render import (
    render_composition_profile,
    render_composition_profile_with_hit_regions,
)
from warhammer40k_arcade_ui.preferences import io as preferences_io
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.preferences.io import load_preferences, write_preferences
from warhammer40k_arcade_ui.render.arcade_window import (
    ArcadeWarhammerWindow,
    HudPreferencesConfigurationError,
)
from warhammer40k_arcade_ui.render.primitives import (
    CirclePrimitive,
    PolygonPrimitive,
    TextPrimitive,
)
from warhammer40k_arcade_ui.render.scissor import (
    intersect_scissors,
    scissor_tuple,
    scoped_scissor,
)
from warhammer40k_arcade_ui.resources.source import ConfigSource


def test_widget_registry_exposes_expected_phase19_inventory() -> None:
    assert {
        "HudContainer",
        "IconTextBar",
        "DonutGauge",
        "DatasheetPanel",
        "AssignmentGroupRow",
        "DiceTray",
        "CurrentActionPanel",
    }.issubset(known_widget_types())
    assert {"render_mode", "clip_children"}.issubset(component_allowed_attributes("HudContainer"))
    assert {"inner_diameter", "outer_diameter", "progress_fraction"}.issubset(
        component_allowed_attributes("DonutGauge")
    )
    assert "action.movement" in known_icon_ids()
    assert "dice.aeldari.d6.face_6" in known_icon_ids()
    assert "selected_unit" in known_data_refs()
    assert "dice_tray" in known_data_refs()


def test_current_action_panel_renders_clickable_finite_option_buttons() -> None:
    payload = {
        "schema_version": 1,
        "profile_id": "current_action_buttons",
        "layout_preset": "compass_ring",
        "theme": "default",
        "sample_data": {
            "current_action": {
                "title": "Current Action: Movement",
                "actor": "player-a",
                "request": "select_movement_action",
                "status": "Movement action pending",
                "confirm_hint": "ENTER: submit selected option",
                "buttons": [
                    {
                        "button_id": "finite_option_0_normal_move",
                        "command_id": "select_finite_option",
                        "action_kind": "finite_option",
                        "request_id": "decision-request-1",
                        "option_id": "normal_move",
                        "label": "Normal Move",
                        "state": "selected",
                        "selected": True,
                        "enabled": True,
                    },
                    {
                        "button_id": "finite_option_1_advance",
                        "command_id": "select_finite_option",
                        "action_kind": "finite_option",
                        "request_id": "decision-request-1",
                        "option_id": "advance",
                        "label": "Advance",
                        "state": "normal",
                        "selected": False,
                        "enabled": True,
                    },
                    {
                        "button_id": "finite_option_2_remain_stationary",
                        "command_id": "select_finite_option",
                        "action_kind": "finite_option",
                        "request_id": "decision-request-1",
                        "option_id": "remain_stationary",
                        "label": "Remain Stationary",
                        "state": "normal",
                        "selected": False,
                        "enabled": True,
                    },
                    {
                        "button_id": "finite_option_3_fall_back",
                        "command_id": "select_finite_option",
                        "action_kind": "finite_option",
                        "request_id": "decision-request-1",
                        "option_id": "fall_back",
                        "label": "Fall Back",
                        "state": "normal",
                        "selected": False,
                        "enabled": True,
                    },
                ],
            }
        },
        "regions": {
            "bottom_workbench": {
                "widget": {
                    "type": "CurrentActionPanel",
                    "id": "current_action_panel",
                    "data_ref": "current_action",
                    "button_height": 34,
                    "button_min_width": 90,
                }
            }
        },
    }
    result = parse_hud_composition_payload(payload, preview=True)
    assert result.profile is not None, result.diagnostics

    render_result = render_composition_profile_with_hit_regions(
        result.profile,
        viewport_width_px=640,
        viewport_height_px=360,
        component_id="current_action_panel",
    )
    texts = [
        primitive.text for primitive in render_result.primitives if type(primitive) is TextPrimitive
    ]

    assert "Current Action: Movement" in texts
    assert "Normal Move" in texts
    assert "Advance" in texts
    assert len(render_result.hit_regions) == 4
    assert render_result.hit_regions[0].option_id == "normal_move"
    assert render_result.hit_regions[0].request_id == "decision-request-1"
    first_row_tops = {region.bounds[3] for region in render_result.hit_regions[:3]}
    assert len(first_row_tops) == 1
    assert render_result.hit_regions[3].bounds[3] < render_result.hit_regions[0].bounds[3]
    assert render_result.hit_regions[0].contains(
        (render_result.hit_regions[0].bounds[0] + render_result.hit_regions[0].bounds[2]) / 2.0,
        (render_result.hit_regions[0].bounds[1] + render_result.hit_regions[0].bounds[3]) / 2.0,
    )


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


def test_phase23_size_overflow_and_status_chip_shape_parsers() -> None:
    assert parse_size_spec("48px").value == 48.0
    assert parse_size_spec("35%").unit == "percent"
    assert parse_size_spec("2fr").unit == "fr"
    assert parse_size_spec("fit-content").unit == "fit_content"
    overflow = parse_overflow_policy({"mode": "shrink_to_fit", "min_font_size_px": 9})
    assert overflow.mode == "shrink_to_fit"
    assert overflow.min_font_size_px == 9.0
    round_shape = parse_status_chip_shape({"shape": "round", "diameter_px": 44})
    square_shape = parse_status_chip_shape({"shape": "square", "size_px": 52})
    assert round_shape.square_extent_px == 44.0
    assert square_shape.square_extent_px == 52.0


def test_phase31_scroll_config_parser_accepts_two_axis_scroll() -> None:
    scroll = parse_scroll_config(
        {
            "enabled": True,
            "axes": "both",
            "wheel_axis": "auto",
            "show_scrollbars": "always",
            "wheel_step_px": 36,
            "clamp_to_content": True,
        }
    )

    assert scroll.enabled is True
    assert scroll.allows_x is True
    assert scroll.allows_y is True
    assert scroll.wheel_axis == "auto"
    assert scroll.show_scrollbars == "always"
    assert scroll.wheel_step_px == 36.0


def test_player_units_roster_renders_scroll_region_and_unit_buttons() -> None:
    result = parse_hud_composition_payload(
        {
            "schema_version": 1,
            "profile_id": "player_units_roster_preview",
            "layout_preset": "compass_ring",
            "theme": "default",
            "sample_data": {
                "hud.player_units.roster": {
                    "title": "Player Units",
                    "summary": "6 projected unit(s)",
                    "buttons": [
                        {
                            "button_id": f"player_unit_{index}",
                            "command_id": "select_unit",
                            "action_kind": "select_unit",
                            "unit_id": f"unit-{index}",
                            "label": f"Intercessor Unit {index}",
                            "icon_id": "entity.unit",
                            "text_icon": "UN",
                            "enabled": True,
                            "selected": index == 2,
                            "state": "selected" if index == 2 else "normal",
                        }
                        for index in range(6)
                    ],
                }
            },
            "regions": {
                "left_rail": {
                    "widget": {
                        "type": "PlayerUnitsRoster",
                        "id": "player_units_roster",
                        "data_ref": "hud.player_units.roster",
                        "title": "Player Units",
                        "height": "140px",
                        "button_height": 30,
                        "scroll": {"enabled": True, "axes": "y"},
                    }
                }
            },
        },
        preview=True,
    )
    assert result.profile is not None, result.diagnostics

    render_result = render_composition_profile_with_hit_regions(
        result.profile,
        viewport_width_px=360,
        viewport_height_px=260,
        component_id="player_units_roster",
    )

    assert [region.component_id for region in render_result.scroll_regions] == [
        "player_units_roster"
    ]
    assert render_result.scroll_regions[0].max_offset_y > 0.0
    assert any(region.action_kind == "select_unit" for region in render_result.hit_regions)
    assert {region.unit_id for region in render_result.hit_regions} <= {
        f"unit-{index}" for index in range(6)
    }


def test_composition_rejects_invalid_phase23_schema_values() -> None:
    payload = {
        "schema_version": 1,
        "profile_id": "bad_phase23_values",
        "layout_preset": "compass_ring",
        "theme": "default",
        "regions": {
            "top_ribbon": {
                "widget": {
                    "type": "HudContainer",
                    "id": "root",
                    "layout": {"kind": "stack", "orientation": "horizontal"},
                    "children": [
                        {
                            "type": "StatusChip",
                            "id": "bad_chip",
                            "label": "Bad",
                            "width": "-1px",
                            "shape": {"shape": "triangle"},
                        },
                        {
                            "type": "IconTextBar",
                            "id": "bad_bar",
                            "primary_label": "Bad",
                            "overflow": {"mode": "explode"},
                        },
                        {
                            "type": "Tooltip",
                            "id": "bad_constraints",
                            "title": "Bad constraints",
                            "min_width": "120px",
                            "max_width": "64px",
                            "scroll": {"enabled": True, "axes": "diagonal"},
                        },
                    ],
                }
            }
        },
    }

    result = parse_hud_composition_payload(payload)

    assert result.profile is None
    assert {
        "invalid_size_spec",
        "invalid_status_chip_shape",
        "invalid_overflow_policy",
        "invalid_size_constraint",
        "invalid_scroll_config",
    }.issubset(_codes(result))


def test_documented_production_hud_compositions_load() -> None:
    docs_dir = Path(__file__).parents[1] / "docs" / "hud"
    for filename in ("default-hud.yaml", "command-bench-hud.yaml"):
        result = load_hud_composition(docs_dir / filename)

        assert result.profile is not None, result.diagnostics
        assert result.diagnostics == ()
        assert result.profile.sample_data == {}


def test_phase23_overflow_stress_preview_loads() -> None:
    path = Path(__file__).parents[1] / "docs" / "hud" / "examples" / "overflow-stress-preview.yaml"

    result = load_hud_composition(path, preview=True)

    assert result.profile is not None, result.diagnostics
    assert result.profile.profile_id == "overflow_stress_preview"


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
    assert result.profile.source_path is None
    assert result.profile.source is not None
    assert result.profile.source.kind == "builtin"
    assert result.profile.source.name == "hud/default-hud.yaml"

    missing_preferences = replace(
        preferences,
        hud=replace(preferences.hud, composition_profile="docs/hud/missing.yaml"),
    )
    missing_result = load_hud_composition_for_preferences(missing_preferences)

    assert missing_result.profile is None
    assert "composition_file_error" in _codes(missing_result)


def test_platform_default_preferences_without_composition_profile_fail_loudly(
    tmp_path: Path,
) -> None:
    preferences = default_preferences()
    preferences = replace(
        preferences,
        hud=replace(preferences.hud, composition_profile=None),
    )
    preference_path = tmp_path / "ui-preferences.yaml"

    result = load_hud_composition_for_preferences(
        preferences,
        source=ConfigSource(kind="user_default", name=str(preference_path), path=preference_path),
    )

    assert result.profile is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.severity == "error"
    assert diagnostic.code == "platform_preferences_missing_hud_composition"
    assert "Move that file out of the way or update it manually" in diagnostic.message
    assert "warhammer40k-export-preferences --profile default --format yaml" in diagnostic.message


def test_stale_platform_default_preferences_raise_terminal_startup_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preferences = default_preferences()
    preferences = replace(
        preferences,
        hud=replace(preferences.hud, composition_profile=None),
    )
    preference_path = tmp_path / "ui-preferences.yaml"
    write_preferences(preferences=preferences, path=preference_path)
    monkeypatch.setattr(preferences_io, "default_preferences_path", lambda: preference_path)

    with pytest.raises(HudPreferencesConfigurationError) as exc_info:
        ArcadeWarhammerWindow(config=AppConfig(window_width=320, window_height=240))

    message = str(exc_info.value)
    assert str(preference_path) in message
    assert "Platform default UI preferences are incompatible" in message
    assert "Move that file out of the way or update it manually" in message
    assert "warhammer40k-export-preferences --profile default --format yaml" in message
    assert "mv " in message


def test_builtin_and_explicit_hud_composition_references_load() -> None:
    builtin = load_hud_composition_reference("default-hud")
    explicit = load_hud_composition(Path("docs/hud/default-hud.yaml"))

    assert builtin.profile is not None, builtin.diagnostics
    assert explicit.profile is not None, explicit.diagnostics
    assert builtin.profile.profile_id == explicit.profile.profile_id
    assert builtin.profile.source is not None
    assert builtin.profile.source.display_name == "builtin:hud/default-hud.yaml"
    assert explicit.profile.source is not None
    assert explicit.profile.source.kind == "explicit_path"


def test_hud_composition_reference_resolves_relative_to_filesystem_preference_source(
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / "ui-preferences.yaml"
    hud_path = tmp_path / "hud" / "custom-hud.yaml"
    hud_path.parent.mkdir()
    hud_path.write_text(
        Path("docs/hud/default-hud.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    preferences = default_preferences()
    preferences = replace(
        preferences,
        hud=replace(preferences.hud, composition_profile="hud/custom-hud.yaml"),
    )
    write_preferences(preferences=preferences, path=profile_path)
    preferences_result = load_preferences(profile_path)
    assert preferences_result.preferences is not None
    assert preferences_result.source is not None

    result = load_hud_composition_for_preferences(
        preferences_result.preferences,
        source=preferences_result.source,
    )

    assert result.profile is not None, result.diagnostics
    assert result.profile.source is not None
    assert result.profile.source.kind == "explicit_path"
    assert result.profile.source.path == hud_path


def test_hud_composition_reference_resolves_relative_to_package_resource_source() -> None:
    preferences = default_preferences()
    preferences = replace(
        preferences,
        hud=replace(preferences.hud, composition_profile="../hud/default-hud.yaml"),
    )

    result = load_hud_composition_for_preferences(
        preferences,
        source=ConfigSource(kind="builtin", name="preferences/custom.yaml"),
    )

    assert result.profile is not None, result.diagnostics
    assert result.profile.source is not None
    assert result.profile.source.kind == "builtin"
    assert result.profile.source.name == "hud/default-hud.yaml"


def test_unsafe_package_relative_hud_reference_returns_diagnostic() -> None:
    preferences = default_preferences()
    preferences = replace(
        preferences,
        hud=replace(preferences.hud, composition_profile="../../outside.yaml"),
    )

    result = load_hud_composition_for_preferences(
        preferences,
        source=ConfigSource(kind="builtin", name="preferences/default.yaml"),
    )

    assert result.profile is None
    assert result.diagnostics
    assert result.diagnostics[0].code == "composition_source_error"


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


def test_workbench_preview_renders_dice_tray_in_right_two_thirds() -> None:
    path = Path(__file__).parents[1] / "docs" / "hud" / "examples" / "workbench-preview.yaml"
    result = load_hud_composition(path, preview=True)
    assert result.profile is not None, result.diagnostics

    primitives = render_composition_profile(
        result.profile,
        viewport_width_px=900,
        viewport_height_px=360,
        component_id="workbench_preview_root",
    )

    dice_tray_panel = _panel_for_text(primitives, "Dice Tray")
    texts = [primitive.text for primitive in primitives if type(primitive) is TextPrimitive]

    assert _polygon_left(dice_tray_panel) > 300.0
    assert "Reroll" in texts
    assert "x1" in texts
    assert "sel 1" in texts
    assert "decline" in texts


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


def test_datasheet_preview_stat_cells_stay_inside_panel_bounds() -> None:
    path = Path(__file__).parents[1] / "docs" / "hud" / "examples" / "unit-datasheet-preview.yaml"
    result = load_hud_composition(path, preview=True)
    assert result.profile is not None, result.diagnostics

    primitives = render_composition_profile(
        result.profile,
        viewport_width_px=1280,
        viewport_height_px=800,
    )
    panel = _panel_for_text(primitives, "Selected Unit")
    oc_label = _exact_text_primitive(primitives, "OC")

    estimated_text_right = oc_label.position[0] + (oc_label.font_size * len(oc_label.text) * 0.3)
    assert estimated_text_right <= _polygon_right(panel)


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


def test_phase23_status_chip_shapes_and_axis_sizes_render_deterministically() -> None:
    path = Path(__file__).parents[1] / "docs" / "hud" / "examples" / "overflow-stress-preview.yaml"
    result = load_hud_composition(path, preview=True)
    assert result.profile is not None, result.diagnostics

    primitives = render_composition_profile(
        result.profile,
        viewport_width_px=960,
        viewport_height_px=540,
        component_id="overflow_stress_top_ribbon",
    )
    round_chip = next(
        primitive
        for primitive in primitives
        if type(primitive) is CirclePrimitive and primitive.layer == "hud_widget_status_chip"
    )
    square_panel = _square_panel(primitives, size=52.0)

    assert round_chip.radius == 24.0
    assert _polygon_right(square_panel) - _polygon_left(square_panel) == 52.0
    assert _polygon_top(square_panel) - _polygon_bottom(square_panel) == 52.0


def test_phase23_stack_layout_honors_px_fr_fill_and_fit_content() -> None:
    payload = {
        "schema_version": 1,
        "profile_id": "phase23_axis_sizes",
        "layout_preset": "compass_ring",
        "theme": "default",
        "regions": {
            "bottom_workbench": {
                "widget": {
                    "type": "HudContainer",
                    "id": "root",
                    "render_mode": "none",
                    "layout": {
                        "kind": "stack",
                        "orientation": "horizontal",
                        "gap_px": 0,
                        "padding_px": 0,
                    },
                    "children": [
                        {
                            "type": "IconTextBar",
                            "id": "fixed",
                            "primary_label": "Fixed",
                            "width": "100px",
                        },
                        {
                            "type": "IconTextBar",
                            "id": "fraction",
                            "primary_label": "Fraction",
                            "width": "2fr",
                        },
                        {
                            "type": "IconTextBar",
                            "id": "fill",
                            "primary_label": "Fill",
                            "width": "fill",
                        },
                        {
                            "type": "IconTextBar",
                            "id": "fit",
                            "primary_label": "Fit content",
                            "width": "fit-content",
                        },
                    ],
                }
            }
        },
    }
    result = parse_hud_composition_payload(payload)
    assert result.profile is not None, result.diagnostics

    primitives = render_composition_profile(
        result.profile,
        viewport_width_px=500,
        viewport_height_px=220,
        component_id="root",
    )
    fixed_panel = _panel_for_text(primitives, "Fixed")
    fraction_panel = _panel_for_text(primitives, "Fraction")
    fill_panel = _panel_for_text(primitives, "Fill")

    assert _polygon_right(fixed_panel) - _polygon_left(fixed_panel) == 100.0
    assert (_polygon_right(fraction_panel) - _polygon_left(fraction_panel)) > (
        _polygon_right(fill_panel) - _polygon_left(fill_panel)
    )


def test_phase23_component_primitives_carry_clip_rects() -> None:
    path = Path(__file__).parents[1] / "docs" / "hud" / "examples" / "overflow-stress-preview.yaml"
    result = load_hud_composition(path, preview=True)
    assert result.profile is not None, result.diagnostics

    primitives = render_composition_profile(
        result.profile,
        viewport_width_px=960,
        viewport_height_px=540,
        component_id="long_pending_action_status",
    )

    assert any(
        type(primitive) is TextPrimitive and primitive.clip_rect is not None
        for primitive in primitives
    )


def test_phase23_scissor_helpers_intersect_and_restore_context() -> None:
    ctx = FakeScissorContext()
    ctx.scissor = (0, 0, 100, 100)

    assert scissor_tuple(ScreenRect(4.2, 5.8, 10.1, 20.1)) == (4, 5, 11, 21)
    assert intersect_scissors((0, 0, 100, 100), (50, 20, 100, 10)) == (50, 20, 50, 10)

    with scoped_scissor(ctx, ScreenRect(20.0, 30.0, 90.0, 90.0)):
        assert ctx.scissor == (20, 30, 80, 70)

    assert ctx.scissor == (0, 0, 100, 100)


def test_phase23_arcade_scissor_clips_headless_framebuffer() -> None:
    import arcade

    window = arcade.Window(64, 64, visible=False)
    arcade.set_window(window)
    try:
        framebuffer = cast(_FramebufferReader, window.ctx.screen)
        framebuffer.use()
        window.clear(color=(0, 0, 0, 255))
        with scoped_scissor(window.ctx, ScreenRect(0.0, 0.0, 32.0, 64.0)):
            arcade.draw_polygon_filled(
                ((0.0, 0.0), (64.0, 0.0), (64.0, 64.0), (0.0, 64.0)),
                (255, 0, 0, 255),
            )
        window.ctx.finish()
        rgba = framebuffer.read(
            viewport=(0, 0, 64, 64),
            components=4,
            attachment=0,
            dtype="f1",
        )
    finally:
        window.close()

    assert _pixel(rgba, x=8, y=32) == (255, 0, 0, 255)
    assert _pixel(rgba, x=56, y=32) == (0, 0, 0, 255)


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


def test_hud_preview_accepts_packaged_builtin_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_profile_ids: list[str] = []

    def fake_render_headless_artifacts(
        *,
        profile: HudCompositionProfile,
        primitives: object,
        width: int,
        height: int,
        component_id: str | None,
        artifact_dir: Path,
    ) -> hud_preview.PreviewArtifactPaths:
        del primitives, width, height, component_id
        captured_profile_ids.append(profile.profile_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        image_path = artifact_dir / "preview.png"
        metadata_path = artifact_dir / "preview.json"
        image_path.write_bytes(b"png")
        metadata_path.write_text("{}", encoding="utf-8")
        return hud_preview.PreviewArtifactPaths(image_path=image_path, metadata_path=metadata_path)

    monkeypatch.setattr(hud_preview, "render_headless_artifacts", fake_render_headless_artifacts)

    hud_preview_main(["default-hud", "--headless", "--artifact-dir", str(tmp_path)])

    assert captured_profile_ids == ["default_compass_hud"]


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


class FakeScissorContext:
    """Small context double for scoped scissor tests."""

    def __init__(self) -> None:
        self.scissor: tuple[int, int, int, int] | None = None


class _FramebufferReader(Protocol):
    """Subset of Arcade framebuffer behavior used by the scissor regression test."""

    def use(self) -> None:
        """Bind the framebuffer."""

        ...

    def read(
        self,
        *,
        viewport: tuple[int, int, int, int],
        components: int,
        attachment: int,
        dtype: str,
    ) -> bytes:
        """Read raw framebuffer bytes."""

        ...


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


def _panel_for_text(
    primitives: tuple[object, ...],
    text: str,
) -> PolygonPrimitive:
    text_primitive = _exact_text_primitive(primitives, text)
    panels = [primitive for primitive in primitives if type(primitive) is PolygonPrimitive]
    containing_panels = [
        panel
        for panel in panels
        if _polygon_left(panel) <= text_primitive.position[0] <= _polygon_right(panel)
        and _polygon_bottom(panel) <= text_primitive.position[1] <= _polygon_top(panel)
    ]
    assert containing_panels
    return max(containing_panels, key=lambda panel: _polygon_left(panel))


def _square_panel(primitives: tuple[object, ...], *, size: float) -> PolygonPrimitive:
    matches = [
        primitive
        for primitive in primitives
        if type(primitive) is PolygonPrimitive
        and _polygon_right(primitive) - _polygon_left(primitive) == size
        and _polygon_top(primitive) - _polygon_bottom(primitive) == size
    ]
    assert len(matches) == 1
    return matches[0]


def _polygon_left(primitive: PolygonPrimitive) -> float:
    return min(point[0] for point in primitive.points)


def _polygon_right(primitive: PolygonPrimitive) -> float:
    return max(point[0] for point in primitive.points)


def _polygon_top(primitive: PolygonPrimitive) -> float:
    return max(point[1] for point in primitive.points)


def _polygon_bottom(primitive: PolygonPrimitive) -> float:
    return min(point[1] for point in primitive.points)


def _pixel(rgba: bytes, *, x: int, y: int) -> tuple[int, int, int, int]:
    index = ((y * 64) + x) * 4
    return (rgba[index], rgba[index + 1], rgba[index + 2], rgba[index + 3])
