# Phase 2 — Core client adapter layer

## Goal

Isolate Arcade from the engine’s adapter/session contract.

Build the UI around a small internal client facade rather than letting render/input code call the
engine directly. The core contract is centered on `DecisionRequest`, finite submissions,
parameterized submissions, movement/placement proposal payloads, `GameViewPayload`, and
viewer-scoped event deltas.

## Tasks

- [x] Create `core_client/protocol.py` with UI-facing typed structures:
  - `UiGameView`
  - `UiDecision`
  - `UiFiniteOption`
  - `UiMovementProposalRequest`
  - `UiInvalidDiagnostic`
- [x] Create `core_client/local_session_client.py`.
- [x] Implement a local/in-process client wrapper:
  - `start_game(...)`
  - `advance_until_decision_or_terminal()`
  - `get_view(viewer_player_id)`
  - `get_events_since(cursor, viewer_player_id)`
  - `submit_finite(request_id, selected_option_id)`
  - `submit_movement_payload(request_id, payload)`
- [x] Preserve explicit `request_id` in all submission calls.
- [x] Convert engine-facing payloads into simple UI view models.
- [x] Add a fake/mock client for UI testing without launching a real game.

## Acceptance criteria

- [x] UI modules do not import engine internals directly.
- [x] All user choices flow through the client facade.
- [x] All submissions include `request_id`.
- [x] Stale or invalid responses can be represented in UI state.
- [x] Unit tests prove the client facade can represent:
  - no pending decision
  - finite decision
  - movement proposal request
  - invalid movement diagnostic
  - terminal state

## Closeout milestone

**Milestone 2: “Engine Boundary Stable”**

The UI has a narrow, testable boundary to the core engine and can later swap local in-process mode
for WebSocket/network mode.

## Implementation notes

- Added `warhammer40k-core-v2` as an editable local dependency through
  `../Warhammer_40k_AI`.
- Added `warhammer40k_arcade_ui.core_client.protocol` with JSON-safe UI dataclasses and the
  `UiCoreClient` protocol.
- Added `warhammer40k_arcade_ui.core_client.local_session_client.LocalSessionClient`.
- Added `warhammer40k_arcade_ui.core_client.fake_client.FakeCoreClient` for future render/input/HUD
  tests that should not start a real engine session.
- `LocalSessionClient.submit_finite(...)` and `LocalSessionClient.submit_movement_payload(...)`
  require the UI-supplied `request_id`. They do not call the core helper methods that infer the
  pending request ID. Instead they validate stale request drift at the UI boundary and construct
  `FiniteOptionSubmission` or `ParameterizedSubmission` with the explicit request ID before
  submitting through `GameLifecycle.submit_decision(...)`.
- Request-ID drift, no-pending-request submissions, finite submissions against parameterized
  requests, parameterized submissions against finite requests, unsupported parameterized decision
  types, and non-pending finite option IDs are represented as `UiClientStatus.invalid(...)`.
- Engine proposal diagnostics are converted into `UiInvalidDiagnostic` values for display by later
  HUD phases.

## Verification

- `uv lock`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run pyright`
- `uv run mypy src tests`
- `uv run pytest`
- `uv run pre-commit run --all-files`
