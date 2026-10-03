"""Tests for UI-facing core client protocol models."""

from __future__ import annotations

import pytest

from tests.support.contract_fixtures import (
    current_decision_payload,
    current_game_view_payload,
    decision_from_fixture,
)
from warhammer40k_arcade_ui.core_client.fake_client import FakeCoreClient
from warhammer40k_arcade_ui.core_client.protocol import (
    UiClientProtocolError,
    UiClientStatus,
    UiEventDelta,
    UiGameView,
    UiMovementProposalRequest,
    UiParameterizedProposalRequest,
)
from warhammer40k_arcade_ui.state.interaction_dispatch import interaction_route_for_decision


def test_status_represents_no_pending_decision() -> None:
    status = UiClientStatus.from_payload(
        {
            "stage": "setup",
            "status_kind": "advanced",
            "decision_request": None,
            "message": None,
            "payload": None,
        }
    )

    assert status.status_kind == "advanced"
    assert status.decision is None
    assert status.invalid_diagnostics == ()


def test_status_represents_finite_decision() -> None:
    decision_payload = {
        "request_id": "decision-request-000004",
        "decision_type": "select_movement_action",
        "actor_id": "player-a",
        "payload": {"unit_instance_id": "unit-1"},
        "is_parameterized": False,
        "options": [
            {
                "option_id": "normal_move",
                "label": "Normal Move",
                "payload": {"movement_phase_action": "normal_move"},
            }
        ],
    }
    status = UiClientStatus.from_payload(
        {
            "stage": "battle",
            "status_kind": "waiting_for_decision",
            "decision_request": current_decision_payload(decision_payload),
            "message": None,
            "payload": None,
        }
    )

    assert status.decision == decision_from_fixture(decision_payload)


def test_status_represents_movement_proposal_request() -> None:
    proposal_payload = _movement_proposal_request_payload()

    status = UiClientStatus.from_payload(
        {
            "stage": "battle",
            "status_kind": "waiting_for_decision",
            "decision_request": current_decision_payload(
                {
                    "request_id": "decision-request-000005",
                    "decision_type": "submit_movement_proposal",
                    "actor_id": "player-a",
                    "payload": {"proposal_request": proposal_payload},
                    "is_parameterized": True,
                    "options": [
                        {
                            "option_id": "submit_parameterized_payload",
                            "label": "Submit Parameterized Payload",
                            "payload": {"submission_kind": "parameterized"},
                        }
                    ],
                }
            ),
            "message": None,
            "payload": None,
        }
    )

    assert status.decision is not None
    assert status.decision.is_parameterized is True
    assert status.decision.movement_proposal == UiMovementProposalRequest.from_payload(
        proposal_payload
    )
    assert status.decision.parameterized_proposal == UiParameterizedProposalRequest.from_payload(
        proposal_payload
    )


def test_status_represents_scout_move_as_movement_proposal_request() -> None:
    proposal_payload = _scout_move_proposal_request_payload()

    status = UiClientStatus.from_payload(
        {
            "stage": "setup",
            "status_kind": "waiting_for_decision",
            "decision_request": current_decision_payload(
                {
                    "request_id": "decision-request-scout-001",
                    "decision_type": "submit_scout_move",
                    "actor_id": "player-a",
                    "payload": {"proposal_request": proposal_payload},
                    "is_parameterized": True,
                    "options": [
                        {
                            "option_id": "submit_parameterized_payload",
                            "label": "Submit Parameterized Payload",
                            "payload": {"submission_kind": "parameterized"},
                        }
                    ],
                }
            ),
            "message": None,
            "payload": None,
        }
    )

    assert status.decision is not None
    assert status.decision.is_parameterized is True
    assert status.decision.movement_proposal == UiMovementProposalRequest.from_payload(
        proposal_payload
    )
    assert status.decision.movement_proposal is not None
    assert status.decision.movement_proposal.proposal_kind == "scout_move"
    assert status.decision.movement_proposal.movement_phase_action is None
    assert status.decision.movement_proposal.scout_distance_inches == 6.0


