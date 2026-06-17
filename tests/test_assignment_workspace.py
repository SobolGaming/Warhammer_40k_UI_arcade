"""Tests for generic assignment proposal workspaces."""

from __future__ import annotations

from typing import cast

from warhammer40k_arcade_ui.core_client.protocol import JsonObject, UiDecision
from warhammer40k_arcade_ui.hud.action_summary import build_action_visual_summary
from warhammer40k_arcade_ui.hud.ergonomics import build_hud_ergonomics_view
from warhammer40k_arcade_ui.hud.runtime_data import runtime_data_for_ergonomic_hud
from warhammer40k_arcade_ui.hud.view_models import (
    build_assignment_hud_panel,
    build_finite_decision_panel,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.state.assignment_submission import prepare_assignment_submission
from warhammer40k_arcade_ui.state.assignment_workspace import (
    AssignmentWorkspace,
    is_assignment_parameterized_decision,
)

_DEFAULT_TARGET_BINDING: dict[str, object] = {
    "target_kind": "friendly_unit",
    "target_player_id": "player_1",
    "target_unit_instance_id": "intercessor_squad",
}


def test_shooting_assignment_workspace_builds_payload_from_engine_candidates() -> None:
    decision = _shooting_declaration_decision()

    workspace = AssignmentWorkspace.start_for_pending(decision)

    assert workspace is not None
    assert workspace.is_ready is True
    assert workspace.request_id == "shooting-request-1"
    assert workspace.proposal_kind == "shooting_declaration"
    assert workspace.assigned_ref_keys == ("model:intercessor_1",)
    assert workspace.target_ref_keys == ("unit:guardian_squad",)
    assert workspace.payload_preview is not None
    assert workspace.payload_preview["proposal_request_id"] == "shooting-request-1"
    assert workspace.payload_preview["proposal_kind"] == "shooting_declaration"
    assert workspace.payload_preview["declarations"] == [
        {
            "attacker_model_instance_id": "intercessor_1",
            "wargear_id": "bolt_rifle",
            "weapon_profile_id": "bolt_rifle_profile",
            "target_unit_instance_id": "guardian_squad",
            "shooting_type": "normal",
        }
    ]
    assert workspace.payload_preview["firing_deck_selection"] is None


def test_shooting_assignment_workspace_can_seed_unit_wide_target_candidate() -> None:
    decision = _shooting_declaration_decision(
        available_weapons=[
            {
                "model_instance_id": "intercessor_1",
                "wargear_id": "bolt_rifle",
                "weapon_profile_id": "bolt_rifle_profile",
                "weapon_profile": {"name": "Bolt Rifle"},
            },
            {
                "model_instance_id": "intercessor_2",
                "wargear_id": "bolt_rifle",
                "weapon_profile_id": "bolt_rifle_profile",
                "weapon_profile": {"name": "Bolt Rifle"},
            },
        ],
        target_candidates=[
            {
                "is_legal": True,
                "attacker_unit_instance_id": "intercessor_squad",
                "observer_model_id": "intercessor_1",
                "weapon_profile_id": "bolt_rifle_profile",
                "target_unit_instance_id": "guardian_squad",
                "shooting_types": ["normal"],
                "visibility_cache_key": "visibility-cache-1",
            }
        ],
    )

    workspace = AssignmentWorkspace.start_for_pending(decision)

    assert workspace is not None
    assert workspace.is_ready is True
    assert workspace.payload_preview is not None
    declarations = workspace.payload_preview["declarations"]
    assert type(declarations) is list
    declaration_objects = [declaration for declaration in declarations if type(declaration) is dict]
    assert [declaration["attacker_model_instance_id"] for declaration in declaration_objects] == [
        "intercessor_1",
        "intercessor_2",
    ]
    assert len(workspace.rows) == 2


def test_melee_assignment_workspace_builds_payload_from_engaged_targets() -> None:
    decision = _melee_declaration_decision()

    workspace = AssignmentWorkspace.start_for_pending(decision)

    assert workspace is not None
    assert workspace.is_ready is True
    assert workspace.payload_preview is not None
    assert workspace.payload_preview["proposal_kind"] == "melee_declaration"
    assert workspace.payload_preview["declarations"] == [
        {
            "attacker_model_instance_id": "intercessor_1",
            "wargear_id": "close_combat_weapon",
            "weapon_profile_id": "close_combat_weapon_profile",
            "target_allocations": [
                {
                    "target_unit_instance_id": "guardian_squad",
                }
            ],
        }
    ]


def test_stratagem_assignment_workspace_uses_exposed_binding_and_decline_flag() -> None:
    decision = _stratagem_target_binding_decision(declinable=True)

    workspace = AssignmentWorkspace.start_for_pending(decision)

    assert workspace is not None
    assert workspace.is_ready is True
    assert workspace.declinable is True
    assert workspace.decline_payload == {"submission_kind": "decline_stratagem_window"}
    assert workspace.payload_preview is not None
    proposal = cast(JsonObject, workspace.payload_preview["proposal"])
    assert proposal["proposal_kind"] == "stratagem_target_binding"
    assert proposal["target_binding"] == {
        "target_kind": "friendly_unit",
        "target_player_id": "player_1",
        "target_unit_instance_id": "intercessor_squad",
    }


def test_stratagem_assignment_workspace_requires_unambiguous_binding_candidate() -> None:
    decision = _stratagem_target_binding_decision(
        target_binding=None,
        target_binding_candidates=[
            {
                "target_kind": "friendly_unit",
                "target_player_id": "player_1",
                "target_unit_instance_id": "intercessor_squad",
            },
            {
                "target_kind": "friendly_unit",
                "target_player_id": "player_1",
                "target_unit_instance_id": "guardian_squad",
            },
        ],
    )

    workspace = AssignmentWorkspace.start_for_pending(decision)

    assert workspace is not None
    assert workspace.is_ready is False
    assert workspace.payload_preview is None
    assert workspace.diagnostic_lines == (
        "Stratagem target binding needs an explicit future target choice.",
    )


def test_stratagem_assignment_workspace_without_binding_shows_catalog_context() -> None:
    decision = _stratagem_target_binding_decision(target_binding=None, declinable=True)

    workspace = AssignmentWorkspace.start_for_pending(decision)

    assert workspace is not None
    assert workspace.is_ready is False
    assert workspace.declinable is True
    assert workspace.rows[0].label == "Test Stratagem"
    assert "Stratagem: Test Stratagem" in workspace.rows[0].summary_lines
    assert workspace.diagnostic_lines == (
        "Stratagem request does not expose a selectable target binding candidate yet.",
    )


def test_finite_opportunity_window_is_not_assignment_workspace() -> None:
    decision = UiDecision.from_payload(
        {
            "request_id": "finite-stratagem-window-1",
            "decision_type": "use_stratagem",
            "actor_id": "player_1",
            "payload": {
                "submission_family": "opportunity_window",
                "window_kind": "command_re_roll",
            },
            "is_parameterized": False,
            "options": [
                {
                    "option_id": "decline_opportunity",
                    "label": "Decline",
                    "payload": {"submission_kind": "opportunity_submission"},
                }
            ],
        }
    )

    assert is_assignment_parameterized_decision(decision) is False
    assert AssignmentWorkspace.start_for_pending(decision) is None


def test_prepare_assignment_submission_preserves_request_payload_and_result_id() -> None:
    decision = _shooting_declaration_decision()
    workspace = AssignmentWorkspace.start_for_pending(decision)
    assert workspace is not None

    invalid_status, submission, next_result_index = prepare_assignment_submission(
        assignment_workspace=workspace,
        pending_decision=decision,
        next_result_index=7,
    )

    assert invalid_status is None
    assert submission is not None
    assert submission.request_id == "shooting-request-1"
    assert submission.result_id == "ui-result-000007"
    assert submission.payload == workspace.payload_preview
    assert next_result_index == 8


def test_prepare_assignment_submission_rejects_decline_without_engine_flag() -> None:
    decision = _stratagem_target_binding_decision(declinable=False)
    workspace = AssignmentWorkspace.start_for_pending(decision)
    assert workspace is not None

    invalid_status, submission, next_result_index = prepare_assignment_submission(
        assignment_workspace=workspace,
        pending_decision=decision,
        next_result_index=7,
        decline=True,
    )

    assert submission is None
    assert invalid_status is not None
    assert invalid_status.invalid_diagnostics[0].violation_code == (
        "assignment_decline_not_available"
    )
    assert next_result_index == 7


def test_assignment_hud_and_visual_summary_use_workspace_rows() -> None:
    decision = _shooting_declaration_decision()
    workspace = AssignmentWorkspace.start_for_pending(decision)
    assert workspace is not None

    panel = build_assignment_hud_panel(
        movement_draft=None,
        placement_draft=None,
        assignment_workspace=workspace,
        pending_decision=decision,
        highlighted_option_index=0,
        diagnostics=(),
        preferences=default_preferences(),
        preference_source_label="test",
    )
    assert panel is not None
    assert panel.operation_kind == "shooting_declaration"
    assert panel.readiness_state == "ready"
    assert panel.groups[0].source_ref_keys == ("model:intercessor_1",)
    assert panel.groups[0].target_ref_keys == ("unit:guardian_squad",)

    summary = build_action_visual_summary(
        movement_draft=None,
        pending_decision=decision,
        diagnostics=(),
        intensity="review",
        max_labels=6,
        assignment_hud_panel=panel,
    )

    assert summary is not None
    assert summary.operation_kind == "assignment"
    assert summary.groups[0].color_role == "assignment"
    assert summary.groups[0].source_ref_keys == ("model:intercessor_1",)
    assert summary.groups[0].target_ref_keys == ("unit:guardian_squad",)


def test_current_action_panel_exposes_assignment_submit_and_decline_buttons() -> None:
    decision = _stratagem_target_binding_decision(declinable=True)
    workspace = AssignmentWorkspace.start_for_pending(decision)
    assert workspace is not None
    preferences = default_preferences()
    assignment_panel = build_assignment_hud_panel(
        movement_draft=None,
        placement_draft=None,
        assignment_workspace=workspace,
        pending_decision=decision,
        highlighted_option_index=0,
        diagnostics=(),
        preferences=preferences,
        preference_source_label="test",
    )
    assert assignment_panel is not None

    ergonomics = build_hud_ergonomics_view(
        view=default_battlefield_view(),
        preferences=preferences,
        unit_panel=None,
        finite_decision_panel=build_finite_decision_panel(
            pending_decision=decision,
            highlighted_option_index=0,
            status_message="Proposal required: stratagem_target_binding",
            diagnostics=(),
        ),
        movement_draft_panel=None,
        assignment_hud_panel=assignment_panel,
        event_log_lines=(),
    )
    runtime = runtime_data_for_ergonomic_hud(ergonomics)
    current_action = runtime["current_action"]
    assert type(current_action) is dict
    buttons = current_action["buttons"]
    assert type(buttons) is list
    first_button = buttons[0]
    assert type(first_button) is dict
    button_kinds = [button["action_kind"] for button in buttons if type(button) is dict]

    assert current_action["source_kind"] == "engine_parameterized"
    assert first_button["action_kind"] == "assignment_submit"
    assert first_button["selected"] is True
    assert first_button["enabled"] is True
    assert button_kinds == ["assignment_submit", "assignment_decline", "assignment_clear"]
    clear_button = buttons[2]
    assert type(clear_button) is dict
    assert clear_button["action_kind"] == "assignment_clear"
    assert clear_button["enabled"] is False


def test_assignment_runtime_data_exposes_selectable_target_row() -> None:
    decision = _stratagem_target_binding_decision(declinable=True)
    workspace = AssignmentWorkspace.start_for_pending(decision)
    assert workspace is not None
    preferences = default_preferences()
    assignment_panel = build_assignment_hud_panel(
        movement_draft=None,
        placement_draft=None,
        assignment_workspace=workspace,
        pending_decision=decision,
        highlighted_option_index=0,
        diagnostics=(),
        preferences=preferences,
        preference_source_label="test",
    )
    assert assignment_panel is not None

    ergonomics = build_hud_ergonomics_view(
        view=default_battlefield_view(),
        preferences=preferences,
        unit_panel=None,
        finite_decision_panel=build_finite_decision_panel(
            pending_decision=decision,
            highlighted_option_index=0,
            status_message="Proposal required: stratagem_target_binding",
            diagnostics=(),
        ),
        movement_draft_panel=None,
        assignment_hud_panel=assignment_panel,
        event_log_lines=(),
        selected_assignment_group_id="stratagem-target:stratagem-request-1",
    )
    runtime = runtime_data_for_ergonomic_hud(ergonomics)
    assignment_groups = runtime["assignment_groups"]
    assert type(assignment_groups) is list
    first_group = assignment_groups[0]
    assert type(first_group) is dict
    assert first_group["action_kind"] == "assignment_select"
    assert first_group["unit_id"] == "intercessor_squad"
    assert first_group["selected"] is True
    current_assignment = runtime["current_assignment"]
    assert type(current_assignment) is dict
    assert current_assignment["action_kind"] == "assignment_select"


def _shooting_declaration_decision(
    *,
    available_weapons: list[dict[str, object]] | None = None,
    target_candidates: list[dict[str, object]] | None = None,
) -> UiDecision:
    if available_weapons is None:
        available_weapons = [
            {
                "model_instance_id": "intercessor_1",
                "wargear_id": "bolt_rifle",
                "weapon_profile_id": "bolt_rifle_profile",
                "weapon_profile": {"name": "Bolt Rifle"},
            }
        ]
    if target_candidates is None:
        target_candidates = [
            {
                "is_legal": True,
                "observer_model_id": "intercessor_1",
                "weapon_profile_id": "bolt_rifle_profile",
                "target_unit_instance_id": "guardian_squad",
                "shooting_types": ["normal"],
                "visibility_cache_key": "visibility-cache-1",
            }
        ]
    return UiDecision.from_payload(
        {
            "request_id": "shooting-request-1",
            "decision_type": "submit_shooting_declaration",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "shooting-request-1",
                    "decision_type": "submit_shooting_declaration",
                    "actor_id": "player_1",
                    "game_id": "game-1",
                    "battle_round": 1,
                    "phase": "shooting",
                    "active_player_id": "player_1",
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": "shooting_declaration",
                    "source_decision_request_id": "select-shooting-unit",
                    "source_decision_result_id": "ui-result-000001",
                    "selected_shooting_type": "normal",
                    "ruleset_descriptor_hash": "rules",
                    "visibility_cache_key": "visibility-cache-1",
                    "available_weapons": available_weapons,
                    "target_candidates": target_candidates,
                }
            },
            "is_parameterized": True,
            "options": [_submit_parameterized_option()],
        }
    )


