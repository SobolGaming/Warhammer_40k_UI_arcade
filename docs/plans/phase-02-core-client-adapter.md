# Phase 2 — Core client adapter layer

## Goal

Isolate Arcade from the engine’s adapter/session contract.

Build the UI around a small internal client facade rather than letting render/input code call the
engine directly. The core contract is centered on `DecisionRequest`, finite submissions,
parameterized submissions, movement/placement proposal payloads, `GameViewPayload`, and
viewer-scoped event deltas.

## Tasks

- [ ] Create `core_client/protocol.py` with UI-facing typed structures:
  - `UiGameView`
  - `UiDecision`
  - `UiFiniteOption`
  - `UiMovementProposalRequest`
  - `UiInvalidDiagnostic`
- [ ] Create `core_client/local_session_client.py`.
- [ ] Implement a local/in-process client wrapper:
  - `start_game(...)`
  - `advance_until_decision_or_terminal()`
  - `get_view(viewer_player_id)`
  - `get_events_since(cursor, viewer_player_id)`
  - `submit_finite(request_id, selected_option_id)`
  - `submit_movement_payload(request_id, payload)`
- [ ] Preserve explicit `request_id` in all submission calls.
- [ ] Convert engine-facing payloads into simple UI view models.
- [ ] Add a fake/mock client for UI testing without launching a real game.

## Acceptance criteria

- [ ] UI modules do not import engine internals directly.
- [ ] All user choices flow through the client facade.
- [ ] All submissions include `request_id`.
- [ ] Stale or invalid responses can be represented in UI state.
- [ ] Unit tests prove the client facade can represent:
  - no pending decision
  - finite decision
  - movement proposal request
  - invalid movement diagnostic
  - terminal state

## Closeout milestone

**Milestone 2: “Engine Boundary Stable”**

The UI has a narrow, testable boundary to the core engine and can later swap local in-process mode
for WebSocket/network mode.