def test_status_represents_generic_parameterized_request_without_movement_shape() -> None:
    status = UiClientStatus.from_payload(
        {
            "stage": "battle",
            "status_kind": "waiting_for_decision",
            "decision_request": current_decision_payload(
                {
                    "request_id": "decision-request-000009",
                    "decision_type": "submit_stratagem_target_proposal",
                    "actor_id": "player-a",
                    "payload": {
                        "proposal_request": {
                            "request_id": "decision-request-000009",
                            "decision_type": "submit_stratagem_target_proposal",
                            "actor_id": "player-a",
                            "proposal_kind": "stratagem_target_binding",
                            "trigger_window": "after_unit_selected_as_target",
                        }
                    },
                    "is_parameterized": True,
                    "options": [
                        {
                            "option_id": "submit_parameterized_payload",
                            "label": "Submit Parameterized Payload",
                            "payload": {"submission_kind": "parameterized"},
                        }
                    ],
                }
            ),
            "message": None,
            "payload": None,
        }
    )

    assert status.decision is not None
    assert status.decision.is_parameterized is True
    assert status.decision.movement_proposal is None
    assert status.decision.parameterized_proposal is not None
    assert status.decision.parameterized_proposal.proposal_kind == "stratagem_target_binding"


def test_status_represents_placement_proposal_request() -> None:
    proposal_payload = _placement_proposal_request_payload()

    status = UiClientStatus.from_payload(
        {
            "stage": "battle",
            "status_kind": "waiting_for_decision",
            "decision_request": current_decision_payload(
                {
                    "request_id": "decision-request-placement-001",
                    "decision_type": "submit_placement_proposal",
                    "actor_id": "player-a",
                    "payload": {"proposal_request": proposal_payload},
                    "is_parameterized": True,
                    "options": [
                        {
                            "option_id": "submit_parameterized_payload",
                            "label": "Submit Parameterized Payload",
                            "payload": {"submission_kind": "parameterized"},
                        }
                    ],
                }
            ),
            "message": None,
            "payload": None,
        }
    )

    assert status.decision is not None
    assert status.decision.is_parameterized is True
    assert status.decision.movement_proposal is None
    assert status.decision.placement_proposal is not None
    assert status.decision.placement_proposal.request_id == "decision-request-placement-001"
    assert status.decision.parameterized_proposal == UiParameterizedProposalRequest.from_payload(
        proposal_payload
    )


def test_status_strictly_parses_cult_ambush_marker_request_before_variant_selection() -> None:
    proposal_payload = _cult_ambush_marker_request_payload()
    decision_payload = {
        "schema_version": "decision-request-view-v5-phase17n-step4",
        "request_id": "decision-request-marker-001",
        "decision_type": "submit_cult_ambush_marker_placement",
        "actor_id": "player-a",
        "payload": proposal_payload,
        "is_parameterized": True,
        "options": [
            {
                "option_id": "submit_parameterized_payload",
                "label": "Submit Parameterized Payload",
                "payload": {"submission_kind": "parameterized"},
            }
        ],
        "interaction": _cult_ambush_marker_interaction_payload(),
    }

    status = UiClientStatus.from_payload(
        {
            "stage": "battle",
            "status_kind": "waiting_for_decision",
            "decision_request": decision_payload,
            "message": None,
            "payload": None,
        }
    )

    assert status.decision is not None
    proposal = status.decision.placement_proposal
    assert proposal is not None
    assert proposal.proposal_kind == "cult_ambush_marker_placement"
    assert proposal.unit_instance_id == "army-alpha:replacement-unit"
    assert proposal.context["marker_id"] == "cult-ambush-marker:001"
    assert status.decision.interaction is not None
    assert [variant.variant_id for variant in status.decision.interaction.submission_variants] == [
        "place_marker",
        "no_marker",
    ]
    route = interaction_route_for_decision(status.decision)
    assert route.supported is False
    assert route.diagnostic is not None
    assert "multiple submission variants" in route.diagnostic


