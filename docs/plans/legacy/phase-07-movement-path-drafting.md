# Phase 7 — Movement path drafting UI

## Goal

Let the user create a visible movement path before submitting it.

This is the first major Warhammer-specific interaction. The core repo treats `PathWitness` as
mandatory for movement/charge/pile-in/consolidate/disembark/reserves/reactive movement unless a
rule explicitly models teleport/setup placement.

## Contract review notes

Reviewed against `Warhammer_40k_AI` `main` at `16d0adf` on 2026-06-04.

- Phase 7 is only a drafting phase. It should create local draft state and a JSON-safe movement
  payload preview; engine submission remains a later movement proposal submission phase.
- Movement drafting activates only for `decision_type: "submit_movement_proposal"`.
  `submit_placement_proposal`, `submit_shooting_declaration`,
  `submit_stratagem_target_proposal`, and other parameterized requests must stay visible as
  proposal-required/unsupported-by-this-tool states until their own tools exist.
- Movement action finite options now carry explicit movement context. Normal Move and Advance keep
  default option IDs, Take to the Skies variants append `:fly_take_to_skies`, and Fall Back options
  are mode-scoped such as `fall_back:ordered_retreat` or `fall_back:desperate_escape`.
- A movement proposal request includes `movement_phase_action` plus context keys such as
  `source_selected_option_id`, `movement_mode`, and, for Fall Back, `fall_back_mode`. The draft
  state and payload builder must copy these engine-issued tokens exactly.
- The movement payload shape must include `proposal_request_id`, `proposal_kind`,
  `unit_instance_id`, `movement_phase_action`, `witness`, optional `model_movements`, and the
  engine-issued `movement_mode` / `fall_back_mode` when present in the request context.
- Local measurement and warning overlays remain advisory. They must not decide legality, invent
  movement modes, infer Fall Back modes, or transform placement proposals into endpoint-only
  movement validation.

## Tasks

- [x] Add `MovementDraft` state:
  - selected unit id
  - proposal request id
  - proposal kind
  - movement phase action
  - engine-issued movement mode, if present
  - engine-issued Fall Back mode, if present
  - source decision request/result ids
  - per-model path points
  - current cursor preview point
  - local-only validity hints
- [x] Activate drafting only when the current pending proposal is a movement proposal for the
  selected unit.
- [x] Implement movement tool modes:
  - unit-level simple path mode
  - model-level edit mode, deferred if too large
- [x] Add path interactions:
  - click to add waypoint
  - drag endpoint
  - right-click/remove last waypoint
  - Escape cancel draft
  - Enter marks the draft ready and builds the payload preview; it must not call the engine until
    the movement proposal submission phase wires submission.
- [x] Render:
  - movement path line
  - waypoints
  - final ghost base positions
  - movement budget ring/overlay
  - warning color/style for advisory local violations
- [x] Add measurement overlay:
  - segment length
  - total path length
  - remaining budget estimate
- [x] Keep local validation advisory:
  - endpoint distance estimate
  - table bounds estimate
  - obvious self-overlap indicator
  - engine remains authority
- [x] Add a payload builder for the current draft that emits the core contract shape and copies
  `movement_phase_action`, `movement_mode`, and `fall_back_mode` from the pending proposal request.
- [x] Display a clear unsupported-tool state for non-movement parameterized requests rather than
  attempting to draft a movement path for them.

## Acceptance criteria

- [x] Movement proposal request activates movement drafting mode.
- [x] Non-movement parameterized requests do not activate movement drafting mode.
- [x] User can create, edit, and cancel a path.
- [x] Draft path renders in world space and survives camera pan/zoom.
- [x] UI can build a JSON-safe movement payload shape.
- [x] Payload includes proposal request id, proposal kind, unit id, movement phase action, witness,
  and optional model movements.
- [x] Payload preserves engine-issued `movement_mode` and Fall Back `fall_back_mode` values when the
  pending request requires them.
