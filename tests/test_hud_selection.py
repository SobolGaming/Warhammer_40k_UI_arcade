"""Tests for selected-unit HUD and context action models."""

from __future__ import annotations

from dataclasses import replace

from warhammer40k_arcade_ui.core_client.protocol import (
    UiDecision,
    UiFiniteOption,
    UiInvalidDiagnostic,
)
from warhammer40k_arcade_ui.hud.view_models import (
    build_assignment_hud_panel,
    build_context_menu,
    build_debug_inspector,
    build_finite_decision_panel,
    build_movement_draft_panel,
    build_unit_panel,
    decision_targets_unit,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft
from warhammer40k_arcade_ui.state.selection import SelectionState


def test_unit_panel_options_are_derived_from_pending_decision_data() -> None:
    view = default_battlefield_view()
    selection = _selected_intercessors()
    decision = _finite_decision_for("intercessor_squad")

    panel = build_unit_panel(
        view=view,
        selection=selection,
        pending_decision=decision,
        highlighted_option_id="normal_move",
    )

    assert panel is not None
    assert panel.unit_id == "intercessor_squad"
    assert panel.model_count == 3
    assert panel.selected_model_id == "intercessor_1"
    assert panel.pending_request_id == "decision-request-000004"
    assert [action.option_id for action in panel.available_actions] == [
        "normal_move",
        "advance",
    ]
    assert panel.available_actions[0].highlighted is True
    assert panel.available_actions[1].highlighted is False
    assert panel.available_actions[1].disabled_reason == "Unit is battle-shocked."


def test_context_menu_only_uses_finite_options_for_targeted_unit() -> None:
    view = default_battlefield_view()
    selection = _selected_intercessors().open_context_menu((7.0, 18.0))
    decision = _finite_decision_for("intercessor_squad")

    menu = build_context_menu(
        view=view,
        selection=selection,
        pending_decision=decision,
    )

    assert menu is not None
    assert menu.request_id == "decision-request-000004"
    assert [action.label for action in menu.actions] == ["Normal Move", "Advance"]


def test_context_menu_ignores_non_targeted_and_parameterized_decisions() -> None:
    view = default_battlefield_view()
    selection = _selected_intercessors().open_context_menu((7.0, 18.0))

    non_targeted = build_context_menu(
        view=view,
        selection=selection,
        pending_decision=_finite_decision_for("guardian_squad"),
    )
    parameterized = build_context_menu(
        view=view,
        selection=selection,
        pending_decision=UiDecision(
            request_id="decision-request-000005",
            decision_type="submit_movement_proposal",
            actor_id="player_1",
            payload={"unit_instance_id": "intercessor_squad"},
            options=(
                UiFiniteOption(
                    option_id="submit_parameterized_payload",
                    label="Submit Parameterized Payload",
                    payload={"submission_kind": "parameterized"},
                ),
            ),
            is_parameterized=True,
        ),
    )

    assert non_targeted is None
    assert parameterized is None


def test_finite_decision_panel_is_generic_and_highlights_option() -> None:
    decision = UiDecision(
        request_id="decision-request-000021",
        decision_type="select_reaction",
        actor_id="player_2",
        payload={"trigger_window": "after_normal_move"},
        options=(
            UiFiniteOption(
                option_id="decline_reaction",
                label="Decline",
                payload={},
            ),
            UiFiniteOption(
                option_id="core:fire-overwatch",
                label="Fire Overwatch",
                payload={"stratagem_id": "core:fire-overwatch"},
            ),
        ),
        is_parameterized=False,
    )

    panel = build_finite_decision_panel(
        pending_decision=decision,
        highlighted_option_index=1,
        status_message="Waiting: select_reaction",
        diagnostics=(),
    )

    assert panel.request_id == "decision-request-000021"
    assert panel.decision_type == "select_reaction"
    assert panel.actor_id == "player_2"
    assert [option.option_id for option in panel.options] == [
        "decline_reaction",
        "core:fire-overwatch",
    ]
    assert panel.options[1].highlighted is True


def test_finite_decision_panel_hides_parameterized_fixed_submit_option() -> None:
    decision = UiDecision.from_payload(
        {
            "request_id": "decision-request-000005",
            "decision_type": "submit_movement_proposal",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-000005",
                    "decision_type": "submit_movement_proposal",
                    "actor_id": "player_1",
                    "game_id": "phase6-game",
                    "battle_round": 1,
                    "phase": "movement",
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": "normal_move",
                    "source_decision_request_id": "decision-request-000004",
                    "source_decision_result_id": "ui-result-000001",
                    "movement_phase_action": "normal_move",
                    "placement_kinds": [],
                    "context": {"source_selected_option_id": "normal_move"},
                }
            },
            "options": [
                {
                    "option_id": "submit_parameterized_payload",
                    "label": "Submit Parameterized Payload",
                    "payload": {"submission_kind": "parameterized"},
                }
            ],
        }
    )

    panel = build_finite_decision_panel(
        pending_decision=decision,
        highlighted_option_index=0,
        status_message="Proposal required: normal_move",
        diagnostics=(),
    )

    assert panel.proposal_kind == "normal_move"
    assert panel.options == ()


