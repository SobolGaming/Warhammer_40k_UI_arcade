"""Movement proposal submission orchestration for local UI state."""

from __future__ import annotations

from dataclasses import dataclass, replace

from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientStatus,
    UiCoreClient,
    UiDecision,
    UiGameView,
)
from warhammer40k_arcade_ui.state.finite_decision import (
    FiniteDecisionUiState,
    refresh_submission_projection,
)
from warhammer40k_arcade_ui.state.movement_draft import (
    SUPPORTED_MOVEMENT_DRAFT_DECISION_TYPES,
    SUPPORTED_MOVEMENT_DRAFT_PROPOSAL_KINDS,
    MovementDraft,
    movement_proposal_profile,
)


@dataclass(frozen=True, slots=True)
class MovementProposalSubmission:
    """Prepared parameterized movement proposal preserving request and result IDs."""

    request_id: str
    payload: JsonObject
    result_id: str


@dataclass(frozen=True, slots=True)
class MovementSubmissionResult:
    """State returned after attempting to submit a movement draft."""

    finite_state: FiniteDecisionUiState
    refreshed_view: UiGameView | None
    clear_movement_draft: bool
    viewer_player_id: str | None = None
    reset_movement_draft_ready: bool = False


def prepare_movement_submission(
    *,
    movement_draft: MovementDraft | None,
    pending_decision: UiDecision | None,
    next_result_index: int,
) -> tuple[UiClientStatus | None, MovementProposalSubmission | None, int]:
    """Prepare a movement proposal submission or return a UI-boundary invalid status."""

    if movement_draft is None:
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="no_movement_draft",
                message="Movement submission requires a ready movement draft.",
                field="payload",
            ),
            None,
            next_result_index,
        )
    if pending_decision is None:
        return (
            _local_invalid(
                pending_decision=None,
                violation_code="no_pending_decision",
                message="Movement submission requires a pending movement proposal request.",
                field="request_id",
            ),
            None,
            next_result_index,
        )
    if not pending_decision.is_parameterized:
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="movement_payload_for_finite_request",
                message="Movement payload submission requires a parameterized request.",
                field="request_id",
            ),
            None,
            next_result_index,
        )
    proposal = pending_decision.movement_proposal
    if proposal is None or proposal.decision_type not in SUPPORTED_MOVEMENT_DRAFT_DECISION_TYPES:
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="unsupported_parameterized_request",
                message=(
                    "Movement draft submission requires a supported movement-shaped "
                    "parameterized request."
                ),
                field="decision_type",
            ),
            None,
            next_result_index,
        )
    if proposal.proposal_kind not in SUPPORTED_MOVEMENT_DRAFT_PROPOSAL_KINDS:
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="unsupported_movement_proposal_kind",
                message="Movement draft submission does not support this proposal kind.",
                field="proposal_kind",
            ),
            None,
            next_result_index,
        )
    if proposal.request_id != movement_draft.proposal_request_id:
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="stale_request_id",
                message="Movement draft request_id does not match the pending request.",
                field="request_id",
            ),
            None,
            next_result_index,
        )
    if not movement_draft.matches_proposal_context(pending_decision=pending_decision):
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="movement_proposal_context_drift",
                message="Movement draft context does not match the pending proposal request.",
                field="proposal_request",
            ),
            None,
            next_result_index,
        )
    payload = movement_draft.payload_preview
    if payload is None:
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="movement_draft_not_ready",
                message="Movement draft must be marked ready before submission.",
                field="payload",
            ),
            None,
            next_result_index,
        )
    result_id = f"ui-result-{next_result_index:06d}"
    return (
        None,
        MovementProposalSubmission(
            request_id=proposal.request_id,
            payload=payload,
            result_id=result_id,
        ),
        next_result_index + 1,
    )


def submit_movement_draft(
    *,
    state: FiniteDecisionUiState,
    movement_draft: MovementDraft | None,
    client: UiCoreClient | None,
    viewer_player_id: str,
) -> MovementSubmissionResult:
    """Submit a ready movement draft and refresh status, projection, and viewer events."""

    if client is None:
        no_client_status = _local_invalid(
            pending_decision=state.pending_decision,
            violation_code="no_core_client",
            message="Movement submission requires a configured core client.",
            field="client",
        )
        return MovementSubmissionResult(
            finite_state=state.apply_status(no_client_status),
            refreshed_view=None,
            clear_movement_draft=False,
        )
    invalid_status, submission, next_result_index = prepare_movement_submission(
        movement_draft=movement_draft,
        pending_decision=state.pending_decision,
        next_result_index=state.next_result_index,
    )
    if submission is None:
        if invalid_status is None:
            raise MovementSubmissionError("Movement submission preparation returned no status.")
        return MovementSubmissionResult(
            finite_state=state.apply_status(invalid_status),
            refreshed_view=None,
            clear_movement_draft=False,
        )
    prepared_state = replace(
        state,
        status_kind="submitting",
        status_message="Submitting movement proposal",
        diagnostics=(),
        next_result_index=next_result_index,
    )
    proposal = state.pending_decision.movement_proposal if state.pending_decision else None
    if proposal is None:
        raise MovementSubmissionError("Prepared movement submission lost pending proposal.")
    profile = movement_proposal_profile(
        decision_type=proposal.decision_type,
        proposal_kind=proposal.proposal_kind,
    )
    submitted_status = (
        client.submit_parameterized_payload(
            request_id=submission.request_id,
            payload=submission.payload,
            result_id=submission.result_id,
        )
        if profile.submits_through_generic_parameterized_client
        else client.submit_movement_payload(
            request_id=submission.request_id,
            payload=submission.payload,
            result_id=submission.result_id,
        )
    )
    authoritative_status = (
        submitted_status
        if submitted_status.status_kind == "invalid"
        else client.advance_until_decision_or_terminal()
    )
    refresh = refresh_submission_projection(
        state=prepared_state,
        status=authoritative_status,
        client=client,
        fallback_viewer_player_id=viewer_player_id,
    )
    return MovementSubmissionResult(
        finite_state=refresh.finite_state,
        refreshed_view=refresh.refreshed_view,
        clear_movement_draft=submitted_status.status_kind != "invalid",
        viewer_player_id=refresh.viewer_player_id,
        reset_movement_draft_ready=submitted_status.status_kind == "invalid",
    )


class MovementSubmissionError(ValueError):
    """Raised when movement submission state is internally inconsistent."""


def _local_invalid(
    *,
    pending_decision: UiDecision | None,
    violation_code: str,
    message: str,
    field: str,
) -> UiClientStatus:
    return UiClientStatus.invalid(
        stage="battle",
        violation_code=violation_code,
        message=message,
        field=field,
        payload={
            "invalid_reason": violation_code,
            "field": field,
        },
        decision=pending_decision,
    )