def test_status_requires_explicit_is_parameterized_even_with_parameterized_option() -> None:
    decision = current_decision_payload(_stratagem_decision_payload())
    del decision["is_parameterized"]
    with pytest.raises(
        UiClientProtocolError,
        match="decision request is missing required field: is_parameterized",
    ):
        UiClientStatus.from_payload(
            {
                "stage": "battle",
                "status_kind": "waiting_for_decision",
                "decision_request": decision,
                "message": None,
                "payload": None,
            }
        )


def test_status_rejects_non_bool_is_parameterized() -> None:
    decision = current_decision_payload(
        {
            "request_id": "decision-request-000004",
            "decision_type": "select_movement_action",
            "actor_id": "player-a",
            "payload": {"unit_instance_id": "unit-1"},
            "is_parameterized": False,
            "options": [
                {
                    "option_id": "normal_move",
                    "label": "Normal Move",
                    "payload": {"movement_phase_action": "normal_move"},
                }
            ],
        }
    )
    decision["is_parameterized"] = "false"
    with pytest.raises(UiClientProtocolError, match="is_parameterized must be a bool"):
        UiClientStatus.from_payload(
            {
                "stage": "battle",
                "status_kind": "waiting_for_decision",
                "decision_request": decision,
                "message": None,
                "payload": None,
            }
        )


@pytest.mark.parametrize("missing_key", ["request_id", "decision_type", "actor_id"])
def test_status_parameterized_proposal_request_requires_nested_identity_envelope(
    missing_key: str,
) -> None:
    decision = current_decision_payload(_stratagem_decision_payload())
    decision_payload = decision["payload"]
    assert type(decision_payload) is dict
    proposal_request = decision_payload["proposal_request"]
    assert type(proposal_request) is dict
    del proposal_request[missing_key]

    with pytest.raises(UiClientProtocolError, match=f"requires {missing_key}"):
        UiClientStatus.from_payload(
            {
                "stage": "battle",
                "status_kind": "waiting_for_decision",
                "decision_request": decision,
                "message": None,
                "payload": None,
            }
        )


@pytest.mark.parametrize(
    ("identity_key", "replacement_value", "expected_message"),
    [
        pytest.param(
            "request_id",
            "decision-request-other",
            "request_id must match decision_request.request_id",
        ),
        pytest.param(
            "decision_type",
            "submit_movement_proposal",
            "decision_type must match decision_request.decision_type",
        ),
        pytest.param(
            "actor_id",
            "player-b",
            "actor_id must match decision_request.actor_id",
        ),
    ],
)
def test_status_parameterized_proposal_request_identity_must_match_outer_decision(
    identity_key: str,
    replacement_value: str,
    expected_message: str,
) -> None:
    decision = current_decision_payload(_stratagem_decision_payload())
    decision_payload = decision["payload"]
    assert type(decision_payload) is dict
    proposal_request = decision_payload["proposal_request"]
    assert type(proposal_request) is dict
    proposal_request[identity_key] = replacement_value

    with pytest.raises(UiClientProtocolError, match=expected_message):
        UiClientStatus.from_payload(
            {
                "stage": "battle",
                "status_kind": "waiting_for_decision",
                "decision_request": decision,
                "message": None,
                "payload": None,
            }
        )


def test_status_parameterized_outer_actor_id_is_required_for_identity_match() -> None:
    decision = current_decision_payload(_stratagem_decision_payload())
    del decision["actor_id"]
    with pytest.raises(
        UiClientProtocolError,
        match="decision request is missing required field: actor_id",
    ):
        UiClientStatus.from_payload(
            {
                "stage": "battle",
                "status_kind": "waiting_for_decision",
                "decision_request": decision,
                "message": None,
                "payload": None,
            }
        )


