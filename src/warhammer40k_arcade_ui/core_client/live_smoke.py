"""Opt-in real-core startup harness for manual movement smoke testing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from warhammer40k_core.core.army_catalog import ArmyCatalog
from warhammer40k_core.core.ruleset_descriptor import RulesetDescriptor
from warhammer40k_core.engine.army_mustering import ArmyMusterRequest
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
from warhammer40k_core.engine.game_state import GameConfig
from warhammer40k_core.engine.list_validation import (
    DetachmentSelection,
    ModelProfileSelection,
    UnitMusterSelection,
)
from warhammer40k_core.engine.mission_setup import MissionSetup
from warhammer40k_core.engine.phase import SetupStep
from warhammer40k_core.geometry.pose import Pose
from warhammer40k_core.rules.mission_pack_import import chapter_approved_2026_27_mission_pack

from warhammer40k_arcade_ui.core_client.local_session_client import (
    LocalSessionClient,
    status_from_lifecycle,
)
from warhammer40k_arcade_ui.core_client.protocol import UiClientStatus, UiGameView
from warhammer40k_arcade_ui.render.core_projection import (
    CoreProjectionRenderError,
    battlefield_view_from_game_view,
)
from warhammer40k_arcade_ui.render.view_models import BattlefieldView

LIVE_CORE_SMOKE_VIEWER_PLAYER_ID = "player-a"
LIVE_CORE_SMOKE_FIXED_SECONDARY_OPTION_ID = "fixed:assassination:bring-it-down"
type LiveCoreSmokeStopPhase = Literal["deployment", "movement"]


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
    status = _submit_expected_finite(
        client=client,
        status=status,
        expected_decision_type="select_secondary_missions",
        selected_option_id=LIVE_CORE_SMOKE_FIXED_SECONDARY_OPTION_ID,
        result_id="ui-live-smoke-secondary-player-a",
    )
    status = _submit_expected_finite(
        client=client,
        status=status,
        expected_decision_type="select_secondary_missions",
        selected_option_id=LIVE_CORE_SMOKE_FIXED_SECONDARY_OPTION_ID,
        result_id="ui-live-smoke-secondary-player-b",
    )
    status = _submit_smoke_deployments(client=client, status=status, stop_at_phase=stop_phase)
    expected_decision = (
        SUBMIT_DEPLOYMENT_PLACEMENT_DECISION_TYPE
        if stop_phase == "deployment"
        else "select_movement_unit"
    )
    _assert_expected_pending_decision(status, expected_decision)
    effective_viewer_player_id = _smoke_viewer_player_id(
        status=status,
        stop_phase=stop_phase,
        default_viewer_player_id=viewer_player_id,
    )
    game_view = client.get_view(effective_viewer_player_id)
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
    if stop_phase != "deployment" or status.decision is None:
        return default_viewer_player_id
    return status.decision.actor_id or default_viewer_player_id


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
            if not decision.options:
                raise LiveCoreSmokeError("Expected deployment unit options.")
            current = client.submit_finite(
                request_id=decision.request_id,
                selected_option_id=decision.options[0].option_id,
                result_id=result_id,
            )
            if (
                stop_at_phase == "deployment"
                and current.decision is not None
                and current.decision.decision_type == SUBMIT_DEPLOYMENT_PLACEMENT_DECISION_TYPE
            ):
                return current
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


def _validated_stop_phase(stop_at_phase: str | None) -> LiveCoreSmokeStopPhase:
    if stop_at_phase is None:
        return "movement"
    if stop_at_phase == "deployment":
        return "deployment"
    if stop_at_phase == "movement":
        return "movement"
    raise LiveCoreSmokeError(f"Unsupported live-core smoke stop phase: {stop_at_phase}.")


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
                player_id=request_context.player_id,
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


def _army_id_from_unit_instance_id(unit_instance_id: str) -> str:
    return unit_instance_id.split(":", 1)[0]


def _smoke_deployment_pose(
    *,
    index: int,
    player_id: str,
    unit_instance_id: str,
) -> Pose:
    row = index // 3
    column = index % 3
    base_y = _deployment_base_y_for_unit(unit_instance_id)
    if player_id == "player-b":
        return Pose.at(58.8 - (row * 1.4), base_y + (column * 1.8), 0.0, facing_degrees=180.0)
    return Pose.at(1.2 + (row * 1.4), base_y + (column * 1.8), 0.0, facing_degrees=0.0)


def _deployment_base_y_for_unit(unit_instance_id: str) -> float:
    unit_suffix = unit_instance_id.rsplit("-", 1)[-1]
    if unit_suffix in {"1", "2"}:
        return 7.0
    if unit_suffix in {"3", "4"}:
        return 25.0
    return 16.0


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
    catalog = ArmyCatalog.phase9a_canonical_content_pack()
    return GameConfig(
        game_id="ui-live-smoke-game",
        ruleset_descriptor=RulesetDescriptor.warhammer_40000_eleventh(
            descriptor_version="core-v2-ui-live-smoke-603fb16"
        ),
        army_catalog=catalog,
        army_muster_requests=(
            _army_muster_request(
                catalog=catalog,
                player_id="player-a",
                army_id="army-alpha",
                unit_selection_ids=("intercessor-unit-1", "intercessor-unit-3"),
            ),
            _army_muster_request(
                catalog=catalog,
                player_id="player-b",
                army_id="army-beta",
                unit_selection_ids=("intercessor-unit-2", "intercessor-unit-4"),
            ),
        ),
        player_ids=("player-a", "player-b"),
        turn_order=("player-a", "player-b"),
        fixed_secondary_mission_ids=("assassination", "bring-it-down", "cleanse"),
        mission_setup=MissionSetup.from_mission_pack(
            mission_pack=chapter_approved_2026_27_mission_pack(),
            mission_pool_entry_id="mission-take-and-hold-vs-purge-the-foe-layout-3",
            terrain_layout_id="take-and-hold-vs-purge-the-foe-layout-3",
            attacker_player_id="player-a",
            defender_player_id="player-b",
        ),
        allow_legacy_non_strict_rosters=True,
    )


def _army_muster_request(
    *,
    catalog: ArmyCatalog,
    player_id: str,
    army_id: str,
    unit_selection_ids: tuple[str, ...],
) -> ArmyMusterRequest:
    return ArmyMusterRequest(
        army_id=army_id,
        player_id=player_id,
        catalog_id=catalog.catalog_id,
        source_package_id=catalog.source_package_id,
        ruleset_id=catalog.ruleset_id,
        detachment_selection=DetachmentSelection(
            faction_id="core-marine-force",
            detachment_ids=("core-combined-arms",),
        ),
        unit_selections=tuple(
            UnitMusterSelection(
                unit_selection_id=unit_selection_id,
                datasheet_id="core-intercessor-like-infantry",
                model_profile_selections=(
                    ModelProfileSelection(
                        model_profile_id="core-intercessor-like",
                        model_count=5,
                    ),
                ),
            )
            for unit_selection_id in unit_selection_ids
        ),
    )
