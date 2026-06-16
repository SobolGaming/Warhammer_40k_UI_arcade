"""Placement proposal submission orchestration for local UI state."""

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
from warhammer40k_arcade_ui.state.placement_draft import (
    PLACEMENT_PROPOSAL_DECISION_TYPES,
    SUPPORTED_PLACEMENT_PROPOSAL_KINDS,
    PlacementDraft,
)


@dataclass(frozen=True, slots=True)
class PlacementProposalSubmission:
    """Prepared parameterized placement proposal preserving request and result IDs."""

    request_id: str
    payload: JsonObject
    result_id: str


@dataclass(frozen=True, slots=True)
class PlacementSubmissionResult:
    """State returned after attempting to submit a placement draft."""

    finite_state: FiniteDecisionUiState
    refreshed_view: UiGameView | None
    clear_placement_draft: bool
    viewer_player_id: str | None = None


class PlacementSubmissionError(ValueError):
    """Raised when placement submission state is internally inconsistent."""


def prepare_placement_submission(
    *,
    placement_draft: PlacementDraft | None,
    pending_decision: UiDecision | None,
    next_result_index: int,
) -> tuple[UiClientStatus | None, PlacementProposalSubmission | None, int]:
    """Prepare a placement proposal submission or return a UI-boundary invalid status."""

    if placement_draft is None:
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="no_placement_draft",
                message="Placement submission requires a ready placement draft.",
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
                message="Placement submission requires a pending placement proposal request.",
                field="request_id",
            ),
            None,
            next_result_index,
        )
    if not pending_decision.is_parameterized:
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="placement_payload_for_finite_request",
                message="Placement payload submission requires a parameterized request.",
                field="request_id",
            ),
            None,
            next_result_index,
        )
    proposal = pending_decision.placement_proposal
    if proposal is None or proposal.decision_type not in PLACEMENT_PROPOSAL_DECISION_TYPES:
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="unsupported_parameterized_request",
                message="Placement payload submission requires a placement proposal request.",
                field="decision_type",
            ),
            None,
            next_result_index,
        )
    if proposal.proposal_kind not in SUPPORTED_PLACEMENT_PROPOSAL_KINDS:
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="unsupported_placement_proposal_kind",
                message="Placement draft submission does not support this proposal kind.",
                field="proposal_kind",
            ),
            None,
            next_result_index,
        )
    if proposal.request_id != placement_draft.proposal_request_id:
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="stale_request_id",
                message="Placement draft request_id does not match the pending request.",
                field="request_id",
            ),
            None,
            next_result_index,
        )
    if not placement_draft.matches_proposal_context(pending_decision=pending_decision):
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="placement_proposal_context_drift",
                message="Placement draft context does not match the pending proposal request.",
                field="proposal_request",
            ),
            None,
            next_result_index,
        )
    payload = placement_draft.payload_preview
    if payload is None:
        return (
            _local_invalid(
                pending_decision=pending_decision,
                violation_code="placement_draft_not_ready",
                message="Placement draft must be marked ready before submission.",
                field="payload",
            ),
            None,
            next_result_index,
        )
    result_id = f"ui-result-{next_result_index:06d}"
    return (
        None,
        PlacementProposalSubmission(
            request_id=proposal.request_id,
            payload=payload,
            result_id=result_id,
        ),
        next_result_index + 1,
    )


def submit_placement_draft(
    *,
    state: FiniteDecisionUiState,
    placement_draft: PlacementDraft | None,
    client: UiCoreClient | None,
    viewer_player_id: str,
) -> PlacementSubmissionResult:
    """Submit a ready placement draft and refresh status, projection, and viewer events."""

    if client is None:
        no_client_status = _local_invalid(
            pending_decision=state.pending_decision,
            violation_code="no_core_client",
            message="Placement submission requires a configured core client.",
            field="client",
        )
        return PlacementSubmissionResult(
            finite_state=state.apply_status(no_client_status),
            refreshed_view=None,
            clear_placement_draft=False,
        )
    invalid_status, submission, next_result_index = prepare_placement_submission(
        placement_draft=placement_draft,
        pending_decision=state.pending_decision,
        next_result_index=state.next_result_index,
    )
    if submission is None:
        if invalid_status is None:
            raise PlacementSubmissionError("Placement submission preparation returned no status.")
        return PlacementSubmissionResult(
            finite_state=state.apply_status(invalid_status),
            refreshed_view=None,
            clear_placement_draft=False,
        )
    prepared_state = replace(
        state,
        status_kind="submitting",
        status_message="Submitting placement proposal",
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
    return PlacementSubmissionResult(
        finite_state=refresh.finite_state,
        refreshed_view=refresh.refreshed_view,
        clear_placement_draft=True,
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
