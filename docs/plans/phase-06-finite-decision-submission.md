# Phase 6 — Finite decision submission

## Goal

Let the user answer engine-provided finite `DecisionRequest` options through the authoritative
decision contract.

Movement action selection, such as choosing Normal Move, is the first visible vertical slice. The UI
surface must remain generic because the current AI contract also uses finite options for scoring
choices, reaction and sequencing windows, shooting choices, allocation/save/defensive choices,
Stratagem windows, and other lifecycle decisions.

The adapter contract’s finite-decision flow requires the UI to submit the current pending
`request_id` plus exactly one pending option ID. The UI must not invent option IDs, infer hidden
engine semantics from payloads, or answer parameterized proposal requests through the finite path.

## Contract Review Notes

- `FiniteOptionSubmission(request_id, selected_option_id, result_id)` remains the authoritative
  finite result shape.
- The UI boundary must keep `request_id` explicit. Any lower-level local-session helper that can
  infer the current pending request does not change the UI-facing contract.
- A finite submission is valid only when the selected option ID names one option on the current
  pending request, and the submitted result payload matches that option payload.
- Parameterized proposal requests are still `DecisionRequest`s, but they contain the fixed
  `submit_parameterized_payload` option and require a later payload-specific submission flow.
  Phase 6 should show that such a request is pending but must not present it as an ordinary finite
  option.
- Viewer-scoped event deltas must be requested with the current viewer and cursor. Event rendering
  should treat the adapter stream as already visibility-scoped and avoid exposing internal/replay
  payloads.

## Tasks

- [ ] Implement a generic finite-decision view model:
  - current request ID
  - decision type
  - actor ID
  - labeled finite options
  - selected/highlighted option cursor
  - parameterized-request indicator for future proposal phases
- [ ] Implement finite option buttons in the HUD from pending request options.
- [ ] Implement radial/context menu finite option selection from pending request options.
- [ ] Keep movement action labels as data from the engine request, not hard-coded UI rules.
- [ ] Do not render parameterized `submit_parameterized_payload` as a finite action button; display
  it as “proposal required” or equivalent pending state until later phases add the payload tool.
- [ ] On selection:
  - create a UI result ID
  - submit selected option ID with the current request ID
  - refresh status, viewer-scoped view, and viewer-scoped event delta
- [ ] Display success, invalid, stale, or terminal status.
- [ ] Add event log panel from viewer-scoped event deltas and persist the next event cursor.
- [ ] Surface follow-up pending requests after a finite answer, including parameterized proposal
  requests created by choosing a movement action.
- [ ] Add keyboard shortcuts:
  - Escape cancels local UI selection/menu state
  - Enter confirms highlighted finite option
  - Tab cycles selectable units/options without creating a new selection from hover state
- [ ] Add tests for generic finite-decision rendering across at least:
  - movement action selection
  - a non-movement finite decision type
  - parameterized proposal pending state

## Acceptance criteria

- [ ] User can select a finite option from the UI.
- [ ] Submission includes the current request ID and exact selected option ID.
- [ ] UI refreshes after accepted submission.
- [ ] Stale/invalid submission response is visible and does not silently disappear.
- [ ] UI does not submit when the pending request is parameterized.
- [ ] UI does not depend on movement-only option IDs or decision types.
- [ ] A finite movement-action answer can advance into a visible pending movement proposal request
  without the UI trying to fabricate a proposal payload.
- [ ] Event log entries come from viewer-scoped event deltas and update the stored cursor.
- [ ] Tests verify exact submitted option id and request id.
- [ ] Tests verify UI cannot submit when no pending request exists.
- [ ] Tests verify UI cannot submit a non-existent option id.
- [ ] Tests verify UI cannot submit a finite result for a parameterized request.
- [ ] Tests verify Tab does not select a merely hovered model while cycling option focus.

## Manual Validation Checklist

After implementation, manually exercise these user-facing behaviors:

- [ ] Launch the UI and confirm a finite pending request appears in the HUD with request ID,
  decision type, actor, and options.
- [ ] Select a movement finite option such as Normal Move and confirm the UI refreshes into the next
  pending request/state instead of silently changing local model positions.
- [ ] Confirm stale/invalid status text remains visible long enough to diagnose the failed action.
- [ ] Confirm a parameterized movement proposal request is displayed as requiring a proposal tool,
  not as a clickable finite action.
- [ ] Confirm Escape closes local menu/selection state, Enter confirms the highlighted finite
  option, and Tab cycles focus without selecting a hovered model.
- [ ] Confirm event log lines advance after accepted finite decisions and are viewer-scoped.

## Closeout milestone

**Milestone 6: “Authoritative Finite Decision UI”**

The UI can answer engine-provided finite decisions correctly and visibly handles invalid/stale
outcomes.
