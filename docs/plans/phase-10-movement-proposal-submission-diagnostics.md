# Phase 10 - Movement proposal submission and diagnostics

## Goal

Submit the aggregated per-model movement path proposal to the engine and display authoritative
result/diagnostics.

The adapter contract distinguishes malformed/stale/context-drift submissions from rule-invalid but
well-formed proposals. Malformed or stale proposals leave the pending request unresolved;
rule-invalid but well-formed proposals can be recorded and followed by a fresh proposal request with
diagnostics.

## Contract review notes

Reviewed against `Warhammer_40k_AI` `main` at `16d0adf` on 2026-06-04.

- Phase 10 depends on the Phase 8 entity selection foundation and Phase 9 per-model movement
  assignment workflow. Submission should not preserve the old unit-simple "move every model
  together" drafting behavior.
- Phase 10 should submit only `submit_movement_proposal` payloads. Placement, shooting declaration,
  Stratagem target-binding, and other parameterized proposal families remain visible but unsupported
  by this movement submission tool.
- Submission must use the current explicit `request_id` at the UI boundary. The UI facade should
  continue constructing `ParameterizedSubmission` with that request ID rather than relying on any
  core local-session helper that infers the first pending request.
- The engine validates stale request IDs, proposal-kind drift, unit drift,
  `movement_phase_action` drift, `movement_mode` drift, Fall Back `fall_back_mode` drift, malformed
  witness shape, and missing required payload fields before authoritative mutation.
- For movement and placement, a well-formed but rule-invalid proposal may be recorded as a rejected
  attempt and followed by a fresh proposal request. If the fresh request still targets the same
  unit/proposal kind/mode context, the UI may offer retry from the last path as a local convenience.
- Shooting declaration proposals have a different retry policy and different payload shape; do not
  generalize movement retry behavior to shooting in this phase.
- Invalid diagnostics should be read from the engine `proposal_validation` payload:
  `proposal_request_id`, `proposal_kind`, `status`, and each violation's `violation_code`,
  `message`, and optional `field`.

## Tasks

- [ ] Implement `submit_movement_payload`.
- [ ] Keep `request_id` explicit in the UI submission method and reject stale request drift before
  constructing an engine-facing result.
- [ ] Submit through the parameterized path only; never answer
  `submit_parameterized_payload` as an ordinary finite option.
- [ ] Add result handling:
  - accepted
  - invalid shape
  - stale request
  - movement mode or Fall Back mode drift
  - rule-invalid movement
  - unsupported proposal kind
  - unsupported non-movement parameterized request
- [ ] Add diagnostics panel:
  - violation code
  - message
  - affected field/model/path segment, if present
- [ ] On accepted movement:
  - clear draft
  - clear request-scoped movement assignment state
  - refresh battlefield projection
  - append events
- [ ] On invalid movement:
  - retain or reconstruct draft if still relevant
  - show diagnostic
  - update to new request id and proposal context if engine emits a fresh movement proposal request
- [ ] Add "retry from last path" affordance if safe.
- [ ] Add snapshot tests for representative diagnostic payloads.
- [ ] Add auto-follow lifecycle behavior after accepted movement:
  - refresh viewer-scoped events;
  - advance until the next pending decision or terminal status;
  - build the next request-scoped selection profile;
  - show waiting/opponent context if the next actor is not the viewer.

## Acceptance criteria

- [ ] Accepted movement visibly updates model positions after view refresh.
- [ ] Invalid movement displays authoritative diagnostics.
- [ ] Stale request errors are obvious to the user.
- [ ] Movement-mode and Fall Back mode drift diagnostics are obvious to the user.
- [ ] UI never mutates authoritative model positions before engine acceptance.
- [ ] UI submits the aggregate per-model movement payload produced by Phase 9.
- [ ] UI rejects or displays unsupported non-movement parameterized requests without trying to
  submit them through the movement payload path.
- [ ] Tests verify invalid diagnostics are surfaced.
- [ ] Tests verify accepted movement clears draft state.
- [ ] Tests verify rejected movement does not locally commit final positions.
- [ ] Tests verify retry-from-last-path is offered only when the fresh proposal request still
  targets the same unit, proposal kind, movement action, movement mode, and Fall Back mode context.
- [ ] Tests verify stale request ID rejection happens at the UI boundary before engine mutation.

## Closeout milestone

**Milestone 10: "End-to-End Movement UI"**

A user can complete the full flow: select unit -> select movement action -> draw path -> submit
movement proposal -> see accepted state or authoritative diagnostics.
