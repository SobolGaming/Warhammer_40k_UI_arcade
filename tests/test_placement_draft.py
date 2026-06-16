"""Tests for local placement draft state and payload previews."""

from __future__ import annotations

from typing import cast

from warhammer40k_arcade_ui.core_client.protocol import JsonObject, UiDecision
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.state.placement_draft import PlacementDraft
from warhammer40k_arcade_ui.state.selection import SelectionState


def test_reinforcement_placement_draft_uses_projected_unit_models() -> None:
    view = default_battlefield_view()
    decision = _placement_proposal_decision()

    draft = PlacementDraft.start_for_pending(
        view=view,
        selection=_empty_selection(),
        pending_decision=decision,
    )

    assert draft is not None
    assert draft.selected_unit_id == "intercessor_squad"
    assert draft.proposal_request_id == "decision-request-placement-001"
    assert draft.proposal_kind == "reinforcement_placement"
    assert draft.placement_kind == "reinforcement"
    assert [pose.model_id for pose in draft.model_poses] == [
        "intercessor_1",
        "intercessor_2",
        "intercessor_3",
    ]
    assert draft.placed_model_count == 0
    assert draft.unplaced_model_count == 3


def test_reinforcement_placement_payload_includes_every_required_model() -> None:
    draft = _ready_reinforcement_draft()

    payload = draft.payload_preview

    assert payload is not None
    assert payload["proposal_request_id"] == "decision-request-placement-001"
    assert payload["proposal_kind"] == "reinforcement_placement"
    assert payload["unit_instance_id"] == "intercessor_squad"
    assert payload["placement_kind"] == "reinforcement"
    attempted_placement = cast(JsonObject, payload["attempted_placement"])
    model_placements = cast(list[JsonObject], attempted_placement["model_placements"])
    assert [placement["model_instance_id"] for placement in model_placements] == [
        "intercessor_1",
        "intercessor_2",
        "intercessor_3",
    ]
    first_pose = cast(JsonObject, model_placements[0]["pose"])
    assert first_pose["position"] == {"x": 8.0, "y": 18.0, "z": 0.0}


def test_deployment_placement_payload_uses_setup_family_shape() -> None:
    draft = _ready_draft(_deployment_placement_decision())

    payload = draft.payload_preview

    assert payload is not None
    assert payload["proposal_kind"] == "deployment_placement"
    assert payload["game_id"] == "phase28-game"
    assert payload["ruleset_descriptor_hash"] == "ruleset-hash-001"
    assert payload["setup_step"] == "deployment"
    assert payload["player_id"] == "player_1"
    assert payload["unit_instance_id"] == "intercessor_squad"
    assert payload["placement_kind"] == "deployment_zone"
    assert type(payload["model_placements"]) is list


def test_deployment_placement_draft_uses_display_base_size_for_unprojected_unit() -> None:
    model_id = "army-alpha:strategic-reserve-unit:core-vehicle-monster:001:model:001"
    draft = PlacementDraft.start_for_pending(
        view=default_battlefield_view(),
        selection=_empty_selection(),
        pending_decision=_unprojected_vehicle_deployment_decision(model_id=model_id),
        model_display_by_id={
            model_id: {
                "model_instance_id": model_id,
                "base_size": {
                    "base_size_id": "base-size:core-vehicle-monster",
                    "kind": "circular",
                    "diameter_mm": 120.0,
                },
            }
        },
    )

    assert draft is not None
    assert len(draft.model_poses) == 1
    assert abs(draft.model_poses[0].base_radius - (120.0 / 25.4 / 2.0)) < 1.0e-9


def test_placement_hover_preview_does_not_clear_ready_payload() -> None:
    ready = _ready_reinforcement_draft()

    hovered = ready.with_cursor_preview((12.0, 20.0))

    assert hovered.is_ready is True
    assert hovered.payload_preview == ready.payload_preview
    assert hovered.cursor_preview_point == ready.cursor_preview_point


def _ready_reinforcement_draft() -> PlacementDraft:
    return _ready_draft(_placement_proposal_decision())


def _ready_draft(decision: UiDecision) -> PlacementDraft:
    view = default_battlefield_view()
    draft = PlacementDraft.start_for_pending(
        view=view,
        selection=_empty_selection(),
        pending_decision=decision,
    )
    assert draft is not None
    draft = draft.place_current_model((8.0, 18.0))
    draft = draft.place_current_model((8.0, 22.0))
    draft = draft.place_current_model((8.0, 26.0)).mark_ready()
    assert draft.is_ready
    return draft


def _empty_selection() -> SelectionState:
    return SelectionState.initial(default_preferences())


def _placement_proposal_decision() -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": "decision-request-placement-001",
            "decision_type": "submit_placement_proposal",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-placement-001",
                    "decision_type": "submit_placement_proposal",
                    "actor_id": "player_1",
                    "game_id": "phase28-game",
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": "reinforcement_placement",
                    "source_decision_request_id": "decision-request-unit-001",
                    "source_decision_result_id": "ui-result-unit-001",
                    "placement_kinds": ["reinforcement"],
                    "context": {
                        "placement_kind": "reinforcement",
                        "reserve_state": "strategic_reserves",
                    },
                }
            },
            "is_parameterized": True,
            "options": [_parameterized_option_payload()],
        }
    )


def _deployment_placement_decision() -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": "decision-request-deployment-001",
            "decision_type": "submit_deployment_placement",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-deployment-001",
                    "decision_type": "submit_deployment_placement",
                    "actor_id": "player_1",
                    "game_id": "phase28-game",
                    "ruleset_descriptor_hash": "ruleset-hash-001",
                    "setup_step": "deployment",
                    "player_id": "player_1",
                    "unit_instance_id": "intercessor_squad",
                    "proposal_kind": "deployment_placement",
                    "placement_kind": "deployment_zone",
                    "model_instance_ids": [
                        "intercessor_1",
                        "intercessor_2",
                        "intercessor_3",
                    ],
                    "source_decision_request_id": "decision-request-deploy-unit-001",
                    "source_decision_result_id": "ui-result-deploy-unit-001",
                    "context": {},
                }
            },
            "is_parameterized": True,
            "options": [_parameterized_option_payload()],
        }
    )


def _unprojected_vehicle_deployment_decision(*, model_id: str) -> UiDecision:
    unit_id = "army-alpha:strategic-reserve-unit:core-vehicle-monster:001"
    return UiDecision.from_payload(
        {
            "request_id": "decision-request-deployment-vehicle-001",
            "decision_type": "submit_deployment_placement",
            "actor_id": "player_1",
            "payload": {
                "proposal_request": {
                    "request_id": "decision-request-deployment-vehicle-001",
                    "decision_type": "submit_deployment_placement",
                    "actor_id": "player_1",
                    "game_id": "phase28-game",
                    "ruleset_descriptor_hash": "ruleset-hash-001",
                    "setup_step": "deployment",
                    "player_id": "player_1",
                    "unit_instance_id": unit_id,
                    "proposal_kind": "deployment_placement",
                    "placement_kind": "deployment_zone",
                    "model_instance_ids": [model_id],
                    "source_decision_request_id": "decision-request-deploy-unit-vehicle-001",
                    "source_decision_result_id": "ui-result-deploy-unit-vehicle-001",
                    "context": {},
                }
            },
            "is_parameterized": True,
            "options": [_parameterized_option_payload()],
        }
    )


def _parameterized_option_payload() -> dict[str, object]:
    return {
        "option_id": "submit_parameterized_payload",
        "label": "Submit Parameterized Payload",
        "payload": {"submission_kind": "parameterized"},
    }
