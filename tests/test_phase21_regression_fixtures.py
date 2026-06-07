"""Phase 21 golden fixture coverage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientStatus,
    UiDecision,
    UiParameterizedProposalRequest,
    validate_json_value,
)
from warhammer40k_arcade_ui.preferences.io import load_preferences

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "phase21_regression_suite.json"
INVALID_PREFERENCES_PATH = Path(__file__).parent / "fixtures" / "invalid_ui_preferences.yaml"
DEFAULT_PREFERENCES_PATH = Path(__file__).parents[1] / "docs" / "preferences" / "default.yaml"


def test_phase21_regression_fixture_sections_are_json_safe_and_parseable() -> None:
    fixture = _fixture()

    validate_json_value(fixture)
    for name, decision_payload in _object_section(fixture, "decision_requests").items():
        decision = UiDecision.from_payload(decision_payload)
        assert decision.request_id == _required_str(decision_payload, "request_id"), name
        assert decision.decision_type == _required_str(decision_payload, "decision_type"), name
        assert decision.actor_id == _required_str(decision_payload, "actor_id"), name

    for name, proposal_payload in _object_section(fixture, "pending_proposals").items():
        proposal = UiParameterizedProposalRequest.from_payload(proposal_payload)
        assert proposal.request_id == _required_str(proposal_payload, "request_id"), name
        assert proposal.decision_type == _required_str(proposal_payload, "decision_type"), name
        assert proposal.actor_id == _required_str(proposal_payload, "actor_id"), name

    for name, status_payload in _object_section(fixture, "client_statuses").items():
        status = UiClientStatus.from_payload(status_payload)
        assert status.stage == "battle", name


def test_phase21_regression_fixture_covers_required_request_families() -> None:
    fixture = _fixture()

    assert set(_object_section(fixture, "decision_requests")) == {
        "finite_movement_options",
        "finite_fight_activation",
        "finite_fight_interrupt",
        "complete_reinforcements",
        "complete_disembarks",
        "complete_shooting_phase",
        "complete_charge_phase",
    }
    assert set(_object_section(fixture, "pending_proposals")) == {
        "normal_move",
        "fall_back",
        "charge_move",
        "pile_in",
        "consolidate",
        "melee_declaration",
        "stratagem_target_binding",
        "shooting_declaration",
    }
    assert set(_object_section(fixture, "client_statuses")) == {
        "accepted_movement_response",
        "invalid_movement_response",
    }


def test_phase21_preference_fixtures_include_default_and_invalid_profiles() -> None:
    default_result = load_preferences(DEFAULT_PREFERENCES_PATH)
    invalid_result = load_preferences(INVALID_PREFERENCES_PATH)

    assert default_result.preferences is not None
    assert default_result.diagnostics == ()
    assert invalid_result.preferences is not None
    assert {
        "unknown_command_id",
        "invalid_key_syntax",
        "invalid_modifier",
        "unknown_overlay_id",
        "invalid_hud_layout_preset",
    }.issubset({diagnostic.code for diagnostic in invalid_result.diagnostics})


def _fixture() -> JsonObject:
    payload: object = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if type(payload) is not dict:
        raise AssertionError("Phase 21 fixture must be a JSON object.")
    return cast(JsonObject, payload)


def _object_section(payload: JsonObject, key: str) -> dict[str, JsonObject]:
    section = payload[key]
    if type(section) is not dict:
        raise AssertionError(f"{key} must be an object.")
    return cast(dict[str, JsonObject], section)


def _required_str(payload: JsonObject, key: str) -> str:
    value = payload[key]
    if type(value) is not str:
        raise AssertionError(f"{key} must be a string.")
    return value
