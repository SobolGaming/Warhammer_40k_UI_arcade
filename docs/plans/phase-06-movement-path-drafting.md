# Phase 6 — Movement path drafting UI

## Goal

Let the user create a visible movement path before submitting it.

This is the first major Warhammer-specific interaction. The core repo treats `PathWitness` as
mandatory for movement/charge/pile-in/consolidate/disembark/reserves/reactive movement unless a
rule explicitly models teleport/setup placement.

## Tasks

- [ ] Add `MovementDraft` state:
  - selected unit id
  - proposal request id
  - proposal kind
  - per-model path points
  - current cursor preview point
  - local-only validity hints
- [ ] Implement movement tool modes:
  - unit-level simple path mode
  - model-level edit mode, deferred if too large
- [ ] Add path interactions:
  - click to add waypoint
  - drag endpoint
  - right-click/remove last waypoint
  - Escape cancel draft
  - Enter submit draft
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

## Acceptance criteria

- [ ] Movement proposal request activates movement drafting mode.
- [ ] User can create, edit, and cancel a path.
- [ ] Draft path renders in world space and survives camera pan/zoom.
- [ ] UI can build a JSON-safe movement payload shape.
- [ ] Payload includes proposal request id, proposal kind, unit id, and witness.
- [ ] Client-side warnings are clearly labeled as preview/advisory.
- [ ] Tests verify movement draft state transitions.
- [ ] Tests verify generated payload shape from a simple two-point path.
- [ ] Tests verify canceling draft does not submit anything.

## Closeout milestone

**Milestone 6: “Movement Path Planner”**

A user can select a unit, choose Normal Move, draft a movement path, preview the result, and prepare
an engine-compatible movement proposal payload.
