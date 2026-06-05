"""Tests for request-scoped entity selection profiles and state."""

from __future__ import annotations

from dataclasses import replace

import pytest

from warhammer40k_arcade_ui.core_client.protocol import UiDecision, UiFiniteOption
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.state.entity_selection import (
    EntityRef,
    EntitySelectionError,
    EntitySelectionProfile,
    EntitySelectionState,
    SelectionCardinality,
    build_entity_selection_profile,
    entity_ref_for_model,
    entity_ref_for_unit,
    visual_anchor_diagnostics,
)


def test_entity_ref_validates_kind_id_and_anchor() -> None:
    ref = EntityRef(kind="model", entity_id="model-a", visual_anchor_world=(1.0, 2.0))

    assert ref.selection_key == "model:model-a"

    with pytest.raises(EntitySelectionError):
        EntityRef(kind="model", entity_id="")
    with pytest.raises(EntitySelectionError):
        EntityRef(kind="model", entity_id="model-a", visual_anchor_world=(float("nan"), 2.0))


def test_movement_profile_selects_models_and_exposes_safe_visual_anchors() -> None:
    view = default_battlefield_view()
    profile = build_entity_selection_profile(
        view=view,
        pending_decision=_movement_proposal_decision(),
    )
    model_ref = _model_ref("intercessor_squad", "intercessor_1")
    state = EntitySelectionState.initial(profile).replace_selection(model_ref)

    assert profile.is_supported is True
    assert profile.request_id == "decision-request-000005"
    assert profile.decision_type == "submit_movement_proposal"
    assert profile.active_layer == "model"
    assert [ref.selection_key for ref in profile.candidates_for_layer("model")] == [
        "model:intercessor_1",
        "model:intercessor_2",
        "model:intercessor_3",
    ]
    assert [ref.selection_key for ref in state.selected_refs] == ["model:intercessor_1"]
    assert state.selected_refs[0].visual_anchor_world == (7.0, 18.0)
    assert state.visual_anchor_diagnostics() == ()


def test_movement_profile_can_expand_unit_to_all_models_in_model_layer() -> None:
    profile = build_entity_selection_profile(
        view=default_battlefield_view(),
        pending_decision=_movement_proposal_decision(),
    )
    unit_ref = _unit_ref("intercessor_squad")
    state = EntitySelectionState.initial(profile).replace_selection(unit_ref)

    assert state.active_layer == "model"
    assert [ref.selection_key for ref in state.selected_refs] == [
        "model:intercessor_1",
        "model:intercessor_2",
        "model:intercessor_3",
    ]


def test_add_subtract_and_toggle_selection_are_deterministic() -> None:
    profile = build_entity_selection_profile(
        view=default_battlefield_view(),
        pending_decision=_movement_proposal_decision(),
    )
    model_1 = _model_ref("intercessor_squad", "intercessor_1")
    model_2 = _model_ref("intercessor_squad", "intercessor_2")

    selected = (
        EntitySelectionState.initial(profile)
        .add_selection(model_2)
        .add_selection(model_1)
        .toggle_selection(model_2)
        .subtract_selection(model_1)
    )

    assert selected.selected_refs == ()
    assert selected.diagnostics == ()

    reordered = EntitySelectionState.initial(profile).add_selection(model_2).add_selection(model_1)
    assert [ref.selection_key for ref in reordered.selected_refs] == [
        "model:intercessor_1",
        "model:intercessor_2",
    ]


def test_finite_unit_profile_aliases_model_click_to_unit_candidate() -> None:
    view = default_battlefield_view()
    profile = build_entity_selection_profile(
        view=view,
        pending_decision=_finite_unit_decision(),
    )
    model_ref = _model_ref("intercessor_squad", "intercessor_1")
    state = EntitySelectionState.initial(profile).replace_selection(model_ref)

    assert profile.active_layer == "unit"
    assert [ref.selection_key for ref in profile.candidates_for_layer("unit")] == [
        "unit:intercessor_squad",
        "unit:guardian_squad",
    ]
    assert [ref.selection_key for ref in state.selected_refs] == ["unit:intercessor_squad"]


def test_finite_unit_profile_rejects_additive_second_unit() -> None:
    profile = build_entity_selection_profile(
        view=default_battlefield_view(),
        pending_decision=_finite_unit_decision(),
    )
    state = (
        EntitySelectionState.initial(profile)
        .replace_selection(_unit_ref("intercessor_squad"))
        .add_selection(_unit_ref("guardian_squad"))
    )

    assert [ref.selection_key for ref in state.selected_refs] == ["unit:intercessor_squad"]
    assert state.diagnostics[-1].code == "additive_selection_not_allowed"