- [x] Client-side warnings are clearly labeled as preview/advisory.
- [x] Tests verify movement draft state transitions.
- [x] Tests verify generated payload shape from a simple two-point path.
- [x] Tests verify Fall Back payload generation preserves the pending `fall_back_mode`.
- [x] Tests verify canceling draft does not submit anything.
- [x] Tests verify unsupported parameterized requests remain visible but do not create movement
  drafts.

## Closeout milestone

**Milestone 7: “Movement Path Planner”**

A user can select a unit, choose Normal Move, draft a movement path, preview the result, and prepare
an engine-compatible movement proposal payload.

## Implementation notes

Implemented on 2026-06-04.

- Added `state.movement_draft.MovementDraft` as local-only draft state for movement proposals.
  Draft activation is gated by the pending `submit_movement_proposal` request and selected unit.
- Added JSON-safe movement payload preview generation. The builder preserves
  `movement_phase_action`, `movement_mode`, and Fall Back `fall_back_mode` exactly as issued by the
  engine proposal request.
- Added movement draft world primitives for path lines, waypoints, endpoint preview, final ghost
  bases, and advisory movement-budget rings.
- Added a movement draft HUD panel with proposal context, segment/total/remaining measurements,
  ready state, and preview-only hints.
- Added input handling for waypoint creation, endpoint preview, right-click waypoint removal,
  Escape cancel, and Enter ready-state/payload-preview generation. Phase 7 does not submit the
  parameterized payload to the engine.
- Activated the `movement_path_draft` and `movement_budget` overlays in the preferences registry so
  users can bind and exchange them in YAML/JSON profiles.
- Added `WARHAMMER40K_ARCADE_UI_DEBUG_PHASE7=1` as an alias for the deterministic debug fixture used
  to manually exercise movement action selection and draft activation.

Known limitations deferred to later movement phases:

- Ready movement payloads are previewed locally but not submitted to the engine.
- Accepted movement does not update authoritative model positions until Phase 10 wires
  parameterized submission and projection refresh.
- Local hints are intentionally advisory and incomplete; the engine remains the only authority for
  legal movement.
- Model-level edit mode is represented as a draft mode but remains deferred for larger units.
- The current unit-simple draft interaction can move every model together. Phase 9 replaces this
  with explicit per-model and selected-subset movement assignment before engine submission.

## Verification

Focused validation completed during implementation:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest tests/test_movement_draft.py \
  tests/test_hud_selection.py tests/test_render_primitives.py tests/test_selection_state.py \
  tests/test_debug_fixtures.py tests/test_entrypoint.py
UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest tests/test_preferences.py
```

Full repository gates completed during PR preparation:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .
UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check .
UV_CACHE_DIR=/tmp/uv-cache uv run pyright
UV_CACHE_DIR=/tmp/uv-cache uv run mypy src tests
UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest
UV_CACHE_DIR=/tmp/uv-cache PRE_COMMIT_HOME=/tmp/pre-commit-cache uv run pre-commit run --all-files
```

Result: all commands passed. The full pytest run collected 75 tests and passed them all.

## Manual validation checklist

Use the deterministic debug fixture:

```bash
WARHAMMER40K_ARCADE_UI_DEBUG_PHASE7=1 uv run warhammer40k-arcade-ui \
  --ui-prefs docs/preferences/default.yaml
```

- [x] Select a model from the visible infantry unit.
- [x] Open the selected-unit actions menu with Space.
- [x] Choose the Normal Move finite option.
- [x] Confirm the finite choice with Enter.
- [x] Verify the HUD changes to a movement draft/proposal-required panel for the selected unit.
- [x] Left-click on the table to add movement waypoints.
- [x] Move the mouse and verify the endpoint preview follows the cursor.
- [x] Verify movement path, waypoint, final ghost base, and movement budget overlays render in world
  space.
- [x] Pan or zoom the camera and verify the path remains anchored to the table.
- [x] Right-click without dragging to remove the last waypoint.
- [x] Press Enter and verify the panel reports the draft as ready; no authoritative model movement
  should occur in Phase 7.
- [x] Press Escape and verify the local draft clears.
- [x] Try a non-movement parameterized request, if available in a later fixture, and verify it is
  shown as unsupported by the movement draft tool rather than activating movement drafting.
