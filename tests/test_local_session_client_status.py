# pyright: reportPrivateUsage=false
"""Actorless startup status diagnostics retain only viewer-safe authority."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest
from warhammer40k_core.adapters.setup_smoke import canonical_setup_prebattle_smoke_config
from warhammer40k_core.engine.event_log import JsonValue
from warhammer40k_core.engine.phase import GameLifecycleStage, LifecycleStatus

from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.state.finite_decision import FiniteDecisionUiState


@pytest.mark.integration
def test_transition_budget_failure_before_first_viewer_has_safe_reason() -> None:
    client = LocalSessionClient()
    config = replace(canonical_setup_prebattle_smoke_config(), max_lifecycle_transitions=1)

    started = client.start_game(config)
    assert started.status_kind == "advanced"
    failed = client.advance_until_decision_or_terminal()

    assert failed.status_kind == "unsupported"
    assert failed.decision is None
    assert failed.payload == {"unsupported_reason": "transition_budget_exhausted"}
    assert failed.message == (
        "Core stopped at its transition safety boundary (transition_budget_exhausted)."
    )
    assert FiniteDecisionUiState.from_status(failed).status_message == failed.message


@pytest.mark.parametrize(
    ("kind", "payload", "expected_message", "expected_payload"),
    [
        (
            "unsupported",
            {"unsupported_reason": "transition_budget_exhausted", "secret": "hidden-model-id"},
            "Core stopped at its transition safety boundary (transition_budget_exhausted).",
            {"unsupported_reason": "transition_budget_exhausted"},
        ),
        (
            "unsupported",
            {"unsupported_reason": "hidden-model-id", "secret": "hidden-model-id"},
            "Core reported an unsupported status before a player view was available.",
            None,
        ),
        (
            "invalid",
            {"violation_code": "hidden-model-id", "secret": "hidden-model-id"},
            "Core reported an invalid status before a player view was available.",
            None,
        ),
    ],
)
def test_actorless_failure_does_not_copy_unredacted_message_or_payload(
    kind: str,
    payload: dict[str, str],
    expected_message: str,
    expected_payload: dict[str, str] | None,
) -> None:
    client = LocalSessionClient()
    if kind == "unsupported":
        core_status = LifecycleStatus.unsupported(
            stage=GameLifecycleStage.SETUP,
            message="Secret unit hidden-model-id is waiting.",
            payload=cast(JsonValue, payload),
        )
    else:
        core_status = LifecycleStatus.invalid(
            stage=GameLifecycleStage.SETUP,
            message="Secret unit hidden-model-id is waiting.",
            payload=cast(JsonValue, payload),
        )

    ui_status = client._status_from_lifecycle(core_status)

    assert ui_status.message == expected_message
    assert ui_status.payload == expected_payload
    assert "hidden-model-id" not in str(ui_status)
