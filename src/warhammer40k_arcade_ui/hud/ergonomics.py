"""Preference-aware HUD ergonomics view models."""

from __future__ import annotations

from dataclasses import dataclass

from warhammer40k_arcade_ui.hud.toolkit import (
    AssignmentGroupRowView as ToolkitAssignmentGroupRowView,
)
from warhammer40k_arcade_ui.hud.toolkit import (
    HudState,
    IconTextBarView,
    StatusChipView,
    UnitRailCardView,
)
from warhammer40k_arcade_ui.hud.view_models import (
    AssignmentGroupState,
    AssignmentHudPanelView,
    ContextMenuAction,
    FiniteDecisionPanelView,
    MovementDraftPanelView,
    UnitPanelView,
)
from warhammer40k_arcade_ui.preferences.registries import command_registry
from warhammer40k_arcade_ui.preferences.schema import HotkeyBinding, UiPreferences
from warhammer40k_arcade_ui.render.view_models import BattlefieldView


@dataclass(frozen=True, slots=True)
class HudErgonomicsView:
    """Composed ergonomic HUD content for the current frame."""

    status_chips: tuple[StatusChipView, ...]
    selected_unit_card: UnitRailCardView | None
    selected_unit_rows: tuple[IconTextBarView, ...]
    action_rows: tuple[IconTextBarView, ...]
    assignment_rows: tuple[ToolkitAssignmentGroupRowView, ...]
    diagnostic_lines: tuple[str, ...]
    event_lines: tuple[str, ...]
    hotkey_hints: tuple[str, ...]
    text_scale: float
    high_contrast: bool


def build_hud_ergonomics_view(
    *,
    view: BattlefieldView,
    preferences: UiPreferences,
    unit_panel: UnitPanelView | None,
    finite_decision_panel: FiniteDecisionPanelView,
    movement_draft_panel: MovementDraftPanelView | None,
    assignment_hud_panel: AssignmentHudPanelView | None,
    event_log_lines: tuple[str, ...],
) -> HudErgonomicsView:
    """Build a toolkit-backed HUD summary without adding rule semantics."""

    diagnostic_lines = _diagnostic_lines(finite_decision_panel, movement_draft_panel)
    selected_unit_card = _selected_unit_card(unit_panel)
    return HudErgonomicsView(
        status_chips=_status_chips(
            view=view,
            finite_decision_panel=finite_decision_panel,
            preferences=preferences,
        ),
        selected_unit_card=selected_unit_card,
        selected_unit_rows=_selected_unit_rows(unit_panel),
        action_rows=_action_rows(
            finite_decision_panel=finite_decision_panel,
            movement_draft_panel=movement_draft_panel,
            preferences=preferences,
        ),
        assignment_rows=_assignment_rows(assignment_hud_panel),
        diagnostic_lines=diagnostic_lines,
        event_lines=_filtered_event_lines(
            event_log_lines=event_log_lines,
            active_player_id=view.hud.active_player_id,
            phase_label=view.hud.phase_label,
            diagnostic_lines=diagnostic_lines,
            enabled=preferences.hud.show_event_log,
        ),
        hotkey_hints=_hotkey_hints(preferences),
        text_scale=preferences.hud.text_scale,
        high_contrast=preferences.hud.high_contrast,
    )


def _status_chips(
    *,
    view: BattlefieldView,
    finite_decision_panel: FiniteDecisionPanelView,
    preferences: UiPreferences,
) -> tuple[StatusChipView, ...]:
    pending_label = (
        finite_decision_panel.decision_type
        or finite_decision_panel.proposal_kind
        or view.hud.pending_decision_summary
    )
    chips: list[StatusChipView] = []
    if preferences.hud.show_phase:
        chips.append(
            StatusChipView(
                component_id="phase_status_chip",
                label="Phase",
                value=view.hud.phase_label,
                icon_id="phase.movement",
                color_role="active",
            )
        )
    if preferences.hud.show_active_player:
        chips.append(
            StatusChipView(
                component_id="active_player_status_chip",
                label="Active",
                value=view.hud.active_player_id,
                icon_id="status.active",
                color_role="player",
            )
        )
    chips.append(
        StatusChipView(
            component_id="pending_status_chip",
            label="Pending",
            value=pending_label,
            icon_id="action.summary",
            color_role="warning" if finite_decision_panel.diagnostic_lines else "neutral",
        )
    )
    return tuple(chips)


def _selected_unit_card(unit_panel: UnitPanelView | None) -> UnitRailCardView | None:
    if unit_panel is None:
        return None
    return UnitRailCardView(
        component_id="selected_unit_card",
        unit_label=unit_panel.unit_label,
        short_label=unit_panel.unit_id,
        model_count_summary=f"{unit_panel.model_count} model(s)",
        activation_state="selected",
        color_role="player",
    )


def _selected_unit_rows(unit_panel: UnitPanelView | None) -> tuple[IconTextBarView, ...]:
    if unit_panel is None:
        return ()
    rows = [
        IconTextBarView(
            component_id="selected_unit_header",
            icon_id="entity.unit",
            primary_label="Selected unit",
            secondary_label=unit_panel.unit_label,
            value_text=f"{unit_panel.model_count} model(s)",
            state="selected",
        ),
        IconTextBarView(
            component_id="selected_unit_position",
            icon_id="entity.model",
            primary_label="Position",
            secondary_label=unit_panel.position_summary,
        ),
    ]
    if unit_panel.selected_model_id is not None:
        rows.append(
            IconTextBarView(
                component_id="selected_model_row",
                icon_id="entity.model",
                primary_label="Selected model",
                secondary_label=unit_panel.selected_model_id,
                state="selected",
            )
        )
    if unit_panel.available_actions:
        rows.append(
            IconTextBarView(
                component_id="selected_unit_actions",
                icon_id="action.movement",
                primary_label="Actions",
                secondary_label=", ".join(
                    _action_label(action) for action in unit_panel.available_actions
                ),
                value_text="SPACE",
                state="selected"
                if any(action.highlighted for action in unit_panel.available_actions)
                else "normal",
            )
        )
    return tuple(rows)


