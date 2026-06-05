"""Opt-in real-core startup harness for manual movement smoke testing."""

from __future__ import annotations

from dataclasses import dataclass

from warhammer40k_core.core.army_catalog import ArmyCatalog
from warhammer40k_core.core.ruleset_descriptor import RulesetDescriptor
from warhammer40k_core.engine.army_mustering import ArmyMusterRequest
from warhammer40k_core.engine.game_state import GameConfig
from warhammer40k_core.engine.list_validation import (
    DetachmentSelection,
    ModelProfileSelection,
    UnitMusterSelection,
)
from warhammer40k_core.engine.mission_setup import MissionSetup
from warhammer40k_core.rules.mission_pack_import import chapter_approved_2025_26_mission_pack

from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import UiClientStatus, UiGameView
from warhammer40k_arcade_ui.render.core_projection import (
    CoreProjectionRenderError,
    battlefield_view_from_game_view,
)
from warhammer40k_arcade_ui.render.view_models import BattlefieldView

LIVE_CORE_SMOKE_VIEWER_PLAYER_ID = "player-a"
LIVE_CORE_SMOKE_FIXED_SECONDARY_OPTION_ID = "fixed:assassination:bring_it_down"


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
) -> LiveCoreSmokeStartup:
    """Start a real local core session and advance to the first movement-unit choice."""

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
    _assert_expected_pending_decision(status, "select_movement_unit")
    game_view = client.get_view(viewer_player_id)
    event_delta = client.get_events_since(0, viewer_player_id)
    try:
        battlefield_view = battlefield_view_from_game_view(game_view)
    except CoreProjectionRenderError as exc:
        raise LiveCoreSmokeError(str(exc)) from exc
    return LiveCoreSmokeStartup(
        core_client=client,
        status=status,
        game_view=game_view,
        battlefield_view=battlefield_view,
        viewer_player_id=viewer_player_id,
        event_cursor=event_delta.next_cursor,
    )


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
                unit_selection_ids=("intercessor-unit-1",),
            ),
            _army_muster_request(
                catalog=catalog,
                player_id="player-b",
                army_id="army-beta",
                unit_selection_ids=("intercessor-unit-2",),
            ),
        ),
        player_ids=("player-a", "player-b"),
        turn_order=("player-a", "player-b"),
        fixed_secondary_mission_ids=("assassination", "bring_it_down", "cleanse"),
        mission_setup=MissionSetup.from_mission_pack(
            mission_pack=chapter_approved_2025_26_mission_pack(),
            mission_pool_entry_id="mission-a",
            terrain_layout_id="layout-1",
            attacker_player_id="player-a",
            defender_player_id="player-b",
        ),
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
            detachment_id="core-combined-arms",
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