def test_movement_draft_panel_shows_measurements_and_ready_state() -> None:
    view = default_battlefield_view()
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(),
        pending_decision=_movement_proposal_decision(),
    )
    assert draft is not None
    ready_draft = draft.add_waypoint(view=view, world_point=(10.0, 18.0)).mark_ready(view=view)

    panel = build_movement_draft_panel(
        movement_draft=ready_draft,
        pending_decision=_movement_proposal_decision(),
    )

    assert panel is not None
    assert panel.status_line == "Movement draft ready"
    assert panel.request_id == "decision-request-000005"
    assert panel.unit_id == "intercessor_squad"
    assert panel.movement_phase_action == "normal_move"
    assert panel.movement_mode == "normal"
    assert panel.active_layer == "model"
    assert panel.active_model_ids == ("intercessor_1",)
    assert panel.assigned_model_count == 1
    assert panel.total_model_count == 3
    assert panel.unchanged_model_count == 2
    assert panel.total_path_inches == 3.0
    assert panel.remaining_budget_inches == 3.0
    assert panel.ready is True


def test_movement_draft_panel_reports_unsupported_parameterized_request() -> None:
    panel = build_movement_draft_panel(
        movement_draft=None,
        pending_decision=_shooting_proposal_decision(),
    )

    assert panel is not None
    assert panel.status_line == "Unsupported proposal tool: shooting_declaration"
    assert panel.proposal_kind == "shooting_declaration"


def test_movement_draft_panel_surfaces_authoritative_diagnostics() -> None:
    view = default_battlefield_view()
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(),
        pending_decision=_movement_proposal_decision(),
    )
    assert draft is not None

    panel = build_movement_draft_panel(
        movement_draft=draft,
        pending_decision=_movement_proposal_decision(),
        status_message="Normal Move path is not legal.",
        diagnostics=(
            UiInvalidDiagnostic(
                violation_code="movement_budget_exceeded",
                message="Normal Move path exceeds the movement budget.",
                field="witness",
                proposal_request_id="decision-request-000005",
                proposal_kind="normal_move",
            ),
        ),
    )

    assert panel is not None
    assert panel.status_line == "Normal Move path is not legal."
    assert panel.diagnostic_lines == (
        "movement_budget_exceeded [witness]: Normal Move path exceeds the movement budget.",
    )


