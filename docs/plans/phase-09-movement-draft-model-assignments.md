# Phase 9 - Movement draft model assignments

## Goal

Replace the current all-model synchronized movement draft with independent model-path assignment.

In plain language: when the player is moving a unit, they should be able to say "move this model,"
"move these three models together," or "move the whole unit" deliberately. The UI should collect
those model paths into one movement proposal, but it should not assume that selecting one model means
every model in the unit moves in the same way.

## Contract Review Notes

Reviewed against the local `Warhammer_40k_AI` checkout on 2026-06-04.

- `MovementProposalPayload` supports a `PathWitness` containing independent `model_paths`.
- The engine validates movement budgets, coherency, terrain, engagement rules, movement mode, Fall
  Back mode, and all authoritative legality.
- The UI must preserve `proposal_request_id`, `proposal_kind`, `unit_instance_id`,
  `movement_phase_action`, optional `movement_mode`, and optional `fall_back_mode` from the pending
  proposal request.
- The UI must not submit movement yet in this phase. Submission remains Phase 10.

## Prerequisites

- Phase 8 `EntityRef`, `EntitySelectionProfile`, and `EntitySelectionState`.
- Existing Phase 7 `MovementDraft` payload preview and render primitive support.

## Tasks

- [x] Refactor `MovementDraft` from unit-simple translation into per-model assignments:
  - model ID;
  - starting pose;
  - path points;
  - final pose;
  - assigned group ID or assignment batch ID.
- [x] Create a movement assignment workspace:
  - proposal request ID;
  - movement context;
  - proposal unit model refs;
  - active selected model subset;
  - drafted paths by model;
  - assignment group IDs for subsets drafted together;
  - unassigned or unchanged model hints;
  - payload preview.
- [x] Seed movement request-selection from the currently inspected model when that model belongs to
  the proposal unit.
- [x] Support movement assignment modes:
  - one selected model receives a path;
  - multiple selected models receive the same translated path;
  - whole-unit layer intentionally assigns the same translated path to all current models;
  - separate model subsets can receive separate paths in the same proposal.
- [x] Update input behavior during active movement draft:
  - normal click selects/replaces the active movement model subset;
  - Shift-click adds models to the active subset;
  - Ctrl-click removes models from the active subset;
  - waypoint click applies only to the active subset;
  - right-click removes the last waypoint for the active subset;
  - Escape cancels the active draft or clears the active subset according to workspace state.
- [x] Update movement payload preview:
  - include independent `witness.model_paths`;
  - include `model_movements` for every proposal-unit model, including unchanged models;
  - preserve engine-issued movement context tokens;
  - avoid endpoint-only movement validation.
- [x] Decide and document no-op model handling:
  - include unchanged models as explicit start/end no-op paths in `witness.model_paths`;
  - include unchanged models as explicit start/end no-op paths in `model_movements`;
  - do not omit any proposal-unit model from either payload collection.
- [x] Render request-selection separately from inspect selection:
  - active movement-selected models;
  - assigned but inactive models;
  - unassigned models in the proposal unit;
  - per-model ghost final bases;
  - per-model path colors or group colors.
- [x] Update advisory hints:
  - estimated path length by active selection;
  - model assignment completeness;
  - estimated over-budget path;
  - obvious table-bound and self-overlap warnings;
  - "engine validates movement" reminder.
- [x] Expose movement visual-summary data for later Phase 13:
  - per-model path points;
  - final ghost-base poses;
  - active assignment group;
  - assigned/unassigned state;
  - advisory warning state;
  - grouped-path relationships for subsets drafted together.
- [x] Remove or retire the old `unit_simple` default as an accidental behavior.

## Acceptance Criteria

- [x] Selecting one model and adding waypoints moves only that model in the preview.
- [x] Shift-selecting multiple models and adding waypoints moves only that subset.
- [x] Selecting all models through an explicit unit-layer or select-all command moves the whole unit.
- [x] Different model subsets can have different drafted paths in one movement proposal.
- [x] Payload preview contains independent model paths for each drafted model.
- [x] Payload preview includes every proposal-unit model in both `witness.model_paths` and
  `model_movements`.
