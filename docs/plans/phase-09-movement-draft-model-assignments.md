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

- [ ] Refactor `MovementDraft` from unit-simple translation into per-model assignments:
  - model ID;
  - starting pose;
  - path points;
  - final pose;
  - assigned group ID or assignment batch ID.
- [ ] Create a movement assignment workspace:
  - proposal request ID;
  - movement context;
  - proposal unit model refs;
  - active selected model subset;
  - drafted paths by model;
  - unassigned or unchanged model hints;
  - payload preview.
- [ ] Seed movement request-selection from the currently inspected model when that model belongs to
  the proposal unit.
- [ ] Support movement assignment modes:
  - one selected model receives a path;
  - multiple selected models receive the same translated path;
  - whole-unit layer intentionally assigns the same translated path to all current models;
  - separate model subsets can receive separate paths in the same proposal.
- [ ] Update input behavior during active movement draft:
  - normal click selects/replaces the active movement model subset;
  - Shift-click adds models to the active subset;
  - Ctrl-click removes models from the active subset;
  - waypoint click applies only to the active subset;
  - right-click removes the last waypoint for the active subset;
  - Escape cancels the active draft or clears the active subset according to workspace state.
- [ ] Update movement payload preview:
  - include independent `witness.model_paths`;
  - include `model_movements` for models with drafted movement;
  - preserve engine-issued movement context tokens;
  - avoid endpoint-only movement validation.
- [ ] Decide and document no-op model handling:
  - include unchanged models as explicit no-op witness paths; or
  - omit unchanged models from `model_movements` while preserving witness compatibility.
- [ ] Render request-selection separately from inspect selection:
  - active movement-selected models;
  - assigned but inactive models;
  - unassigned models in the proposal unit;
  - per-model ghost final bases;
  - per-model path colors or group colors.
- [ ] Update advisory hints:
  - estimated path length by active selection;
  - model assignment completeness;
  - estimated over-budget path;
  - obvious table-bound and self-overlap warnings;
  - "engine validates movement" reminder.
- [ ] Remove or retire the old `unit_simple` default as an accidental behavior.

## Acceptance Criteria

- [ ] Selecting one model and adding waypoints moves only that model in the preview.
- [ ] Shift-selecting multiple models and adding waypoints moves only that subset.
- [ ] Selecting all models through an explicit unit-layer or select-all command moves the whole unit.
- [ ] Different model subsets can have different drafted paths in one movement proposal.
- [ ] Payload preview contains independent model paths for each drafted model.
- [ ] Engine-issued movement context is preserved exactly.
- [ ] The UI does not submit the movement payload in this phase.
- [ ] Local hints are visually and textually advisory.
- [ ] Existing camera pan/zoom and world-space path rendering continue to work.

## Tests

- [ ] One-model movement draft state transition.
- [ ] Multi-model subset movement draft state transition.
- [ ] Whole-unit explicit movement assignment.
- [ ] Separate subset paths in one proposal.
- [ ] Removing the last waypoint from one subset does not erase other subset paths.
- [ ] Payload preview with independent model paths.
- [ ] Fall Back payload preview preserves `fall_back_mode`.
- [ ] Request drift clears or reconciles movement assignments.
- [ ] Render primitive tests for active, assigned, and unassigned movement selection overlays.
- [ ] HUD view-model tests for assignment completeness and advisory hints.

## Manual Validation Checklist

- [ ] Start the deterministic movement debug fixture.
- [ ] Select one model, choose Normal Move, and confirm only that model gets a path preview.
- [ ] Shift-select a second model and confirm both selected models move together.
- [ ] Select the rest of the unit separately and draft a different path.
- [ ] Use the explicit whole-unit selection command and confirm all models move only when that
  command is used.
- [ ] Remove a waypoint for the active subset and confirm other model paths remain.
- [ ] Press Enter and inspect the ready payload preview; no engine submission should occur yet.

## Closeout Milestone

**Milestone 9: "Per-Model Movement Planner"**

The UI can build a single movement proposal preview from independently drafted model paths.