def test_invalid_status_represents_proposal_diagnostics() -> None:
    status = UiClientStatus.from_payload(
        {
            "stage": "battle",
            "status_kind": "invalid",
            "decision_request": None,
            "message": "Movement proposal is invalid.",
            "payload": {
                "proposal_validation": {
                    "proposal_request_id": "decision-request-000005",
                    "proposal_kind": "normal_move",
                    "is_valid": False,
                    "status": "invalid",
                    "violations": [
                        {
                            "violation_code": "proposal_payload_missing_field",
                            "message": "Proposal payload missing required field.",
                            "field": "proposal_request_id",
                        }
                    ],
                }
            },
        }
    )

    assert len(status.invalid_diagnostics) == 1
    diagnostic = status.invalid_diagnostics[0]
    assert diagnostic.violation_code == "proposal_payload_missing_field"
    assert diagnostic.proposal_request_id == "decision-request-000005"
    assert diagnostic.proposal_kind == "normal_move"
    assert diagnostic.field == "proposal_request_id"


def test_invalid_status_represents_prebattle_resolution_violations() -> None:
    status = UiClientStatus.from_payload(
        {
            "stage": "setup",
            "status_kind": "invalid",
            "decision_request": None,
            "message": "Pre-battle proposal submission is invalid.",
            "payload": {
                "invalid_reason": "prebattle_proposal_invalid",
                "request_id": "decision-request-000019",
                "resolution": {
                    "is_valid": False,
                    "proposal": {
                        "proposal_kind": "scout_move",
                        "proposal_request_id": "decision-request-000019",
                        "unit_instance_id": "army-alpha:scout-redeploy-unit",
                    },
                    "violations": [
                        {
                            "violation_code": "path_validation_failed",
                            "message": "Path witness intersects terrain.",
                            "field": "witness",
                            "model_instance_id": (
                                "army-alpha:scout-redeploy-unit:core-intercessor-like:001"
                            ),
                            "blocker_id": (
                                "take-and-hold-vs-purge-the-foe-layout-3-"
                                "upper-flank-ruin:ground-floor"
                            ),
                        },
                        {
                            "violation_code": "terrain_path_validation_failed",
                            "message": (
                                "Model cannot end within a terrain wall, floor, or other "
                                "terrain volume."
                            ),
                            "field": "witness",
                        },
                    ],
                },
            },
        }
    )

    assert len(status.invalid_diagnostics) == 2
    first_diagnostic = status.invalid_diagnostics[0]
    assert first_diagnostic.violation_code == "path_validation_failed"
    assert first_diagnostic.message == "Path witness intersects terrain."
    assert first_diagnostic.field == "witness"
    assert first_diagnostic.proposal_request_id == "decision-request-000019"
    assert first_diagnostic.proposal_kind == "scout_move"
    second_diagnostic = status.invalid_diagnostics[1]
    assert second_diagnostic.violation_code == "terrain_path_validation_failed"


def test_invalid_status_preserves_top_level_reinforcement_violations() -> None:
    status = UiClientStatus.from_payload(
        {
            "stage": "battle",
            "status_kind": "invalid",
            "decision_request": None,
            "message": "Reinforcement placement is invalid.",
            "payload": {
                "request_id": "decision-request-000003",
                "placement_kind": "strategic_reserves",
                "phase_body_status": "reinforcement_placement_invalid",
                "violations": [
                    {
                        "violation_code": "large_model_exception_edge_contact_missing",
                        "message": "Large-model exception requires touching the battlefield edge.",
                        "model_instance_id": "model-1",
                        "blocker_id": None,
                        "battlefield_edge": "south",
                    }
                ],
            },
        }
    )

    assert len(status.invalid_diagnostics) == 1
    diagnostic = status.invalid_diagnostics[0]
    assert diagnostic.violation_code == "large_model_exception_edge_contact_missing"
    assert diagnostic.message == "Large-model exception requires touching the battlefield edge."
    assert diagnostic.proposal_request_id == "decision-request-000003"
    assert diagnostic.proposal_kind == "strategic_reserves"
    assert diagnostic.field is None


def test_invalid_status_without_payload_uses_message_diagnostic() -> None:
    status = UiClientStatus.from_payload(
        {
            "stage": "battle",
            "status_kind": "invalid",
            "decision_request": None,
            "message": "Submitted result is invalid.",
            "payload": None,
        }
    )

    assert len(status.invalid_diagnostics) == 1
    assert status.invalid_diagnostics[0].violation_code == "invalid_status"
    assert status.invalid_diagnostics[0].message == "Submitted result is invalid."


