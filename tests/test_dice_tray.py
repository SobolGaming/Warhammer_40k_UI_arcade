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
