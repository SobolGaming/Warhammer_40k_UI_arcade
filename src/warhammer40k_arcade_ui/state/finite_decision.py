"""Local UI state for finite decision selection and submission."""

from __future__ import annotations

from dataclasses import dataclass, replace

from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientStatus,
    UiCoreClient,
    UiDecision,
    UiEventDelta,
    UiFiniteOption,
    UiGameView,
    UiInvalidDiagnostic,
)

MAX_EVENT_LOG_LINES = 6


@dataclass(frozen=True, slots=True)
class FiniteDecisionSubmission:
    """Prepared finite decision submission preserving engine request/option IDs."""

    request_id: str
    selected_option_id: str
    result_id: str


@dataclass(frozen=True, slots=True)
class FiniteDecisionUiState:
    """Local finite-decision focus, status, result-ID, and event cursor state."""

    pending_decision: UiDecision | None = None
    highlighted_option_index: int = 0
    status_kind: str = "idle"
    status_message: str = "Ready"
    diagnostics: tuple[UiInvalidDiagnostic, ...] = ()
    event_cursor: int = 0
    event_log_lines: tuple[str, ...] = ()
    next_result_index: int = 1

    @property
    def finite_options(self) -> tuple[UiFiniteOption, ...]:
        """Return selectable finite options for the current request."""

        if self.pending_decision is None or self.pending_decision.is_parameterized:
            return ()
        return self.pending_decision.options

    @property
    def highlighted_option(self) -> UiFiniteOption | None:
        """Return the currently highlighted finite option, if any."""

        options = self.finite_options
        if not options:
            return None
        return options[self.highlighted_option_index]

    @classmethod
    def from_status(
        cls,
        status: UiClientStatus,
        *,
        event_cursor: int = 0,
        event_log_lines: tuple[str, ...] = (),
    ) -> FiniteDecisionUiState:
        """Create finite UI state from an initial client status."""

        return cls(
            pending_decision=status.decision,
            status_kind=status.status_kind,
            status_message=_status_message(status),
            diagnostics=status.invalid_diagnostics,
            event_cursor=event_cursor,
            event_log_lines=_trim_event_lines(event_log_lines),
        )._normalized()

    def cycle_option(self) -> FiniteDecisionUiState:
        """Move focus to the next finite option without changing model selection."""

        options = self.finite_options
        if not options:
            return self
        return replace(
            self,
            highlighted_option_index=(self.highlighted_option_index + 1) % len(options),
        )

    def highlight_option_for_unit(self, unit_id: str | None) -> FiniteDecisionUiState:
        """Move focus to the finite option naming a selected unit, if one exists."""

        if unit_id is None:
            return self
        options = self.finite_options
        payload_matches: list[int] = []
        for index, option in enumerate(options):
            if option.option_id == unit_id:
                return replace(self, highlighted_option_index=index)
            if _option_payload_targets_unit(option, unit_id):
                payload_matches.append(index)
        if len(payload_matches) == 1:
            return replace(self, highlighted_option_index=payload_matches[0])
        return self

    def with_local_invalid(
        self,
        *,
        violation_code: str,
        message: str,
        field: str,
    ) -> FiniteDecisionUiState:
        """Record a local UI-boundary invalid state without submitting to the engine."""

        diagnostic = UiInvalidDiagnostic(
            violation_code=violation_code,
            message=message,
            field=field,
        )
        return replace(
            self,
            status_kind="invalid",
            status_message=message,
            diagnostics=(diagnostic,),
        )

    def with_fatal_game_engine_error(
        self,
        *,
        message: str,
        detail: str,
    ) -> FiniteDecisionUiState:
        """Record a fatal engine/client projection failure before UI shutdown."""

        diagnostic = UiInvalidDiagnostic(
            violation_code="fatal_game_engine_error",
            message=detail,
            field="core_engine",
        )
        return replace(
            self,
            pending_decision=None,
            highlighted_option_index=0,
            status_kind="fatal",
            status_message=message,
            diagnostics=(diagnostic,),
        )

    def prepare_submission(
        self,
        selected_option_id: str | None = None,
    ) -> tuple[FiniteDecisionUiState, FiniteDecisionSubmission | None]:
        """Build a finite submission, or record why no submission is allowed."""

        decision = self.pending_decision
        if decision is None:
            return (
                self.with_local_invalid(
                    violation_code="no_pending_decision",
                    message="Finite submission requires a pending DecisionRequest.",
                    field="request_id",
                ),
                None,
            )
        if decision.is_parameterized:
            return (
                self.with_local_invalid(
                    violation_code="finite_submission_for_parameterized_request",
                    message="Finite submission cannot answer a parameterized request.",
                    field="selected_option_id",
                ),
                None,
            )
        option = (
            self.highlighted_option
            if selected_option_id is None
            else _option_by_id(decision.options, selected_option_id)
        )
        if option is None:
            return (
                self.with_local_invalid(
                    violation_code="selected_option_not_pending",
                    message="Finite submission selected option is not pending.",
                    field="selected_option_id",
                ),
                None,
            )
        result_id = f"ui-result-{self.next_result_index:06d}"
        return (
            replace(
                self,
                status_kind="submitting",
                status_message=f"Submitting {option.label}",
                diagnostics=(),
                next_result_index=self.next_result_index + 1,
            ),
            FiniteDecisionSubmission(
                request_id=decision.request_id,
                selected_option_id=option.option_id,
                result_id=result_id,
            ),
        )

    def apply_status(self, status: UiClientStatus) -> FiniteDecisionUiState:
        """Apply the latest authoritative client status."""

        pending_decision = (
            status.decision
            if status.decision is not None
            else self.pending_decision
            if status.status_kind == "invalid"
            else None
        )
        return replace(
            self,
            pending_decision=pending_decision,
            highlighted_option_index=_highlighted_option_index_for_transition(
                current_decision=self.pending_decision,
                next_decision=pending_decision,
                current_index=self.highlighted_option_index,
            ),
            status_kind=status.status_kind,
            status_message=_status_message(status),
            diagnostics=status.invalid_diagnostics,
        )._normalized()

    def apply_view(self, view: UiGameView) -> FiniteDecisionUiState:
        """Apply viewer-scoped pending-decision state from a refreshed projection."""

        return replace(
            self,
            pending_decision=view.pending_decision,
            highlighted_option_index=_highlighted_option_index_for_transition(
                current_decision=self.pending_decision,
                next_decision=view.pending_decision,
                current_index=self.highlighted_option_index,
            ),
        )._normalized()

    def apply_event_delta(self, delta: UiEventDelta) -> FiniteDecisionUiState:
        """Append viewer-scoped event lines and persist the next cursor."""

        return replace(
            self,
            event_cursor=delta.next_cursor,
            event_log_lines=_trim_event_lines(
                (*self.event_log_lines, *(_event_line(event) for event in delta.events))
            ),
        )

    def _normalized(self) -> FiniteDecisionUiState:
        options = self.finite_options
        if not options and self.highlighted_option_index == 0:
            return self
        if not options:
            return replace(self, highlighted_option_index=0)
        if 0 <= self.highlighted_option_index < len(options):
            return self
        return replace(self, highlighted_option_index=0)


