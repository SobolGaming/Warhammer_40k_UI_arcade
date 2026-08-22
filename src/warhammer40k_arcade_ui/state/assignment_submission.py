"""Generic assignment proposal submission orchestration."""

from __future__ import annotations

from dataclasses import dataclass, replace

from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientStatus,
    UiCoreClient,
    UiDecision,
    UiGameView,
)
from warhammer40k_arcade_ui.state.assignment_workspace import (
    ASSIGNMENT_DECISION_TYPES,
    ASSIGNMENT_PROPOSAL_KINDS,
    AssignmentWorkspace,
)
from warhammer40k_arcade_ui.state.finite_decision import (
    FiniteDecisionUiState,
    refresh_submission_projection,
)


@dataclass(frozen=True, slots=True)
class AssignmentProposalSubmission:
    """Prepared assignment proposal preserving request and result IDs."""

    request_id: str
    payload: JsonObject
    result_id: str


@dataclass(frozen=True, slots=True)
class AssignmentSubmissionResult:
    """State returned after attempting to submit an assignment workspace."""

    finite_state: FiniteDecisionUiState
    refreshed_view: UiGameView | None
    clear_assignment_workspace: bool
    viewer_player_id: str | None = None


class AssignmentSubmissionError(ValueError):
    """Raised when assignment submission state is internally inconsistent."""


def prepare_assignment_submission(
    *,
    assignment_workspace: AssignmentWorkspace | None,
    pending_decision: UiDecision | None,
    next_result_index: int,
    decline: bool = False,
) -> tuple[UiClientStatus | None, AssignmentProposalSubmission | None, int]:
    """Prepare an assignment proposal or decline submission."""

    if assignment_workspace is None:
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="no_assignment_workspace",
                message="Assignment submission requires an active assignment workspace.",
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
                message="Assignment submission requires a pending assignment proposal request.",
                field="request_id",
            ),
            None,
            next_result_index,
        )
    if not pending_decision.is_parameterized:
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="assignment_payload_for_finite_request",
                message="Assignment payload submission requires a parameterized request.",
                field="request_id",
            ),
            None,
            next_result_index,
        )
    proposal = pending_decision.parameterized_proposal
    if proposal is None or proposal.decision_type not in ASSIGNMENT_DECISION_TYPES:
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="unsupported_assignment_request",
                message="Assignment submission requires a supported assignment request.",
                field="decision_type",
            ),
            None,
            next_result_index,
        )
    if proposal.proposal_kind not in ASSIGNMENT_PROPOSAL_KINDS:
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="unsupported_assignment_proposal_kind",
                message="Assignment submission does not support this proposal kind.",
                field="proposal_kind",
            ),
            None,
            next_result_index,
        )
    if not assignment_workspace.is_for(pending_decision):
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="stale_request_id",
                message="Assignment workspace request_id does not match the pending request.",
                field="request_id",
            ),
            None,
            next_result_index,
        )
    if decline:
        payload = assignment_workspace.decline_payload
        if payload is None:
            return (
                _local_invalid(
                    pending_decision=pending_decision,
                    violation_code="assignment_decline_not_available",
                    message="Assignment request is not marked declinable by the engine.",
                    field="payload",
                ),
                None,
                next_result_index,
            )
    else:
        payload = assignment_workspace.payload_preview
        if payload is None or assignment_workspace.diagnostic_lines:
            return (
                _local_invalid(
                    pending_decision=pending_decision,
                    violation_code="assignment_workspace_not_ready",
                    message="Assignment workspace must be complete before submission.",
                    field="payload",
                ),
                None,
                next_result_index,
            )
    result_id = f"ui-result-{next_result_index:06d}"
    return (
        None,
        AssignmentProposalSubmission(
            request_id=proposal.request_id,
            payload=payload,
            result_id=result_id,
        ),
        next_result_index + 1,
    )


def submit_assignment_workspace(
    *,
    state: FiniteDecisionUiState,
    assignment_workspace: AssignmentWorkspace | None,
    client: UiCoreClient | None,
    viewer_player_id: str,
    decline: bool = False,
) -> AssignmentSubmissionResult:
    """Submit an assignment workspace and refresh status/projection."""

    if client is None:
        no_client_status = _local_invalid(
            pending_decision=state.pending_decision,
            violation_code="no_core_client",
            message="Assignment submission requires a configured core client.",
            field="client",
        )
        return AssignmentSubmissionResult(
            finite_state=state.apply_status(no_client_status),
            refreshed_view=None,
            clear_assignment_workspace=False,
        )
    invalid_status, submission, next_result_index = prepare_assignment_submission(
        assignment_workspace=assignment_workspace,
        pending_decision=state.pending_decision,
        next_result_index=state.next_result_index,
        decline=decline,
    )
    if submission is None:
        if invalid_status is None:
            raise AssignmentSubmissionError("Assignment submission preparation returned no status.")
        return AssignmentSubmissionResult(
            finite_state=state.apply_status(invalid_status),
            refreshed_view=None,
            clear_assignment_workspace=False,
        )
    prepared_state = replace(
        state,
        status_kind="submitting",
        status_message="Submitting assignment proposal",
        diagnostics=(),
        next_result_index=next_result_index,
    )
    submitted_status = client.submit_parameterized_payload(
        request_id=submission.request_id,
        payload=submission.payload,
        result_id=submission.result_id,
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
    return AssignmentSubmissionResult(
        finite_state=refresh.finite_state,
        refreshed_view=refresh.refreshed_view,
        clear_assignment_workspace=submitted_status.status_kind != "invalid",
        viewer_player_id=refresh.viewer_player_id,
    )


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
