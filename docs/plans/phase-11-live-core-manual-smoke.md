# Phase 11 - Live core manual smoke path

## Goal

Add an opt-in launch mode that uses the real `Warhammer_40k_AI` local session path for thin manual
end-to-end testing.

In plain language: Phase 10 proves the UI can build and submit a movement proposal through the UI
client boundary. The default debug fixture is still fake, so it cannot prove that the current core
engine accepts, rejects, mutates, advances, and projects a real game. This phase adds a small live
core smoke harness so a human reviewer can launch the UI, reach a real pending decision, submit a
real movement proposal, and see the engine's actual response or diagnostics.

This is not a rules shortcut and not a second game setup system. The UI should use approved core
factory/session APIs and treat the core projection as authoritative.

## Scope

- Add an explicit opt-in runtime mode, such as `--live-core-smoke`, that selects the real local
  session smoke harness instead of the debug fake client.
- Use `LocalSessionClient` and the core engine lifecycle path; do not duplicate lifecycle,
  validation, event, replay, or mutation logic in the UI.
- Load or construct one canonical minimal game configuration through approved core APIs or stable
  core fixtures.
- Advance to the first viewer-scoped pending decision and bind that status/view to the existing
  Arcade window.
- Support the movement smoke path only:
  - select an engine-provided finite movement action;
  - draft per-model movement paths;
  - submit the movement payload from Phase 10;
  - display accepted status, refreshed projection, or authoritative diagnostics.
- Keep the default launch and fake debug launch behavior unchanged.

## Non-Goals

- No new proposal kinds, finite option IDs, or adapter-visible payload shapes.
- No UI-owned movement legality checks.
- No automatic test coverage for every graphical interaction.
- No shooting, charge, fight, Stratagem, scoring, AI, replay, or network workflow.
- No broad compatibility layer for arbitrary core game configurations yet.

## Tasks

- [ ] Review the current `Warhammer_40k_AI` local-session and adapter contracts before
  implementation and record the core commit reviewed.
- [ ] Identify the smallest stable core game setup API or fixture that can produce a movement-phase
  pending decision.
- [ ] Add a live-core smoke startup factory isolated behind `core_client` or an adjacent launch
  module that does not leak mutable engine internals into render, HUD, input, or local state.
- [ ] Add a CLI flag and README command for the smoke mode.
- [ ] Start `LocalSessionClient`, call the real game/session start path, and advance until a pending
  decision or terminal status.
- [ ] Fetch the initial viewer-scoped projection and event cursor through the UI-facing client
  protocol.
- [ ] Bind the existing finite-decision, movement-draft, movement-submission, projection-refresh,
  and diagnostics flow to that live client.
- [ ] Add typed startup diagnostics for missing core fixtures, unsupported setup shape, no pending
  movement-capable decision, or projection payloads the current renderer cannot represent.
- [ ] Add tests for:
  - CLI/config selection of live-core smoke mode;
  - smoke startup factory behavior using stable core fixture APIs where possible;
  - import-boundary checks proving live core imports remain isolated from render/HUD/input/state;
  - unsupported startup diagnostics.
- [ ] Update manual validation instructions after implementation.

## Acceptance Criteria

- [ ] `uv run warhammer40k-arcade-ui --live-core-smoke --ui-prefs docs/preferences/default.yaml`
  launches through the real local core path.
- [ ] The UI shows the real pending decision from the smoke game rather than a fake debug request.
- [ ] Selecting an engine-provided movement option preserves the exact request ID and option ID.
- [ ] Drafting and submitting a movement proposal calls the real core parameterized submission path.
- [ ] Accepted movement clears the local draft and refreshes model positions from the real
  projection.
- [ ] Invalid movement shows authoritative core diagnostics without locally committing the draft.
- [ ] Unsupported live-core setup/projection states produce typed visible diagnostics.
- [ ] Default fake/debug workflows continue to work for deterministic UI tests.
- [ ] Full repository gates pass.

## Tests

- [ ] CLI argument tests for live-core smoke mode.
- [ ] Live smoke startup tests at the `core_client` boundary, using real core fixture/factory APIs
  if available.
- [ ] State-flow regression tests proving Phase 10 movement submission works with a live-client
  shaped response.
- [ ] Static/import-boundary test keeping mutable core imports out of render, HUD, input, and local
  UI state.
- [ ] Diagnostic tests for missing or unsupported live smoke setup.

## Manual Validation Checklist

After implementation:

- [ ] Launch:

  ```bash
  uv run warhammer40k-arcade-ui --live-core-smoke --ui-prefs docs/preferences/default.yaml
  ```

- [ ] Confirm the debug panel indicates a live core smoke profile/client, not the fake debug client.
- [ ] Confirm the pending decision shown in the HUD matches an engine-provided movement decision.
- [ ] Select one model, draft a path, press Enter once, and confirm only a local payload preview is
  ready.
- [ ] Press Enter again and confirm the engine response is visible as accepted or invalid.
- [ ] If accepted, confirm local draft overlays clear and model bases move only after projection
  refresh.
- [ ] If invalid, confirm the diagnostic code/message comes from the engine and the draft remains
  available for retry when the engine emits a compatible retry request.

## Closeout Milestone

**Milestone 11: "Live Core Movement Smoke"**

A human reviewer can manually exercise the real local core movement decision path from launch to
movement proposal response without leaving the Arcade UI.