def test_assignment_hud_shows_ready_movement_groups_and_refs() -> None:
    view = default_battlefield_view()
    preferences = default_preferences()
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(),
        pending_decision=_movement_proposal_decision(),
    )
    assert draft is not None
    ready_draft = draft.add_waypoint(view=view, world_point=(10.0, 18.0)).mark_ready(view=view)

    panel = build_assignment_hud_panel(
        movement_draft=ready_draft,
        pending_decision=_movement_proposal_decision(),
        highlighted_option_index=0,
        diagnostics=(),
        preferences=preferences,
        preference_source_label="default.yaml",
        debug_visible=True,
    )

    assert panel is not None
    assert panel.request_id == "decision-request-000005"
    assert panel.decision_type == "submit_movement_proposal"
    assert panel.operation_kind == "movement"
    assert panel.proposal_kind == "normal_move"
    assert panel.active_layer == "model"
    assert panel.active_selection_ref_keys == ("model:intercessor_1",)
    assert panel.assigned_ref_keys == ("model:intercessor_1",)
    assert panel.unassigned_ref_keys == ("model:intercessor_2", "model:intercessor_3")
    assert panel.readiness_state == "ready"
    assert [group.group_id for group in panel.groups] == [
        "assignment-group-000001",
        "unassigned-or-no-op",
    ]
    assert panel.groups[0].source_ref_keys == ("model:intercessor_1",)
    assert panel.groups[1].label == "No-op ready: 2 model(s)"
    assert panel.preference_source_label == "default.yaml"


def test_assignment_hud_can_be_hidden_by_preferences() -> None:
    preferences = default_preferences()
    preferences = replace(
        preferences,
        hud=replace(preferences.hud, show_assignment_hud=False),
    )

    panel = build_assignment_hud_panel(
        movement_draft=None,
        pending_decision=_movement_proposal_decision(),
        highlighted_option_index=0,
        diagnostics=(),
        preferences=preferences,
        preference_source_label="default.yaml",
        debug_visible=True,
    )

    assert panel is None


def test_assignment_hud_reports_unsupported_charge_move_without_movement_draft() -> None:
    view = default_battlefield_view()
    draft = MovementDraft.start_for_pending(
        view=view,
        selection=_selected_intercessors(),
        pending_decision=_charge_move_proposal_decision(),
    )

    panel = build_assignment_hud_panel(
        movement_draft=draft,
        pending_decision=_charge_move_proposal_decision(),
        highlighted_option_index=0,
        diagnostics=(),
        preferences=default_preferences(),
        preference_source_label="default.yaml",
        debug_visible=False,
    )

    assert draft is None
    assert panel is not None
    assert panel.operation_kind == "unsupported"
    assert panel.proposal_kind == "charge_move"
    assert panel.readiness_state == "unsupported"
    assert panel.groups[0].label == "Unsupported proposal tool: charge_move"


def test_assignment_hud_summarizes_fight_order_finite_options() -> None:
    decision = UiDecision(
        request_id="decision-request-fight-001",
        decision_type="select_fight_activation",
        actor_id="player_1",
        payload={"ordering_band": "fights_first"},
        options=(
            UiFiniteOption(
                option_id="fight:normal:intercessor_squad",
                label="Intercessors fight",
                payload={"unit_instance_id": "intercessor_squad"},
            ),
            UiFiniteOption(
                option_id="eligible_to_fight_pass",
                label="Pass",
                payload={},
            ),
        ),
        is_parameterized=False,
    )

    panel = build_assignment_hud_panel(
        movement_draft=None,
        pending_decision=decision,
        highlighted_option_index=0,
        diagnostics=(),
        preferences=default_preferences(),
        preference_source_label="default.yaml",
        debug_visible=False,
    )

    assert panel is not None
    assert panel.operation_kind == "finite"
    assert panel.readiness_state == "finite"
    assert panel.active_selection_ref_keys == ("unit:intercessor_squad",)
    assert [group.group_id for group in panel.groups] == [
        "finite:fight:normal:intercessor_squad",
        "finite:eligible_to_fight_pass",
    ]
    assert panel.groups[0].source_ref_keys == ("unit:intercessor_squad",)
    assert panel.groups[0].summary_lines == ("Fight type: normal; unit: intercessor_squad",)
    assert panel.groups[1].summary_lines == ("Engine-issued pass option.",)


