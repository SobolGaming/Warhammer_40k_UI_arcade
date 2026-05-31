# Phase 5 — Finite decision submission

## Goal

Let the user choose a movement action such as Normal Move through the authoritative decision contract.

The adapter contract’s finite-decision flow requires adapters to select one of the pending request’s
option IDs rather than inventing option IDs.

## Tasks

- [ ] Implement finite option buttons in the HUD.
- [ ] Implement radial/context menu finite option selection.
- [ ] On selection:
  - create a UI result id
  - submit selected option id with current request id
  - refresh status/view/events
- [ ] Display success, invalid, stale, or terminal status.
- [ ] Add event log panel from viewer-scoped event deltas.
- [ ] Add keyboard shortcuts:
  - Escape cancels local UI selection/menu state
  - Enter confirms highlighted finite option
  - Tab cycles selectable units/options

## Acceptance criteria

- [ ] User can select a finite option from the UI.
- [ ] Submission includes the current request id.
- [ ] UI refreshes after accepted submission.
- [ ] Stale/invalid submission response is visible and does not silently disappear.
- [ ] Tests verify exact submitted option id and request id.
- [ ] Tests verify UI cannot submit when no pending request exists.
- [ ] Tests verify UI cannot submit a non-existent option id.

## Closeout milestone

**Milestone 5: “Authoritative Finite Decision UI”**

The UI can answer engine-provided finite decisions correctly and visibly handles invalid/stale
outcomes.
