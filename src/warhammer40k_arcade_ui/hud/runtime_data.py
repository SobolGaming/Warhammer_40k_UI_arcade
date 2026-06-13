"""Runtime binding data for HUD composition profiles.

The composition YAML owns placement and presentation. This module keeps the runtime data adapter in
Python so HUD configuration cannot query raw engine state or invent gameplay semantics.
"""

from __future__ import annotations

from dataclasses import replace

from warhammer40k_arcade_ui.hud.ergonomics import HudErgonomicsView
from warhammer40k_arcade_ui.hud.toolkit import (
    AssignmentGroupRowView,
    HudTheme,
    IconTextBarView,
    StatusChipView,
    UnitRailCardView,
    default_hud_theme,
)
from warhammer40k_arcade_ui.preferences.schema import JsonObject


def runtime_data_for_ergonomic_hud(ergonomics: HudErgonomicsView) -> JsonObject:
    """Return JSON-safe named presentation bindings for a HUD composition profile."""

    status_chips = {
        _status_chip_key(chip): _status_chip_data(chip) for chip in ergonomics.status_chips
    }
    selected_unit = _selected_unit_data(
        card=ergonomics.selected_unit_card,
        rows=ergonomics.selected_unit_rows,
    )
    action_rows = tuple(_icon_text_bar_data(row) for row in ergonomics.action_rows)
    assignment_rows = tuple(_assignment_row_data(row) for row in ergonomics.assignment_rows)
    assignment_notice_rows = tuple(
        _icon_text_bar_data(row) for row in ergonomics.assignment_notice_rows
    )
    current_action = _current_action_data(action_rows)
    current_assignment = _current_assignment_data(
        assignment_rows=assignment_rows,
        notice_rows=assignment_notice_rows,
        subtitle=ergonomics.assignment_subtitle,
        color_role=ergonomics.assignment_color_role,
    )
    diagnostics = tuple(
        _line_data(line, title="Diagnostic") for line in ergonomics.diagnostic_lines
    )
    events = tuple(_line_data(line, title="Filtered event") for line in ergonomics.event_lines)
    hotkeys = tuple(_line_data(line, title="Hotkey") for line in ergonomics.hotkey_hints)
    data: JsonObject = {
        "phase_state": status_chips.get("phase", _fallback_status("Phase", "")),
        "active_player": status_chips.get("active_player", _fallback_status("Active", "")),
        "command_points": _fallback_status("CP", "-"),
        "mission_summary": {
            "title": "Missions",
            "summary": _mission_summary(status_chips),
        },
        "player_roster": {
            "unit_label": "Player roster",
            "summary": _roster_summary(selected_unit),
            "status": "viewer-scoped projection",
        },
        "opponent_roster": {
            "unit_label": "Opponent roster",
            "summary": "Opponent projection",
            "status": "",
        },
        "selected_unit": selected_unit,
        "selected_model": _selected_model_data(ergonomics.selected_unit_rows),
        "selection_status": _selection_status(selected_unit),
        "current_action": current_action,
        "movement_budget": _movement_budget_data(ergonomics.action_rows),
        "current_assignment": current_assignment,
        "assignment_groups": list(assignment_rows),
        "debug_status": _debug_status(diagnostics=diagnostics, events=events, hotkeys=hotkeys),
        "hud.status_chips": list(status_chips.values()),
        "hud.status_chips.phase": status_chips.get("phase", _fallback_status("Phase", "")),
        "hud.status_chips.active_player": status_chips.get(
            "active_player",
            _fallback_status("Active", ""),
        ),
        "hud.status_chips.pending": status_chips.get("pending", _fallback_status("Pending", "")),
        "hud.selected_unit.card": selected_unit,
        "hud.selected_unit.rows": [
            _icon_text_bar_data(row) for row in ergonomics.selected_unit_rows
        ],
        "hud.workbench.actions": list(action_rows),
        "hud.workbench.assignments.groups": list(assignment_rows),
        "hud.workbench.assignments.notices": list(assignment_notice_rows),
        "hud.workbench.review.diagnostics": list(diagnostics),
        "hud.workbench.review.events": list(events),
        "hud.workbench.review.hotkeys": list(hotkeys),
    }
    return data


def theme_for_ergonomic_hud(ergonomics: HudErgonomicsView) -> HudTheme:
    """Return the toolkit theme adjusted by ergonomic HUD preferences."""

    scale = max(0.75, min(1.6, ergonomics.text_scale))
    base = default_hud_theme(high_contrast=ergonomics.high_contrast)
    return replace(
        base,
        base_font_size_px=base.base_font_size_px * scale,
        compact_font_size_px=base.compact_font_size_px * scale,
        title_font_size_px=base.title_font_size_px * scale,
        line_height_px=base.line_height_px * scale,
        icon_size_px=base.icon_size_px * scale,
        inner_padding_px=base.inner_padding_px * scale,
    )


def _status_chip_key(chip: StatusChipView) -> str:
    if chip.component_id == "phase_status_chip":
        return "phase"
    if chip.component_id == "active_player_status_chip":
        return "active_player"
    if chip.component_id == "pending_status_chip":
        return "pending"
    return chip.component_id


