# Phase 3 — Arcade rendering foundation

## Goal

Render a battlefield that can be panned, zoomed, and inspected without interaction complexity.

## Tasks

- [ ] Implement `ArcadeWarhammerWindow`.
- [ ] Add world-space camera:
  - pan
  - zoom
  - screen-to-world coordinate conversion
  - world-to-screen coordinate conversion
- [ ] Render table bounds.
- [ ] Render deployment zones as optional translucent overlays.
- [ ] Render objectives.
- [ ] Render terrain footprints as simple polygons/rectangles.
- [ ] Render units as placeholder tokens.
- [ ] Render model bases as circles or ellipses.
- [ ] Add a basic HUD layer independent of the world camera:
  - phase label
  - active player
  - pending decision summary
  - event log stub

## Acceptance criteria

- [ ] The app launches to a visible battlefield.
- [ ] Pan and zoom do not distort table coordinates.
- [ ] World coordinates are displayed under the mouse for debugging.
- [ ] Placeholder unit/model rendering works from fixture data.
- [ ] HUD remains fixed while the battlefield camera moves.
- [ ] Rendering code is testable where practical:
  - coordinate conversion tests
  - camera clamp/zoom tests
  - view-model-to-render-primitive tests

## Closeout milestone

**Milestone 3: “Inspectable Battlefield”**

A user can launch the UI, pan/zoom around the table, and visually inspect placeholder units,
objectives, and terrain.
