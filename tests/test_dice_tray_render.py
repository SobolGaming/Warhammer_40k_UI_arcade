"""Dice assignment evidence must survive the runtime HUD renderer and framebuffer."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops

from warhammer40k_arcade_ui.core_client.protocol import JsonObject
from warhammer40k_arcade_ui.hud.composition import (
    HudCompositionProfile,
    find_component,
    load_hud_composition_reference,
)
from warhammer40k_arcade_ui.hud.dice_tray import (
    build_dice_tray_view,
    dice_tray_runtime_data,
)
from warhammer40k_arcade_ui.hud.layouts import ScreenRect
from warhammer40k_arcade_ui.hud.preview import render_headless_artifacts
from warhammer40k_arcade_ui.hud.toolkit import default_hud_theme
from warhammer40k_arcade_ui.hud.toolkit_render import render_component_tree
from warhammer40k_arcade_ui.render.primitives import RenderPrimitive, TextPrimitive

_TRAY_RECT = ScreenRect(0.0, 0.0, 760.0, 148.0)
_SOURCE_RULE_ID = "gw-11e-core-dice-results:treated-as-set-to"


def test_dice_tray_renderer_separates_component_and_aggregate_assignments() -> None:
    component_data = _override_data(component_index=0)
    aggregate_data = _override_data(component_index=None)
    _, component_primitives = _render_tray(component_data)
    _, aggregate_primitives = _render_tray(aggregate_data)

    component_lines = _assignment_lines(component_primitives)
    aggregate_lines = _assignment_lines(aggregate_primitives)
    assert component_lines == (
        "Physical 2, 5 | Assigned 9, 5 | die 1=9",
        f"Rule source: {_SOURCE_RULE_ID}",
    )
    assert aggregate_lines == (
        "Physical 2, 5 | Aggregate assigned 14",
        f"Rule source: {_SOURCE_RULE_ID}",
    )
    assert component_lines != aggregate_lines
    assert component_data["values"] == aggregate_data["values"] == [2, 5]
    assert component_data["total"] == aggregate_data["total"] == 14
    assert component_data["faces"] == aggregate_data["faces"]
    for primitives in (component_primitives, aggregate_primitives):
        assert any(
            type(primitive) is TextPrimitive and "total 14" in primitive.text
            for primitive in primitives
        )
        assignment_primitives = tuple(
            primitive
            for primitive in primitives
            if type(primitive) is TextPrimitive and primitive.layer == "hud_widget_dice_assignment"
        )
        assert all(
            0.0 <= primitive.position[1] <= _TRAY_RECT.height for primitive in assignment_primitives
        )


def test_dice_tray_renderer_keeps_core_total_and_rejects_malformed_evidence() -> None:
    aggregate_data = _override_data(component_index=None)
    aggregate_data["total"] = 21
    _, primitives = _render_tray(aggregate_data)
    assert _assignment_lines(primitives)[0] == "Physical 2, 5 | Aggregate assigned 14"
    assert any(
        type(primitive) is TextPrimitive and "total 21" in primitive.text
        for primitive in primitives
    )

    malformed_data = _override_data(component_index=0)
    override = malformed_data["result_override"]
    assert type(override) is dict
    override["component_index"] = 9
    _, malformed_primitives = _render_tray(malformed_data)
    assert _assignment_lines(malformed_primitives) == (
        "Diagnostic: Malformed dice override evidence.",
    )
    malformed_values = _override_data(component_index=0)
    malformed_values["assigned_values"] = [9]
    _, malformed_value_primitives = _render_tray(malformed_values)
    assert _assignment_lines(malformed_value_primitives) == (
        "Diagnostic: Malformed dice assignment evidence.",
    )


def test_compact_dice_tray_keeps_assignment_scope_visible() -> None:
    compact_rect = ScreenRect(0.0, 0.0, 320.0, 140.0)
    _, component_primitives = _render_tray(_override_data(component_index=0), rect=compact_rect)
    _, aggregate_primitives = _render_tray(_override_data(component_index=None), rect=compact_rect)

    assert _assignment_lines(component_primitives)[0] == ("Physical 2, 5 | Assigned 9, 5 | die 1=9")
    assert _assignment_lines(aggregate_primitives)[0] == ("Physical 2, 5 | Aggregate assigned 14")


def test_dice_tray_headless_frame_distinguishes_override_scope(tmp_path: Path) -> None:
    component_profile, component_primitives = _render_tray(_override_data(component_index=0))
    aggregate_profile, aggregate_primitives = _render_tray(_override_data(component_index=None))
    component_path = render_headless_artifacts(
        profile=component_profile,
        primitives=component_primitives,
        width=760,
        height=148,
        component_id="bottom_dice_tray",
        artifact_dir=tmp_path / "component",
    ).image_path
    aggregate_path = render_headless_artifacts(
        profile=aggregate_profile,
        primitives=aggregate_primitives,
        width=760,
        height=148,
        component_id="bottom_dice_tray",
        artifact_dir=tmp_path / "aggregate",
    ).image_path

    with Image.open(component_path) as component, Image.open(aggregate_path) as aggregate:
        # The strip above the physical face columns must visibly change with the scope.
        evidence_region = (0, 42, 760, 86)
        difference = ImageChops.difference(
            component.convert("RGB").crop(evidence_region),
            aggregate.convert("RGB").crop(evidence_region),
        )
        assert difference.getbbox() is not None


def _override_data(*, component_index: int | None) -> JsonObject:
    replacement_value = 9 if component_index is not None else 14
    view = build_dice_tray_view(
        event_payloads=(
            {
                "event_type": "dice_roll_resolved",
                "payload": {
                    "roll_state": {
                        "original_result": {
                            "roll_id": "dice-assignment-1",
                            "spec": {
                                "roll_type": "charge",
                                "reason": "Core charge dice",
                                "expression": {"dice_count": 2, "sides": 6},
                            },
                            "values": [2, 5],
                            "total": 7,
                            "source": "fixed",
                        },
                        "current_values": [9, 5] if component_index is not None else [2, 5],
                        "current_total": 14,
                        "rerolls": [],
                        "result_override": {
                            "decision_id": "dice-assignment-decision-1",
                            "request_id": "dice-assignment-request-1",
                            "source_rule_id": _SOURCE_RULE_ID,
                            "replacement_value": replacement_value,
                            "component_index": component_index,
                        },
                    }
                },
            },
        ),
        pending_decision=None,
    )
    assert view.active_roll is not None
    assert view.diagnostics == ()
    return dice_tray_runtime_data(view)


def _render_tray(
    data: JsonObject, *, rect: ScreenRect = _TRAY_RECT
) -> tuple[HudCompositionProfile, tuple[RenderPrimitive, ...]]:
    loaded = load_hud_composition_reference("default-hud")
    assert loaded.profile is not None, loaded.diagnostics
    node = find_component(loaded.profile, "bottom_dice_tray")
    assert node is not None
    return loaded.profile, render_component_tree(
        node,
        rect=rect,
        theme=default_hud_theme(),
        sample_data={"dice_tray": data},
    )


def _assignment_lines(primitives: tuple[RenderPrimitive, ...]) -> tuple[str, ...]:
    return tuple(
        primitive.text
        for primitive in primitives
        if type(primitive) is TextPrimitive and primitive.layer == "hud_widget_dice_assignment"
    )