def _status_chip_data(chip: StatusChipView) -> JsonObject:
    return {
        "label": chip.label,
        "title": chip.label,
        "value": chip.value,
        "summary": chip.value,
        "icon_id": chip.icon_id or "",
        "color_role": chip.color_role,
        "state": chip.state,
    }


def _fallback_status(label: str, value: str) -> JsonObject:
    return {"label": label, "title": label, "value": value, "summary": value}


def _selected_unit_data(
    *,
    card: UnitRailCardView | None,
    rows: tuple[IconTextBarView, ...],
) -> JsonObject:
    if card is None:
        return {
            "label": "No selected unit",
            "unit_label": "No selected unit",
            "summary": "Select a model or unit",
            "status": "",
            "stats": {},
        }
    selected_model = _selected_model_data(rows)
    stats: JsonObject = {}
    model_count = _first_int(card.model_count_summary)
    if model_count is not None:
        stats["Models"] = model_count
    if selected_model.get("summary"):
        stats["Sel"] = "1"
    return {
        "label": card.unit_label,
        "unit_label": card.unit_label,
        "name": card.unit_label,
        "subtitle": card.unit_label,
        "summary": card.model_count_summary,
        "status": card.short_label or card.activation_state,
        "model_count_summary": card.model_count_summary,
        "activation_state": card.activation_state,
        "stats": stats,
    }


def _selected_model_data(rows: tuple[IconTextBarView, ...]) -> JsonObject:
    for row in rows:
        if row.component_id == "selected_model_row":
            return _icon_text_bar_data(row)
    return {"label": "Selected model", "summary": "", "value": ""}


def _selection_status(selected_unit: JsonObject) -> JsonObject:
    summary = selected_unit.get("summary")
    return {
        "label": "Selection",
        "summary": str(summary) if summary is not None else "",
        "status": str(selected_unit.get("status") or ""),
    }


def _icon_text_bar_data(row: IconTextBarView) -> JsonObject:
    return {
        "id": row.component_id,
        "label": row.primary_label,
        "title": row.primary_label,
        "summary": row.secondary_label,
        "subtitle": row.secondary_label,
        "value": row.value_text,
        "icon_id": row.icon_id or "",
        "state": row.state,
        "density": row.density,
    }


def _assignment_row_data(row: AssignmentGroupRowView) -> JsonObject:
    summary = " | ".join(row.summary_lines[:2])
    return {
        "id": row.component_id,
        "label": row.group_label,
        "title": row.group_label,
        "group_label": row.group_label,
        "summary": summary,
        "summary_lines": list(row.summary_lines),
        "status": row.state,
        "operation_kind": row.operation_kind,
        "state": row.state,
    }


def _current_action_data(action_rows: tuple[JsonObject, ...]) -> JsonObject:
    for row in action_rows:
        if row.get("id") == "movement_draft_row":
            return row
    for row in action_rows:
        if row.get("id") == "highlighted_option_row":
            return row
    if action_rows:
        return action_rows[0]
    return {"label": "Current Action", "summary": "No active action", "value": ""}


def _movement_budget_data(action_rows: tuple[IconTextBarView, ...]) -> JsonObject:
    for row in action_rows:
        if row.component_id == "movement_draft_row":
            progress = 1.0 if row.state == "active" else 0.5
            return {
                "label": row.primary_label,
                "summary": row.secondary_label,
                "value": row.value_text,
                "progress_fraction": progress,
            }
    return {
        "label": "Move",
        "summary": "No movement draft",
        "value": "",
        "progress_fraction": 0.0,
    }


def _current_assignment_data(
    *,
    assignment_rows: tuple[JsonObject, ...],
    notice_rows: tuple[JsonObject, ...],
    subtitle: str,
    color_role: str,
) -> JsonObject:
    if notice_rows:
        notice = dict(notice_rows[0])
        notice["status"] = subtitle
        notice["color_role"] = color_role
        return notice
    if assignment_rows:
        assignment = dict(assignment_rows[0])
        assignment["status"] = subtitle
        assignment["color_role"] = color_role
        return assignment
    return {
        "label": "Assignments",
        "summary": subtitle,
        "status": subtitle,
        "color_role": color_role,
    }


def _line_data(line: str, *, title: str) -> JsonObject:
    return {
        "label": title,
        "title": title,
        "summary": line,
        "subtitle": line,
        "value": "",
    }


def _debug_status(
    *,
    diagnostics: tuple[JsonObject, ...],
    events: tuple[JsonObject, ...],
    hotkeys: tuple[JsonObject, ...],
) -> JsonObject:
    for collection in (diagnostics, events, hotkeys):
        if collection:
            return collection[0]
    return {"label": "Review", "summary": "No diagnostics", "value": ""}


def _mission_summary(status_chips: dict[str, JsonObject]) -> str:
    phase = status_chips.get("phase", {}).get("value")
    active = status_chips.get("active_player", {}).get("value")
    parts = tuple(str(part) for part in (phase, active) if part)
    return " | ".join(parts)


def _roster_summary(selected_unit: JsonObject) -> str:
    label = selected_unit.get("unit_label")
    if type(label) is str and label and label != "No selected unit":
        return f"Selected: {label}"
    return "Select a unit to inspect"


def _first_int(text: str) -> int | None:
    digits = ""
    for character in text:
        if character.isdigit():
            digits += character
        elif digits:
            break
    if not digits:
        return None
    return int(digits)