- [x] Unchanged models are represented as explicit start/end no-op paths in both payload
  collections.
- [x] Engine-issued movement context is preserved exactly.
- [x] The UI does not submit the movement payload in this phase.
- [x] Local hints are visually and textually advisory.
- [x] Existing camera pan/zoom and world-space path rendering continue to work.
- [x] Movement assignment state can be converted into a summary-friendly view model without reading
  mutable engine internals.

## Tests

- [x] One-model movement draft state transition.
- [x] Multi-model subset movement draft state transition.
- [x] Whole-unit explicit movement assignment.
- [x] Separate subset paths in one proposal.
- [x] Removing the last waypoint from one subset does not erase other subset paths.
- [x] Payload preview with independent model paths.
- [x] Fall Back payload preview preserves `fall_back_mode`.
- [x] Request drift clears or reconciles movement assignments.
- [x] Render primitive tests for active, assigned, and unassigned movement selection overlays.
- [x] HUD view-model tests for assignment completeness and advisory hints.
- [x] Tests for movement visual-summary source data generated from assignment groups.
- [x] Regression tests that unchanged models remain explicit start/end no-op paths in both
  `witness.model_paths` and `model_movements`.

## Manual Validation Checklist

- [x] Start the deterministic movement debug fixture with
  `WARHAMMER40K_ARCADE_UI_DEBUG_PHASE7=1 uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/default.yaml`.
- [x] Select one model, choose Normal Move, click empty table space, and confirm only that model
  gets a path preview.
- [x] Shift-click a second model in the same unit, click empty table space, and confirm both
  selected models move together.
- [x] Click another model without Shift, draft a different path, and confirm earlier model paths
  remain.
- [x] Press `g` to select the current model's group, draft a path, and confirm all models move only
  after that explicit group-selection command.
- [x] Right-click while a subset is active and confirm the last waypoint is removed only for that
  active subset.
- [x] Press Enter and inspect the ready payload preview; no engine submission should occur yet.
- [x] Confirm unchanged models are shown as no-op in the preview payload once the debug payload
  viewer exists in Phase 10; until then this is covered by automated payload tests.

## Closeout Milestone

**Milestone 9: "Per-Model Movement Planner"**

The UI can build a single movement proposal preview from independently drafted model paths.

## Implementation Closeout

Completed on 2026-06-04.

Implemented:

- Refactored `MovementDraft` to `model_assignments` mode with request-scoped
  `EntitySelectionState`, per-model `MovementModelPath` rows, assignment group IDs, active subset
  operations, and summary-friendly `MovementAssignmentView` rows.
- Wired active movement selection into Arcade input:
  - model click replaces the active subset;
  - Shift-click adds a model;
  - Ctrl-click removes a model;
  - empty-table click adds a waypoint for the active subset;
  - right-click removes the last waypoint for the active subset;
  - `g` selects the current model group;
  - Tab cycles request-scoped movement focus when no finite options are pending.
- Updated movement render primitives for active, assigned, and unassigned request-selection
  overlays, per-model paths, ghost bases, and active-model budget rings.
- Updated the movement draft HUD with active model IDs, assignment completeness, unchanged no-op
  counts, and advisory hints.
- Updated payload preview generation so every proposal-unit model appears in both
  `witness.model_paths` and `model_movements`; unchanged models are explicit start/end no-op paths.

Verification during implementation:

- `UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest tests/test_movement_draft.py tests/test_render_primitives.py tests/test_hud_selection.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check .`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pyright`
- `UV_CACHE_DIR=/tmp/uv-cache uv run mypy src tests`

Reviewer notes:

- This phase still does not submit the movement payload. Phase 10 remains responsible for engine
  submission and authoritative diagnostics.
- Movement hints, path lengths, out-of-bounds checks, and overlap warnings are advisory UI preview
  information only.
- The most important review point is the no-op payload invariant: unchanged models must remain
  explicit start/end no-op paths in both payload collections.
