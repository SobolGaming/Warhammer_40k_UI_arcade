# Phase 8 — HUD ergonomics pass

## Goal

Improve decision-making speed and reduce cognitive load.

## Tasks

- [ ] Add selected-unit radial menu polish:
  - movement actions
  - inspect
  - measure
  - cancel
- [ ] Add range overlays:
  - movement budget
  - advance preview band, if data exists
  - weapon range rings as non-authoritative info overlays
- [ ] Add tooltip system:
  - action descriptions
  - invalid diagnostic explanation
  - model/unit id debug mode
- [ ] Add event log filtering:
  - current player
  - current phase
  - invalid diagnostics
- [ ] Add keyboard-first workflow:
  - select next unit
  - open action menu
  - confirm action
  - submit/cancel draft
- [ ] Add accessibility basics:
  - scalable HUD text
  - color-independent warning icons
  - high-contrast toggle

## Acceptance criteria

- [ ] A movement can be completed with mostly keyboard input.
- [ ] A movement can be completed with mostly mouse input.
- [ ] HUD labels distinguish authoritative facts from preview estimates.
- [ ] Radial menu is not required for functionality; there is also a panel/button path.
- [ ] Tests cover HUD view-model generation for selected unit and pending request.

## Closeout milestone

**Milestone 8: “Usable Movement Client”**

The UI is no longer only a technical prototype; it is comfortable enough for repeated manual
movement-phase testing.
