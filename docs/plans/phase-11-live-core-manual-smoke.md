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

- [x] Review the current `Warhammer_40k_AI` local-session and adapter contracts before
  implementation and record the core commit reviewed.
- [x] Identify the smallest stable core game setup API or fixture that can produce a movement-phase
  pending decision.
- [x] Add a live-core smoke startup factory isolated behind `core_client` or an adjacent launch
  module that does not leak mutable engine internals into render, HUD, input, or local state.
- [x] Add a CLI flag and README command for the smoke mode.
- [x] Start `LocalSessionClient`, call the real game/session start path, and advance until a pending
  decision or terminal status.
- [x] Fetch the initial viewer-scoped projection and event cursor through the UI-facing client
  protocol.
- [x] Bind the existing finite-decision, movement-draft, movement-submission, projection-refresh,
  and diagnostics flow to that live client.
- [x] Add typed startup diagnostics for missing core fixtures, unsupported setup shape, no pending
  movement-capable decision, or projection payloads the current renderer cannot represent.
- [x] Add tests for:
  - CLI/config selection of live-core smoke mode;
  - smoke startup factory behavior using stable core fixture APIs where possible;
  - import-boundary checks proving live core imports remain isolated from render/HUD/input/state;
  - unsupported startup diagnostics.
- [x] Update manual validation instructions after implementation.

## Acceptance Criteria

- [x] `uv run warhammer40k-arcade-ui --live-core-smoke --ui-prefs docs/preferences/default.yaml`
  launches through the real local core path.
- [x] The UI shows the real pending decision from the smoke game rather than a fake debug request.
- [x] Selecting an engine-provided movement option preserves the exact request ID and option ID.
- [x] Drafting and submitting a movement proposal calls the real core parameterized submission path.
- [x] Accepted movement clears the local draft and refreshes model positions from the real
  projection.
- [x] Invalid movement shows authoritative core diagnostics without locally committing the draft.
- [x] Unsupported live-core setup/projection states produce typed visible diagnostics.
- [x] Default fake/debug workflows continue to work for deterministic UI tests.
- [x] Full repository gates pass.

## Tests

- [x] CLI argument tests for live-core smoke mode.
- [x] Live smoke startup tests at the `core_client` boundary, using real core fixture/factory APIs
  if available.
- [x] State-flow regression tests proving Phase 10 movement submission works with a live-client
  shaped response.
- [x] Static/import-boundary test keeping mutable core imports out of render, HUD, input, and local
  UI state.
- [x] Diagnostic tests for missing or unsupported live smoke setup.

## Contract Review Notes

Reviewed `Warhammer_40k_AI` at `603fb16` on 2026-06-05:

- `docs/ADAPTER_DECISION_CONTRACT.md`
- `docs/DECISION_SUBMISSION_CATALOG.md`
- `src/warhammer40k_core/adapters/local_session.py`
- movement lifecycle tests around `select_movement_unit`, `select_movement_action`, and
  `submit_movement_proposal`.

Relevant contract points:

- Movement remains a two-step finite path followed by a parameterized movement proposal:
  `select_movement_unit` -> `select_movement_action` -> `submit_movement_proposal`.
- `select_movement_action` emits engine-provided options including `normal_move`, `advance`, and
  `remain_stationary`; Normal Move and Advance always require `submit_movement_proposal`.
- The proposal request uses the fixed `submit_parameterized_payload` option and the UI must preserve
  the explicit request ID at the UI boundary.
- Movement `PathWitness` payloads must contain non-endpoint path evidence for moved straight
  segments. Phase 11 updated the UI movement draft serializer to include midpoint evidence for
  simple moved segments while preserving explicit start/end no-op paths for unchanged models.
- The core `LocalGameSession` still has helper methods that infer the pending request, but the UI
  wrapper continues to construct `FiniteOptionSubmission` and `ParameterizedSubmission` directly
  with explicit request IDs.
- The live smoke setup uses the core canonical Phase 9A content pack and Chapter Approved 2025-26
  mission setup. The UI does not define rules or legal actions.

## Manual Validation Checklist

After implementation:

- [ ] Launch:

  ```bash
  uv run warhammer40k-arcade-ui --live-core-smoke --ui-prefs docs/preferences/default.yaml
  ```

