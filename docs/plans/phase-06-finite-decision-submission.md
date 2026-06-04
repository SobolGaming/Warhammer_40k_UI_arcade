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

- [x] Implement a generic finite-decision view model:
  - current request ID
  - decision type
  - actor ID
  - labeled finite options
  - selected/highlighted option cursor
  - parameterized-request indicator for future proposal phases
- [x] Implement finite option buttons in the HUD from pending request options.
- [x] Implement radial/context menu finite option selection from pending request options.
- [x] Keep movement action labels as data from the engine request, not hard-coded UI rules.
- [x] Do not render parameterized `submit_parameterized_payload` as a finite action button; display
  it as “proposal required” or equivalent pending state until later phases add the payload tool.
- [x] On selection:
  - create a UI result ID
  - submit selected option ID with the current request ID
  - refresh status, viewer-scoped view, and viewer-scoped event delta
- [x] Display success, invalid, stale, or terminal status.
- [x] Add event log panel from viewer-scoped event deltas and persist the next event cursor.
- [x] Surface follow-up pending requests after a finite answer, including parameterized proposal
  requests created by choosing a movement action.
- [x] Add keyboard shortcuts:
  - Escape cancels local UI selection/menu state
  - Enter confirms highlighted finite option
  - Tab cycles selectable units/options without creating a new selection from hover state
- [x] Add tests for generic finite-decision rendering across at least:
  - movement action selection
  - a non-movement finite decision type
  - parameterized proposal pending state

## Acceptance criteria

- [x] User can select a finite option from the UI.
- [x] Submission includes the current request ID and exact selected option ID.
- [x] UI refreshes after accepted submission.
- [x] Stale/invalid submission response is visible and does not silently disappear.
- [x] UI does not submit when the pending request is parameterized.
- [x] UI does not depend on movement-only option IDs or decision types.
- [x] A finite movement-action answer can advance into a visible pending movement proposal request
  without the UI trying to fabricate a proposal payload.
- [x] Event log entries come from viewer-scoped event deltas and update the stored cursor.
- [x] Tests verify exact submitted option id and request id.
- [x] Tests verify UI cannot submit when no pending request exists.
- [x] Tests verify UI cannot submit a non-existent option id.
- [x] Tests verify UI cannot submit a finite result for a parameterized request.
- [x] Tests verify Tab does not select a merely hovered model while cycling option focus.

## Manual Validation Checklist

Normal launch remains fixture-backed and has no pending engine request:

```bash
uv run warhammer40k-arcade-ui
```

- [x] Confirm the app still launches to the fixture battlefield.
- [x] Confirm the decision panel shows a ready/no-pending state and the existing fixture event lines.
- [x] Hover over a model without selecting it and press Tab.
  - Expected: no model is selected from hover alone.

Use the opt-in Phase 6 debug fixture for finite-decision manual validation:

```bash
WARHAMMER40K_ARCADE_UI_DEBUG_PHASE6=1 uv run warhammer40k-arcade-ui
```

- [x] Confirm a finite pending request appears in the HUD with request ID, decision type, actor, and
  options.
- [x] Press Tab.
  - Expected: option focus moves between Normal Move and Advance.
  - Expected: no model is selected merely because the mouse is hovering over a model.
- [x] Press Enter while Normal Move is highlighted.
  - Expected: the UI submits `decision-request-phase6-debug-000001` /
    `normal_move` / `ui-result-000001` through the fake UI client.
  - Expected: the HUD refreshes to a parameterized movement proposal state and does not move
    fixture model positions.
- [x] Confirm the parameterized movement proposal request is displayed as requiring a proposal tool,
  not as a clickable finite action.
- [x] Confirm event log lines advance with the viewer-scoped `decision_recorded` event summary.
- [ ] Launch with
  `WARHAMMER40K_ARCADE_UI_DEBUG_PHASE6=1 uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/keyboard-heavy.yaml`,
  select the Intercessors, press Space to open selected-unit actions, and click a context-menu
  action.
  - Expected: enabled actions submit through the same finite path.

Stale/invalid engine-result display is covered by automated tests with fake and local clients. A
future live-game/debug harness should add a quick manual stale-request scenario once live projection
binding exists.

## Closeout milestone

**Milestone 6: “Authoritative Finite Decision UI”**

The UI can answer engine-provided finite decisions correctly and visibly handles invalid/stale
outcomes.

## Implementation Notes

Completed on 2026-06-03.

- Added `warhammer40k_arcade_ui.state.finite_decision` for local finite-option focus,
  deterministic `ui-result-*` generation, UI-boundary invalid diagnostics, status refresh, and
  viewer-scoped event cursor/log state.
- Added `warhammer40k_arcade_ui.debug_fixtures` plus
  `WARHAMMER40K_ARCADE_UI_DEBUG_PHASE6=1` launch support for manual finite-decision validation in
  the current fixture-backed app.
- Extended `core_client.protocol` with `UiParameterizedProposalRequest` so generic parameterized
  proposals can be displayed without forcing every parameterized request through the movement
  proposal parser. Movement proposal parsing remains available when the proposal payload has the
  movement/placement shape.
- Added a generic finite-decision HUD panel that shows request ID, decision type, actor, focused
  finite options, parameterized proposal-required state, and invalid diagnostics.
- Wired `ArcadeWarhammerWindow` to submit finite options through an injected `UiCoreClient`, using
  explicit current request IDs and engine-provided option IDs only.
- Context menu actions can submit finite options when a client is configured; disabled actions
  surface a local diagnostic rather than submitting.
- Enter confirms the highlighted finite option. Tab cycles finite-option focus when finite options
  exist; otherwise it only cycles an already selected overlapping hit set. This fixes the hover-only
  Tab selection behavior observed after Phase 5.
- Event lines are derived from viewer-scoped event deltas and persist the next cursor. They display
  compact event type/player or event type/status summaries rather than full payload dumps.

This phase did not update the core adapter decision contract because it implements the existing
finite decision and parameterized proposal display contracts without adding new option families,
proposal kinds, payload shapes, or visibility behavior.

## Verification

Ran after implementation:

- `UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest tests/test_finite_decision_state.py tests/test_hud_selection.py tests/test_render_primitives.py tests/test_selection_state.py tests/test_core_client_protocol.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest tests/test_debug_fixtures.py`

Full quality-gate results should be recorded before PR handoff.