def submit_finite_option(
    *,
    state: FiniteDecisionUiState,
    client: UiCoreClient,
    selected_option_id: str | None,
    viewer_player_id: str,
) -> FiniteDecisionUiState:
    """Submit a selected finite option and refresh status, view, and viewer events."""

    prepared_state, submission = state.prepare_submission(selected_option_id)
    if submission is None:
        return prepared_state
    submitted_status = client.submit_finite(
        request_id=submission.request_id,
        selected_option_id=submission.selected_option_id,
        result_id=submission.result_id,
    )
    refreshed_state = prepared_state.apply_status(submitted_status)
    refreshed_view = client.get_view(viewer_player_id)
    refreshed_state = refreshed_state.apply_view(refreshed_view)
    event_delta = client.get_events_since(refreshed_state.event_cursor, viewer_player_id)
    return refreshed_state.apply_event_delta(event_delta)


def _option_by_id(
    options: tuple[UiFiniteOption, ...],
    selected_option_id: str,
) -> UiFiniteOption | None:
    for option in options:
        if option.option_id == selected_option_id:
            return option
    return None


def _highlighted_option_index_for_transition(
    *,
    current_decision: UiDecision | None,
    next_decision: UiDecision | None,
    current_index: int,
) -> int:
    if next_decision is None or current_decision is None:
        return 0
    if current_decision.request_id != next_decision.request_id:
        return 0
    return current_index


def _option_payload_targets_unit(option: UiFiniteOption, unit_id: str) -> bool:
    payload = option.payload
    if type(payload) is not dict:
        return False
    return payload.get("unit_instance_id") == unit_id or payload.get("unit_id") == unit_id


def _status_message(status: UiClientStatus) -> str:
    if status.invalid_diagnostics:
        return status.invalid_diagnostics[0].message
    if status.message is not None:
        return status.message
    if status.decision is None:
        return status.status_kind
    if status.decision.is_parameterized:
        proposal = status.decision.parameterized_proposal
        label = (
            proposal.proposal_kind
            if proposal is not None and proposal.proposal_kind is not None
            else status.decision.decision_type
        )
        return f"Proposal required: {label}"
    return f"Waiting: {status.decision.decision_type}"


def _event_line(event: JsonObject) -> str:
    event_type = _event_string(event, "event_type") or _event_string(event, "type") or "event"
    payload = event.get("payload")
    if type(payload) is dict:
        player_id = _event_string(payload, "player_id")
        if player_id is not None:
            return f"{event_type}: {player_id}"
        status = _event_string(payload, "status")
        if status is not None:
            return f"{event_type}: {status}"
    return event_type


def _event_string(payload: JsonObject, key: str) -> str | None:
    value = payload.get(key)
    if type(value) is str and value:
        return value
    return None


def _trim_event_lines(lines: tuple[str, ...]) -> tuple[str, ...]:
    if len(lines) <= MAX_EVENT_LOG_LINES:
        return lines
    return lines[-MAX_EVENT_LOG_LINES:]
