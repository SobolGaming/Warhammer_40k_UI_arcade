"""Real retained Fight and Shooting models stay visible until core removes their pose."""

from __future__ import annotations

import json
from typing import cast

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.engine.damage_allocation import (
    DestructionReactionKind,
    DestructionReactionSource,
)
from warhammer40k_core.engine.lifecycle import GameLifecycle

from tests.support.contract42_battle_fixture import shooting_client
from tests.support.render_capture import capture_window_frame
from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import JsonObject, UiClientStatus
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow
from warhammer40k_arcade_ui.render.core_projection import battlefield_view_from_game_view
from warhammer40k_arcade_ui.render.primitives import PLAYER_2_COLOR
from warhammer40k_arcade_ui.state.assignment_workspace import AssignmentWorkspace
from warhammer40k_arcade_ui.state.finite_decision import FiniteDecisionUiState


@pytest.mark.parametrize(
    "reaction_kind",
    [
        DestructionReactionKind.FIGHT_ON_DEATH,
        DestructionReactionKind.SHOOT_ON_DEATH,
    ],
)
def test_real_retained_model_renders_until_core_removes_pose(
    reaction_kind: DestructionReactionKind,
) -> None:
    client = shooting_client(lethal_attack=True)
    seeded_session = cast(LocalGameSession, client.session)
    state = seeded_session.lifecycle.state
    assert state is not None
    victim = next(
        unit
        for army in state.army_definitions
        if army.player_id == "player-b"
        for unit in army.units
    )
    model_id = victim.own_models[0].model_instance_id
    state.record_model_destruction_reaction_sources(
        model_instance_id=model_id,
        sources=(
            DestructionReactionSource(
                source_id="contract42-retained-source",
                source_rule_id="contract42-retained-source",
                reaction_kind=reaction_kind,
            ),
        ),
    )
    client = LocalSessionClient(
        session=LocalGameSession(
            lifecycle=GameLifecycle.from_payload(seeded_session.lifecycle.to_payload())
        )
    )

    _choose(client, "select_shooting_unit", "army-alpha:shooter", "select-shooter")
    _choose(client, "select_shooting_type", "normal", "select-type")
    shooting = _current(client)
    assert shooting.decision is not None
    assert shooting.decision.decision_type == "submit_shooting_declaration"
    workspace = AssignmentWorkspace.start_for_pending(shooting.decision)
    assert workspace is not None
    assert workspace.is_ready
    assert workspace.payload_preview is not None
    result = client.submit_parameterized_payload(
        request_id=shooting.decision.request_id,
        payload=workspace.payload_preview,
        result_id="lethal-shot",
    )
    assert result.status_kind == "waiting_for_decision", result.invalid_diagnostics
    assert result.decision is not None
    assert result.decision.decision_type == "select_destruction_reaction"
    assert result.decision.actor_id == "player-b"
    assert "contract42-retained-source" in {option.option_id for option in result.decision.options}

    retained_view = client.get_view("player-b")
    assert retained_view.battlefield_view is not None
    model = cast(JsonObject, retained_view.battlefield_view.models_by_id[model_id])
    assert model["state"] == "destroyed"
    assert model["pose"] is not None
    rendered = battlefield_view_from_game_view(retained_view)
    assert any(model.model_id == model_id for unit in rendered.units for model in unit.models)
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=rendered,
        preferences=default_preferences(),
        initial_game_view=retained_view,
        viewer_player_id="player-b",
    )
    try:
        projected = next(
            model for unit in rendered.units for model in unit.models if model.model_id == model_id
        )
        screen_x, screen_y = window.camera.world_to_screen(projected.position)
        region = (round(screen_x) - 8, round(screen_y) - 8, 16, 16)
        frame = capture_window_frame(window, source_name="contract42-retained-real")
        assert frame.close_color_count(PLAYER_2_COLOR, tolerance=0, region=region) > 0

        continuation = client.submit_finite(
            request_id=result.decision.request_id,
            selected_option_id="contract42-retained-source",
            result_id="accept-retained-reaction",
        )
        assert continuation.status_kind != "invalid", continuation.invalid_diagnostics
        if reaction_kind is DestructionReactionKind.SHOOT_ON_DEATH:
            assert continuation.decision is not None
            assert continuation.decision.decision_type == "submit_shooting_declaration"
            retained_workspace = AssignmentWorkspace.start_for_pending(continuation.decision)
            assert retained_workspace is not None
            assert retained_workspace.is_ready
            assert retained_workspace.payload_preview is not None
            declarations = retained_workspace.payload_preview["declarations"]
            assert type(declarations) is list
            assert any(
                type(declaration) is dict and declaration["attacker_model_instance_id"] == model_id
                for declaration in declarations
            )
            continuation = client.submit_parameterized_payload(
                request_id=continuation.decision.request_id,
                payload=retained_workspace.payload_preview,
                result_id="retained-shooting-declaration",
            )
            assert continuation.status_kind != "invalid", continuation.invalid_diagnostics

        removed_view = client.get_view("player-b")
        assert removed_view.battlefield_view is not None
        removed_model = cast(JsonObject, removed_view.battlefield_view.models_by_id[model_id])
        assert removed_model["pose"] is None
        window._apply_refreshed_game_view(  # pyright: ignore[reportPrivateUsage]
            view=removed_view,
            state=FiniteDecisionUiState(),
        )
        removed = capture_window_frame(window, source_name="contract42-retained-removed-real")
        assert removed.close_color_count(PLAYER_2_COLOR, tolerance=0, region=region) == 0
    finally:
        window.close()

    for viewer in ("player-a", "player-b"):
        events = client.get_events_since(0, viewer).events
        selected = next(
            event for event in events if event["event_type"] == "fight_on_death_retention_selected"
        )
        assert cast(JsonObject, selected["payload"])["model_instance_id"] == model_id
        public = json.dumps(events)
        assert '"cause_id"' not in public
        assert '"logical_death_event_id"' not in public
        assert '"retention_sha256"' not in public
        if reaction_kind is DestructionReactionKind.SHOOT_ON_DEATH:
            assert any(
                event["event_type"] == "retained_shooting_attacks_completed" for event in events
            )


def _current(client: LocalSessionClient) -> UiClientStatus:
    return client.advance_until_decision_or_terminal()


def _choose(
    client: LocalSessionClient,
    expected_type: str,
    option_id: str,
    result_id: str,
) -> None:
    status = _current(client)
    assert status.decision is not None
    assert status.decision.decision_type == expected_type
    assert option_id in {option.option_id for option in status.decision.options}
    result = client.submit_finite(
        request_id=status.decision.request_id,
        selected_option_id=option_id,
        result_id=result_id,
    )
    assert result.status_kind != "invalid", result.invalid_diagnostics
