# Phase 8 — Movement proposal submission and diagnostics

## Goal

Submit the movement path to the engine and display authoritative result/diagnostics.

The adapter contract distinguishes malformed/stale/context-drift submissions from rule-invalid but
well-formed proposals. Malformed or stale proposals leave the pending request unresolved;
rule-invalid but well-formed proposals can be recorded and followed by a fresh proposal request with
diagnostics.

## Tasks

- [ ] Implement `submit_movement_payload`.
- [ ] Add result handling:
  - accepted
  - invalid shape
  - stale request
  - rule-invalid movement
  - unsupported proposal kind
- [ ] Add diagnostics panel:
  - violation code
  - message
  - affected field/model/path segment, if present
- [ ] On accepted movement:
  - clear draft
  - refresh battlefield projection
  - append events
- [ ] On invalid movement:
  - retain or reconstruct draft if still relevant
  - show diagnostic
  - update to new request id if engine emits a fresh proposal request
- [ ] Add “retry from last path” affordance if safe.
- [ ] Add snapshot tests for representative diagnostic payloads.

## Acceptance criteria

- [ ] Accepted movement visibly updates model positions after view refresh.
- [ ] Invalid movement displays authoritative diagnostics.
- [ ] Stale request errors are obvious to the user.
- [ ] UI never mutates authoritative model positions before engine acceptance.
- [ ] Tests verify invalid diagnostics are surfaced.
- [ ] Tests verify accepted movement clears draft state.
- [ ] Tests verify rejected movement does not locally commit final positions.

## Closeout milestone

**Milestone 8: “End-to-End Movement UI”**

A user can complete the full flow: select unit → select movement action → draw path → submit
movement proposal → see accepted state or authoritative diagnostics.