def test_invalid_status_without_payload_or_message_has_malformed_payload_diagnostic() -> None:
    status = UiClientStatus.from_payload(
        {
            "stage": "battle",
            "status_kind": "invalid",
            "decision_request": None,
            "message": None,
            "payload": None,
        }
    )

    assert len(status.invalid_diagnostics) == 1
    diagnostic = status.invalid_diagnostics[0]
    assert diagnostic.violation_code == "malformed_invalid_status_payload"
    assert diagnostic.field == "payload"
    assert diagnostic.message == "Invalid lifecycle status did not include diagnostics."


def test_invalid_status_with_unrecognized_payload_has_malformed_payload_diagnostic() -> None:
    status = UiClientStatus.from_payload(
        {
            "stage": "battle",
            "status_kind": "invalid",
            "decision_request": None,
            "message": None,
            "payload": {"unexpected": "shape"},
        }
    )

    assert status.payload == {"unexpected": "shape"}
    assert len(status.invalid_diagnostics) == 1
    diagnostic = status.invalid_diagnostics[0]
    assert diagnostic.violation_code == "malformed_invalid_status_payload"
    assert diagnostic.field == "payload"
    assert diagnostic.message == "Invalid lifecycle status payload is missing diagnostics."


def test_invalid_status_with_non_object_payload_has_malformed_payload_diagnostic() -> None:
    status = UiClientStatus.from_payload(
        {
            "stage": "battle",
            "status_kind": "invalid",
            "decision_request": None,
            "message": None,
            "payload": ["unexpected", "shape"],
        }
    )

    assert status.payload == ["unexpected", "shape"]
    assert len(status.invalid_diagnostics) == 1
    diagnostic = status.invalid_diagnostics[0]
    assert diagnostic.violation_code == "malformed_invalid_status_payload"
    assert diagnostic.field == "payload"
    assert diagnostic.message == "Invalid lifecycle status payload must be an object."


def test_status_represents_terminal_state() -> None:
    status = UiClientStatus.from_payload(
        {
            "stage": "complete",
            "status_kind": "terminal",
            "decision_request": None,
            "message": "Game complete.",
            "payload": {"winner": "player-a"},
        }
    )

    assert status.status_kind == "terminal"
    assert status.message == "Game complete."
    assert status.payload == {"winner": "player-a"}


def test_game_view_represents_viewer_projection() -> None:
    decision = {
        "request_id": "decision-request-000005",
        "decision_type": "submit_movement_proposal",
        "actor_id": "player-a",
        "payload": {"proposal_request": _movement_proposal_request_payload()},
        "is_parameterized": True,
        "options": [
            {
                "option_id": "submit_parameterized_payload",
                "label": "Submit Parameterized Payload",
                "payload": {"submission_kind": "parameterized"},
            }
        ],
    }
    view = UiGameView.from_payload(
        current_game_view_payload(
            {
                "viewer_player_id": "player-a",
                "game_id": "phase2-game",
                "stage": "battle",
                "battle_round": 1,
                "active_player_id": "player-a",
                "current_setup_step": None,
                "current_battle_phase": "movement",
                "player_ids": ["player-a", "player-b"],
                "battlefield_state": None,
                "mission_setup": None,
                "public_secondary_mission_choices": [],
                "public_secondary_mission_card_states": [],
                "public_command_point_ledgers": [],
                "public_victory_point_ledgers": [],
                "public_stratagem_use_records": [],
                "pending_decision": decision,
                "pending_proposal": None,
            }
        )
    )

    assert view.viewer_player_id == "player-a"
    assert view.pending_decision is not None
    assert view.pending_proposal is not None
    assert view.pending_proposal.request_id == "decision-request-000005"
    assert view.pending_proposal.proposal_kind == "normal_move"
    assert view.unit_display_by_id == {}
    assert view.model_display_by_id == {}


