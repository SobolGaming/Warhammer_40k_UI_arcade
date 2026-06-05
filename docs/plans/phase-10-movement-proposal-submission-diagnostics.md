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

- [x] Implement `submit_movement_payload`.
- [x] Keep `request_id` explicit in the UI submission method and reject stale request drift before
  constructing an engine-facing result.
- [x] Submit through the parameterized path only; never answer
  `submit_parameterized_payload` as an ordinary finite option.
- [x] Add result handling:
  - accepted
  - invalid shape
  - stale request
  - movement mode or Fall Back mode drift
  - rule-invalid movement
  - unsupported proposal kind
  - unsupported non-movement parameterized request
- [x] Add diagnostics panel:
  - violation code
  - message
  - affected field/model/path segment, if present
- [x] On accepted movement:
  - clear draft
  - clear request-scoped movement assignment state
  - refresh battlefield projection
  - append events
- [x] On invalid movement:
  - retain or reconstruct draft if still relevant
  - show diagnostic
  - update to new request id and proposal context if engine emits a fresh movement proposal request
- [x] Add "retry from last path" affordance if safe.
- [x] Add snapshot tests for representative diagnostic payloads.
- [x] Add auto-follow lifecycle behavior after accepted movement:
  - refresh viewer-scoped events;
  - advance until the next pending decision or terminal status;
  - build the next request-scoped selection profile;
  - show waiting/opponent context if the next actor is not the viewer.

## Acceptance criteria

- [x] Accepted movement visibly updates model positions after view refresh.
- [x] Invalid movement displays authoritative diagnostics.
- [x] Stale request errors are obvious to the user.
- [x] Movement-mode and Fall Back mode drift diagnostics are obvious to the user.
- [x] UI never mutates authoritative model positions before engine acceptance.
- [x] UI submits the aggregate per-model movement payload produced by Phase 9.
- [x] UI rejects or displays unsupported non-movement parameterized requests without trying to
  submit them through the movement payload path.
- [x] Tests verify invalid diagnostics are surfaced.
- [x] Tests verify accepted movement clears draft state.
- [x] Tests verify rejected movement does not locally commit final positions.
- [x] Tests verify retry-from-last-path is offered only when the fresh proposal request still
  targets the same unit, proposal kind, movement action, movement mode, and Fall Back mode context.
- [x] Tests verify stale request ID rejection happens at the UI boundary before engine mutation.

## Closeout milestone

**Milestone 10: "End-to-End Movement UI"**

A user can complete the full flow: select unit -> select movement action -> draw path -> submit
movement proposal -> see accepted state or authoritative diagnostics.

## Implementation closeout notes

Implemented on 2026-06-05.

- Added `state.movement_submission` for deterministic movement proposal preparation and submission.
  It preserves the explicit pending request ID, creates deterministic `ui-result-*` IDs, rejects
  stale/not-ready/unsupported submissions at the UI boundary, and calls
  `UiCoreClient.submit_movement_payload(...)`.
- The Arcade window now treats Enter as a two-step movement flow: first Enter marks the local draft
  ready; second Enter submits the ready payload. Without a configured core client, the UI shows a
  typed local diagnostic rather than pretending submission succeeded.
- Non-invalid movement submissions now auto-follow by calling
  `advance_until_decision_or_terminal()`, refreshing the viewer-scoped projection, and appending
  viewer-scoped event deltas. Invalid submissions do not auto-advance.
- Accepted movement clears the local movement draft and request-scoped movement overlays. Refreshed
  projections can update model positions from either the existing render payload shape or the core
  battlefield runtime `placed_armies/unit_placements/model_placements` shape.
- Invalid movement diagnostics are displayed in the movement draft panel and finite decision panel
  using authoritative `proposal_validation` fields: violation code, message, and optional field.
- Rule-invalid movement retains the prior path only when the engine emits a fresh movement proposal
  with the same unit, proposal kind, source action request/result IDs, movement action,
  `movement_mode`, and Fall Back `fall_back_mode`. The retry draft is retargeted to the new request
  ID and must be marked ready again before resubmission.
- Unsupported non-movement parameterized requests remain visible but cannot be submitted through the
  movement payload path.
- No new engine proposal kind, finite option ID, payload shape, or visibility behavior was added;
  the existing adapter contract already covers this UI behavior.

## Automated verification

Focused checks run during implementation:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .
UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check .
UV_CACHE_DIR=/tmp/uv-cache uv run mypy src tests
UV_CACHE_DIR=/tmp/uv-cache uv run pyright
UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest \
  tests/test_movement_submission.py \
  tests/test_movement_draft.py \
  tests/test_hud_selection.py \
  tests/test_render_primitives.py \
  tests/test_core_client_protocol.py
```

Full PR gates should still be run before merge:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/
PRE_COMMIT_HOME=/tmp/pre-commit-cache UV_CACHE_DIR=/tmp/uv-cache uv run pre-commit run --all-files
```

## Manual validation checklist

Use the debug flow until a richer live-game harness is available:

```bash
WARHAMMER40K_ARCADE_UI_DEBUG_PHASE7=1 \
  uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/default.yaml
```

- Select the Intercessor unit, choose Normal Move from the context menu, and confirm that a
  movement draft opens for only the proposal unit.
- Move one model and press Enter once. Confirm the movement panel shows `Payload preview: ready`
  and model positions have not authoritatively changed.
- Press Enter a second time. With the debug fake client, confirm the status changes to
  `Debug movement accepted.`, the event log includes `movement_proposal_submitted`,
  `movement_proposal_accepted`, and `battlefield_projection_refreshed`, the movement draft clears,
  and model bases update from the submitted final poses. With a live movement-capable core client,
  accepted movement should clear the draft and update model bases from the refreshed engine
  projection.
- Trigger or simulate an invalid movement response and confirm the movement panel shows
  `Invalid: <violation_code> [<field>]: <message>`.
- For invalid movement that emits a same-context retry request, confirm the drafted paths remain
  visible but the payload must be marked ready again before resubmission.
- Confirm unsupported non-movement parameterized requests still show as unsupported and are not
  submitted through the movement tool.