def _melee_declaration_decision() -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": "melee-request-1",
            "decision_type": "submit_melee_declaration",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "melee-request-1",
                    "decision_type": "submit_melee_declaration",
                    "actor_id": "player_1",
                    "game_id": "game-1",
                    "battle_round": 1,
                    "active_player_id": "player_1",
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": "melee_declaration",
                    "source_decision_request_id": "select-fight-unit",
                    "source_decision_result_id": "ui-result-000001",
                    "ruleset_descriptor_hash": "rules",
                    "target_unit_instance_ids": ["guardian_squad"],
                    "available_weapons": [
                        {
                            "model_instance_id": "intercessor_1",
                            "wargear_id": "close_combat_weapon",
                            "weapon_profile_id": "close_combat_weapon_profile",
                            "is_extra_attacks": False,
                            "maximum_declared_targets": 1,
                            "fixed_attacks": 2,
                            "engaged_target_unit_instance_ids": ["guardian_squad"],
                            "weapon_profile": {"name": "Close Combat Weapon"},
                        }
                    ],
                }
            },
            "is_parameterized": True,
            "options": [_submit_parameterized_option()],
        }
    )


def _stratagem_target_binding_decision(
    *,
    declinable: bool = False,
    target_binding: dict[str, object] | None = _DEFAULT_TARGET_BINDING,
    target_binding_candidates: list[dict[str, object]] | None = None,
) -> UiDecision:
    proposal_request: dict[str, object] = {
        "request_id": "stratagem-request-1",
        "decision_type": "submit_stratagem_target_proposal",
        "actor_id": "player_1",
        "proposal_kind": "stratagem_target_binding",
        "context": {
            "game_id": "game-1",
            "player_id": "player_1",
            "battle_round": 1,
            "phase": "movement",
            "active_player_id": "player_1",
            "trigger_kind": "selected_to_move",
            "timing_window_id": None,
            "trigger_payload": {"affected_unit_instance_id": "intercessor_squad"},
        },
        "catalog_record": {
            "record_id": "record-1",
            "definition": {
                "stratagem_id": "core:test",
                "name": "Test Stratagem",
            },
        },
        "effect_selection": None,
    }
    if target_binding is not None:
        proposal_request["target_binding"] = target_binding
    if target_binding_candidates is not None:
        proposal_request["target_binding_candidates"] = target_binding_candidates
    return UiDecision.from_payload(
        {
            "request_id": "stratagem-request-1",
            "decision_type": "submit_stratagem_target_proposal",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": proposal_request,
                "declinable": declinable,
            },
            "is_parameterized": True,
            "options": [_submit_parameterized_option()],
        }
    )


def _submit_parameterized_option() -> dict[str, object]:
    return {
        "option_id": "submit_parameterized_payload",
        "label": "Submit Parameterized Payload",
        "payload": {"submission_kind": "parameterized"},
    }