- [ ] Confirm the table label begins with `Live Core` and the finite-decision HUD is not showing a
  `phase6`/`phase10` fake debug request.
- [ ] Confirm the finite-decision HUD starts at real `select_movement_unit` with the option
  `army-alpha:intercessor-unit-1`.
- [ ] Press Enter to select the engine-emitted movement unit option.
- [ ] Click a player-a model on the table, open the selected-unit actions menu, and choose
  `Normal Move`.
- [ ] Select the whole unit, draft a short translated path, press Enter once, and confirm only a
  local payload preview is ready.
- [ ] Press Enter again and confirm the engine response either advances to the next live pending
  decision, such as a Fire Overwatch reaction prompt, or shows an authoritative invalid diagnostic.
- [ ] If accepted, confirm local draft overlays clear and model bases move only after projection
  refresh.
- [ ] If invalid, confirm the diagnostic code/message comes from the engine and the draft remains
  available for retry when the engine emits a compatible retry request.
- [ ] Confirm diagonal live-core terrain slots render as rotated footprints rather than large
  axis-aligned overlap boxes. The engine still owns authoritative terrain occupancy; this visual
  footprint comes from core source rotation provenance when present.

## Implementation Closeout

Implemented on 2026-06-05.

- Added `--live-core-smoke` as an explicit CLI launch mode.
- Added `core_client.live_smoke` to construct a real local core smoke game using
  `LocalSessionClient`, the canonical core content pack, Chapter Approved 2025-26 mission setup,
  and explicit UI request/result IDs.
- The startup harness advances through both fixed-secondary setup choices into the first real
  `select_movement_unit` decision, then passes the real client/status/view/event cursor into the
  Arcade window.
- Added `render.core_projection` to build a renderable `BattlefieldView` from the viewer-scoped
  core `GameViewPayload` shape, including mission table dimensions, deployment zones, objective
  markers, terrain footprints, and placed units/models.
- Live-core terrain rendering now uses core source rotation/origin provenance for visible ruin
  footprints when that provenance matches the projected engine footprint bounds. If no recognized
  provenance is present, the UI falls back to the engine-projected axis-aligned footprint.
- The existing finite-decision, context menu, movement draft, movement submission, authoritative
  diagnostics, event refresh, and projection-refresh paths are reused; no new decision IDs,
  proposal kinds, or validation paths were added.
- Real-core accepted movement now has automated coverage: a whole-unit Normal Move payload is
  submitted through `LocalSessionClient.submit_movement_payload`, emits
  `movement_activation_completed`, and advances into the live Fire Overwatch reaction proposal.
- Follow-up core projection/parser failures are now handled as fatal engine/client errors at the
  Arcade window boundary. The HUD shows `Fatal game engine error`, logs the traceback, and closes the
  window cleanly after a short delay instead of allowing the exception to unwind through Pyglet.

## Post-Implementation Core Impact Review

Reviewed `Warhammer_40k_AI` `main` at `2d4d730` on 2026-06-05.

- The core projection now includes normalized `pending_proposal` metadata for parameterized
  requests. The earlier missing-`request_id` follow-up projection issue should now be treated as
  resolved in the engine contract; the UI should keep treating a missing request ID as a fatal
  contract error rather than adding fallback submission behavior.
- New live-core features after the movement smoke path include Charge Move proposals and Fight
  phase finite activation/interrupt decisions. They are outside this phase's manual smoke scope,
  but later live smoke scripts should add coverage for them once their UI tools exist.

## Automated Verification

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest \
  tests/test_live_core_smoke.py \
  tests/test_entrypoint.py \
  tests/test_core_client_local_session.py
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .
UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check .
UV_CACHE_DIR=/tmp/uv-cache uv run mypy src tests
UV_CACHE_DIR=/tmp/uv-cache uv run pyright
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/
PRE_COMMIT_HOME=/tmp/pre-commit-cache UV_CACHE_DIR=/tmp/uv-cache uv run pre-commit run --all-files
```

## Closeout Milestone

**Milestone 11: "Live Core Movement Smoke"**

A human reviewer can manually exercise the real local core movement decision path from launch to
movement proposal response without leaving the Arcade UI.
