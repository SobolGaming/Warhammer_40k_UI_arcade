"""Tests for presentation-only dice tray reduction and runtime data."""

from __future__ import annotations

from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiDecision,
    UiEventDelta,
    UiFiniteOption,
)
from warhammer40k_arcade_ui.hud.dice_tray import (
    build_dice_tray_view,
    dice_tray_runtime_data,
)
from warhammer40k_arcade_ui.state.finite_decision import FiniteDecisionUiState


def test_dice_tray_reduces_generic_dice_rolled_event_into_face_columns() -> None:
    view = build_dice_tray_view(
        event_payloads=(
            {
                "event_type": "dice_rolled",
                "payload": {
                    "roll_id": "roll-hit-000001",
                    "spec": {
                        "roll_type": "hit_roll",
                        "reason": "Bolt rifle attacks",
                        "expression": {"dice_count": 3, "sides": 6},
                    },
                    "values": [1, 1, 5],
                    "total": 7,
                    "source": "CORE",
                },
            },
        ),
        pending_decision=None,
    )

    assert view.active_roll is not None
    assert view.active_roll.roll_id == "roll-hit-000001"
    assert view.active_roll.values == (1, 1, 5)
    assert view.active_roll.total == 7
    assert view.face_columns[0].count == 2
    assert view.face_columns[4].count == 1
    assert view.face_columns[0].asset_id == "dice.aeldari.d6.face_1"


def test_dice_tray_reduces_advance_roll_state_event() -> None:
    view = build_dice_tray_view(
        event_payloads=(
            {
                "event_type": "advance_roll_resolved",
                "payload": {
                    "advance_roll": {
                        "request": {"unit_instance_id": "army-alpha:unit-3"},
                        "value": 4,
                        "roll_state": {
                            "original_result": {
                                "roll_id": "roll-advance-000001",
                                "spec": {
                                    "roll_type": "advance",
                                    "reason": "CORE Intercessor-like Infantry",
                                    "expression": {"dice_count": 1, "sides": 6},
                                },
                                "values": [4],
                                "total": 4,
                                "source": "CORE",
                            },
                            "current_values": [4],
                            "current_total": 4,
                            "rerolls": [],
                        },
                    },
                },
            },
        ),
        pending_decision=None,
    )

    assert view.active_roll is not None
    assert view.active_roll.title == "Advance roll"
    assert view.active_roll.subtitle == "army-alpha:unit-3: +4 in"
    assert view.active_roll.total == 4
    assert view.face_columns[3].count == 1


def test_dice_tray_keeps_physical_reroll_faces_separate_from_assigned_components() -> None:
    view = build_dice_tray_view(
        event_payloads=(
            {
                "event_type": "charge_roll_resolved",
                "payload": {
                    "roll_result": {
                        "roll_state": {
                            "original_result": {
                                "roll_id": "charge-roll-1",
                                "spec": {
                                    "roll_type": "charge",
                                    "reason": "Charge",
                                    "expression": {"quantity": 2, "sides": 6, "modifier": 0},
                                },
                                "values": [2, 5],
                                "total": 7,
                                "source": "fixed",
                            },
                            "current_values": [9, 5],
                            "current_total": 14,
                            "rerolls": [
                                {
                                    "selected_indices": [0],
                                    "replacement_result": {"values": [3]},
                                }
                            ],
                            "result_override": {
                                "decision_id": "set-die-1",
                                "request_id": "set-die-request-1",
                                "source_rule_id": "set-die-rule",
                                "previous_values": [3, 5],
                                "replacement_value": 9,
                                "component_index": 0,
                            },
                        }
                    }
                },
            },
        ),
        pending_decision=None,
    )

    assert view.active_roll is not None
    assert view.active_roll.values == (3, 5)
    assert view.active_roll.assigned_values == (9, 5)
    assert view.active_roll.total == 14
    assert view.active_roll.components[0].value == 3
    assert view.active_roll.components[0].assigned_value == 9
    assert view.active_roll.components[0].rerolled is True
    assert view.face_columns[2].count == 1
    assert view.face_columns[4].count == 1
    assert sum(column.count for column in view.face_columns) == 2
    data = dice_tray_runtime_data(view)
    assert data["values"] == [3, 5]
    assert data["assigned_values"] == [9, 5]
    assert data["result_override"] == view.active_roll.result_override


def test_dice_tray_keeps_aggregate_override_out_of_physical_face_columns() -> None:
    view = build_dice_tray_view(
        event_payloads=(
            {
                "event_type": "dice_roll_resolved",
                "payload": {
                    "roll_state": {
                        "original_result": {
                            "roll_id": "roll-aggregate-1",
                            "spec": {
                                "roll_type": "charge",
                                "reason": "Charge",
                                "expression": {"quantity": 2, "sides": 6, "modifier": 0},
                            },
                            "values": [2, 5],
                            "total": 7,
                            "source": "fixed",
                        },
                        "current_values": [2, 5],
                        "current_total": 11,
                        "rerolls": [],
                        "result_override": {
                            "decision_id": "set-roll-1",
                            "request_id": "set-roll-request-1",
                            "source_rule_id": "set-roll-rule",
                            "previous_values": [2, 5],
                            "replacement_value": 11,
                            "component_index": None,
                        },
                    }
                },
            },
        ),
        pending_decision=None,
    )

    assert view.active_roll is not None
    assert view.active_roll.values == (2, 5)
    assert view.active_roll.assigned_values == (2, 5)
    assert view.active_roll.total == 11
    assert [column.count for column in view.face_columns] == [0, 1, 0, 0, 1, 0]
    assert view.active_roll.result_override is not None
    assert view.active_roll.result_override["component_index"] is None


