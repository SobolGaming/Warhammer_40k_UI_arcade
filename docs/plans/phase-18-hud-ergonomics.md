# Phase 18 - HUD ergonomics pass

## Goal

Improve decision-making speed and reduce cognitive load.

This phase should consume the Phase 4 preferences framework, the Phase 16 generic assignment HUD,
and the Phase 17 action visual summaries for overlay defaults, HUD defaults, assignment review,
summary overlays, and hotkeys instead of hard-coding user workflow assumptions into render, input,
or HUD modules.

## Tasks

- [ ] Add selected-unit radial menu polish:
  - movement actions
  - inspect
  - measure
  - cancel
- [ ] Add range overlays using configured defaults where available:
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
  - honor configured hotkeys for known commands and overlays
- [ ] Add accessibility basics:
  - scalable HUD text
  - color-independent warning icons
  - high-contrast toggle
- [ ] Add preference-aware HUD affordances:
  - apply configured selected-model and selected-unit panels;
  - apply configured default overlay sets;
  - surface config diagnostics in a non-authoritative diagnostics view.

## Acceptance criteria

- [ ] A movement can be completed with mostly keyboard input.
- [ ] A movement can be completed with mostly mouse input.
- [ ] HUD labels distinguish authoritative facts from preview estimates.
- [ ] Radial menu is not required for functionality; there is also a panel/button path.
- [ ] Configured overlay defaults and hotkeys route through stable command/overlay registries.
- [ ] Tests cover HUD view-model generation for selected unit and pending request.

## Closeout milestone

**Milestone 14: "Usable Movement Client"**

The UI is no longer only a technical prototype; it is comfortable enough for repeated manual
movement-phase testing.
