# Phase 4 — Selection and unit information HUD

## Goal

Select a unit/model and show useful information without submitting decisions yet.

## Tasks

- [ ] Implement click selection:
  - click model base
  - select owning unit
  - highlight selected unit
- [ ] Add selection cycling for overlapping bases.
- [ ] Add `SelectionState`.
- [ ] Add selected-unit panel:
  - unit name/id
  - model count
  - current position summary
  - available finite options, if a pending decision targets that unit
- [ ] Add radial/context menu prototype:
  - appears near selected unit or cursor
  - shows available actions from current pending finite request
  - disabled actions display reason if provided
- [ ] Add debug inspector toggle:
  - raw request id
  - selected unit id
  - proposal kind
  - cursor position
  - event cursor

## Acceptance criteria

- [ ] Clicking a model selects its unit.
- [ ] Selected unit is visually distinguishable.
- [ ] Unit panel updates when selection changes.
- [ ] Radial/context menu never invents options; it only displays engine-provided options.
- [ ] Tests verify hit detection and selection priority.
- [ ] Tests verify menu options are derived from pending decision data, not hard-coded rule assumptions.

## Closeout milestone

**Milestone 4: “Selectable Tactical View”**

A user can select a unit, inspect it, and see context-sensitive options provided by the engine.
