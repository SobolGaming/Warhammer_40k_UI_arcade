"""Tests for the opt-in real-core manual smoke startup path."""

from __future__ import annotations

from pathlib import Path

import pytest

from warhammer40k_arcade_ui.core_client import live_smoke
from warhammer40k_arcade_ui.core_client.live_smoke import (
    LiveCoreSmokeError,
    build_live_core_smoke_startup,
)
from warhammer40k_arcade_ui.core_client.protocol import JsonObject, JsonValue
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.core_projection import CoreProjectionRenderError
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft
from warhammer40k_arcade_ui.state.selection import SelectionState


def test_live_core_smoke_startup_reaches_real_movement_unit_selection() -> None:
    startup = build_live_core_smoke_startup()
    decision = startup.status.decision

    assert decision is not None
    assert decision.decision_type == "select_movement_unit"
    assert decision.actor_id == "player-a"
    assert [option.option_id for option in decision.options] == [
        "army-alpha:intercessor-unit-1",
        "army-alpha:intercessor-unit-3",
    ]
    assert startup.viewer_player_id == "player-a"
    assert startup.event_cursor > 0
    assert startup.battlefield_view.table.width == 60.0
    assert startup.battlefield_view.table.height == 44.0
    assert [unit.unit_id for unit in startup.battlefield_view.units] == [
        "army-alpha:intercessor-unit-1",
        "army-alpha:intercessor-unit-3",
        "army-beta:intercessor-unit-2",
        "army-beta:intercessor-unit-4",
    ]
    assert startup.battlefield_view.units[0].models[0].model_id == (
        "army-alpha:intercessor-unit-1:core-intercessor-like:001"
    )


def test_live_core_smoke_uses_real_finite_and_parameterized_movement_path() -> None:
    startup = build_live_core_smoke_startup()
    unit_decision = startup.status.decision
    assert unit_decision is not None

    action_status = startup.core_client.submit_finite(
        request_id=unit_decision.request_id,
        selected_option_id="army-alpha:intercessor-unit-1",
        result_id="ui-test-live-smoke-unit",
    )
    action_decision = action_status.decision
    assert action_decision is not None
    assert action_decision.decision_type == "select_movement_action"
    assert {option.option_id for option in action_decision.options} == {
        "advance",
        "normal_move",
        "remain_stationary",
    }

    proposal_status = startup.core_client.submit_finite(
        request_id=action_decision.request_id,
        selected_option_id="normal_move",
        result_id="ui-test-live-smoke-normal-move",
    )
    proposal_decision = proposal_status.decision

    assert proposal_decision is not None
    assert proposal_decision.decision_type == "submit_movement_proposal"
    assert proposal_decision.is_parameterized is True
    assert proposal_decision.movement_proposal is not None
    assert proposal_decision.movement_proposal.proposal_kind == "normal_move"
    assert proposal_decision.movement_proposal.unit_instance_id == ("army-alpha:intercessor-unit-1")

    unit = startup.battlefield_view.units[0]
    first_model = unit.models[0]
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_at(
        view=startup.battlefield_view,
        world_point=first_model.position,
        preferences=preferences,
    )
    draft = MovementDraft.start_for_pending(
        view=startup.battlefield_view,
        selection=selection,
        pending_decision=proposal_decision,
    )

    assert draft is not None

    anchor_x = sum(model.position[0] for model in unit.models) / len(unit.models)
    anchor_y = sum(model.position[1] for model in unit.models) / len(unit.models)
    ready_draft = (
        draft.select_current_group(view=startup.battlefield_view)
        .add_waypoint(
            view=startup.battlefield_view,
            world_point=(anchor_x + 1.0, anchor_y),
        )
        .mark_ready(view=startup.battlefield_view)
    )

    assert ready_draft.payload_preview is not None
    payload_preview = ready_draft.payload_preview
    witness = _required_object(payload_preview, "witness")
    model_paths = _required_list(witness, "model_paths")
    assert all(
        len(_required_list(_required_object_value(model_path), "poses")) == 3
        for model_path in model_paths
    )

    accepted_status = startup.core_client.submit_movement_payload(
        request_id=proposal_decision.request_id,
        payload=payload_preview,
        result_id="ui-test-live-smoke-submit-move",
    )
    event_delta = startup.core_client.get_events_since(
        startup.event_cursor,
        startup.viewer_player_id,
    )

    assert accepted_status.status_kind == "waiting_for_decision"
    assert accepted_status.decision is not None
    assert accepted_status.decision.decision_type == "select_movement_unit"
    assert [option.option_id for option in accepted_status.decision.options] == [
        "army-alpha:intercessor-unit-3"
    ]
    assert _required_object_value(accepted_status.payload)["legal_unit_count"] == 1
    assert "movement_activation_completed" in _event_types(event_delta.events)


def test_live_core_smoke_surfaces_projection_errors_as_startup_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def bad_projection(view: object) -> object:
        raise CoreProjectionRenderError("projection unavailable")

    monkeypatch.setattr(live_smoke, "battlefield_view_from_game_view", bad_projection)

    with pytest.raises(LiveCoreSmokeError, match="projection unavailable"):
        build_live_core_smoke_startup()


def test_core_imports_remain_isolated_to_core_client_package() -> None:
    source_root = Path(__file__).parents[1] / "src" / "warhammer40k_arcade_ui"
    offenders: list[str] = []
    for path in source_root.rglob("*.py"):
        if "core_client" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "warhammer40k_core" in text:
            offenders.append(str(path.relative_to(source_root)))

    assert offenders == []


def _required_object(payload: JsonObject, key: str) -> JsonObject:
    return _required_object_value(payload[key])


def _required_object_value(value: JsonValue) -> JsonObject:
    if type(value) is not dict:
        raise AssertionError("Expected JSON object.")
    return value


def _required_list(payload: JsonObject, key: str) -> list[JsonValue]:
    value = payload[key]
    if type(value) is not list:
        raise AssertionError("Expected JSON list.")
    return value


def _event_types(events: tuple[JsonObject, ...]) -> tuple[str, ...]:
    event_types: list[str] = []
    for event in events:
        event_type = event.get("event_type")
        if type(event_type) is str:
            event_types.append(event_type)
    return tuple(event_types)