def test_game_view_preserves_optional_display_maps() -> None:
    view = UiGameView.from_payload(
        current_game_view_payload(
            {
                "viewer_player_id": "player-a",
                "game_id": "phase28-game",
                "stage": "setup",
                "battle_round": 1,
                "active_player_id": None,
                "current_setup_step": "deployment",
                "current_battle_phase": None,
                "player_ids": ["player-a", "player-b"],
                "battlefield_state": None,
                "mission_setup": None,
                "public_secondary_mission_choices": [],
                "public_secondary_mission_card_states": [],
                "public_command_point_ledgers": [],
                "public_victory_point_ledgers": [],
                "public_stratagem_use_records": [],
                "pending_decision": None,
                "pending_proposal": None,
                "unit_display_by_id": {
                    "unit-1": {
                        "unit_instance_id": "unit-1",
                        "owner_player_id": "player-a",
                        "unit_display_name": "Battleline Infantry",
                        "keywords": [],
                        "faction_keywords": [],
                        "model_instance_ids": ["model-1", "model-2"],
                    }
                },
                "model_display_by_id": {
                    "model-1": {
                        "model_instance_id": "model-1",
                        "unit_instance_id": "unit-1",
                        "keywords": [],
                        "faction_keywords": [],
                        "keyword_source_ids": [],
                        "base_characteristics": {},
                        "current_characteristics": {},
                    }
                },
            }
        )
    )

    assert view.unit_display_by_id["unit-1"] == {
        "unit_instance_id": "unit-1",
        "owner_player_id": "player-a",
        "unit_display_name": "Battleline Infantry",
        "keywords": [],
        "faction_keywords": [],
        "model_instance_ids": ["model-1", "model-2"],
    }
    assert view.model_display_by_id["model-1"] == {
        "model_instance_id": "model-1",
        "unit_instance_id": "unit-1",
        "keywords": [],
        "faction_keywords": [],
        "keyword_source_ids": [],
        "base_characteristics": {},
        "current_characteristics": {},
    }


def test_game_view_pending_proposal_missing_request_id_fails_fast() -> None:
    nested_proposal = _stratagem_target_proposal_request_payload_with_identity(
        request_id="decision-request-000006",
        actor_id="player-b",
    )

    view_payload = current_game_view_payload(
        {
            "viewer_player_id": "player-a",
            "game_id": "ui-live-smoke-game",
            "stage": "battle",
            "battle_round": 1,
            "active_player_id": "player-a",
            "current_setup_step": None,
            "current_battle_phase": "movement",
            "player_ids": ["player-a", "player-b"],
            "battlefield_state": None,
            "mission_setup": None,
            "public_secondary_mission_choices": [],
            "public_secondary_mission_card_states": [],
            "public_command_point_ledgers": [],
            "public_victory_point_ledgers": [],
            "public_stratagem_use_records": [],
            "pending_decision": {
                "request_id": "decision-request-000006",
                "decision_type": "submit_stratagem_target_proposal",
                "actor_id": "player-b",
                "payload": {
                    "proposal_request": nested_proposal,
                    "declinable": True,
                },
                "options": [
                    {
                        "option_id": "submit_parameterized_payload",
                        "label": "Submit Parameterized Payload",
                        "payload": {"submission_kind": "parameterized"},
                    }
                ],
                "is_parameterized": True,
            },
            "pending_proposal": None,
        }
    )
    pending_proposal = view_payload["pending_proposal"]
    assert type(pending_proposal) is dict
    del pending_proposal["request_id"]

    with pytest.raises(UiClientProtocolError, match="request_id is required"):
        UiGameView.from_payload(view_payload)


