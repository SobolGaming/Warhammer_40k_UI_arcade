# pyright: reportPrivateUsage=false
"""Real placement requests preserve opaque army identities from public authority."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest
from warhammer40k_core.adapters.setup_smoke import canonical_setup_prebattle_smoke_config

from tests.test_contract42_split_placement import _split_fixture_config
from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientStatus,
    UiDecision,
    UiGameView,
    UiSupportProfile,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow
from warhammer40k_arcade_ui.render.core_projection import battlefield_view_from_game_view
from warhammer40k_arcade_ui.state.placement_draft import PlacementDraft, PlacementDraftError
from warhammer40k_arcade_ui.state.selection import SelectionState

pytestmark = pytest.mark.integration


def _current(client: LocalSessionClient, status: UiClientStatus) -> UiDecision:
    if status.status_kind == "advanced":
        status = client.advance_until_decision_or_terminal()
    assert status.status_kind == "waiting_for_decision", status
    assert status.decision is not None
    return status.decision


def _draft(
    view: UiGameView,
    *,
    support_profile: UiSupportProfile | None,
    battlefield_state: JsonObject | None = None,
) -> PlacementDraft:
    assert view.pending_decision is not None
    assert view.battlefield_view is not None
    result = PlacementDraft.start_for_pending(
        view=battlefield_view_from_game_view(view),
        selection=SelectionState.initial(default_preferences()),
        pending_decision=view.pending_decision,
        model_display_by_id=view.model_display_by_id,
        authoritative_models_by_id=view.battlefield_view.models_by_id,
        battlefield_state=(
            view.battlefield_state if battlefield_state is None else battlefield_state
        ),
        support_profile=support_profile,
        projection_state_hash=view.projection_state_hash,
    )
    assert result is not None
    return result


def _submit_placement(
    client: LocalSessionClient,
    decision: UiDecision,
    draft: PlacementDraft,
    *,
    result_id: str,
) -> UiClientStatus:
    x, y = (4.0, 51.0) if decision.actor_id == "player-a" else (40.0, 8.0)
    for index in range(draft.total_model_count):
        delta_x = (index // 3) * 1.8
        point_x = x + delta_x if decision.actor_id == "player-a" else x - delta_x
        draft = draft.place_current_model((point_x, y + (index % 3) * 1.8))
    payload = draft.mark_ready().payload_preview
    assert payload is not None
    model_rows = cast(list[JsonObject], payload["model_placements"])
    assert model_rows
    assert all(row["army_id"] == draft.army_id for row in model_rows)
    submitted = client.submit_parameterized_payload(
        request_id=decision.request_id,
        payload=payload,
        result_id=result_id,
    )
    assert submitted.status_kind != "invalid", submitted.invalid_diagnostics
    return submitted


def test_ordinary_deployment_uses_full_public_army_id_and_rejects_conflicts() -> None:
    config = canonical_setup_prebattle_smoke_config()
    config = replace(
        config,
        army_muster_requests=(
            config.army_muster_requests[0],
            replace(config.army_muster_requests[1], army_id="army-beta:custom"),
        ),
    )
    client = LocalSessionClient()
    status = client.start_game(config)
    for index in range(25):
        decision = _current(client, status)
        if decision.decision_type == "submit_deployment_placement":
            break
        assert not decision.is_parameterized
        selected = {
            "select_secondary_missions": "fixed:assassination:bring_it_down",
            "select_reserve_declaration": "complete_reserve_declarations",
        }.get(decision.decision_type, decision.options[0].option_id)
        status = client.submit_finite(
            request_id=decision.request_id,
            selected_option_id=selected,
            result_id=f"opaque-ordinary-setup-{index}",
        )
    else:
        raise AssertionError("Ordinary deployment was not reached.")

    assert decision.actor_id == "player-b"
    view = client.get_view(decision.actor_id)
    profile = client.get_support_profile(decision.actor_id)
    assert view.battlefield_state is not None
    draft = _draft(view, support_profile=profile)
    assert draft.army_id == "army-beta:custom"
    assert draft.is_for(
        pending_decision=view.pending_decision,
        projection_state_hash=view.projection_state_hash,
    )
    with pytest.raises(PlacementDraftError, match="public army"):
        _draft(view, support_profile=None, battlefield_state={"placed_armies": []})
    missing_authority_view = replace(view, battlefield_state={"placed_armies": []})
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=battlefield_view_from_game_view(missing_authority_view),
        preferences=default_preferences(),
        pending_decision=missing_authority_view.pending_decision,
        initial_game_view=missing_authority_view,
        viewer_player_id=decision.actor_id,
    )
    try:
        window._sync_placement_draft()  # pyright: ignore[reportPrivateUsage]
        assert window.placement_draft is None
        assert window.finite_state.status_kind == "invalid"
        assert window.finite_state.diagnostics[0].violation_code == "placement_draft_unavailable"
        assert "public army" in window.finite_state.status_message
    finally:
        window.close()
    with pytest.raises(PlacementDraftError, match="Placed and mustered owner armies differ"):
        _draft(
            view,
            support_profile=profile,
            battlefield_state={
                "placed_armies": [{"player_id": "player-b", "army_id": "other-army"}]
            },
        )
    submitted = _submit_placement(client, decision, draft, result_id="opaque-ordinary-placement")
    assert submitted.status_kind in {"waiting_for_decision", "advanced"}


def test_split_successor_deployment_uses_full_public_army_id_and_split_origin() -> None:
    config = _split_fixture_config()
    old_id = "army-alpha"
    opaque_id = "army-alpha:custom"
    config = replace(
        config,
        army_muster_requests=(
            replace(config.army_muster_requests[0], army_id=opaque_id),
            config.army_muster_requests[1],
        ),
        reserve_unit_points=tuple(
            replace(row, unit_instance_id=opaque_id + row.unit_instance_id[len(old_id) :])
            if row.unit_instance_id.startswith(old_id + ":")
            else row
            for row in config.reserve_unit_points
        ),
    )
    client = LocalSessionClient()
    status = client.start_game(config)
    for index in range(60):
        decision = _current(client, status)
        if decision.is_parameterized:
            assert decision.decision_type == "submit_deployment_placement"
            assert decision.actor_id is not None
            view = client.get_view(decision.actor_id)
            profile = client.get_support_profile(decision.actor_id)
            draft = _draft(view, support_profile=profile)
            if decision.actor_id == "player-a":
                assert ":split:" in draft.selected_unit_id
                assert draft.army_id == opaque_id
                assert any(pose.split_origin for pose in draft.model_poses)
                ready = draft
                for model_index in range(ready.total_model_count):
                    ready = ready.place_current_model(
                        (4.0 + (model_index // 3) * 1.8, 51.0 + (model_index % 3) * 1.8)
                    )
                payload = ready.mark_ready().payload_preview
                assert payload is not None
                rows = cast(list[JsonObject], payload["model_placements"])
                assert rows
                assert all(
                    row["army_id"] == opaque_id
                    and row["unit_instance_id"] == draft.selected_unit_id
                    and "split_origin" in row
                    for row in rows
                )
                accepted = client.submit_parameterized_payload(
                    request_id=decision.request_id,
                    payload=payload,
                    result_id="opaque-split-successor",
                )
                assert accepted.status_kind in {"waiting_for_decision", "advanced"}
                assert not accepted.invalid_diagnostics
                return
            status = _submit_placement(
                client, decision, draft, result_id=f"opaque-split-other-placement-{index}"
            )
            continue
        selected = decision.options[0].option_id
        if decision.decision_type == "select_secondary_missions":
            selected = "fixed:assassination:bring_it_down"
        elif decision.decision_type == "select_reserve_declaration":
            selected = "complete_reserve_declarations"
        elif decision.decision_type == "select_unit_split_membership" and any(
            option.option_id == "split" for option in decision.options
        ):
            selected = "split"
        elif decision.decision_type == "select_deployment_unit" and decision.actor_id == "player-a":
            view = client.get_view("player-a")
            assert view.battlefield_view is not None
            successors = {
                cast(str, cast(JsonObject, row)["unit_instance_id"])
                for row in view.battlefield_view.models_by_id.values()
                if "split_origin" in cast(JsonObject, row)
            }
            selected = next(
                option.option_id
                for option in decision.options
                if type(option.payload) is dict
                and option.payload.get("unit_instance_id") in successors
            )
        status = client.submit_finite(
            request_id=decision.request_id,
            selected_option_id=selected,
            result_id=f"opaque-split-finite-{index}",
        )
    raise AssertionError("Split successor deployment was not reached.")
