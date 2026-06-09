"""Local in-process core session client."""

from __future__ import annotations

from dataclasses import dataclass, field

from warhammer40k_core.adapters.contracts import FiniteOptionSubmission, ParameterizedSubmission
from warhammer40k_core.adapters.event_stream import EventStreamCursor
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.engine.decision_request import DecisionRequest
from warhammer40k_core.engine.game_state import GameConfig
from warhammer40k_core.engine.phase import LifecycleStatus

from warhammer40k_arcade_ui.core_client.protocol import (
    JsonValue,
    UiClientProtocolError,
    UiClientStatus,
    UiDecision,
    UiEventDelta,
    UiGameView,
    validate_json_value,
)

_MOVEMENT_PROPOSAL_DECISION_TYPE = "submit_movement_proposal"


@dataclass(slots=True)
class LocalSessionClient:
    """UI-facing facade over the core engine's local in-process session."""

    session: LocalGameSession = field(default_factory=LocalGameSession)
    _next_result_index: int = 1

    def start_game(self, config: object) -> UiClientStatus:
        """Start a local game session."""

        if type(config) is not GameConfig:
            raise UiClientProtocolError("LocalSessionClient start_game requires a GameConfig.")
        return _status_from_lifecycle(self.session.start(config))

    def advance_until_decision_or_terminal(self) -> UiClientStatus:
        """Advance until the core lifecycle requests input or reaches a terminal status."""

        return _status_from_lifecycle(self.session.advance_until_decision_or_terminal())

    def get_view(self, viewer_player_id: str) -> UiGameView:
        """Return a viewer-scoped game projection."""

        return UiGameView.from_payload(self.session.view(viewer_player_id=viewer_player_id))

    def get_events_since(self, cursor: int, viewer_player_id: str) -> UiEventDelta:
        """Return viewer-scoped event records after the supplied cursor."""

        return UiEventDelta.from_payload(
            self.session.events_since(
                EventStreamCursor(value=cursor),
                viewer_player_id=viewer_player_id,
            )
        )

    def submit_finite(
        self,
        *,
        request_id: str,
        selected_option_id: str,
        result_id: str | None = None,
    ) -> UiClientStatus:
        """Submit a finite option using the explicit UI-supplied request ID."""

        pending_request = self._pending_request()
        if pending_request is None:
            return self._invalid_submission_status(
                violation_code="no_pending_decision",
                message="Finite submission requires a pending DecisionRequest.",
                field="request_id",
            )
        pending_decision = _decision_from_request(pending_request)
        if pending_request.request_id != request_id:
            return self._invalid_submission_status(
                violation_code="stale_request_id",
                message="Finite submission request_id does not match the pending request.",
                field="request_id",
                decision=pending_decision,
            )
        if pending_request.is_parameterized_submission_request():
            return self._invalid_submission_status(
                violation_code="finite_submission_for_parameterized_request",
                message="Finite submission cannot answer a parameterized request.",
                field="selected_option_id",
                decision=pending_decision,
            )
        if selected_option_id not in {option.option_id for option in pending_request.options}:
            return self._invalid_submission_status(
                violation_code="selected_option_not_pending",
                message="Finite submission selected option is not pending.",
                field="selected_option_id",
                decision=pending_decision,
            )
        submission = FiniteOptionSubmission(
            request_id=request_id,
            selected_option_id=selected_option_id,
            result_id=result_id or self._next_result_id(),
        )
        return _status_from_lifecycle(
            self.session.lifecycle.submit_decision(submission.to_result(pending_request))
        )

    def submit_movement_payload(
        self,
        *,
        request_id: str,
        payload: JsonValue,
        result_id: str | None = None,
    ) -> UiClientStatus:
        """Submit a parameterized movement payload using the explicit request ID."""

        pending_request = self._pending_request()
        if pending_request is None:
            return self._invalid_submission_status(
                violation_code="no_pending_decision",
                message="Movement payload submission requires a pending DecisionRequest.",
                field="request_id",
            )
        pending_decision = _decision_from_request(pending_request)
        if pending_request.request_id != request_id:
            return self._invalid_submission_status(
                violation_code="stale_request_id",
                message="Movement payload request_id does not match the pending request.",
                field="request_id",
                decision=pending_decision,
            )
        if not pending_request.is_parameterized_submission_request():
            return self._invalid_submission_status(
                violation_code="movement_payload_for_finite_request",
                message="Movement payload submission requires a parameterized request.",
                field="request_id",
                decision=pending_decision,
            )
        if pending_request.decision_type != _MOVEMENT_PROPOSAL_DECISION_TYPE:
            return self._invalid_submission_status(
                violation_code="unsupported_parameterized_request",
                message="submit_movement_payload can answer only movement proposal requests.",
                field="decision_type",
                decision=pending_decision,
            )
        submission = ParameterizedSubmission(
            request_id=request_id,
            payload=validate_json_value(payload),
            result_id=result_id or self._next_result_id(),
        )
        return _status_from_lifecycle(
            self.session.lifecycle.submit_decision(submission.to_result(pending_request))
        )

    def _pending_request(self) -> DecisionRequest | None:
        pending_requests = self.session.lifecycle.decision_controller.queue.pending_requests
        if not pending_requests:
            return None
        return pending_requests[0]

    def _next_result_id(self) -> str:
        result_id = f"ui-result-{self._next_result_index:06d}"
        self._next_result_index += 1
        return result_id

    def _invalid_submission_status(
        self,
        *,
        violation_code: str,
        message: str,
        field: str,
        decision: UiDecision | None = None,
    ) -> UiClientStatus:
        return UiClientStatus.invalid(
            stage=self._current_stage(),
            violation_code=violation_code,
            message=message,
            field=field,
            payload={
                "invalid_reason": violation_code,
                "field": field,
            },
            decision=decision,
        )

    def _current_stage(self) -> str:
        state = self.session.lifecycle.state
        if state is None:
            return "setup"
        return state.stage.value


def _status_from_lifecycle(status: LifecycleStatus) -> UiClientStatus:
    payload = dict(status.to_payload())
    if status.decision_request is not None:
        decision_payload = dict(status.decision_request.to_payload())
        decision_payload["is_parameterized"] = (
            status.decision_request.is_parameterized_submission_request()
        )
        payload["decision_request"] = decision_payload
    return UiClientStatus.from_payload(payload)


def _decision_from_request(request: DecisionRequest) -> UiDecision:
    return UiDecision.from_payload(
        {
            "request_id": request.request_id,
            "decision_type": request.decision_type,
            "actor_id": request.actor_id,
            "payload": request.payload,
            "options": [option.to_payload() for option in request.options],
            "is_parameterized": request.is_parameterized_submission_request(),
        }
    )
