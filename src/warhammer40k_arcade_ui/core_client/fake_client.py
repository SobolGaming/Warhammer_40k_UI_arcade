"""Fake UI core client for deterministic UI tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from warhammer40k_arcade_ui.core_client.protocol import (
    JsonValue,
    UiClientStatus,
    UiEventDelta,
    UiGameView,
)


@dataclass(frozen=True, slots=True)
class SubmittedFiniteDecision:
    """Finite submission recorded by `FakeCoreClient`."""

    request_id: str
    selected_option_id: str
    result_id: str


@dataclass(frozen=True, slots=True)
class SubmittedMovementPayload:
    """Movement payload submission recorded by `FakeCoreClient`."""

    request_id: str
    payload: JsonValue
    result_id: str


def _new_finite_submissions() -> list[SubmittedFiniteDecision]:
    return []


def _new_movement_submissions() -> list[SubmittedMovementPayload]:
    return []


@dataclass(slots=True)
class FakeCoreClient:
    """Scriptable fake for UI modules that should not launch a real game."""

    status: UiClientStatus
    view: UiGameView | None = None
    event_delta: UiEventDelta | None = None
    finite_submissions: list[SubmittedFiniteDecision] = field(
        default_factory=_new_finite_submissions
    )
    movement_submissions: list[SubmittedMovementPayload] = field(
        default_factory=_new_movement_submissions
    )
    advance_call_count: int = 0
    movement_status: UiClientStatus | None = None
    movement_view: UiGameView | None = None
    movement_event_delta: UiEventDelta | None = None
    movement_view_from_payload: Callable[[JsonValue], UiGameView] | None = None

    def start_game(self, config: object) -> UiClientStatus:
        return self.status

    def advance_until_decision_or_terminal(self) -> UiClientStatus:
        self.advance_call_count += 1
        return self.status

    def get_view(self, viewer_player_id: str) -> UiGameView:
        if self.view is None:
            raise ValueError("FakeCoreClient view is not configured.")
        return self.view

    def get_events_since(self, cursor: int, viewer_player_id: str) -> UiEventDelta:
        if self.event_delta is None:
            raise ValueError("FakeCoreClient event_delta is not configured.")
        return self.event_delta

    def submit_finite(
        self,
        *,
        request_id: str,
        selected_option_id: str,
        result_id: str,
    ) -> UiClientStatus:
        self.finite_submissions.append(
            SubmittedFiniteDecision(
                request_id=request_id,
                selected_option_id=selected_option_id,
                result_id=result_id,
            )
        )
        return self.status

    def submit_movement_payload(
        self,
        *,
        request_id: str,
        payload: JsonValue,
        result_id: str,
    ) -> UiClientStatus:
        self.movement_submissions.append(
            SubmittedMovementPayload(
                request_id=request_id,
                payload=payload,
                result_id=result_id,
            )
        )
        if self.movement_status is not None:
            self.status = self.movement_status
        if self.movement_view_from_payload is not None:
            self.view = self.movement_view_from_payload(payload)
        elif self.movement_view is not None:
            self.view = self.movement_view
        if self.movement_event_delta is not None:
            self.event_delta = self.movement_event_delta
        return self.status
