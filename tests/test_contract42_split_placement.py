"""Real Contract 42 split ownership and placement through the public session."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.adapters.setup_smoke import canonical_setup_prebattle_smoke_config
from warhammer40k_core.core.datasheet import (
    CatalogAbilitySourceKind,
    CatalogAbilitySupport,
    CatalogJsonObject,
    DatasheetAbilityDescriptor,
)
from warhammer40k_core.engine.decision_request import DecisionRequest
from warhammer40k_core.engine.game_state import GameConfig
from warhammer40k_core.engine.wargear_selections import ModelProfileSelection
from warhammer40k_core.rules.objective_terminology import ObjectiveRuleScope
from warhammer40k_core.rules.rule_compiler import compile_rule_source_text
from warhammer40k_core.rules.source_data import RuleSourceText
from warhammer40k_core.rules.source_packages.warhammer_40000_11th import (
    datasheet_keyword_lexicon_2026_06_14 as keyword_source,
)

from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiGameView,
    invalid_diagnostics_from_status,
    validate_json_value,
)
from warhammer40k_arcade_ui.diagnostics.forensic_trace import (
    ForensicTraceConfig,
    JsonLinesTraceWriter,
)
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow
from warhammer40k_arcade_ui.render.core_projection import battlefield_view_from_game_view
from warhammer40k_arcade_ui.state.finite_decision import FiniteDecisionUiState
from warhammer40k_arcade_ui.state.placement_draft import PlacementDraft
from warhammer40k_arcade_ui.state.selection import SelectionState

pytestmark = pytest.mark.integration


def test_split_successor_origin_and_owner_survive_viewer_switch_and_placement(
    tmp_path: Path,
) -> None:
    session = LocalGameSession()
    session.start(_split_fixture_config())
    status = session.advance_until_decision_or_terminal()
    result_index = 1

    while status.decision_request is not None and status.decision_request.decision_type != (
        "select_unit_split_membership"
    ):
        request = status.decision_request
        option = request.options[0]
        status = session.submit_option(
            request_id=request.request_id,
            option_id=option.option_id,
            result_id=f"split-fixture-{result_index}",
        )
        result_index += 1
    assert status.decision_request is not None
    assert status.decision_request.actor_id == "player-a"
    request = status.decision_request
    assert any(option.option_id == "split" for option in request.options)
    status = session.submit_option(
        request_id=request.request_id,
        option_id="split",
        result_id=f"split-fixture-{result_index}",
    )
    result_index += 1
    owner_pending_view = _view(session, "player-a")
    assert owner_pending_view.pending_decision is not None
    owner_request_id = owner_pending_view.pending_decision.request_id
    for _ in range(10):
        request = cast(DecisionRequest, status.decision_request)
        assert request is not None
        assert request.decision_type == "select_unit_split_membership"
        status = session.submit_option(
            request_id=request.request_id,
            option_id=request.options[0].option_id,
            result_id=f"split-fixture-{result_index}",
        )
        result_index += 1

    view_a = _view(session, "player-a")
    view_b = _view(session, "player-b")
    assert view_a.battlefield_view is not None
    assert view_b.battlefield_view is not None
    split_models = {
        model_id: cast(JsonObject, value)
        for model_id, value in view_a.battlefield_view.models_by_id.items()
        if "split_origin" in cast(JsonObject, value)
    }
    assert split_models
    assert all(
        cast(JsonObject, model["split_origin"])["source_unit_instance_id"]
        == "army-alpha:scout-redeploy-unit"
        for model in split_models.values()
    )
    assert not any(":split:" in key for key in view_b.unit_display_by_id)
    assert not any(
        "split_origin" in cast(JsonObject, value)
        for value in view_b.battlefield_view.models_by_id.values()
    )
    client = LocalSessionClient(session=session.fork())
    assert client.get_view("player-a").viewer_player_id == "player-a"
    assert client.get_view("player-b").viewer_player_id == "player-b"
    assert client.get_view("player-a").viewer_player_id == "player-a"
    opponent_events = client.get_events_since(0, "player-b")
    assert not any(event["event_type"] == "unit_split_applied" for event in opponent_events.events)
    assert "army-alpha:scout-redeploy-unit:split:" not in json.dumps(opponent_events.events)
    opponent_request = cast(DecisionRequest, status.decision_request)
    assert opponent_request.actor_id == "player-b"
    opponent_status = client.submit_finite(
        request_id=opponent_request.request_id,
        selected_option_id=opponent_request.options[0].option_id,
        result_id="split-opponent-status-probe",
    )
    assert "army-alpha:scout-redeploy-unit:split:" not in json.dumps(opponent_status.payload)

    trace_path = tmp_path / "viewer-transition.jsonl"
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=battlefield_view_from_game_view(owner_pending_view),
        preferences=default_preferences(),
        pending_decision=owner_pending_view.pending_decision,
        initial_game_view=owner_pending_view,
        viewer_player_id="player-a",
        trace_writer=JsonLinesTraceWriter(
            ForensicTraceConfig(level="summary", trace_path=trace_path)
        ),
    )
    try:
        assert window._trace_context().request_id == owner_request_id  # pyright: ignore[reportPrivateUsage]
        window._selection_state = window.selection_state.select_model_id(  # pyright: ignore[reportPrivateUsage]
            unit_id="army-alpha:scout-redeploy-unit",
            model_id=None,
            preferences=default_preferences(),
        )
        initial_selection = window.selection_state
        assert initial_selection.selected_unit_id == "army-alpha:scout-redeploy-unit"
        window._apply_refreshed_game_view(  # pyright: ignore[reportPrivateUsage]
            view=view_b,
            state=FiniteDecisionUiState(pending_decision=view_b.pending_decision),
        )
        opponent_selection = window.selection_state
        assert opponent_selection.selected_unit_id is None
        assert window._hud_selected_unit_id() != "army-alpha:scout-redeploy-unit"  # pyright: ignore[reportPrivateUsage]
        assert not any(":split:" in key for key in window._known_unit_display_by_id)  # pyright: ignore[reportPrivateUsage]
        context = window._trace_context()  # pyright: ignore[reportPrivateUsage]
        assert context.viewer_player_id == "player-b"
        assert context.request_id != owner_request_id
        assert context.request_id == (
            None if view_b.pending_decision is None else view_b.pending_decision.request_id
        )
        trace_rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
        refreshed = [
            row
            for row in trace_rows
            if row.get("event_name") == "ui.projection_refreshed"
            and row.get("viewer_player_id") == "player-b"
        ]
        assert refreshed
        assert refreshed[-1].get("request_id") != owner_request_id
        window._apply_refreshed_game_view(  # pyright: ignore[reportPrivateUsage]
            view=view_a,
            state=FiniteDecisionUiState(pending_decision=view_a.pending_decision),
        )
        assert any(":split:" in key for key in window._known_unit_display_by_id)  # pyright: ignore[reportPrivateUsage]
    finally:
        window.close()

    for _ in range(20):
        request = cast(DecisionRequest, status.decision_request)
        assert request is not None
        if request.decision_type == "submit_deployment_placement":
            current_view = _view(session, cast(str, request.actor_id))
            draft = _placed_draft(current_view)
            assert current_view.pending_decision is not None
            assert current_view.pending_decision.placement_proposal is not None
            assert draft.selected_unit_id == (
                current_view.pending_decision.placement_proposal.unit_instance_id
            )
            payload = draft.to_payload()
            if ":split:" in draft.selected_unit_id:
                placements = cast(list[JsonObject], payload["model_placements"])
                assert all("split_origin" in placement for placement in placements)
                assert all(
                    placement["unit_instance_id"] == draft.selected_unit_id
                    and placement["player_id"] == "player-a"
                    for placement in placements
                )
                before = _view(session, "player-a").projection_state_hash
                records = session.decision_record_count()
                invalid_payload = copy.deepcopy(payload)
                cast(list[JsonObject], invalid_payload["model_placements"])[0].pop("split_origin")
                invalid = session.submit_parameterized_payload(
                    request_id=request.request_id,
                    payload=invalid_payload,
                    result_id=f"split-fixture-invalid-{result_index}",
                )
                assert invalid.status_kind.value == "invalid"
                diagnostics = invalid_diagnostics_from_status(
                    status_kind=invalid.status_kind.value,
                    message=invalid.message,
                    payload=validate_json_value(invalid.payload),
                )
                assert diagnostics
                assert all(
                    diagnostic.violation_code != "invalid_status" for diagnostic in diagnostics
                )
                assert session.decision_record_count() == records
                assert _view(session, "player-a").projection_state_hash == before
                accepted = session.submit_parameterized_payload(
                    request_id=request.request_id,
                    payload=payload,
                    result_id=f"split-fixture-valid-{result_index}",
                )
                assert accepted.status_kind.value != "invalid", accepted.payload
                assert session.decision_record_count() == records + 1
                return
            status = session.submit_parameterized_payload(
                request_id=request.request_id,
                payload=payload,
                result_id=f"split-fixture-{result_index}",
            )
        else:
            option = next(
                (option for option in request.options if ":split:" in option.option_id),
                request.options[0],
            )
            status = session.submit_option(
                request_id=request.request_id,
                option_id=option.option_id,
                result_id=f"split-fixture-{result_index}",
            )
        result_index += 1
    raise AssertionError("Split successor deployment was not reached.")


def _placed_draft(view: UiGameView) -> PlacementDraft:
    assert view.pending_decision is not None
    assert view.battlefield_view is not None
    draft = PlacementDraft.start_for_pending(
        view=battlefield_view_from_game_view(view),
        selection=SelectionState.initial(default_preferences()),
        pending_decision=view.pending_decision,
        model_display_by_id=view.model_display_by_id,
        authoritative_models_by_id=view.battlefield_view.models_by_id,
        projection_state_hash=view.projection_state_hash,
    )
    assert draft is not None
    x = 40.0 if draft.player_id == "player-b" else 4.0
    y = 8.0 if draft.player_id == "player-b" else 51.0
    for index in range(draft.total_model_count):
        draft = draft.place_current_model((x + (index // 3) * 1.8, y + (index % 3) * 1.8))
    return draft


def _view(session: LocalGameSession, player_id: str) -> UiGameView:
    return UiGameView.from_payload(session.view(viewer_player_id=player_id))


def _split_fixture_config() -> GameConfig:
    source_id = "test-source:tactical-squad:combat-squads"
    source_text = (
        "At the start of the Declare Battle Formations step, before any units have been set up, "
        "this unit can be split into two units, each containing five models."
    )
    rule = compile_rule_source_text(
        RuleSourceText.from_raw(
            source_id=source_id,
            raw_text=source_text,
            objective_scope=ObjectiveRuleScope.NON_CORE_RULES,
        ),
        source_keyword_sequence_parts=keyword_source.canonical_datasheet_keyword_sequence_parts(),
    ).rule_ir
    ability = DatasheetAbilityDescriptor(
        ability_id="test-combat-squads",
        name="Combat Squads",
        source_id=source_id,
        support=CatalogAbilitySupport.GENERIC_RULE_IR,
        source_kind=CatalogAbilitySourceKind.DATASHEET,
        effect_description=source_text,
        rule_ir_payload=cast(CatalogJsonObject, rule.to_payload()),
    )
    config = canonical_setup_prebattle_smoke_config()
    catalog = replace(
        config.army_catalog,
        datasheets=tuple(
            replace(datasheet, abilities=(*datasheet.abilities, ability))
            if datasheet.datasheet_id == "core-intercessor-like-infantry"
            else datasheet
            for datasheet in config.army_catalog.datasheets
        ),
    )
    musters = tuple(
        replace(
            muster,
            unit_selections=tuple(
                replace(
                    unit,
                    model_profile_selections=(
                        ModelProfileSelection(
                            model_profile_id="core-intercessor-like", model_count=10
                        ),
                    ),
                )
                if (
                    muster.player_id == "player-a"
                    and unit.unit_selection_id == "scout-redeploy-unit"
                )
                else unit
                for unit in muster.unit_selections
            ),
        )
        for muster in config.army_muster_requests
    )
    return replace(config, army_catalog=catalog, army_muster_requests=musters)
