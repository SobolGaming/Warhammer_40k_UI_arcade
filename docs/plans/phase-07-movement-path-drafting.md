# Phase 7 — Movement path drafting UI

## Goal

Let the user create a visible movement path before submitting it.

This is the first major Warhammer-specific interaction. The core repo treats `PathWitness` as
mandatory for movement/charge/pile-in/consolidate/disembark/reserves/reactive movement unless a
rule explicitly models teleport/setup placement.

## Contract review notes

Reviewed against `Warhammer_40k_AI` `main` at `16d0adf` on 2026-06-04.

- Phase 7 is only a drafting phase. It should create local draft state and a JSON-safe movement
  payload preview; engine submission remains Phase 8.
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

- [ ] Add `MovementDraft` state:
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
- [ ] Activate drafting only when the current pending proposal is a movement proposal for the
  selected unit.
- [ ] Implement movement tool modes:
  - unit-level simple path mode
  - model-level edit mode, deferred if too large
- [ ] Add path interactions:
  - click to add waypoint
  - drag endpoint
  - right-click/remove last waypoint
  - Escape cancel draft
  - Enter marks the draft ready and builds the payload preview; it must not call the engine until
    Phase 8 wires submission.
- [ ] Render:
  - movement path line
  - waypoints
  - final ghost base positions
  - movement budget ring/overlay
  - warning color/style for advisory local violations
- [ ] Add measurement overlay:
  - segment length
  - total path length
  - remaining budget estimate
- [ ] Keep local validation advisory:
  - endpoint distance estimate
  - table bounds estimate
  - obvious self-overlap indicator
  - engine remains authority
- [ ] Add a payload builder for the current draft that emits the core contract shape and copies
  `movement_phase_action`, `movement_mode`, and `fall_back_mode` from the pending proposal request.
- [ ] Display a clear unsupported-tool state for non-movement parameterized requests rather than
  attempting to draft a movement path for them.

## Acceptance criteria

- [ ] Movement proposal request activates movement drafting mode.
- [ ] Non-movement parameterized requests do not activate movement drafting mode.
- [ ] User can create, edit, and cancel a path.
- [ ] Draft path renders in world space and survives camera pan/zoom.
- [ ] UI can build a JSON-safe movement payload shape.
- [ ] Payload includes proposal request id, proposal kind, unit id, movement phase action, witness,
  and optional model movements.
- [ ] Payload preserves engine-issued `movement_mode` and Fall Back `fall_back_mode` values when the
  pending request requires them.
- [ ] Client-side warnings are clearly labeled as preview/advisory.
- [ ] Tests verify movement draft state transitions.
- [ ] Tests verify generated payload shape from a simple two-point path.
- [ ] Tests verify Fall Back payload generation preserves the pending `fall_back_mode`.
- [ ] Tests verify canceling draft does not submit anything.
- [ ] Tests verify unsupported parameterized requests remain visible but do not create movement
  drafts.

## Closeout milestone

**Milestone 7: “Movement Path Planner”**

A user can select a unit, choose Normal Move, draft a movement path, preview the result, and prepare
an engine-compatible movement proposal payload.
