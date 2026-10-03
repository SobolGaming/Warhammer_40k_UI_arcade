"""Contract 42 request-layout and identity regressions."""

from __future__ import annotations

import copy
import json
from typing import cast

import pytest

from tests.support.core_contract_examples import required_core_example_path
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientProtocolError,
    UiDecision,
    UiParameterizedProposalRequest,
)

_FLAT_TYPES = (
    "submit_cult_ambush_marker_placement",
    "submit_healing_revival_placement",
    "submit_catalog_model_materialization_placement",
    "submit_return_on_death_placement",
)


@pytest.mark.parametrize("decision_type", _FLAT_TYPES)
def test_declared_flat_layout_normalizes_exact_outer_identity(decision_type: str) -> None:
    case = next(
        case
        for case in _interaction_cases()
        if cast(JsonObject, case["request"])["decision_type"] == decision_type
    )
    request = cast(JsonObject, case["request"])
    request_id = cast(str, request["request_id"])
    actor_id = cast(str, request["actor_id"])
    raw_context = cast(JsonObject, request["payload"])
    context: JsonObject = {**raw_context, "source_context": {"origin": "engine"}}

    parsed = UiParameterizedProposalRequest.from_decision_payload(
        payload=context,
        decision_request_id=request_id,
        decision_type=decision_type,
        actor_id=actor_id,
    )

    assert parsed.request_id == request["request_id"]
    assert parsed.decision_type == decision_type
    assert parsed.actor_id == request["actor_id"]
    assert parsed.payload["source_context"] == {"origin": "engine"}
    assert parsed.payload["proposal_kind"] == raw_context["proposal_kind"]

    changes: tuple[JsonObject, ...] = (
        {**context, "request_id": "wrong-request"},
        {**context, "actor_id": "wrong-actor"},
        {**context, "decision_type": "wrong-type"},
        {**context, "proposal_request": {}},
    )
    for changed in changes:
        with pytest.raises(UiClientProtocolError):
            UiParameterizedProposalRequest.from_decision_payload(
                payload=changed,
                decision_request_id=request_id,
                decision_type=decision_type,
                actor_id=actor_id,
            )


def test_nested_layout_requires_identity_and_rejects_flat_substitution() -> None:
    path = required_core_example_path("decisions", "families/submit_movement_proposal.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert type(raw) is dict
    request = cast(JsonObject, raw)
    assert UiDecision.from_payload(request).movement_proposal is not None
    original_payload = cast(JsonObject, request["payload"])
    nested = cast(JsonObject, original_payload["proposal_request"])

    for missing_key in ("request_id", "decision_type", "actor_id"):
        broken = copy.deepcopy(request)
        broken_payload = cast(JsonObject, broken["payload"])
        broken_nested = cast(JsonObject, broken_payload["proposal_request"])
        del broken_nested[missing_key]
        with pytest.raises(UiClientProtocolError, match="requires"):
            UiDecision.from_payload(broken)

    for changed in (
        {**nested, "request_id": "wrong-request"},
        {**nested, "actor_id": "wrong-actor"},
    ):
        broken = copy.deepcopy(request)
        cast(JsonObject, broken["payload"])["proposal_request"] = changed
        with pytest.raises(UiClientProtocolError, match="must match"):
            UiDecision.from_payload(broken)

    flattened = copy.deepcopy(request)
    flattened["payload"] = nested
    with pytest.raises(UiClientProtocolError, match="nested proposal_request"):
        UiDecision.from_payload(flattened)


def _interaction_cases() -> list[JsonObject]:
    path = required_core_example_path("decisions", "interaction-conformance.json")
    inventory = cast(JsonObject, json.loads(path.read_text(encoding="utf-8")))
    cases = inventory["cases"]
    assert type(cases) is list
    assert all(type(case) is dict for case in cases)
    return cast(list[JsonObject], cases)
