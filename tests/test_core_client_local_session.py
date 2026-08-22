"""Tests for the public local core-session facade."""

from __future__ import annotations

import pytest
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.adapters.setup_smoke import canonical_setup_prebattle_smoke_config

from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    UiClientStatus,
    UiClientSubmissionError,
    UiDecision,
)


def test_local_session_submit_finite_rejects_stale_explicit_request_id() -> None:
    client, waiting = _waiting_public_client()
    decision = _required_decision(waiting)

    with pytest.raises(UiClientSubmissionError, match="does not match pending request"):
        client.submit_finite(
            request_id="decision-request-stale",
            selected_option_id=decision.options[0].option_id,
            result_id="ui-result-stale",
        )

    refreshed = client.get_view(_required_actor(decision.actor_id))
    assert refreshed.pending_decision is not None
    assert refreshed.pending_decision.request_id == decision.request_id


def test_local_session_submit_finite_requires_explicit_result_id() -> None:
    client, waiting = _waiting_public_client()
    decision = _required_decision(waiting)

    with pytest.raises(TypeError):
        client.submit_finite(  # type: ignore[call-arg]
            request_id=decision.request_id,
            selected_option_id=decision.options[0].option_id,
        )


def test_local_session_submit_finite_rejects_non_pending_option_id() -> None:
    client, waiting = _waiting_public_client()
    decision = _required_decision(waiting)

    with pytest.raises(UiClientSubmissionError, match="not in the finite action space"):
        client.submit_finite(
            request_id=decision.request_id,
            selected_option_id="invented_option",
            result_id="ui-result-invented",
        )


def test_local_session_parameterized_submission_rejects_finite_request() -> None:
    client, waiting = _waiting_public_client()
    decision = _required_decision(waiting)
    assert decision.is_parameterized is False

    with pytest.raises(UiClientSubmissionError, match="requires a parameterized request"):
        client.submit_parameterized_payload(
            request_id=decision.request_id,
            payload={"proposal_request_id": decision.request_id},
            result_id="ui-result-wrong-kind",
        )


def test_local_session_valid_finite_submission_uses_public_facade() -> None:
    client, waiting = _waiting_public_client()
    decision = _required_decision(waiting)

    submitted = client.submit_finite(
        request_id=decision.request_id,
        selected_option_id=decision.options[0].option_id,
        result_id="ui-result-valid",
    )

    assert submitted.status_kind in {"advanced", "waiting_for_decision"}
    delta = client.get_events_since(0, _required_actor(decision.actor_id))
    assert delta.next_cursor >= delta.cursor


def test_local_session_catalog_is_cached_by_public_identity() -> None:
    client, _waiting = _waiting_public_client()

    first = client.get_rules_catalog()
    second = client.get_rules_catalog()

    assert second is first
    assert first.catalog_id
    assert first.source_hash


def test_local_session_support_profile_is_player_scoped() -> None:
    client, waiting = _waiting_public_client()
    actor_id = _required_actor(_required_decision(waiting).actor_id)

    profile = client.get_support_profile(actor_id)

    assert profile.capability_manifest.viewer_scope == actor_id
    assert profile.capability_manifest.interaction_kinds


def _waiting_public_client() -> tuple[LocalSessionClient, UiClientStatus]:
    client = LocalSessionClient(session=LocalGameSession())
    client.start_game(canonical_setup_prebattle_smoke_config())
    waiting = client.advance_until_decision_or_terminal()
    assert waiting.status_kind == "waiting_for_decision"
    return client, waiting


def _required_decision(status: UiClientStatus) -> UiDecision:
    decision = status.decision
    assert decision is not None
    assert decision.options
    return decision


def _required_actor(actor_id: str | None) -> str:
    assert actor_id is not None
    return actor_id
