"""Contract 41 Damage-to-zero from an exact-build Core-owned checkpoint."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import cast

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.engine.lifecycle import GameLifecycle, GameLifecyclePayload
from warhammer40k_core.rules.rule_ir import RuleIR
from warhammer40k_core.rules.source_packages.warhammer_40000_11th import (
    faction_pack_rule_ir,
)

from warhammer40k_arcade_ui.core_client.compatibility import (
    SUPPORTED_CORE_BUILD_ID,
    SUPPORTED_CORE_REVISION,
    require_supported_core_contract,
)
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientSubmissionError,
)
from warhammer40k_arcade_ui.state.finite_decision import (
    FiniteDecisionUiState,
    submit_finite_option,
)

pytestmark = pytest.mark.integration


def _checkpoint_client() -> tuple[LocalSessionClient, str, str]:
    """Restore Core's source-authenticated in-progress shooting checkpoint."""

    require_supported_core_contract()
    path = Path(__file__).parent / "fixtures/contract42_damage_zero_checkpoint.json.gz"
    fixture = cast(JsonObject, json.loads(gzip.decompress(path.read_bytes())))
    assert fixture["schema_version"] == "contract42-damage-zero-checkpoint-v1"
    assert fixture["core_sha"] == SUPPORTED_CORE_REVISION
    assert fixture["core_build_id"] == SUPPORTED_CORE_BUILD_ID
    assert fixture["source_row_id"] == "000002532:4"
    assert fixture["pending_request_id"] == "decision-request-000013"
    lifecycle = GameLifecycle.from_payload(cast(GameLifecyclePayload, fixture["lifecycle"]))
    return (
        LocalSessionClient(session=LocalGameSession(lifecycle=lifecycle)),
        cast(str, fixture["owner"]),
        cast(str, fixture["opponent"]),
    )


