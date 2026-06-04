"""Tests for selected-unit HUD and context action models."""

from __future__ import annotations

from warhammer40k_arcade_ui.core_client.protocol import UiDecision, UiFiniteOption
from warhammer40k_arcade_ui.hud.view_models import (
    build_context_menu,
    build_debug_inspector,
    build_finite_decision_panel,
    build_unit_panel,
    decision_targets_unit,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.state.selection import SelectionState


def test_unit_panel_options_are_derived_from_pending_decision_data() -> None:
    view = default_battlefield_view()
    selection = _selected_intercessors()
    decision = _finite_decision_for("intercessor_squad")

    panel = build_unit_panel(view=view, selection=selection, pending_decision=decision)

    assert panel is not None
    assert panel.unit_id == "intercessor_squad"
    assert panel.model_count == 3
    assert panel.selected_model_id == "intercessor_1"
    assert panel.pending_request_id == "decision-request-000004"
    assert [action.option_id for action in panel.available_actions] == [
        "normal_move",
        "advance",
    ]
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