def test_debug_inspector_reports_request_selection_cursor_and_event_cursor() -> None:
    selection = _selected_intercessors().toggle_debug_inspector()
    decision = _finite_decision_for("intercessor_squad")

    inspector = build_debug_inspector(
        selection=selection,
        pending_decision=decision,
        cursor_position=(12.0, 13.5),
        event_cursor=7,
        preference_source_label="keyboard-heavy.yaml",
    )

    assert inspector is not None
    assert inspector.lines == (
        "Request: decision-request-000004",
        "Selected unit: intercessor_squad",
        "Proposal kind: none",
        "Cursor: 12.00, 13.50 in",
        "Action summary: hidden",
        "Event cursor: 7",
        "UI prefs: keyboard-heavy.yaml",
    )


def test_decision_target_detection_uses_payload_unit_ids() -> None:
    decision = _finite_decision_for("intercessor_squad")

    assert decision_targets_unit(decision, "intercessor_squad") is True
    assert decision_targets_unit(decision, "guardian_squad") is False


def _selected_intercessors() -> SelectionState:
    view = default_battlefield_view()
    preferences = default_preferences()
    return SelectionState.initial(preferences).select_at(
        view=view,
        world_point=(7.0, 18.0),
        preferences=preferences,
    )


def _finite_decision_for(unit_id: str) -> UiDecision:
    return UiDecision(
        request_id="decision-request-000004",
        decision_type="select_movement_action",
        actor_id="player_1",
        payload={"unit_instance_id": unit_id},
        options=(
            UiFiniteOption(
                option_id="normal_move",
                label="Normal Move",
                payload={"movement_phase_action": "normal_move"},
            ),
            UiFiniteOption(
                option_id="advance",
                label="Advance",
                payload={
                    "movement_phase_action": "advance",
                    "disabled_reason": "Unit is battle-shocked.",
                },
            ),
        ),
        is_parameterized=False,
    )


def _movement_proposal_decision() -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": "decision-request-000005",
            "decision_type": "submit_movement_proposal",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-000005",
                    "decision_type": "submit_movement_proposal",
                    "actor_id": "player_1",
                    "game_id": "phase7-game",
                    "battle_round": 1,
                    "phase": "movement",
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": "normal_move",
                    "source_decision_request_id": "decision-request-000004",
                    "source_decision_result_id": "ui-result-000001",
                    "movement_phase_action": "normal_move",
                    "placement_kinds": [],
                    "context": {
                        "source_selected_option_id": "normal_move",
                        "movement_mode": "normal",
                        "movement_budget_inches": 6.0,
                    },
                }
            },
            "options": [
                {
                    "option_id": "submit_parameterized_payload",
                    "label": "Submit Parameterized Payload",
                    "payload": {"submission_kind": "parameterized"},
                }
            ],
        }
    )


def _shooting_proposal_decision() -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": "decision-request-000009",
            "decision_type": "submit_shooting_declaration",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-000009",
                    "decision_type": "submit_shooting_declaration",
                    "actor_id": "player_1",
                    "proposal_kind": "shooting_declaration",
                }
            },
            "options": [
                {
                    "option_id": "submit_parameterized_payload",
                    "label": "Submit Parameterized Payload",
                    "payload": {"submission_kind": "parameterized"},
                }
            ],
        }
    )


def _charge_move_proposal_decision() -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": "decision-request-charge-001",
            "decision_type": "submit_movement_proposal",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-charge-001",
                    "decision_type": "submit_movement_proposal",
                    "actor_id": "player_1",
                    "game_id": "phase16-game",
                    "battle_round": 1,
                    "phase": "charge",
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": "charge_move",
                    "source_decision_request_id": "decision-request-charge-unit",
                    "source_decision_result_id": "ui-result-charge",
                    "movement_phase_action": "charge_move",
                    "placement_kinds": [],
                    "context": {
                        "movement_mode": "charge",
                        "charge_target_unit_instance_ids": ["guardian_squad"],
                    },
                }
            },
            "options": [
                {
                    "option_id": "submit_parameterized_payload",
                    "label": "Submit Parameterized Payload",
                    "payload": {"submission_kind": "parameterized"},
                }
            ],
        }
    )