@pytest.mark.parametrize("ignore", [False, True])
def test_real_first_failed_save_damage_zero_preserves_source_and_authority(
    ignore: bool,
) -> None:
    client, owner_id, opponent_id = _checkpoint_client()
    status = client.advance_until_decision_or_terminal()
    assert status.status_kind == "waiting_for_decision"
    decision = status.decision
    assert decision is not None
    assert decision.decision_type == "select_modifier_ignores"
    assert decision.request_id == "decision-request-000013"
    assert decision.actor_id == owner_id == "player-a"
    assert opponent_id == "player-b"
    assert {option.option_id for option in decision.options} == {
        "keep-remaining",
        "ignore-remaining",
    }
    assert type(decision.payload) is dict
    payload = decision.payload
    assert cast(JsonObject, payload["subject"])["kind"] == "damage_characteristic"
    context = cast(JsonObject, payload["source_context"])
    assert context["evaluation_stage"] == "failed-save-damage-replacement"
    operations = cast(list[JsonObject], payload["modifiers"])
    assert len(operations) == 1
    operation = cast(JsonObject, operations[0]["operation"])
    assert operation["operation"] == "set"
    assert operation["operand"] == 0
    source_payload = faction_pack_rule_ir.datasheet_rule_ir_payload_by_source_row_id("000002532:4")
    assert source_payload is not None
    source_rule = RuleIR.from_payload(source_payload)
    assert "000002532:4" in cast(str, operation["source_id"])
    assert source_rule.clauses[0].clause_id in cast(str, operation["source_id"])
    assert "army-beta:enemy" in cast(str, operation["source_id"])
    assert cast(str, operation["modifier_id"]).endswith(":failed-save-damage")
    assert operations[0]["operation_type"] == "characteristic"
    assert json.loads(json.dumps(payload)) == payload

    owner = client.get_view(owner_id)
    opponent = client.get_view(opponent_id)
    assert owner.pending_decision == decision
    assert opponent.pending_decision is not None
    assert opponent.pending_decision.decision_type == "hidden_decision"
    assert not opponent.pending_decision.options
    assert decision.request_id not in json.dumps(opponent.pending_decision.payload)
    assert cast(str, operation["modifier_id"]) not in json.dumps(opponent.pending_decision.payload)
    session = client.session
    assert isinstance(session, LocalGameSession)
    records_before = session.decision_record_count()
    assert records_before == 12
    events_before = client.get_events_since(0, owner_id).events
    opponent_events_before = client.get_events_since(0, opponent_id).events
    assert any(
        event["event_type"] == "attack_sequence_step"
        and type(event["payload"]) is dict
        and event["payload"].get("step") == "save"
        for event in events_before
    )
    assert not any(event["event_type"] == "failed_save_damage_replaced" for event in events_before)

    local_invalid = submit_finite_option(
        state=FiniteDecisionUiState.from_status(status),
        client=client,
        selected_option_id=f"{decision.options[0].option_id}:forged",
        viewer_player_id=owner_id,
    )
    assert local_invalid.finite_state.diagnostics[0].violation_code == (
        "selected_option_not_pending"
    )
    assert session.decision_record_count() == records_before
    assert client.get_view(owner_id).pending_decision == decision
    assert client.get_view(owner_id).projection_state_hash == owner.projection_state_hash
    assert client.get_view(opponent_id).projection_state_hash == opponent.projection_state_hash
    assert client.get_events_since(0, owner_id).events == events_before
    assert client.get_events_since(0, opponent_id).events == opponent_events_before
    with pytest.raises(UiClientSubmissionError):
        client.submit_finite(
            request_id=decision.request_id,
            selected_option_id=f"{decision.options[0].option_id}:forged",
            result_id="damage-zero-fixture:forged",
        )
    assert session.decision_record_count() == records_before
    assert client.get_view(owner_id).pending_decision == decision
    assert client.get_view(owner_id).projection_state_hash == owner.projection_state_hash
    assert client.get_view(opponent_id).projection_state_hash == opponent.projection_state_hash
    assert client.get_events_since(0, owner_id).events == events_before
    assert client.get_events_since(0, opponent_id).events == opponent_events_before
    assert "selected_option_not_pending" not in json.dumps(opponent_events_before)

    option_id = "ignore-remaining" if ignore else "keep-remaining"
    option = next(option for option in decision.options if option.option_id == option_id)
    accepted = submit_finite_option(
        state=FiniteDecisionUiState.from_status(status),
        client=client,
        selected_option_id=option.option_id,
        viewer_player_id=owner_id,
    )
    assert accepted.refreshed_view is not None
    assert accepted.finite_state.status_kind != "invalid"
    assert not accepted.finite_state.diagnostics
    assert session.decision_record_count() == records_before + 1
    next_decision = accepted.finite_state.pending_decision
    assert next_decision is not None
    assert accepted.viewer_player_id == next_decision.actor_id
    assert accepted.refreshed_view.viewer_player_id == next_decision.actor_id
    assert next_decision.request_id == "decision-request-000014"
    extra_option = None
    if ignore:
        # Core resumes the same attack at its ordinary Damage evaluation boundary.
        assert next_decision.decision_type == "select_modifier_ignores"
        assert type(next_decision.payload) is dict
        next_context = cast(JsonObject, next_decision.payload["source_context"])
        assert next_context["evaluation_stage"] == "damage-characteristic"
        assert next_context["attack_context_id"] == context["attack_context_id"]
        extra_option = next(
            option for option in next_decision.options if option.option_id == "keep-remaining"
        )
        completed = submit_finite_option(
            state=accepted.finite_state,
            client=client,
            selected_option_id=extra_option.option_id,
            viewer_player_id=owner_id,
        )
        assert completed.finite_state.status_kind != "invalid"
        assert not completed.finite_state.diagnostics
        assert session.decision_record_count() == records_before + 2
    else:
        assert next_decision.decision_type == "select_damage_allocation_model"

    owner_events = client.get_events_since(0, owner_id).events
    opponent_events = client.get_events_since(0, opponent_id).events
    recorded_results: list[JsonObject] = []
    for event in owner_events:
        if event["event_type"] != "decision_recorded":
            continue
        record = cast(JsonObject, event["payload"])
        result = cast(JsonObject, record["result"])
        if result["request_id"] == decision.request_id:
            recorded_results.append(result)
    assert len(recorded_results) == 1
    assert recorded_results[0]["selected_option_id"] == option.option_id
    assert recorded_results[0]["payload"] == option.payload
    assert recorded_results[0]["result_id"] == "ui-result-000001"
    if ignore:
        assert extra_option is not None
        extra_results = tuple(
            cast(JsonObject, cast(JsonObject, event["payload"])["result"])
            for event in owner_events
            if event["event_type"] == "decision_recorded"
            and cast(JsonObject, cast(JsonObject, event["payload"])["result"])["request_id"]
            == next_decision.request_id
        )
        assert len(extra_results) == 1
        assert extra_results[0]["selected_option_id"] == extra_option.option_id
        assert extra_results[0]["payload"] == extra_option.payload
        assert extra_results[0]["result_id"] == "ui-result-000002"
    assert decision.request_id not in json.dumps(opponent_events)
    assert "modifier_ignores_selected" not in json.dumps(opponent_events)
    assert "failed_save_damage_replacement_ignored" not in json.dumps(opponent_events)
    assert "restore_origin" not in json.dumps(owner_events)
    assert "restore_origin" not in json.dumps(opponent_events)
    damage_steps = tuple(
        event["payload"]
        for event in owner_events
        if event["event_type"] == "attack_sequence_step"
        and type(event["payload"]) is dict
        and event["payload"].get("step") == "damage"
        and event["payload"].get("attack_context_id") == context["attack_context_id"]
    )
    assert len(damage_steps) == 1
    opponent_damage_steps = tuple(
        event["payload"]
        for event in opponent_events
        if event["event_type"] == "attack_sequence_step"
        and type(event["payload"]) is dict
        and event["payload"].get("step") == "damage"
        and event["payload"].get("attack_context_id") == context["attack_context_id"]
    )
    assert opponent_damage_steps == damage_steps
    damage_payload = cast(JsonObject, damage_steps[0]["payload"])
    if ignore:
        application = cast(JsonObject, damage_payload["damage_application"])
        assert application["target_unit_instance_id"] == "army-beta:enemy"
        assert application["requested_damage"] == 1
        assert application["wounds_lost"] == 1
        assert cast(int, application["final_wounds_remaining"]) < cast(
            int, application["starting_wounds_remaining"]
        )
        assert not any(
            event["event_type"] == "failed_save_damage_replaced" for event in owner_events
        )
    else:
        assert damage_payload["damage_application"] is None
        replacements = tuple(
            event for event in owner_events if event["event_type"] == "failed_save_damage_replaced"
        )
        assert len(replacements) == 1
        replacement = cast(JsonObject, replacements[0]["payload"])
        assert replacement["source_id"] == operation["source_id"]
        assert replacement["source_unit_instance_id"] == "army-beta:enemy"
        assert replacement["attack_context_id"] == context["attack_context_id"]
        assert replacement["replacement_damage"] == 0
        assert replacements[0] in opponent_events

    stable = client.get_view(owner_id)
    stable_opponent = client.get_view(opponent_id)
    stable_records = session.decision_record_count()
    stable_events = client.get_events_since(0, owner_id).events
    stable_opponent_events = client.get_events_since(0, opponent_id).events
    with pytest.raises(UiClientSubmissionError):
        client.submit_finite(
            request_id=decision.request_id,
            selected_option_id=option.option_id,
            result_id="damage-zero-fixture:stale",
        )
    assert session.decision_record_count() == stable_records
    assert client.get_view(owner_id).projection_state_hash == stable.projection_state_hash
    assert (
        client.get_view(opponent_id).projection_state_hash == stable_opponent.projection_state_hash
    )
    assert client.get_events_since(0, owner_id).events == stable_events
    assert client.get_events_since(0, opponent_id).events == stable_opponent_events
    refreshed_opponent = client.get_view(opponent_id)
    if refreshed_opponent.pending_decision is not None:
        assert decision.request_id not in json.dumps(refreshed_opponent.pending_decision.payload)
