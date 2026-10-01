"""Tests for the opt-in real-core manual smoke startup path."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

import pytest

from warhammer40k_arcade_ui.core_client import live_smoke
from warhammer40k_arcade_ui.core_client.live_smoke import (
    LIVE_CORE_SMOKE_STOP_PHASES,
    LiveCoreSmokeError,
    LiveCoreSmokeStartup,
    LiveCoreSmokeStopPhase,
    build_live_core_smoke_startup,
)
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    JsonValue,
    UiDecision,
    UiFiniteOption,
    UiGameView,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.core_projection import (
    CoreProjectionRenderError,
    battlefield_view_from_game_view,
)
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft
from warhammer40k_arcade_ui.state.selection import SelectionState

pytestmark = pytest.mark.integration


@dataclass(frozen=True, slots=True)
class _CheckpointObservation:
    decision: UiDecision
    game_view: UiGameView
    visible_event_count: int
    decision_record_count: int


type _SmokeTrace = tuple[LiveCoreSmokeStartup, dict[str, _CheckpointObservation]]


@pytest.fixture(scope="module")
def movement_startup() -> LiveCoreSmokeStartup:
    return build_live_core_smoke_startup()


@pytest.fixture
def fresh_movement_startup() -> LiveCoreSmokeStartup:
    return build_live_core_smoke_startup()


@pytest.fixture(scope="module")
def shooting_trace() -> _SmokeTrace:
    """Observe each advertised checkpoint during one public-decision traversal."""

    observed: dict[str, _CheckpointObservation] = {}
    clients: list[LocalSessionClient] = []
    original_checkpoint = live_smoke._is_requested_checkpoint  # pyright: ignore[reportPrivateUsage]

    def make_client() -> LocalSessionClient:
        client = LocalSessionClient()
        clients.append(client)
        return client

    def observe_checkpoint(
        *, stop_phase: LiveCoreSmokeStopPhase, decision: UiDecision, view: UiGameView
    ) -> bool:
        assert clients
        client = clients[0]
        for phase in LIVE_CORE_SMOKE_STOP_PHASES:
            if phase in observed or not original_checkpoint(
                stop_phase=phase, decision=decision, view=view
            ):
                continue
            viewer = decision.actor_id
            assert viewer is not None
            events = client.get_events_since(0, viewer)
            observed[phase] = _CheckpointObservation(
                decision=decision,
                game_view=view,
                visible_event_count=len(events.events),
                decision_record_count=client.session.decision_record_count(),
            )
        return original_checkpoint(stop_phase=stop_phase, decision=decision, view=view)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(live_smoke, "LocalSessionClient", make_client)
        patch.setattr(live_smoke, "_is_requested_checkpoint", observe_checkpoint)
        startup = build_live_core_smoke_startup(stop_at_phase="shooting")
    assert len(clients) == 1
    assert clients[0] is startup.core_client
    return startup, observed


def test_live_core_smoke_startup_reaches_real_movement_unit_selection(
    movement_startup: LiveCoreSmokeStartup,
) -> None:
    startup = movement_startup
    decision = startup.status.decision

    assert decision is not None
    assert decision.decision_type == "select_movement_unit"
    assert decision.actor_id == "player-a"
    assert [option.option_id for option in decision.options] == [
        "army-alpha:deep-strike-unit",
        "army-alpha:scout-redeploy-unit",
        "army-alpha:strategic-reserve-unit",
    ]
    assert startup.viewer_player_id == "player-a"
    assert startup.event_cursor > 0
    assert startup.battlefield_view.table.width == 44.0
    assert startup.battlefield_view.table.height == 60.0
    assert len(startup.battlefield_view.terrain) == 46
    assert {terrain.source_kind for terrain in startup.battlefield_view.terrain} == {
        "terrain_area",
        "terrain_feature",
    }
    assert (
        sum(terrain.source_kind == "terrain_area" for terrain in startup.battlefield_view.terrain)
        == 16
    )
    assert [unit.unit_id for unit in startup.battlefield_view.units] == [
        "army-alpha:deep-strike-unit",
        "army-alpha:scout-redeploy-unit",
        "army-alpha:strategic-reserve-unit",
        "army-beta:scout-redeploy-unit",
    ]
    assert startup.battlefield_view.units[1].models[0].model_id == (
        "army-alpha:scout-redeploy-unit:core-intercessor-like:001"
    )
    monster = next(
        unit
        for unit in startup.battlefield_view.units
        if unit.unit_id == "army-alpha:strategic-reserve-unit"
    )
    assert monster.models[0].position == (18.0, 51.0)


def test_live_core_smoke_observes_deployment_unit_selection(
    shooting_trace: _SmokeTrace,
) -> None:
    _, observed = shooting_trace
    checkpoint = observed["deployment"]
    decision = checkpoint.decision
    game_view = checkpoint.game_view
    battlefield_view = battlefield_view_from_game_view(game_view)

    assert decision is not None
    assert decision.decision_type == "select_deployment_unit"
    assert decision.actor_id == "player-b"
    assert decision.is_parameterized is False
    assert [option.option_id for option in decision.options] == [
        "deploy:army-beta:scout-redeploy-unit",
    ]
    assert [
        _required_object_value(option.payload)["unit_instance_id"] for option in decision.options
    ] == [
        "army-beta:scout-redeploy-unit",
    ]
    assert game_view.viewer_player_id == "player-b"
    assert {
        unit_id
        for unit_id, unit_display in game_view.unit_display_by_id.items()
        if _required_object_value(unit_display).get("owner_player_id") == "player-b"
    } == {"army-beta:scout-redeploy-unit"}
    assert checkpoint.visible_event_count > 0
    assert battlefield_view.table.width == 44.0
    assert battlefield_view.table.height == 60.0
    assert len(battlefield_view.terrain) == 46


def test_live_core_smoke_supports_reachable_setup_prebattle_stop_points(
    shooting_trace: _SmokeTrace,
) -> None:
    _, observed = shooting_trace
    expected_decisions = {
        "setup": ("player-a", "select_secondary_missions"),
        "secondary-missions": ("player-a", "select_secondary_missions"),
        "reserve-declarations": ("player-a", "select_reserve_declaration"),
        "deployment": ("player-b", "select_deployment_unit"),
        "redeploy": ("player-a", "select_redeploy_unit"),
        "prebattle": ("player-a", "select_prebattle_action"),
        "scout-move": ("player-a", "submit_scout_move"),
        "movement": ("player-a", "select_movement_unit"),
        "shooting": ("player-a", "select_shooting_unit"),
    }

    assert set(expected_decisions) == set(LIVE_CORE_SMOKE_STOP_PHASES)
    assert set(observed) == set(expected_decisions)
    for stop_phase, (expected_actor, expected_decision_type) in expected_decisions.items():
        checkpoint = observed[stop_phase]
        decision = checkpoint.decision
        assert decision.actor_id == expected_actor
        assert decision.decision_type == expected_decision_type
        assert checkpoint.game_view.viewer_player_id == expected_actor
        assert checkpoint.game_view.pending_decision is not None
        assert checkpoint.game_view.pending_decision.request_id == decision.request_id
        assert checkpoint.game_view.projection_state_hash
        assert checkpoint.visible_event_count > 0 or stop_phase in {
            "setup",
            "secondary-missions",
        }
    unique_request_ids = tuple(
        observed[phase].decision.request_id
        for phase in LIVE_CORE_SMOKE_STOP_PHASES
        if phase != "secondary-missions"
    )
    assert len(unique_request_ids) == len(set(unique_request_ids))
    record_counts = tuple(
        observed[phase].decision_record_count
        for phase in LIVE_CORE_SMOKE_STOP_PHASES
        if phase != "secondary-missions"
    )
    assert record_counts[0] == 0
    assert all(next_count > count for count, next_count in pairwise(record_counts))


def test_live_core_smoke_reaches_shooting_after_declining_overwatch(
    shooting_trace: _SmokeTrace,
) -> None:
    startup, _ = shooting_trace
    decision = startup.status.decision
    assert decision is not None
    assert decision.decision_type == "select_shooting_unit"
    assert decision.actor_id == "player-a"
    assert startup.game_view.current_battle_phase == "shooting"
    assert startup.viewer_player_id == "player-a"


@pytest.mark.parametrize("phase", ["charge", "fight", "unknown-phase"])
def test_live_core_smoke_rejects_unadvertised_phase_before_session_creation(
    phase: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_client() -> None:
        raise AssertionError("Invalid stop phase started a Core session.")

    monkeypatch.setattr(live_smoke, "LocalSessionClient", unexpected_client)
    with pytest.raises(LiveCoreSmokeError, match="Unsupported live-core smoke stop phase"):
        build_live_core_smoke_startup(stop_at_phase=phase)


def test_live_core_smoke_reports_unknown_finite_family_without_guessing() -> None:
    decision = UiDecision(
        request_id="smoke-unknown-decision",
        decision_type="select_new_setup_action",
        actor_id="player-a",
        payload={},
        options=(UiFiniteOption(option_id="complete_new_action", label="Complete"),),
        is_parameterized=False,
    )
    with pytest.raises(
        LiveCoreSmokeError,
        match="no option policy for 'select_new_setup_action'",
    ):
        live_smoke._automated_option_id(decision)  # pyright: ignore[reportPrivateUsage]


def test_live_core_smoke_uses_real_finite_and_parameterized_movement_path(
    fresh_movement_startup: LiveCoreSmokeStartup,
) -> None:
    startup, proposal_decision, payload_preview = _ready_live_core_normal_move_payload(
        fresh_movement_startup
    )
    witness = _required_object(payload_preview, "witness")
    model_paths = _required_list(witness, "model_paths")
    assert all(
        len(_required_list(_required_object_value(model_path), "poses")) >= 2
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
    assert accepted_status.decision.decision_type in {
        "select_movement_unit",
        "start_mission_action",
    }
    assert "movement_activation_completed" in _event_types(event_delta.events)


def test_live_core_smoke_preserves_canonical_monster_and_surfaces_invalid_advance(
    fresh_movement_startup: LiveCoreSmokeStartup,
) -> None:
    startup = fresh_movement_startup
    unit_decision = startup.status.decision
    assert unit_decision is not None

    action_status = startup.core_client.submit_finite(
        request_id=unit_decision.request_id,
        selected_option_id="army-alpha:strategic-reserve-unit",
        result_id="ui-test-live-smoke-monster-unit",
    )
    action_decision = action_status.decision
    assert action_decision is not None
    assert action_decision.decision_type == "select_movement_action"

    proposal_status = startup.core_client.submit_finite(
        request_id=action_decision.request_id,
        selected_option_id="advance",
        result_id="ui-test-live-smoke-monster-advance",
    )
    proposal_decision = proposal_status.decision
    assert proposal_decision is not None
    assert proposal_decision.decision_type == "submit_movement_proposal"

    monster = next(
        unit
        for unit in startup.battlefield_view.units
        if unit.unit_id == "army-alpha:strategic-reserve-unit"
    )
    model = monster.models[0]
    preferences = default_preferences()
    selection = SelectionState.initial(preferences).select_at(
        view=startup.battlefield_view,
        world_point=model.position,
        preferences=preferences,
    )
    draft = MovementDraft.start_for_pending(
        view=startup.battlefield_view,
        selection=selection,
        pending_decision=proposal_decision,
    )
    assert draft is not None
    ready_draft = (
        draft.select_current_group(view=startup.battlefield_view)
        .add_waypoint(
            view=startup.battlefield_view,
            world_point=(model.position[0] + 2.0, model.position[1]),
        )
        .mark_ready(view=startup.battlefield_view)
    )
    assert ready_draft.payload_preview is not None

    invalid_status = startup.core_client.submit_movement_payload(
        request_id=proposal_decision.request_id,
        payload=ready_draft.payload_preview,
        result_id="ui-test-live-smoke-monster-advance-payload",
    )
    event_delta = startup.core_client.get_events_since(
        startup.event_cursor,
        startup.viewer_player_id,
    )

    assert invalid_status.status_kind == "invalid"
    assert invalid_status.invalid_diagnostics[0].violation_code == (
        "terrain_feature_transit_forbidden"
    )
    assert invalid_status.invalid_diagnostics[0].field == "witness"
    assert "movement_activation_completed" not in _event_types(event_delta.events)


def test_live_core_smoke_handles_endpoint_only_moved_paths(
    fresh_movement_startup: LiveCoreSmokeStartup,
) -> None:
    startup, proposal_decision, payload_preview = _ready_live_core_normal_move_payload(
        fresh_movement_startup
    )
    endpoint_only_payload = _endpoint_only_payload(payload_preview)

    submitted_status = startup.core_client.submit_movement_payload(
        request_id=proposal_decision.request_id,
        payload=endpoint_only_payload,
        result_id="ui-test-live-smoke-submit-endpoint-only-move",
    )

    if submitted_status.status_kind == "invalid":
        payload = _required_object_value(submitted_status.payload)
        proposal_validation = _required_object(payload, "proposal_validation")
        violations = _required_list(proposal_validation, "violations")
        first_violation = _required_object_value(violations[0])

        assert payload["violation_code"] == "endpoint_only_path"
        assert first_violation["violation_code"] == "endpoint_only_path"
        return

    event_delta = startup.core_client.get_events_since(
        startup.event_cursor,
        startup.viewer_player_id,
    )
    assert submitted_status.status_kind == "waiting_for_decision"
    assert submitted_status.decision is not None
    assert submitted_status.decision.decision_type in {
        "select_movement_unit",
        "start_mission_action",
    }
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


def _ready_live_core_normal_move_payload(
    startup: LiveCoreSmokeStartup,
) -> tuple[LiveCoreSmokeStartup, UiDecision, JsonObject]:
    unit_decision = startup.status.decision
    assert unit_decision is not None

    action_status = startup.core_client.submit_finite(
        request_id=unit_decision.request_id,
        selected_option_id="army-alpha:scout-redeploy-unit",
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
    assert proposal_decision.movement_proposal.unit_instance_id == (
        "army-alpha:scout-redeploy-unit"
    )

    unit = next(
        unit
        for unit in startup.battlefield_view.units
        if unit.unit_id == "army-alpha:scout-redeploy-unit"
    )
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
    return startup, proposal_decision, ready_draft.payload_preview


def _endpoint_only_payload(payload: JsonObject) -> JsonObject:
    result = copy.deepcopy(payload)
    witness = _required_object(result, "witness")
    for model_path in _required_list(witness, "model_paths"):
        path = _required_object_value(model_path)
        poses = _required_list(path, "poses")
        if len(poses) == 3 and poses[0] != poses[-1]:
            path["poses"] = [poses[0], poses[-1]]
    for model_movement in _required_list(result, "model_movements"):
        movement = _required_object_value(model_movement)
        poses = _required_list(movement, "path")
        if len(poses) == 3 and poses[0] != poses[-1]:
            movement["path"] = [poses[0], poses[-1]]
            movement["final_pose"] = poses[-1]
    return result


def _event_types(events: tuple[JsonObject, ...]) -> tuple[str, ...]:
    event_types: list[str] = []
    for event in events:
        event_type = event.get("event_type")
        if type(event_type) is str:
            event_types.append(event_type)
    return tuple(event_types)