def test_fake_core_client_records_explicit_submission_ids() -> None:
    status = UiClientStatus(
        stage="battle",
        status_kind="waiting_for_decision",
        payload=None,
    )
    fake = FakeCoreClient(
        status=status,
        event_delta=UiEventDelta(
            viewer_player_id="player-a",
            cursor=0,
            next_cursor=0,
            events=(),
        ),
    )

    returned = fake.submit_finite(
        request_id="decision-request-000004",
        selected_option_id="normal_move",
        result_id="ui-result-000017",
    )
    fake.submit_movement_payload(
        request_id="decision-request-000005",
        payload={"proposal_request_id": "decision-request-000005"},
        result_id="ui-result-000018",
    )
    fake.submit_parameterized_payload(
        request_id="decision-request-placement-001",
        payload={"proposal_request_id": "decision-request-placement-001"},
        result_id="ui-result-000019",
    )

    assert returned is status
    assert fake.finite_submissions[0].request_id == "decision-request-000004"
    assert fake.finite_submissions[0].selected_option_id == "normal_move"
    assert fake.movement_submissions[0].request_id == "decision-request-000005"
    assert fake.parameterized_submissions[0].request_id == "decision-request-placement-001"


def _movement_proposal_request_payload() -> dict[str, object]:
    return {
        "request_id": "decision-request-000005",
        "decision_type": "submit_movement_proposal",
        "actor_id": "player-a",
        "game_id": "phase2-game",
        "battle_round": 1,
        "phase": "movement",
        "unit_instance_id": "unit-1",
        "proposal_kind": "normal_move",
        "source_decision_request_id": "decision-request-000004",
        "source_decision_result_id": "ui-result-000017",
        "movement_phase_action": "normal_move",
        "placement_kinds": [],
        "spatial_context_hash": "fixture-spatial-context-hash",
        "context": {
            "source_selected_option_id": "normal_move",
            "movement_mode": "normal",
        },
    }


def _scout_move_proposal_request_payload() -> dict[str, object]:
    return {
        "request_id": "decision-request-scout-001",
        "decision_type": "submit_scout_move",
        "actor_id": "player-a",
        "game_id": "phase29-scout-game",
        "setup_step": "resolve_prebattle_actions",
        "player_id": "player-a",
        "unit_instance_id": "unit-1",
        "component_unit_instance_ids": ["unit-1"],
        "model_instance_ids": ["model-1", "model-2"],
        "proposal_kind": "scout_move",
        "action_kind": "scout_move",
        "source_rule_id": "core:scouts",
        "placement_kind": None,
        "scout_distance_inches": 6.0,
        "deployment_zone_ids": ["deployment-zone-a"],
        "legal_deployment_zones": [],
        "mission_setup": {},
        "ruleset_descriptor_hash": "ruleset-phase29",
        "source_decision_request_id": "decision-request-prebattle-001",
        "source_decision_result_id": "ui-result-prebattle-001",
        "context": {"source_selected_option_id": "scout_move:unit-1"},
    }


def _placement_proposal_request_payload() -> dict[str, object]:
    return {
        "request_id": "decision-request-placement-001",
        "decision_type": "submit_placement_proposal",
        "actor_id": "player-a",
        "game_id": "phase28-game",
        "unit_instance_id": "unit-1",
        "proposal_kind": "reinforcement_placement",
        "source_decision_request_id": "decision-request-unit-001",
        "source_decision_result_id": "ui-result-unit-001",
        "battle_round": 1,
        "phase": "movement",
        "movement_phase_action": None,
        "spatial_context_hash": "fixture-spatial-context-hash",
        "placement_kinds": ["reinforcement"],
        "context": {
            "placement_kind": "reinforcement",
            "reserve_state": "strategic_reserves",
        },
    }


def _cult_ambush_marker_request_payload() -> dict[str, object]:
    return {
        "request_id": "decision-request-marker-001",
        "decision_type": "submit_cult_ambush_marker_placement",
        "actor_id": "player-a",
        "source_rule_id": "core:cult-ambush",
        "marker_id": "cult-ambush-marker:001",
        "player_id": "player-a",
        "replacement_unit_instance_id": "army-alpha:replacement-unit",
        "destroyed_unit_instance_id": "army-alpha:destroyed-unit",
        "marker_diameter_inches": 32.0 / 25.4,
        "required_enemy_horizontal_distance_inches": 9.0,
        "source_decision_request_id": "decision-request-resurgence-001",
        "source_decision_result_id": "decision-result-resurgence-001",
    }