def _action_rows(
    *,
    finite_decision_panel: FiniteDecisionPanelView,
    movement_draft_panel: MovementDraftPanelView | None,
    preferences: UiPreferences,
) -> tuple[IconTextBarView, ...]:
    rows: list[IconTextBarView] = [
        IconTextBarView(
            component_id="current_decision_row",
            icon_id="action.confirm",
            primary_label="Decision",
            secondary_label=finite_decision_panel.status_line,
            value_text=_hotkey_for_command(preferences, "confirm") or "",
            state="warning" if finite_decision_panel.diagnostic_lines else "active",
        )
    ]
    if finite_decision_panel.options:
        highlighted = tuple(
            option for option in finite_decision_panel.options if option.highlighted
        )
        selected_option = highlighted[0] if highlighted else finite_decision_panel.options[0]
        rows.append(
            IconTextBarView(
                component_id="highlighted_option_row",
                icon_id="action.movement",
                primary_label="Highlighted option",
                secondary_label=selected_option.label,
                value_text=selected_option.option_id,
                state="selected",
            )
        )
    if movement_draft_panel is not None:
        assignment_summary = (
            f"{movement_draft_panel.assigned_model_count}/"
            f"{movement_draft_panel.total_model_count} moved, "
            f"{movement_draft_panel.unchanged_model_count} no-op"
        )
        distance_summary = _movement_distance_summary(movement_draft_panel)
        rows.append(
            IconTextBarView(
                component_id="movement_draft_row",
                icon_id="action.movement",
                primary_label="Movement",
                secondary_label=f"{movement_draft_panel.status_line}; {assignment_summary}",
                value_text=distance_summary,
                state="active" if movement_draft_panel.ready else "warning",
            )
        )
    return tuple(rows)


def _assignment_rows(
    assignment_hud_panel: AssignmentHudPanelView | None,
) -> tuple[ToolkitAssignmentGroupRowView, ...]:
    if assignment_hud_panel is None:
        return ()
    return tuple(
        ToolkitAssignmentGroupRowView(
            component_id=f"assignment_row_{index}",
            group_label=group.label,
            operation_kind=assignment_hud_panel.operation_kind,
            state=_assignment_group_toolkit_state(group.state),
            summary_lines=group.summary_lines,
        )
        for index, group in enumerate(assignment_hud_panel.groups[:3])
    )


def _movement_distance_summary(panel: MovementDraftPanelView) -> str:
    if panel.remaining_budget_inches is not None:
        return f"{panel.remaining_budget_inches:.1f} in left"
    if panel.total_path_inches is not None:
        return f"{panel.total_path_inches:.1f} in"
    return ""


def _action_label(action: ContextMenuAction) -> str:
    label = action.label
    disabled_reason = action.disabled_reason
    if disabled_reason is not None:
        label = f"{label} ({disabled_reason})"
    if action.highlighted:
        return f"> {label} <"
    return label


def _assignment_group_toolkit_state(state: AssignmentGroupState) -> HudState:
    if state == "assigned":
        return "selected"
    if state == "unassigned":
        return "normal"
    return state


def _diagnostic_lines(
    finite_decision_panel: FiniteDecisionPanelView,
    movement_draft_panel: MovementDraftPanelView | None,
) -> tuple[str, ...]:
    lines = list(finite_decision_panel.diagnostic_lines)
    if movement_draft_panel is not None:
        for line in movement_draft_panel.diagnostic_lines:
            if line not in lines:
                lines.append(line)
    return tuple(lines)


def _filtered_event_lines(
    *,
    event_log_lines: tuple[str, ...],
    active_player_id: str,
    phase_label: str,
    diagnostic_lines: tuple[str, ...],
    enabled: bool,
    max_lines: int = 3,
) -> tuple[str, ...]:
    if diagnostic_lines:
        return tuple(f"Invalid: {line}" for line in diagnostic_lines[-max_lines:])
    if not enabled:
        return ()
    if not event_log_lines:
        return ()
    needles = tuple(
        needle
        for needle in (
            active_player_id.lower(),
            phase_label.lower(),
            "invalid",
            "diagnostic",
        )
        if needle
    )
    matching = tuple(
        line for line in event_log_lines if any(needle in line.lower() for needle in needles)
    )
    return (matching or event_log_lines)[-max_lines:]


def _hotkey_hints(preferences: UiPreferences) -> tuple[str, ...]:
    command_ids = (
        "open_selected_unit_actions",
        "confirm",
        "cancel",
        "toggle_action_summary",
        "review_action_summary",
    )
    hints: list[str] = []
    registry = command_registry()
    for command_id in command_ids:
        hint = _hotkey_for_command(preferences, command_id)
        if hint is None:
            continue
        command = registry[command_id]
        hints.append(f"{hint}: {command.label}")
    return tuple(hints)


def _hotkey_for_command(preferences: UiPreferences, command_id: str) -> str | None:
    for binding in preferences.hotkeys:
        if binding.command_id == command_id:
            return _hotkey_label(binding)
    return None


def _hotkey_label(binding: HotkeyBinding) -> str:
    modifiers = tuple(modifier.title() for modifier in binding.modifiers)
    return "+".join((*modifiers, binding.key.upper()))
