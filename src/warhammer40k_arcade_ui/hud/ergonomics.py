"""Preference-aware HUD ergonomics view models."""

from __future__ import annotations

from dataclasses import dataclass

from warhammer40k_arcade_ui.core_client.protocol import JsonObject, UiDecision
from warhammer40k_arcade_ui.hud.dice_tray import DiceTrayView, build_dice_tray_view
from warhammer40k_arcade_ui.hud.toolkit import (
    AssignmentGroupRowView as ToolkitAssignmentGroupRowView,
)
from warhammer40k_arcade_ui.hud.toolkit import (
    CurrentActionView,
    HudButtonView,
    HudColorRole,
    HudState,
    IconTextBarView,
    StatusChipView,
    UnitRailCardView,
)
from warhammer40k_arcade_ui.hud.view_models import (
    AssignmentGroupState,
    AssignmentHudPanelView,
    AssignmentReadinessState,
    ContextMenuAction,
    FiniteDecisionOptionView,
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
    current_action: CurrentActionView
    action_rows: tuple[IconTextBarView, ...]
    assignment_rows: tuple[ToolkitAssignmentGroupRowView, ...]
    assignment_notice_rows: tuple[IconTextBarView, ...]
    assignment_subtitle: str
    assignment_color_role: HudColorRole
    dice_tray: DiceTrayView
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
    event_payloads: tuple[JsonObject, ...] = (),
    pending_decision: UiDecision | None = None,
    hovered_hud_button_id: str | None = None,
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
        current_action=_current_action_view(
            finite_decision_panel=finite_decision_panel,
            movement_draft_panel=movement_draft_panel,
            preferences=preferences,
            hovered_hud_button_id=hovered_hud_button_id,
        ),
        action_rows=_action_rows(
            finite_decision_panel=finite_decision_panel,
            movement_draft_panel=movement_draft_panel,
            preferences=preferences,
        ),
        assignment_rows=_assignment_rows(assignment_hud_panel),
        assignment_notice_rows=_assignment_notice_rows(assignment_hud_panel),
        assignment_subtitle=_assignment_subtitle(assignment_hud_panel),
        assignment_color_role=_assignment_color_role(assignment_hud_panel),
        dice_tray=build_dice_tray_view(
            event_payloads=event_payloads,
            pending_decision=pending_decision,
        ),
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


def _current_action_view(
    *,
    finite_decision_panel: FiniteDecisionPanelView,
    movement_draft_panel: MovementDraftPanelView | None,
    preferences: UiPreferences,
    hovered_hud_button_id: str | None,
) -> CurrentActionView:
    request_summary = (
        finite_decision_panel.decision_type or finite_decision_panel.proposal_kind or ""
    )
    title = _current_action_title(finite_decision_panel)
    status = _current_action_status(
        finite_decision_panel=finite_decision_panel,
        movement_draft_panel=movement_draft_panel,
    )
    buttons = tuple(
        _finite_option_button(
            option=option,
            index=index,
            request_id=finite_decision_panel.request_id,
            hovered_hud_button_id=hovered_hud_button_id,
        )
        for index, option in enumerate(finite_decision_panel.options)
    )
    selected_action_id = next((button.option_id for button in buttons if button.selected), None)
    confirm_hint = _hotkey_for_command(preferences, "confirm")
    cancel_hint = _hotkey_for_command(preferences, "cancel")
    return CurrentActionView(
        component_id="current_action_view",
        title=title,
        request_summary=request_summary,
        actor_summary=finite_decision_panel.actor_id or "",
        advisory_status=status,
        selected_action_id=selected_action_id,
        buttons=buttons,
        confirm_hint=f"{confirm_hint}: submit selected option" if confirm_hint else "",
        cancel_hint=f"{cancel_hint}: cancel/back" if cancel_hint else "",
        source_kind="engine_parameterized"
        if finite_decision_panel.proposal_kind is not None
        else "engine_finite"
        if finite_decision_panel.request_id is not None
        else "none",
    )


def _current_action_title(finite_decision_panel: FiniteDecisionPanelView) -> str:
    label = finite_decision_panel.proposal_kind or finite_decision_panel.decision_type
    if not label:
        return "Current Action"
    lower_label = label.lower()
    if "movement" in lower_label or "move" in lower_label:
        return "Current Action: Movement"
    if "shoot" in lower_label:
        return "Current Action: Shooting"
    if "melee" in lower_label or "fight" in lower_label:
        return "Current Action: Melee"
    if "stratagem" in lower_label:
        return "Current Action: Stratagem"
    if "deploy" in lower_label or "placement" in lower_label:
        return "Current Action: Deployment"
    return f"Current Action: {label.replace('_', ' ').title()}"


def _current_action_status(
    *,
    finite_decision_panel: FiniteDecisionPanelView,
    movement_draft_panel: MovementDraftPanelView | None,
) -> str:
    if movement_draft_panel is not None:
        assignment_summary = (
            f"{movement_draft_panel.assigned_model_count}/"
            f"{movement_draft_panel.total_model_count} moved, "
            f"{movement_draft_panel.unchanged_model_count} no-op"
        )
        distance_summary = _movement_distance_summary(movement_draft_panel)
        parts = (movement_draft_panel.status_line, assignment_summary, distance_summary)
        return " | ".join(part for part in parts if part)
    return finite_decision_panel.status_line


def _finite_option_button(
    *,
    option: FiniteDecisionOptionView,
    index: int,
    request_id: str | None,
    hovered_hud_button_id: str | None,
) -> HudButtonView:
    enabled = option.disabled_reason is None
    semantic_state = _finite_option_button_state(option)
    button_id = f"finite_option_{index}_{option.option_id}"
    if hovered_hud_button_id == button_id and enabled and not option.highlighted:
        semantic_state = "hover"
    return HudButtonView(
        component_id=f"current_action_option_{index}",
        button_id=button_id,
        command_id="select_finite_option",
        action_kind="finite_option",
        option_id=option.option_id,
        request_id=request_id,
        label=option.label,
        tooltip=option.disabled_reason or "",
        state=semantic_state,
        color_role=_finite_option_color_role(option),
        selected=option.highlighted,
        focused=option.highlighted,
        enabled=enabled,
        disabled_reason=option.disabled_reason or "",
        visual_role=_finite_option_color_role(option),
        metadata={"option_id": option.option_id},
    )


def _finite_option_button_state(option: FiniteDecisionOptionView) -> HudState:
    if option.disabled_reason is not None:
        return "disabled"
    if option.highlighted:
        return "selected"
    label = option.label.lower()
    option_id = option.option_id.lower()
    if any(token in label or token in option_id for token in ("decline", "pass", "skip")):
        return "warning"
    if "invalid" in label or "invalid" in option_id:
        return "invalid"
    return "normal"


def _finite_option_color_role(option: FiniteDecisionOptionView) -> HudColorRole:
    if option.disabled_reason is not None:
        return "disabled"
    if option.highlighted:
        return "selected"
    label = option.label.lower()
    option_id = option.option_id.lower()
    if any(token in label or token in option_id for token in ("decline", "pass", "skip")):
        return "warning"
    return "neutral"


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


def _assignment_notice_rows(
    assignment_hud_panel: AssignmentHudPanelView | None,
) -> tuple[IconTextBarView, ...]:
    if assignment_hud_panel is None:
        return ()
    selected_lines = _prioritized_assignment_advisories(assignment_hud_panel.advisory_lines)
    return tuple(
        IconTextBarView(
            component_id=f"assignment_notice_{index}",
            icon_id="action.summary",
            primary_label=_assignment_notice_label(line),
            secondary_label=_assignment_notice_body(line),
            state="warning" if _is_warning_assignment_advisory(line) else "active",
            density="compact",
        )
        for index, line in enumerate(selected_lines)
    )


def _prioritized_assignment_advisories(lines: tuple[str, ...]) -> tuple[str, ...]:
    important = tuple(line for line in lines if _is_warning_assignment_advisory(line))
    remaining = tuple(line for line in lines if line not in important)
    return (*important, *remaining)[:2]


def _is_warning_assignment_advisory(line: str) -> bool:
    lower_line = line.lower()
    return (
        "synthetic midpoint" in lower_line
        or "invalid" in lower_line
        or "unsupported" in lower_line
        or "projection/request drift" in lower_line
        or "missing from this viewer projection" in lower_line
        or "mode context" in lower_line
        or "submission is blocked" in lower_line
    )


def _assignment_notice_label(line: str) -> str:
    if "synthetic midpoint" in line.lower():
        return "Synthetic witness"
    if (
        "projection/request drift" in line.lower()
        or "missing from this viewer projection" in line.lower()
    ):
        return "Projection drift"
    if "mode context" in line.lower():
        return "Context missing"
    return "Advisory"


def _assignment_notice_body(line: str) -> str:
    synthetic_prefix = "UI-generated synthetic midpoint witness evidence will be inserted for "
    if synthetic_prefix in line:
        suffix = line.split(synthetic_prefix, maxsplit=1)[1]
        count_summary = suffix.split(":", maxsplit=1)[0].replace(
            "straight moved model path(s)",
            "straight path(s)",
        )
        return f"Synthetic midpoint witness evidence: {count_summary}."
    return line


def _assignment_subtitle(assignment_hud_panel: AssignmentHudPanelView | None) -> str:
    if assignment_hud_panel is None:
        return "No active assignment draft"
    labels: dict[AssignmentReadinessState, str] = {
        "empty": "Draft empty: add assignments",
        "incomplete": "Drafting paths: preview only",
        "ready": "Draft review: ENTER submits to engine",
        "invalid": "Invalid: fix before submit",
        "unsupported": "Unsupported request shown",
        "finite": "Finite choice review",
    }
    return labels[assignment_hud_panel.readiness_state]


def _assignment_color_role(
    assignment_hud_panel: AssignmentHudPanelView | None,
) -> HudColorRole:
    if assignment_hud_panel is None:
        return "neutral"
    if assignment_hud_panel.readiness_state == "ready":
        return "active"
    if assignment_hud_panel.readiness_state in ("empty", "incomplete", "unsupported"):
        return "preview"
    if assignment_hud_panel.readiness_state == "invalid":
        return "invalid"
    return "selected"


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
