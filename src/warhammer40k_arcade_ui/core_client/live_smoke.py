"""Opt-in real-core startup harness for manual setup/prebattle/movement smoke testing."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from warhammer40k_core.adapters.setup_smoke import canonical_setup_prebattle_smoke_config
from warhammer40k_core.engine.battlefield_state import BattlefieldPlacementKind, ModelPlacement
from warhammer40k_core.engine.decision_request import (
    PARAMETERIZED_DECISION_OPTION_ID,
    DecisionRequest,
)
from warhammer40k_core.engine.decision_result import DecisionResult
from warhammer40k_core.engine.deployment import (
    SELECT_DEPLOYMENT_UNIT_DECISION_TYPE,
    SUBMIT_DEPLOYMENT_PLACEMENT_DECISION_TYPE,
    DeploymentPlacementProposal,
    DeploymentPlacementRequest,
)
from warhammer40k_core.engine.event_log import validate_json_value
from warhammer40k_core.engine.game_state import GameConfig, GameState
from warhammer40k_core.engine.mission_setup import MissionSetup
from warhammer40k_core.engine.phase import SetupStep
from warhammer40k_core.engine.prebattle import (
    SCOUT_MOVE_PROPOSAL_KIND,
    SELECT_PREBATTLE_ACTION_DECISION_TYPE,
    SELECT_REDEPLOY_UNIT_DECISION_TYPE,
    SUBMIT_REDEPLOY_PLACEMENT_DECISION_TYPE,
    SUBMIT_SCOUT_MOVE_DECISION_TYPE,
    PreBattlePlacementProposal,
    PreBattleProposalRequest,
    ScoutMoveProposal,
)
from warhammer40k_core.engine.reserve_declarations import (
    SELECT_RESERVE_DECLARATION_DECISION_TYPE,
)
from warhammer40k_core.engine.sequencing import SEQUENCING_DECISION_TYPE
from warhammer40k_core.engine.setup_flow import SECONDARY_MISSION_DECISION_TYPE
from warhammer40k_core.geometry.pathing import PathWitness
from warhammer40k_core.geometry.pose import Pose
from warhammer40k_core.rules.mission_pack_import import (
    warhammer_event_companion_2026_06_mission_pack,
)

from warhammer40k_arcade_ui.core_client.local_session_client import (
    LocalSessionClient,
    status_from_lifecycle,
)
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientStatus,
    UiDecision,
    UiGameView,
)
from warhammer40k_arcade_ui.render.core_projection import (
    CoreProjectionRenderError,
    battlefield_view_from_game_view,
)
from warhammer40k_arcade_ui.render.view_models import BattlefieldView

LIVE_CORE_SMOKE_VIEWER_PLAYER_ID = "player-a"
LIVE_CORE_SMOKE_FIXED_SECONDARY_OPTION_ID = "fixed:assassination:bring_it_down"
_LIVE_CORE_SMOKE_MISSION_POOL_ENTRY_ID = "mission-take-and-hold-vs-take-and-hold-layout-3"
_LIVE_CORE_SMOKE_TERRAIN_LAYOUT_ID = "take-and-hold-vs-take-and-hold-layout-3"
type LiveCoreSmokeStopPhase = Literal[
    "setup",
    "secondary-missions",
    "reserve-declarations",
    "deployment",
    "redeploy",
    "prebattle",
    "scout-move",
    "movement",
]
LIVE_CORE_SMOKE_STOP_PHASES: tuple[LiveCoreSmokeStopPhase, ...] = (
    "setup",
    "secondary-missions",
    "reserve-declarations",
    "deployment",
    "redeploy",
    "prebattle",
    "scout-move",
    "movement",
)
type _SmokePlacementRequest = DeploymentPlacementRequest | PreBattleProposalRequest


class LiveCoreSmokeError(ValueError):
    """Raised when the real-core smoke harness cannot reach its expected start state."""


@dataclass(frozen=True, slots=True)
class LiveCoreSmokeStartup:
    """Prepared real-core session state for Arcade launch."""

    core_client: LocalSessionClient
    status: UiClientStatus
    game_view: UiGameView
    battlefield_view: BattlefieldView
    viewer_player_id: str
    event_cursor: int


def build_live_core_smoke_startup(
    *,
    viewer_player_id: str = LIVE_CORE_SMOKE_VIEWER_PLAYER_ID,
    stop_at_phase: str | None = None,
) -> LiveCoreSmokeStartup:
    """Start a real local core session and advance to the requested smoke stop point."""

    stop_phase = _validated_stop_phase(stop_at_phase)
    client = LocalSessionClient()
    client.start_game(_live_core_smoke_config())
    status = client.advance_until_decision_or_terminal()
    if stop_phase in {"setup", "secondary-missions"}:
        _assert_expected_pending_decision(status, SECONDARY_MISSION_DECISION_TYPE)
        return _startup_from_status(
            client=client,
            status=status,
            stop_phase=stop_phase,
            viewer_player_id=viewer_player_id,
        )
    status = _submit_expected_finite(
        client=client,
        status=status,
        expected_decision_type=SECONDARY_MISSION_DECISION_TYPE,
        selected_option_id=LIVE_CORE_SMOKE_FIXED_SECONDARY_OPTION_ID,
        result_id="ui-live-smoke-secondary-player-a",
    )
    status = _submit_expected_finite(
        client=client,
        status=status,
        expected_decision_type=SECONDARY_MISSION_DECISION_TYPE,
        selected_option_id=LIVE_CORE_SMOKE_FIXED_SECONDARY_OPTION_ID,
        result_id="ui-live-smoke-secondary-player-b",
    )
    status = _submit_smoke_reserve_declarations(
        client=client,
        status=status,
        stop_at_phase=stop_phase,
    )
    if stop_phase == "reserve-declarations":
        _assert_expected_pending_decision(status, SELECT_RESERVE_DECLARATION_DECISION_TYPE)
        return _startup_from_status(
            client=client,
            status=status,
            stop_phase=stop_phase,
            viewer_player_id=viewer_player_id,
        )
    status = _submit_smoke_deployments(client=client, status=status, stop_at_phase=stop_phase)
    if stop_phase == "deployment":
        _assert_expected_pending_decision(status, SELECT_DEPLOYMENT_UNIT_DECISION_TYPE)
        return _startup_from_status(
            client=client,
            status=status,
            stop_phase=stop_phase,
            viewer_player_id=viewer_player_id,
        )
    status = _submit_smoke_redeploys(client=client, status=status, stop_at_phase=stop_phase)
    if stop_phase == "redeploy":
        _assert_expected_pending_decision(status, SELECT_REDEPLOY_UNIT_DECISION_TYPE)
        return _startup_from_status(
            client=client,
            status=status,
            stop_phase=stop_phase,
            viewer_player_id=viewer_player_id,
        )
    status = _submit_smoke_prebattle_actions(
        client=client,
        status=status,
        stop_at_phase=stop_phase,
    )
    if stop_phase == "prebattle":
        _assert_expected_pending_decision(status, SELECT_PREBATTLE_ACTION_DECISION_TYPE)
        return _startup_from_status(
            client=client,
            status=status,
            stop_phase=stop_phase,
            viewer_player_id=viewer_player_id,
        )
    expected_decision = (
        SUBMIT_SCOUT_MOVE_DECISION_TYPE if stop_phase == "scout-move" else "select_movement_unit"
    )
    _assert_expected_pending_decision(status, expected_decision)
    return _startup_from_status(
        client=client,
        status=status,
        stop_phase=stop_phase,
        viewer_player_id=viewer_player_id,
    )


def _startup_from_status(
    *,
    client: LocalSessionClient,
    status: UiClientStatus,
    stop_phase: LiveCoreSmokeStopPhase,
    viewer_player_id: str,
) -> LiveCoreSmokeStartup:
    effective_viewer_player_id = _smoke_viewer_player_id(
        status=status,
        stop_phase=stop_phase,
        default_viewer_player_id=viewer_player_id,
    )
    game_view = _with_live_smoke_display_maps(client.get_view(effective_viewer_player_id))
    event_delta = client.get_events_since(0, effective_viewer_player_id)
    try:
        battlefield_view = battlefield_view_from_game_view(game_view)
    except CoreProjectionRenderError as exc:
        raise LiveCoreSmokeError(str(exc)) from exc
    return LiveCoreSmokeStartup(
        core_client=client,
        status=status,
        game_view=game_view,
        battlefield_view=battlefield_view,
        viewer_player_id=effective_viewer_player_id,
        event_cursor=event_delta.next_cursor,
    )


def _smoke_viewer_player_id(
    *,
    status: UiClientStatus,
    stop_phase: LiveCoreSmokeStopPhase,
    default_viewer_player_id: str,
) -> str:
    del stop_phase
    if status.decision is None:
        return default_viewer_player_id
    return status.decision.actor_id or default_viewer_player_id


def _with_live_smoke_display_maps(view: UiGameView) -> UiGameView:
    return replace(
        view,
        unit_display_by_id={
            **_live_smoke_unit_display_by_id(),
            **view.unit_display_by_id,
        },
    )


def _live_smoke_unit_display_by_id() -> JsonObject:
    units: JsonObject = {}
    for player_id, army_id, unit_profiles in (
        (
            "player-a",
            "army-alpha",
            (
                ("scout-redeploy-unit", "core-intercessor-like", 5),
                ("strategic-reserve-unit", "core-vehicle-monster", 1),
                ("deep-strike-unit", "core-deep-strike-model", 3),
            ),
        ),
        (
            "player-b",
            "army-beta",
            (("scout-redeploy-unit", "core-intercessor-like", 5),),
        ),
    ):
        for unit_selection_id, model_profile_id, model_count in unit_profiles:
            unit_instance_id = f"{army_id}:{unit_selection_id}"
            units[unit_instance_id] = {
                "unit_instance_id": unit_instance_id,
                "owner_player_id": player_id,
                "visible_status": "visible",
                "unit_display_name": _live_smoke_unit_display_name(unit_selection_id),
                "model_instance_ids": [
                    f"{unit_instance_id}:{model_profile_id}:{index:03d}"
                    for index in range(1, model_count + 1)
                ],
            }
    return units


def _live_smoke_unit_display_name(unit_selection_id: str) -> str:
    return unit_selection_id.replace("-", " ").title()


def _submit_expected_finite(
    *,
    client: LocalSessionClient,
    status: UiClientStatus,
    expected_decision_type: str,
    selected_option_id: str,
    result_id: str,
) -> UiClientStatus:
    decision = status.decision
    if decision is None:
        raise LiveCoreSmokeError(
            f"Expected {expected_decision_type} before live-core smoke setup choice."
        )
    if decision.decision_type != expected_decision_type:
        raise LiveCoreSmokeError(
            f"Expected {expected_decision_type}, got {decision.decision_type}."
        )
    if selected_option_id not in {option.option_id for option in decision.options}:
        raise LiveCoreSmokeError(
            f"Expected option {selected_option_id} for {expected_decision_type}."
        )
    return client.submit_finite(
        request_id=decision.request_id,
        selected_option_id=selected_option_id,
        result_id=result_id,
    )


def _submit_smoke_deployments(
    *,
    client: LocalSessionClient,
    status: UiClientStatus,
    stop_at_phase: LiveCoreSmokeStopPhase,
) -> UiClientStatus:
    current = status
    result_number = 1
    while current.decision is not None and current.decision.decision_type in {
        SELECT_DEPLOYMENT_UNIT_DECISION_TYPE,
        SUBMIT_DEPLOYMENT_PLACEMENT_DECISION_TYPE,
    }:
        decision = current.decision
        result_id = f"ui-live-smoke-deployment-{result_number:06d}"
        if decision.decision_type == SELECT_DEPLOYMENT_UNIT_DECISION_TYPE:
            if stop_at_phase == "deployment":
                return current
            if not decision.options:
                raise LiveCoreSmokeError("Expected deployment unit options.")
            current = client.submit_finite(
                request_id=decision.request_id,
                selected_option_id=decision.options[0].option_id,
                result_id=result_id,
            )
        else:
            request = _pending_core_request(
                client=client,
                expected_decision_type=SUBMIT_DEPLOYMENT_PLACEMENT_DECISION_TYPE,
            )
            current = _submit_deployment_placement(
                client=client,
                request=request,
                result_id=result_id,
            )
        result_number += 1
    return current


def _submit_smoke_reserve_declarations(
    *,
    client: LocalSessionClient,
    status: UiClientStatus,
    stop_at_phase: LiveCoreSmokeStopPhase,
) -> UiClientStatus:
    if stop_at_phase == "reserve-declarations":
        return status
    return _submit_expected_finite(
        client=client,
        status=status,
        expected_decision_type=SELECT_RESERVE_DECLARATION_DECISION_TYPE,
        selected_option_id="complete_reserve_declarations",
        result_id="ui-live-smoke-reserve-complete",
    )


def _submit_smoke_redeploys(
    *,
    client: LocalSessionClient,
    status: UiClientStatus,
    stop_at_phase: LiveCoreSmokeStopPhase,
) -> UiClientStatus:
    current = _submit_expected_sequencing(
        client=client,
        status=status,
        setup_prefix="prebattle:redeploy_units",
        result_id="ui-live-smoke-redeploy-sequencing",
    )
    if stop_at_phase == "redeploy":
        return current
    current = _submit_expected_finite(
        client=client,
        status=current,
        expected_decision_type=SELECT_REDEPLOY_UNIT_DECISION_TYPE,
        selected_option_id="redeploy:army-beta:scout-redeploy-unit",
        result_id="ui-live-smoke-redeploy-select",
    )
    request = _pending_core_request(
        client=client,
        expected_decision_type=SUBMIT_REDEPLOY_PLACEMENT_DECISION_TYPE,
    )
    return _submit_prebattle_placement(
        client=client,
        request=request,
        result_id="ui-live-smoke-redeploy-place",
    )


def _submit_smoke_prebattle_actions(
    *,
    client: LocalSessionClient,
    status: UiClientStatus,
    stop_at_phase: LiveCoreSmokeStopPhase,
) -> UiClientStatus:
    current = _submit_expected_finite(
        client=client,
        status=status,
        expected_decision_type=SELECT_REDEPLOY_UNIT_DECISION_TYPE,
        selected_option_id="complete_redeploys",
        result_id="ui-live-smoke-redeploy-complete",
    )
    current = _submit_expected_sequencing(
        client=client,
        status=current,
        setup_prefix="prebattle:resolve_prebattle_actions",
        result_id="ui-live-smoke-prebattle-sequencing",
    )
    if stop_at_phase == "prebattle":
        return current
    current = _submit_expected_finite(
        client=client,
        status=current,
        expected_decision_type=SELECT_PREBATTLE_ACTION_DECISION_TYPE,
        selected_option_id="scout_move:army-beta:scout-redeploy-unit",
        result_id="ui-live-smoke-scout-select",
    )
    if stop_at_phase == "scout-move":
        return current
    request = _pending_core_request(
        client=client,
        expected_decision_type=SUBMIT_SCOUT_MOVE_DECISION_TYPE,
    )
    current = _submit_scout_move(
        client=client,
        request=request,
        result_id="ui-live-smoke-scout-submit",
    )
    return _submit_expected_finite(
        client=client,
        status=current,
        expected_decision_type=SELECT_PREBATTLE_ACTION_DECISION_TYPE,
        selected_option_id="complete_prebattle_actions",
        result_id="ui-live-smoke-prebattle-complete",
    )


def _validated_stop_phase(stop_at_phase: str | None) -> LiveCoreSmokeStopPhase:
    if stop_at_phase is None:
        return "movement"
    if stop_at_phase in LIVE_CORE_SMOKE_STOP_PHASES:
        return stop_at_phase
    raise LiveCoreSmokeError(f"Unsupported live-core smoke stop phase: {stop_at_phase}.")


def _submit_expected_sequencing(
    *,
    client: LocalSessionClient,
    status: UiClientStatus,
    setup_prefix: str,
    result_id: str,
) -> UiClientStatus:
    decision = status.decision
    if decision is None:
        raise LiveCoreSmokeError("Expected sequencing decision.")
    if decision.decision_type != SEQUENCING_DECISION_TYPE:
        raise LiveCoreSmokeError(
            f"Expected {SEQUENCING_DECISION_TYPE}, got {decision.decision_type}."
        )
    option_id = _option_with_prefix(decision, f"order:{setup_prefix}:player-b")
    return client.submit_finite(
        request_id=decision.request_id,
        selected_option_id=option_id,
        result_id=result_id,
    )


def _pending_core_request(
    *,
    client: LocalSessionClient,
    expected_decision_type: str,
) -> DecisionRequest:
    pending_requests = client.session.lifecycle.decision_controller.queue.pending_requests
    if len(pending_requests) != 1:
        raise LiveCoreSmokeError("Expected exactly one pending core decision request.")
    request = pending_requests[0]
    if request.decision_type != expected_decision_type:
        raise LiveCoreSmokeError(f"Expected {expected_decision_type}, got {request.decision_type}.")
    return request


def _submit_deployment_placement(
    *,
    client: LocalSessionClient,
    request: DecisionRequest,
    result_id: str,
) -> UiClientStatus:
    proposal = _deployment_proposal_for_request(request)
    payload = validate_json_value(proposal.to_payload())
    return status_from_lifecycle(
        client.session.lifecycle.submit_decision(
            DecisionResult(
                result_id=result_id,
                request_id=request.request_id,
                decision_type=request.decision_type,
                actor_id=request.actor_id,
                selected_option_id=PARAMETERIZED_DECISION_OPTION_ID,
                payload=payload,
            )
        )
    )


def _submit_prebattle_placement(
    *,
    client: LocalSessionClient,
    request: DecisionRequest,
    result_id: str,
) -> UiClientStatus:
    proposal = _prebattle_placement_proposal_for_request(
        state=_state(client),
        request=request,
    )
    payload = validate_json_value(proposal.to_payload())
    return status_from_lifecycle(
        client.session.lifecycle.submit_decision(
            DecisionResult(
                result_id=result_id,
                request_id=request.request_id,
                decision_type=request.decision_type,
                actor_id=request.actor_id,
                selected_option_id=PARAMETERIZED_DECISION_OPTION_ID,
                payload=payload,
            )
        )
    )


def _submit_scout_move(
    *,
    client: LocalSessionClient,
    request: DecisionRequest,
    result_id: str,
) -> UiClientStatus:
    proposal = _scout_move_proposal_for_request(
        state=_state(client),
        request=request,
        dx=-1.0,
    )
    payload = validate_json_value(proposal.to_payload())
    return status_from_lifecycle(
        client.session.lifecycle.submit_decision(
            DecisionResult(
                result_id=result_id,
                request_id=request.request_id,
                decision_type=request.decision_type,
                actor_id=request.actor_id,
                selected_option_id=PARAMETERIZED_DECISION_OPTION_ID,
                payload=payload,
            )
        )
    )


def _deployment_proposal_for_request(request: DecisionRequest) -> DeploymentPlacementProposal:
    request_context = DeploymentPlacementRequest.from_decision_request_payload(request.payload)
    model_placements = tuple(
        ModelPlacement(
            army_id=_army_id_from_unit_instance_id(request_context.unit_instance_id),
            player_id=request_context.player_id,
            unit_instance_id=request_context.unit_instance_id,
            model_instance_id=model_instance_id,
            pose=_smoke_deployment_pose(
                index=index,
                request_context=request_context,
                unit_instance_id=request_context.unit_instance_id,
            ),
        )
        for index, model_instance_id in enumerate(request_context.model_instance_ids)
    )
    return DeploymentPlacementProposal(
        proposal_request_id=request_context.request_id,
        proposal_kind=request_context.proposal_kind,
        game_id=request_context.game_id,
        ruleset_descriptor_hash=request_context.ruleset_descriptor_hash,
        setup_step=SetupStep.DEPLOY_ARMIES,
        player_id=request_context.player_id,
        unit_instance_id=request_context.unit_instance_id,
        placement_kind=BattlefieldPlacementKind.DEPLOYMENT,
        model_placements=model_placements,
        context=request_context.context,
    )


def _prebattle_placement_proposal_for_request(
    *,
    state: GameState,
    request: DecisionRequest,
) -> PreBattlePlacementProposal:
    request_context = PreBattleProposalRequest.from_decision_request_payload(request.payload)
    if request_context.placement_kind is None:
        raise LiveCoreSmokeError("Prebattle placement request requires placement_kind.")
    return PreBattlePlacementProposal(
        proposal_request_id=request_context.request_id,
        proposal_kind=request_context.proposal_kind,
        game_id=request_context.game_id,
        ruleset_descriptor_hash=request_context.ruleset_descriptor_hash,
        setup_step=request_context.setup_step,
        player_id=request_context.player_id,
        unit_instance_id=request_context.unit_instance_id,
        action_kind=request_context.action_kind,
        source_rule_id=request_context.source_rule_id,
        placement_kind=request_context.placement_kind,
        model_placements=tuple(
            ModelPlacement(
                army_id=army_id,
                player_id=player_id,
                unit_instance_id=unit_instance_id,
                model_instance_id=model_instance_id,
                pose=_smoke_redeploy_pose(
                    index=index,
                    request_context=request_context,
                    unit_instance_id=unit_instance_id,
                ),
            )
            for index, model_instance_id in enumerate(request_context.model_instance_ids)
            for army_id, player_id, unit_instance_id in (
                _model_source_for_id(state=state, model_instance_id=model_instance_id),
            )
        ),
        context=request_context.context,
    )


def _scout_move_proposal_for_request(
    *,
    state: GameState,
    request: DecisionRequest,
    dx: float,
) -> ScoutMoveProposal:
    request_context = PreBattleProposalRequest.from_decision_request_payload(request.payload)
    if request_context.scout_distance_inches is None:
        raise LiveCoreSmokeError("Scout move request requires scout_distance_inches.")
    return ScoutMoveProposal(
        proposal_request_id=request_context.request_id,
        proposal_kind=SCOUT_MOVE_PROPOSAL_KIND,
        game_id=request_context.game_id,
        ruleset_descriptor_hash=request_context.ruleset_descriptor_hash,
        setup_step=request_context.setup_step,
        player_id=request_context.player_id,
        unit_instance_id=request_context.unit_instance_id,
        action_kind=request_context.action_kind,
        source_rule_id=request_context.source_rule_id,
        scout_distance_inches=request_context.scout_distance_inches,
        witness=_scout_witness(state=state, request_context=request_context, dx=dx),
        context=request_context.context,
    )


def _army_id_from_unit_instance_id(unit_instance_id: str) -> str:
    return unit_instance_id.split(":", 1)[0]


def _smoke_deployment_pose(
    *,
    index: int,
    request_context: DeploymentPlacementRequest,
    unit_instance_id: str,
) -> Pose:
    row = index // 3
    column = index % 3
    origin_x, origin_y = _deployment_origin_for_unit(
        request_context=request_context,
        unit_instance_id=unit_instance_id,
    )
    x_direction = _deployment_x_direction(request_context)
    facing_degrees = 0.0 if x_direction > 0.0 else 180.0
    return Pose.at(
        origin_x + (row * 1.6 * x_direction),
        origin_y + (column * 1.8),
        0.0,
        facing_degrees=facing_degrees,
    )


def _deployment_origin_for_unit(
    *,
    request_context: _SmokePlacementRequest,
    unit_instance_id: str,
) -> tuple[float, float]:
    min_x, min_y, max_x, max_y = _deployment_zone_bounds(request_context)
    width = max_x - min_x
    margin = min(max(width - 2.0, 1.5), max(_deployment_x_margin_for_unit(unit_instance_id), 1.5))
    x = min_x + margin if _deployment_x_direction(request_context) > 0.0 else max_x - margin
    preferred_y = min_y + _deployment_y_offset_for_unit(unit_instance_id)
    y = min(max(preferred_y, min_y + 2.0), max_y - 2.0)
    return (x, y)


def _deployment_zone_bounds(
    request_context: _SmokePlacementRequest,
) -> tuple[float, float, float, float]:
    min_x = min(zone.min_x for zone in request_context.deployment_zones)
    min_y = min(zone.min_y for zone in request_context.deployment_zones)
    max_x = max(zone.max_x for zone in request_context.deployment_zones)
    max_y = max(zone.max_y for zone in request_context.deployment_zones)
    return (min_x, min_y, max_x, max_y)


def _deployment_x_direction(request_context: _SmokePlacementRequest) -> float:
    min_x, _, max_x, _ = _deployment_zone_bounds(request_context)
    table_mid_x = request_context.mission_setup.battlefield_width_inches / 2.0
    zone_mid_x = (min_x + max_x) / 2.0
    return 1.0 if zone_mid_x <= table_mid_x else -1.0


def _deployment_y_offset_for_unit(unit_instance_id: str) -> float:
    if "deep-strike-unit" in unit_instance_id:
        return 4.0
    if "scout-redeploy-unit" in unit_instance_id:
        return 9.0
    if "strategic-reserve-unit" in unit_instance_id:
        return 9.0
    return 9.0


def _deployment_x_margin_for_unit(unit_instance_id: str) -> float:
    if "strategic-reserve-unit" in unit_instance_id:
        return 11.0
    return 4.0


def _smoke_redeploy_pose(
    *,
    index: int,
    request_context: PreBattleProposalRequest,
    unit_instance_id: str,
) -> Pose:
    row = index // 3
    column = index % 3
    origin_x, origin_y = _deployment_origin_for_unit(
        request_context=request_context,
        unit_instance_id=unit_instance_id,
    )
    x_direction = _deployment_x_direction(request_context)
    return Pose.at(
        origin_x + (row * 1.8 * x_direction),
        origin_y + (column * 1.8),
        0.0,
        facing_degrees=0.0 if x_direction > 0.0 else 180.0,
    )


def _scout_witness(
    *,
    state: GameState,
    request_context: PreBattleProposalRequest,
    dx: float,
) -> PathWitness:
    if state.battlefield_state is None:
        raise LiveCoreSmokeError("Scout move witness requires battlefield state.")
    unit_placement = state.battlefield_state.unit_placement_by_id(request_context.unit_instance_id)
    paths: list[tuple[str, tuple[Pose, ...]]] = []
    for placement in unit_placement.model_placements:
        start = placement.pose
        midpoint = Pose.at(
            start.position.x + (dx / 2.0),
            start.position.y,
            start.position.z,
            facing_degrees=start.facing.degrees,
        )
        end = Pose.at(
            start.position.x + dx,
            start.position.y,
            start.position.z,
            facing_degrees=start.facing.degrees,
        )
        paths.append((placement.model_instance_id, (start, midpoint, end)))
    return PathWitness.for_paths(tuple(paths))


def _model_source_for_id(
    *,
    state: GameState,
    model_instance_id: str,
) -> tuple[str, str, str]:
    for army in state.army_definitions:
        for unit in army.units:
            for model in unit.own_models:
                if model.model_instance_id == model_instance_id:
                    return army.army_id, army.player_id, unit.unit_instance_id
    raise LiveCoreSmokeError(f"Smoke model_instance_id is not mustered: {model_instance_id}.")


def _state(client: LocalSessionClient) -> GameState:
    state = client.session.lifecycle.state
    if state is None:
        raise LiveCoreSmokeError("Live smoke session has no game state.")
    return state


def _option_with_prefix(decision: UiDecision, prefix: str) -> str:
    for option in decision.options:
        if option.option_id.startswith(prefix):
            return option.option_id
    raise LiveCoreSmokeError(f"Expected sequencing option starting with {prefix}.")


def _assert_expected_pending_decision(
    status: UiClientStatus,
    expected_decision_type: str,
) -> None:
    decision = status.decision
    if decision is None:
        raise LiveCoreSmokeError(f"Expected {expected_decision_type}, got no pending decision.")
    if decision.decision_type != expected_decision_type:
        raise LiveCoreSmokeError(
            f"Expected {expected_decision_type}, got {decision.decision_type}."
        )


def _live_core_smoke_config() -> GameConfig:
    config = canonical_setup_prebattle_smoke_config(game_id="ui-live-smoke-game")
    if config.mission_setup is None:
        raise LiveCoreSmokeError("Live core smoke config requires a mission setup.")
    return replace(
        config,
        mission_setup=_with_live_core_smoke_battlefield_geometry(config.mission_setup),
    )


def _with_live_core_smoke_battlefield_geometry(base_setup: MissionSetup) -> MissionSetup:
    geometry_setup = MissionSetup.from_mission_pack(
        mission_pack=warhammer_event_companion_2026_06_mission_pack(),
        mission_pool_entry_id=_LIVE_CORE_SMOKE_MISSION_POOL_ENTRY_ID,
        terrain_layout_id=_LIVE_CORE_SMOKE_TERRAIN_LAYOUT_ID,
        attacker_player_id="player-a",
        defender_player_id="player-b",
    )
    return replace(
        base_setup,
        battlefield_layout_id=geometry_setup.battlefield_layout_id,
        deployment_map_id=geometry_setup.deployment_map_id,
        terrain_layout_id=geometry_setup.terrain_layout_id,
        battlefield_width_inches=geometry_setup.battlefield_width_inches,
        battlefield_depth_inches=geometry_setup.battlefield_depth_inches,
        objective_markers=geometry_setup.objective_markers,
        deployment_zones=geometry_setup.deployment_zones,
        battlefield_regions=geometry_setup.battlefield_regions,
        terrain_areas=geometry_setup.terrain_areas,
        terrain_features=geometry_setup.terrain_features,
        objective_terrain_areas=geometry_setup.objective_terrain_areas,
    )