def _cult_ambush_marker_interaction_payload() -> dict[str, object]:
    return {
        "schema_version": "interaction-descriptor-v2-variants",
        "interaction_kind": "battlefield_point_placement",
        "submission_kind": "parameterized",
        "proposal_kind": "cult_ambush_marker_placement",
        "selected_entity_ids": [],
        "required_inputs": [],
        "submission_variants": [
            {
                "variant_id": "place_marker",
                "interaction_kind": "battlefield_point_placement",
                "required_inputs": ["battlefield_point"],
                "proposal_schema_ref": (
                    "proposal-payload.schema.json#/$defs/cult_ambush_marker_point"
                ),
                "display_label": "Place Marker",
            },
            {
                "variant_id": "no_marker",
                "interaction_kind": "confirmation",
                "required_inputs": ["no_marker_reason"],
                "proposal_schema_ref": (
                    "proposal-payload.schema.json#/$defs/cult_ambush_no_marker"
                ),
                "display_label": "No Legal Marker Position",
            },
        ],
        "constraints": {
            "candidate_option_ids": ["submit_parameterized_payload"],
            "entity_kinds": ["marker"],
            "minimum_selections": None,
            "maximum_selections": None,
            "maximum_distance_in": None,
            "minimum_enemy_distance_in": 9.0,
            "exact_model_count": None,
            "must_preserve_coherency": None,
            "may_enter_engagement_range": None,
            "placement_kinds": [],
            "submission_schema_ref": "parameterized-submission.schema.json",
            "proposal_schema_ref": (
                "proposal-payload.schema.json#/$defs/cult_ambush_marker_placement"
            ),
        },
        "display_hints": {
            "confirm_label": "Place Point",
            "decline_label": "No Legal Marker Position",
        },
    }


def _stratagem_target_proposal_request_payload() -> dict[str, object]:
    return {
        "proposal_kind": "stratagem_target_binding",
        "catalog_record": {
            "record_id": "gw-11e-core-stratagems:core:fire-overwatch",
            "availability_kind": "core",
            "detachment_id": None,
            "disabled": False,
            "definition": {
                "stratagem_id": "fire-overwatch",
                "name": "Fire Overwatch",
                "handler_id": "core:fire-overwatch",
                "target_descriptor": "one eligible unit from the player's army that can shoot",
            },
        },
        "context": {
            "game_id": "ui-live-smoke-game",
            "player_id": "player-b",
            "active_player_id": "player-a",
            "battle_round": 1,
            "phase": "movement",
            "trigger_kind": "end_phase",
            "timing_window_id": (
                "fire-overwatch-end-movement-round-01-unit-"
                "army-alpha:intercessor-unit-1-player-player-b"
            ),
            "trigger_payload": {
                "moved_unit_instance_id": "army-alpha:intercessor-unit-1",
                "trigger_window": "end_opponent_movement_phase",
            },
        },
        "target_binding": None,
    }


def _stratagem_target_proposal_request_payload_with_identity(
    *,
    request_id: str,
    actor_id: str,
) -> dict[str, object]:
    payload = _stratagem_target_proposal_request_payload()
    payload.update(
        {
            "request_id": request_id,
            "decision_type": "submit_stratagem_target_proposal",
            "actor_id": actor_id,
        }
    )
    return payload


def _stratagem_decision_payload() -> dict[str, object]:
    return {
        "request_id": "decision-request-000009",
        "decision_type": "submit_stratagem_target_proposal",
        "actor_id": "player-a",
        "payload": {
            "proposal_request": {
                "request_id": "decision-request-000009",
                "decision_type": "submit_stratagem_target_proposal",
                "actor_id": "player-a",
                "proposal_kind": "stratagem_target_binding",
                "trigger_window": "after_unit_selected_as_target",
            }
        },
        "is_parameterized": True,
        "options": [
            {
                "option_id": "submit_parameterized_payload",
                "label": "Submit Parameterized Payload",
                "payload": {"submission_kind": "parameterized"},
            }
        ],
    }