def test_rejects_aliasing_when_ref_is_not_allowed_by_profile() -> None:
    profile = build_entity_selection_profile(
        view=default_battlefield_view(),
        pending_decision=_movement_proposal_decision(),
    )
    guardian_ref = _model_ref("guardian_squad", "guardian_1")

    state = EntitySelectionState.initial(profile).replace_selection(guardian_ref)

    assert state.selected_refs == ()
    assert state.diagnostics[-1].code == "entity_ref_not_selectable"


def test_layer_cycling_only_visits_available_layers() -> None:
    profile = EntitySelectionProfile(
        request_id="request-1",
        decision_type="unit_only",
        actor_id="player_1",
        selectable_layers=("model", "unit"),
        active_layer="unit",
        candidate_refs=(_unit_ref("intercessor_squad"),),
        alias_rules=(),
        cardinality=SelectionCardinality(max_count=1),
        additive_allowed=False,
        subtractive_allowed=False,
        diagnostics=(),
    )
    state = EntitySelectionState.initial(profile).cycle_active_layer()

    assert state.active_layer == "unit"
    assert state.focused_ref is not None
    assert state.focused_ref.selection_key == "unit:intercessor_squad"


def test_unsupported_parameterized_request_produces_typed_diagnostic() -> None:
    profile = build_entity_selection_profile(
        view=default_battlefield_view(),
        pending_decision=_shooting_proposal_decision(),
    )
    state = EntitySelectionState.initial(profile).replace_selection(
        _model_ref("intercessor_squad", "intercessor_1")
    )

    assert profile.is_supported is False
    assert profile.unsupported_reason is not None
    assert profile.diagnostics[0].code == "unsupported_request_profile"
    assert state.selected_refs == ()
    assert state.diagnostics[-1].code == "unsupported_request_profile"


def test_request_scoped_selection_reconciles_same_request_and_clears_on_request_change() -> None:
    view = default_battlefield_view()
    profile = build_entity_selection_profile(
        view=view,
        pending_decision=_movement_proposal_decision(),
    )
    selected = EntitySelectionState.initial(profile).replace_selection(
        _model_ref("intercessor_squad", "intercessor_1")
    )
    same_profile = build_entity_selection_profile(
        view=view,
        pending_decision=_movement_proposal_decision(),
    )
    changed_profile = build_entity_selection_profile(
        view=view,
        pending_decision=_movement_proposal_decision(request_id="decision-request-000006"),
    )

    reconciled = EntitySelectionState.reconcile(previous=selected, profile=same_profile)
    cleared = EntitySelectionState.reconcile(previous=selected, profile=changed_profile)

    assert [ref.selection_key for ref in reconciled.selected_refs] == ["model:intercessor_1"]
    assert cleared.selected_refs == ()
    assert cleared.profile.request_id == "decision-request-000006"


def test_visual_anchor_diagnostics_report_unavailable_anchor() -> None:
    ref = EntityRef(kind="custom", entity_id="hidden-entity")

    diagnostics = visual_anchor_diagnostics((ref,))

    assert diagnostics[0].code == "visual_anchor_unavailable"
    assert diagnostics[0].entity_ref_key == "custom:hidden-entity"


def _model_ref(unit_id: str, model_id: str) -> EntityRef:
    ref = entity_ref_for_model(
        view=default_battlefield_view(),
        unit_id=unit_id,
        model_id=model_id,
    )
    assert ref is not None
    return ref


def _unit_ref(unit_id: str) -> EntityRef:
    ref = entity_ref_for_unit(view=default_battlefield_view(), unit_id=unit_id)
    assert ref is not None
    return ref


def _finite_unit_decision() -> UiDecision:
    return UiDecision(
        request_id="decision-request-000004",
        decision_type="select_target_unit",
        actor_id="player_1",
        payload=None,
        options=(
            UiFiniteOption(
                option_id="target:intercessor_squad",
                label="Intercessors",
                payload={"unit_instance_id": "intercessor_squad"},
            ),
            UiFiniteOption(
                option_id="target:guardian_squad",
                label="Guardians",
                payload={"unit_instance_id": "guardian_squad"},
            ),
        ),
        is_parameterized=False,
    )


def _movement_proposal_decision(
    *,
    request_id: str = "decision-request-000005",
) -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": request_id,
            "decision_type": "submit_movement_proposal",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": request_id,
                    "decision_type": "submit_movement_proposal",
                    "actor_id": "player_1",
                    "game_id": "phase8-game",
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
    decision = _movement_proposal_decision()
    proposal = decision.parameterized_proposal
    assert proposal is not None
    return replace(
        decision,
        decision_type="submit_shooting_declaration",
        movement_proposal=None,
        parameterized_proposal=replace(
            proposal,
            request_id="decision-request-000009",
            decision_type="submit_shooting_declaration",
            proposal_kind="shooting_declaration",
            payload={
                "request_id": "decision-request-000009",
                "decision_type": "submit_shooting_declaration",
                "actor_id": "player_1",
                "proposal_kind": "shooting_declaration",
            },
        ),
    )
