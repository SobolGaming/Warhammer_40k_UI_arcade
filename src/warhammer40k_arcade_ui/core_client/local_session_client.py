"""Local in-process core session client."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from warhammer40k_core.adapters.contracts import FiniteOptionSubmission, ParameterizedSubmission
from warhammer40k_core.adapters.event_stream import EventStreamCursor
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.engine.decision_request import DecisionRequest
from warhammer40k_core.engine.game_state import GameConfig
from warhammer40k_core.engine.phase import LifecycleStatus

from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
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

    def start_game(self, config: object) -> UiClientStatus:
        """Start a local game session."""

        if type(config) is not GameConfig:
            raise UiClientProtocolError("LocalSessionClient start_game requires a GameConfig.")
        return status_from_lifecycle(self.session.start(config))

    def advance_until_decision_or_terminal(self) -> UiClientStatus:
        """Advance until the core lifecycle requests input or reaches a terminal status."""

        return status_from_lifecycle(self.session.advance_until_decision_or_terminal())

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
        result_id: str,
    ) -> UiClientStatus:
        """Submit a finite option using explicit UI-supplied request and result IDs."""

        pending_or_status = self._pending_request_for_submission(
            request_id=request_id,
            no_pending_message="Finite submission requires a pending DecisionRequest.",
        )
        if isinstance(pending_or_status, UiClientStatus):
            return pending_or_status
        pending_request = pending_or_status
        pending_decision = _decision_from_request(pending_request)
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
            result_id=result_id,
        )
        return status_from_lifecycle(
            self.session.lifecycle.submit_decision(submission.to_result(pending_request))
        )

    def submit_movement_payload(
        self,
        *,
        request_id: str,
        payload: JsonValue,
        result_id: str,
    ) -> UiClientStatus:
        """Submit a movement payload using explicit UI-supplied request and result IDs."""

        pending_or_status = self._pending_request_for_submission(
            request_id=request_id,
            no_pending_message=("Movement payload submission requires a pending DecisionRequest."),
        )
        if isinstance(pending_or_status, UiClientStatus):
            return pending_or_status
        pending_request = pending_or_status
        pending_decision = _decision_from_request(pending_request)
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
            result_id=result_id,
        )
        return status_from_lifecycle(
            self.session.lifecycle.submit_decision(submission.to_result(pending_request))
        )

    def submit_parameterized_payload(
        self,
        *,
        request_id: str,
        payload: JsonValue,
        result_id: str,
    ) -> UiClientStatus:
        """Submit a generic parameterized proposal payload with explicit request/result IDs."""

        pending_or_status = self._pending_request_for_submission(
            request_id=request_id,
            no_pending_message=("Parameterized payload submission requires a pending request."),
        )
        if isinstance(pending_or_status, UiClientStatus):
            return pending_or_status
        pending_request = pending_or_status
        pending_decision = _decision_from_request(pending_request)
        if not pending_request.is_parameterized_submission_request():
            return self._invalid_submission_status(
                violation_code="parameterized_payload_for_finite_request",
                message="Parameterized payload submission requires a parameterized request.",
                field="request_id",
                decision=pending_decision,
            )
        submission = ParameterizedSubmission(
            request_id=request_id,
            payload=validate_json_value(payload),
            result_id=result_id,
        )
        return status_from_lifecycle(
            self.session.lifecycle.submit_decision(submission.to_result(pending_request))
        )

    def _pending_request_for_submission(
        self,
        *,
        request_id: str,
        no_pending_message: str,
    ) -> DecisionRequest | UiClientStatus:
        pending_requests = self.session.lifecycle.decision_controller.queue.pending_requests
        if not pending_requests:
            return self._invalid_submission_status(
                violation_code="no_pending_decision",
                message=no_pending_message,
                field="request_id",
            )
        queue_head = pending_requests[0]
        if queue_head.request_id == request_id:
            return queue_head
        queue_head_payload: JsonObject = {
            "submitted_request_id": request_id,
            "queue_head_request_id": queue_head.request_id,
        }
        queue_head_decision = _decision_from_request(queue_head)
        if any(pending.request_id == request_id for pending in pending_requests[1:]):
            return self._invalid_submission_status(
                violation_code="non_head_pending_request",
                message=(
                    "Submission request_id matches a queued request that is not the "
                    "queue head. "
                    f"submitted_request_id={request_id!r}, "
                    f"queue_head_request_id={queue_head.request_id!r}."
                ),
                field="request_id",
                decision=queue_head_decision,
                payload_fields=queue_head_payload,
            )
        return self._invalid_submission_status(
            violation_code="stale_request_id",
            message=(
                "Submission request_id does not match any pending request. "
                f"submitted_request_id={request_id!r}, "
                f"queue_head_request_id={queue_head.request_id!r}."
            ),
            field="request_id",
            decision=queue_head_decision,
            payload_fields=queue_head_payload,
        )

    def _invalid_submission_status(
        self,
        *,
        violation_code: str,
        message: str,
        field: str,
        decision: UiDecision | None = None,
        payload_fields: JsonObject | None = None,
    ) -> UiClientStatus:
        payload: JsonObject = {
            "invalid_reason": violation_code,
            "field": field,
        }
        if payload_fields is not None:
            payload.update(payload_fields)
        return UiClientStatus.invalid(
            stage=self._current_stage(),
            violation_code=violation_code,
            message=message,
            field=field,
            payload=payload,
            decision=decision,
        )

    def _current_stage(self) -> str:
        state = self.session.lifecycle.state
        if state is None:
            return "setup"
        return state.stage.value


def status_from_lifecycle(status: LifecycleStatus) -> UiClientStatus:
    return UiClientStatus.from_payload(
        {
            "stage": status.stage.value,
            "status_kind": status.status_kind.value,
            "decision_request": (
                None
                if status.decision_request is None
                else _decision_payload_from_request(status.decision_request)
            ),
            "message": status.message,
            "payload": status.payload,
        }
    )


def _decision_from_request(request: DecisionRequest) -> UiDecision:
    return UiDecision.from_payload(_decision_payload_from_request(request))


def _decision_payload_from_request(request: DecisionRequest) -> JsonObject:
    return {
        "request_id": request.request_id,
        "decision_type": request.decision_type,
        "actor_id": request.actor_id,
        "payload": request.payload,
        "options": [cast(JsonValue, option.to_payload()) for option in request.options],
        "is_parameterized": request.is_parameterized_submission_request(),
    }