def test_dice_tray_preserves_core_hit_threshold_and_snap_source_flags() -> None:
    view = build_dice_tray_view(
        event_payloads=(
            {
                "event_type": "attack_hit_resolved",
                "payload": {
                    "hit_roll": {
                        "critical_threshold": 3,
                        "critical_is_threshold": True,
                        "success_requires_exact": True,
                        "threshold_source_ids": ["core:anti-infantry", "core:snap"],
                        "roll_state": {
                            "original_result": {
                                "roll_id": "hit-roll-1",
                                "spec": {
                                    "roll_type": "hit_roll",
                                    "expression": {"quantity": 1, "sides": 6, "modifier": 0},
                                },
                                "values": [3],
                                "total": 3,
                            },
                            "current_values": [3],
                            "current_total": 3,
                            "rerolls": [],
                            "result_override": None,
                        },
                    }
                },
            },
        ),
        pending_decision=None,
    )

    assert view.active_roll is not None
    assert view.active_roll.roll_evidence == {
        "critical_threshold": 3,
        "critical_is_threshold": True,
        "success_requires_exact": True,
        "threshold_source_ids": ["core:anti-infantry", "core:snap"],
    }
    assert dice_tray_runtime_data(view)["roll_evidence"] == view.active_roll.roll_evidence


def test_dice_tray_reports_mismatched_reroll_record_without_inventing_faces() -> None:
    view = build_dice_tray_view(
        event_payloads=(
            {
                "event_type": "dice_roll_resolved",
                "payload": {
                    "roll_state": {
                        "original_result": {
                            "roll_id": "roll-invalid-1",
                            "spec": {
                                "roll_type": "charge",
                                "expression": {"quantity": 2, "sides": 6, "modifier": 0},
                            },
                            "values": [2, 5],
                        },
                        "current_values": [3, 5],
                        "current_total": 8,
                        "rerolls": [
                            {
                                "selected_indices": [0],
                                "replacement_result": {"values": [3, 4]},
                            }
                        ],
                        "result_override": None,
                    }
                },
            },
        ),
        pending_decision=None,
    )

    assert view.active_roll is None
    assert view.diagnostics == ("Dice reroll replacement does not match selected components.",)
    assert all(column.count == 0 for column in view.face_columns)


def test_dice_tray_marks_pending_reroll_selectable_counts_and_options() -> None:
    decision = UiDecision(
        request_id="decision-request-reroll-000001",
        decision_type="select_dice_reroll",
        actor_id="player-a",
        payload={
            "roll_id": "roll-hit-000001",
            "roll_type": "hit_roll",
            "current_values": [1, 1, 5],
            "allowed_selections": [[0], [1], [0, 1]],
        },
        options=(
            UiFiniteOption(option_id="decline", label="Decline", payload={}),
            UiFiniteOption(
                option_id="reroll:0,1",
                label="Reroll both ones",
                payload={"selected_indices": [0, 1]},
            ),
        ),
        is_parameterized=False,
    )

    view = build_dice_tray_view(
        event_payloads=(
            {
                "event_type": "dice_rolled",
                "payload": {
                    "roll_id": "roll-hit-000001",
                    "spec": {
                        "roll_type": "hit_roll",
                        "reason": "Bolt rifle attacks",
                        "expression": {"dice_count": 3, "sides": 6},
                    },
                    "values": [1, 1, 5],
                    "total": 7,
                    "source": "CORE",
                },
            },
        ),
        pending_decision=decision,
    )
    data = dice_tray_runtime_data(view)

    assert view.reroll_request is not None
    assert view.reroll_request.request_id == "decision-request-reroll-000001"
    assert view.face_columns[0].selectable_count == 2
    assert data["reroll_request"] is not None
    reroll_request = data["reroll_request"]
    assert type(reroll_request) is dict
    assert reroll_request["allowed_selections"] == [[0], [1], [0, 1]]
    assert reroll_request["options"] == [
        {
            "option_id": "decline",
            "label": "Decline",
            "selected_indices": [],
            "is_decline": True,
        },
        {
            "option_id": "reroll:0,1",
            "label": "Reroll both ones",
            "selected_indices": [0, 1],
            "is_decline": False,
        },
    ]


def test_pending_reroll_without_visible_roll_does_not_claim_physical_faces() -> None:
    decision = UiDecision(
        request_id="decision-request-reroll-2",
        decision_type="select_dice_reroll",
        actor_id="player-a",
        payload={
            "roll_id": "roll-unseen-1",
            "roll_type": "charge",
            "current_values": [9, 5],
            "allowed_selections": [[0]],
        },
        options=(UiFiniteOption(option_id="decline", label="Decline", payload={}),),
        is_parameterized=False,
    )

    view = build_dice_tray_view(event_payloads=(), pending_decision=decision)

    assert view.active_roll is not None
    assert view.active_roll.values == ()
    assert view.active_roll.assigned_values == (9, 5)
    assert view.active_roll.total is None
    assert view.diagnostics == ("Physical roll faces are unavailable from viewer-visible events.",)
    assert all(column.count == 0 for column in view.face_columns)


def test_finite_state_keeps_bounded_viewer_event_payload_tail() -> None:
    events: tuple[JsonObject, ...] = tuple(
        {"event_type": "dice_rolled", "payload": {"roll_id": f"roll-{index}"}}
        for index in range(52)
    )
    state = FiniteDecisionUiState().apply_event_delta(
        UiEventDelta(
            viewer_player_id="player-a",
            cursor=0,
            next_cursor=52,
            events=events,
        )
    )

    assert len(state.event_payloads) == 48
    assert state.event_payloads[0]["payload"] == {"roll_id": "roll-4"}
    assert state.event_payloads[-1]["payload"] == {"roll_id": "roll-51"}
