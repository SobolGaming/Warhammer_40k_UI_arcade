"""Tests for opt-in manual validation fixtures."""

from __future__ import annotations

from warhammer40k_arcade_ui.debug_fixtures import (
    phase6_debug_core_client,
    phase6_debug_pending_decision,
)


def test_phase6_debug_fixture_submits_into_parameterized_pending_state() -> None:
    decision = phase6_debug_pending_decision()
    client = phase6_debug_core_client()

    status = client.submit_finite(
        request_id=decision.request_id,
        selected_option_id="normal_move",
        result_id="ui-result-000001",
    )

    assert client.finite_submissions[0].request_id == "decision-request-phase6-debug-000001"
    assert client.finite_submissions[0].selected_option_id == "normal_move"
    assert status.decision is not None
    assert status.decision.is_parameterized is True
    assert status.decision.parameterized_proposal is not None
    assert status.decision.parameterized_proposal.proposal_kind == "normal_move"
