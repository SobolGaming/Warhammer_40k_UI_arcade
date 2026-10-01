"""Tests for generic assignment proposal workspaces."""

from __future__ import annotations

from typing import cast

from warhammer40k_core.core.army_catalog import ArmyCatalog

from tests.support.contract_fixtures import decision_from_fixture
from tests.support.gui_driver import GuiTestDriver
from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.protocol import JsonObject, UiDecision
from warhammer40k_arcade_ui.hud.action_summary import build_action_visual_summary
from warhammer40k_arcade_ui.hud.ergonomics import build_hud_ergonomics_view
from warhammer40k_arcade_ui.hud.runtime_data import runtime_data_for_ergonomic_hud
from warhammer40k_arcade_ui.hud.view_models import (
    build_assignment_hud_panel,
    build_finite_decision_panel,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.state.assignment_submission import prepare_assignment_submission
from warhammer40k_arcade_ui.state.assignment_workspace import (
    AssignmentWorkspace,
    ShootingAssignmentSelection,
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
    assert workspace.editable is True
    assert workspace.shooting_selections == (workspace.shooting_choices[0].selection,)
    assert workspace.assigned_ref_keys == ("model:intercessor_1",)
    assert workspace.target_ref_keys == ("unit:guardian_squad",)
    assert workspace.payload_preview is not None
    assert workspace.payload_preview["proposal_request_id"] == "shooting-request-1"
    assert workspace.payload_preview["proposal_kind"] == "shooting_declaration"
    assert workspace.payload_preview["declarations"] == [
        {
            "attacker_model_instance_id": "intercessor_1",
            "weapon_instance_id": "bolt-rifle-copy-1",
            "wargear_id": "bolt_rifle",
            "weapon_profile_id": "bolt_rifle_profile",
            "target_unit_instance_id": "guardian_squad",
            "shooting_type": "normal",
            "selected_weapon_ability_ids": [],
            "firing_deck_source_unit_instance_id": None,
            "firing_deck_source_model_instance_id": None,
        }
    ]
    assert workspace.payload_preview["firing_deck_selection"] is None


def test_shooting_assignment_workspace_matches_only_the_candidate_physical_copy() -> None:
    decision = _shooting_declaration_decision(
        available_weapons=[
            {
                "model_instance_id": "intercessor_1",
                "weapon_instance_id": "bolt-rifle-copy-1",
                "wargear_id": "bolt_rifle",
                "weapon_profile_id": "bolt_rifle_profile",
                "weapon_profile": {"name": "Bolt Rifle"},
            },
            {
                "model_instance_id": "intercessor_2",
                "weapon_instance_id": "bolt-rifle-copy-2",
                "wargear_id": "bolt_rifle",
                "weapon_profile_id": "bolt_rifle_profile",
                "weapon_profile": {"name": "Bolt Rifle"},
            },
        ],
        target_candidates=[
            {
                "is_legal": True,
                "weapon_instance_id": "bolt-rifle-copy-1",
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
    ]
    assert len(workspace.rows) == 1


def test_shooting_assignment_workspace_keeps_identical_physical_copies_distinct() -> None:
    weapons: list[dict[str, object]] = [
        {
            "model_instance_id": "intercessor_1",
            "weapon_instance_id": copy_id,
            "wargear_id": "bolt_rifle",
            "weapon_profile_id": "bolt_rifle_profile",
        }
        for copy_id in ("copy-a", "copy-b")
    ]
    candidates: list[dict[str, object]] = [
        {
            "is_legal": True,
            "weapon_instance_id": copy_id,
            "weapon_profile_id": "bolt_rifle_profile",
            "target_unit_instance_id": "guardian_squad",
            "shooting_types": ["normal"],
            "visibility_cache_key": "visibility-cache-1",
        }
        for copy_id in ("copy-a", "copy-b")
    ]
    decision = _shooting_declaration_decision(
        available_weapons=weapons,
        target_candidates=candidates,
    )

    workspace = AssignmentWorkspace.start_for_pending(decision)

    assert workspace is not None
    assert workspace.is_ready
    assert len({row.row_id for row in workspace.rows}) == 2
    assert workspace.payload_preview is not None
    declarations = workspace.payload_preview["declarations"]
    assert type(declarations) is list
    assert [row["weapon_instance_id"] for row in declarations if type(row) is dict] == [
        "copy-a",
        "copy-b",
    ]
    assert len({choice.choice_id for choice in workspace.shooting_choices}) == 2
    assert {choice.selection.weapon_instance_id for choice in workspace.shooting_choices} == {
        "copy-a",
        "copy-b",
    }


def test_shooting_assignment_workspace_keeps_legal_profiles_sharing_a_copy() -> None:
    profiles = ("ctan-power-a", "ctan-power-b")
    decision = _shooting_declaration_decision(
        available_weapons=[
            {
                "model_instance_id": "intercessor_1",
                "weapon_instance_id": "shared-physical-copy",
                "wargear_id": "ctan-powers",
                "weapon_profile_id": profile,
            }
            for profile in profiles
        ],
        target_candidates=[
            {
                "is_legal": True,
                "weapon_instance_id": "shared-physical-copy",
                "weapon_profile_id": profile,
                "target_unit_instance_id": "guardian_squad",
                "shooting_types": ["normal"],
            }
            for profile in profiles
        ],
        selection_limits=[
            {
                "model_instance_id": "intercessor_1",
                "weapon_keyword": "C'tan Power",
                "max_selections": 1,
                "weapon_profile_ids": list(profiles),
            }
        ],
    )

    workspace = AssignmentWorkspace.start_for_pending(decision)

    assert workspace is not None
    assert workspace.is_ready
    assert len({row.row_id for row in workspace.rows}) == 2
    assert all(
        "Engine selection limit: 1 C'tan Power per model" in row.summary_lines
        for row in workspace.rows
    )
    assert workspace.payload_preview is not None
    declarations = workspace.payload_preview["declarations"]
    assert type(declarations) is list
    assert [row["weapon_profile_id"] for row in declarations if type(row) is dict] == list(profiles)
    assert {choice.selection.weapon_profile_id for choice in workspace.shooting_choices} == set(
        profiles
    )
    for profile in profiles:
        selected = workspace.with_shooting_selections(
            decision,
            (
                ShootingAssignmentSelection(
                    model_instance_id="intercessor_1",
                    weapon_instance_id="shared-physical-copy",
                    weapon_profile_id=profile,
                    target_unit_instance_id="guardian_squad",
                ),
            ),
        )
        assert selected.is_ready
        assert selected.payload_preview is not None
        chosen = selected.payload_preview["declarations"]
        assert type(chosen) is list
        assert len(chosen) == 1
        assert type(chosen[0]) is dict
        assert chosen[0]["weapon_profile_id"] == profile

    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=default_battlefield_view(),
        preferences=default_preferences(),
        pending_decision=decision,
    )
    driver = GuiTestDriver(window=window)
    try:

        def click(action_kind: str) -> None:
            driver.window.on_draw()
            region = next(
                region
                for region in driver.hud_button_hit_regions
                if region.action_kind == action_kind and region.enabled
            )
            driver.click_screen(
                round((region.bounds[0] + region.bounds[2]) / 2.0),
                round((region.bounds[1] + region.bounds[3]) / 2.0),
            )

        click("assignment_clear")
        choices = tuple(
            choice
            for choice in workspace.shooting_choices
            if choice.selection.target_unit_instance_id == "guardian_squad"
        )
        assert {choice.selection.weapon_profile_id for choice in choices} == set(profiles)
        for choice in choices:
            for _ in range(len(workspace.shooting_choices)):
                driver.window.on_draw()
                visible = next(
                    region
                    for region in driver.hud_button_hit_regions
                    if region.action_kind == "assignment_select"
                )
                if visible.option_id == choice.choice_id:
                    break
                click("assignment_next_choice")
            else:
                raise AssertionError("Emitted profile choice was not reachable in HUD.")
            click("assignment_select")
        edited = driver.window.assignment_workspace
        assert edited is not None
        assert edited.payload_preview is not None
        edited_declarations = edited.payload_preview["declarations"]
        assert type(edited_declarations) is list
        assert {
            cast(str, row["weapon_profile_id"]) for row in edited_declarations if type(row) is dict
        } == (set(profiles))
    finally:
        driver.close()


def test_shooting_assignment_workspace_supports_explicit_empty_and_targetless_choice() -> None:
    decision = _shooting_declaration_decision()
    workspace = AssignmentWorkspace.start_for_pending(decision)
    assert workspace is not None

    empty = workspace.with_shooting_selections(decision, ())

    assert empty.is_ready
    assert empty.payload_preview is not None
    assert empty.payload_preview["declarations"] == []
    assert empty.rows == ()
    assert empty.shooting_selections == ()
    assert empty.shooting_choices == workspace.shooting_choices

    targetless = workspace.with_shooting_selections(
        decision,
        (
            ShootingAssignmentSelection(
                model_instance_id="intercessor_1",
                weapon_instance_id="bolt-rifle-copy-1",
                weapon_profile_id="bolt_rifle_profile",
                target_unit_instance_id=None,
            ),
        ),
    )

    assert targetless.is_ready
    assert targetless.payload_preview is not None
    assert targetless.payload_preview["declarations"] == [
        {
            "attacker_model_instance_id": "intercessor_1",
            "weapon_instance_id": "bolt-rifle-copy-1",
            "wargear_id": "bolt_rifle",
            "weapon_profile_id": "bolt_rifle_profile",
            "target_unit_instance_id": None,
            "shooting_type": "normal",
            "selected_weapon_ability_ids": [],
            "firing_deck_source_unit_instance_id": None,
            "firing_deck_source_model_instance_id": None,
        }
    ]
    assert targetless.target_ref_keys == ()


def test_targetless_duplicate_source_selection_copies_only_an_emitted_option() -> None:
    candidate: dict[str, object] = {
        "model_instance_id": "intercessor_1",
        "weapon_instance_id": "bolt-rifle-copy-1",
        "weapon_profile_id": "bolt_rifle_profile",
        "target_unit_instance_id": None,
        "shooting_type": "normal",
        "required_weapon_ability_selections": [
            {
                "options": [
                    {"option_id": "hazardous-source-a"},
                    {"option_id": "hazardous-source-b"},
                ]
            }
        ],
    }
    decision = _shooting_declaration_decision(targetless_weapon_candidates=[candidate])
    workspace = AssignmentWorkspace.start_for_pending(decision)
    assert workspace is not None
    choice = ShootingAssignmentSelection(
        model_instance_id="intercessor_1",
        weapon_instance_id="bolt-rifle-copy-1",
        weapon_profile_id="bolt_rifle_profile",
        target_unit_instance_id=None,
        selected_weapon_ability_ids=("hazardous-source-b",),
    )

    selected = workspace.with_shooting_selections(decision, (choice,))
    invalid = workspace.with_shooting_selections(
        decision,
        (
            ShootingAssignmentSelection(
                model_instance_id=choice.model_instance_id,
                weapon_instance_id=choice.weapon_instance_id,
                weapon_profile_id=choice.weapon_profile_id,
                target_unit_instance_id=None,
                selected_weapon_ability_ids=("invented-source",),
            ),
        ),
    )

    assert selected.is_ready
    assert selected.payload_preview is not None
    declarations = selected.payload_preview["declarations"]
    assert type(declarations) is list
    assert type(declarations[0]) is dict
    assert declarations[0]["selected_weapon_ability_ids"] == ["hazardous-source-b"]
    assert {row.selection.selected_weapon_ability_ids for row in workspace.shooting_choices} == {
        (),
        ("hazardous-source-a",),
        ("hazardous-source-b",),
    }
    assert selected.shooting_selections == (choice,)
    assert not invalid.is_ready
    assert invalid.diagnostic_lines == (
        "Selected weapon ability ID was not emitted for its source family.",
    )


def test_shooting_choices_expose_emitted_targets_and_complete_source_options() -> None:
    candidates: list[dict[str, object]] = [
        {
            "is_legal": True,
            "weapon_instance_id": "bolt-rifle-copy-1",
            "weapon_profile_id": "bolt_rifle_profile",
            "target_unit_instance_id": "guardian_squad",
            "shooting_types": ["normal"],
            "required_weapon_ability_selections": [
                {
                    "options": [
                        {"option_id": "source-a", "label": "Source A"},
                        {"option_id": "source-b", "label": "Source B"},
                    ]
                },
                {"options": [{"option_id": "source-c", "label": "Source C"}]},
            ],
        },
        {
            "is_legal": True,
            "weapon_instance_id": "bolt-rifle-copy-1",
            "weapon_profile_id": "bolt_rifle_profile",
            "target_unit_instance_id": "second_target",
            "shooting_types": ["normal"],
        },
        {
            "is_legal": False,
            "weapon_instance_id": "bolt-rifle-copy-1",
            "weapon_profile_id": "bolt_rifle_profile",
            "target_unit_instance_id": "illegal_target",
            "shooting_types": ["normal"],
        },
    ]
    targetless: list[dict[str, object]] = [
        {
            "model_instance_id": "intercessor_1",
            "weapon_instance_id": "bolt-rifle-copy-1",
            "weapon_profile_id": "bolt_rifle_profile",
            "target_unit_instance_id": None,
            "shooting_type": "normal",
        }
    ]
    decision = _shooting_declaration_decision(
        target_candidates=candidates,
        targetless_weapon_candidates=targetless,
    )
    workspace = AssignmentWorkspace.start_for_pending(decision)

    assert workspace is not None
    assert workspace.editable
    assert len(workspace.shooting_choices) == 4
    assert len({choice.choice_id for choice in workspace.shooting_choices}) == 4
    repeated = AssignmentWorkspace.start_for_pending(decision)
    assert repeated is not None
    assert workspace.shooting_choices == repeated.shooting_choices
    assert {choice.selection.target_unit_instance_id for choice in workspace.shooting_choices} == {
        "guardian_squad",
        "second_target",
        None,
    }
    source_choices = tuple(
        choice
        for choice in workspace.shooting_choices
        if choice.selection.target_unit_instance_id == "guardian_squad"
    )
    assert {choice.selection.selected_weapon_ability_ids for choice in source_choices} == {
        ("source-a", "source-c"),
        ("source-b", "source-c"),
    }
    assert all(choice.target_ref_keys == ("unit:guardian_squad",) for choice in source_choices)
    assert all(
        "Weapon ability source: source-c" in choice.summary_lines for choice in source_choices
    )
    assert workspace.shooting_choices[-1].target_ref_keys == ()
    assert workspace.shooting_choices[-1].selection.target_unit_instance_id is None

    selected = workspace.with_shooting_selections(decision, (source_choices[1].selection,))
    assert selected.is_ready
    assert selected.shooting_selections == (source_choices[1].selection,)
    assert selected.payload_preview is not None
    declarations = selected.payload_preview["declarations"]
    assert type(declarations) is list
    assert type(declarations[0]) is dict
    assert declarations[0]["selected_weapon_ability_ids"] == ["source-b", "source-c"]

    other_decision = _shooting_declaration_decision(
        request_id="shooting-request-2",
        target_candidates=candidates,
        targetless_weapon_candidates=targetless,
    )
    other_workspace = AssignmentWorkspace.start_for_pending(other_decision)
    assert other_workspace is not None
    assert {choice.choice_id for choice in workspace.shooting_choices}.isdisjoint(
        choice.choice_id for choice in other_workspace.shooting_choices
    )


def test_shooting_firing_deck_choice_preserves_source_and_selection_evidence() -> None:
    bolt_rifle = next(
        item
        for item in ArmyCatalog.phase9a_canonical_content_pack().wargear
        if item.wargear_id == "core-bolt-rifle"
    )
    profile: JsonObject = cast(JsonObject, bolt_rifle.weapon_profiles[0].to_payload())
    profile_id = cast(str, profile["profile_id"])
    decision = _shooting_declaration_decision(
        available_weapons=[
            {
                "model_instance_id": "embarked_model",
                "weapon_instance_id": "embarked-copy-2",
                "wargear_id": "core-bolt-rifle",
                "weapon_profile_id": profile_id,
                "weapon_profile": profile,
                "firing_deck_source_unit_instance_id": "embarked_unit",
                "firing_deck_source_model_instance_id": "embarked_model",
            }
        ],
        target_candidates=[
            {
                "is_legal": True,
                "weapon_instance_id": "embarked-copy-2",
                "weapon_profile_id": profile_id,
                "target_unit_instance_id": "guardian_squad",
                "shooting_types": ["normal"],
            }
        ],
    )
    workspace = AssignmentWorkspace.start_for_pending(decision)
    assert workspace is not None
    assert not workspace.is_ready
    assert workspace.diagnostic_lines == (
        "Firing Deck needs public already-shot-unit and weapon selection evidence.",
    )
    assert workspace.shooting_choices
    assert all(
        choice.selection.firing_deck_source_unit_instance_id == "embarked_unit"
        and choice.selection.firing_deck_source_model_instance_id == "embarked_model"
        for choice in workspace.shooting_choices
    )
    evidence: JsonObject = {
        "player_id": "player_1",
        "battle_round": 1,
        "transport_unit_instance_id": "intercessor_squad",
        "firing_deck_value": 1,
        "weapon_selections": [
            {
                "embarked_unit_instance_id": "embarked_unit",
                "model_instance_id": "embarked_model",
                "weapon_instance_id": "embarked-copy-2",
                "wargear_id": "core-bolt-rifle",
                "weapon_profile": profile,
            }
        ],
        "already_shot_unit_instance_ids": [],
    }

    selected = workspace.with_shooting_selections(
        decision,
        (
            ShootingAssignmentSelection(
                model_instance_id="embarked_model",
                weapon_instance_id="embarked-copy-2",
                weapon_profile_id=profile_id,
                target_unit_instance_id=None,
                firing_deck_source_unit_instance_id="embarked_unit",
                firing_deck_source_model_instance_id="embarked_model",
            ),
        ),
        firing_deck_selection=evidence,
    )

    assert selected.is_ready
    assert selected.payload_preview is not None
    declarations = selected.payload_preview["declarations"]
    assert type(declarations) is list
    assert type(declarations[0]) is dict
    assert declarations[0]["weapon_instance_id"] == "embarked-copy-2"
    assert declarations[0]["firing_deck_source_unit_instance_id"] == "embarked_unit"
    assert declarations[0]["firing_deck_source_model_instance_id"] == "embarked_model"
    assert selected.payload_preview["firing_deck_selection"] == evidence


def test_shooting_missing_physical_id_fails_visibly() -> None:
    decision = _shooting_declaration_decision(
        available_weapons=[
            {
                "model_instance_id": "intercessor_1",
                "wargear_id": "bolt_rifle",
                "weapon_profile_id": "bolt_rifle_profile",
            }
        ]
    )

    workspace = AssignmentWorkspace.start_for_pending(decision)

    assert workspace is not None
    assert not workspace.is_ready
    assert workspace.payload_preview is None
    assert "Shooting weapon candidate is missing physical/model/wargear/profile IDs." in (
        workspace.diagnostic_lines
    )


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
    assert "No selectable target is exposed yet; decline is available." in (
        workspace.rows[0].summary_lines
    )
    assert workspace.diagnostic_lines == ()


def test_required_stratagem_assignment_without_binding_is_invalid() -> None:
    decision = _stratagem_target_binding_decision(target_binding=None, declinable=False)

    workspace = AssignmentWorkspace.start_for_pending(decision)

    assert workspace is not None
    assert workspace.is_ready is False
    assert workspace.declinable is False
    assert workspace.diagnostic_lines == (
        "Stratagem request does not expose a selectable target binding candidate yet.",
    )


def test_finite_opportunity_window_is_not_assignment_workspace() -> None:
    decision = decision_from_fixture(
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
    request_id: str = "shooting-request-1",
    available_weapons: list[dict[str, object]] | None = None,
    target_candidates: list[dict[str, object]] | None = None,
    targetless_weapon_candidates: list[dict[str, object]] | None = None,
    selection_limits: list[dict[str, object]] | None = None,
) -> UiDecision:
    if available_weapons is None:
        available_weapons = [
            {
                "model_instance_id": "intercessor_1",
                "weapon_instance_id": "bolt-rifle-copy-1",
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
                "weapon_instance_id": "bolt-rifle-copy-1",
                "weapon_profile_id": "bolt_rifle_profile",
                "target_unit_instance_id": "guardian_squad",
                "shooting_types": ["normal"],
                "visibility_cache_key": "visibility-cache-1",
            }
        ]
    proposal_request: dict[str, object] = {
        "request_id": request_id,
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
        "shooting_weapon_selection_limits": [] if selection_limits is None else selection_limits,
        "target_candidates": target_candidates,
    }
    if targetless_weapon_candidates is not None:
        proposal_request["targetless_weapon_candidates"] = targetless_weapon_candidates
    return decision_from_fixture(
        {
            "request_id": request_id,
            "decision_type": "submit_shooting_declaration",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": proposal_request,
            },
            "is_parameterized": True,
            "options": [_submit_parameterized_option()],
        }
    )


def _melee_declaration_decision() -> UiDecision:
    return decision_from_fixture(
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
    return decision_from_fixture(
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
