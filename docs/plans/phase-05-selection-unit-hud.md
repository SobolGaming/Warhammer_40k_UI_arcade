# Phase 5 — Selection and unit information HUD

## Goal

Select a unit/model and show useful information without submitting decisions yet.

This phase should consume the Phase 4 preferences framework for default selection overlays,
selected-model/unit information panel defaults, debug inspector defaults, and configured local
selection hotkeys.

This phase does not change the core adapter decision contract. It may display the current
engine-provided finite request and options, but it must not submit options, invent options, invent
proposal kinds, or locally validate game rules.

## Tasks

- [x] Implement click selection:
  - click model base
  - select owning unit
  - highlight selected unit/model through Phase 4 overlay IDs now activated by this phase
- [x] Add selection cycling for overlapping bases.
- [x] Add `SelectionState`.
- [x] Add selected-unit panel:
  - unit name/id
  - model count
  - current position summary
  - available finite options, if a pending decision targets that unit
- [x] Add radial/context menu prototype:
  - appears near selected unit or cursor
  - shows available actions from current pending finite request
  - disabled actions display reason if provided
  - does not submit actions until the finite decision submission phase
- [x] Add debug inspector toggle:
  - raw request id
  - selected unit id
  - proposal kind
  - cursor position
  - event cursor
- [x] Apply relevant Phase 4 preferences:
  - default overlays when a model is selected;
  - default overlays when a unit is selected;
  - selected-model and selected-unit information panel defaults;
  - selection cycling and debug inspector hotkeys.
  - ignore recognized-but-inactive future-facing preference fields.

## Acceptance criteria

- [x] Clicking a model selects its unit.
- [x] Selected unit is visually distinguishable.
- [x] Unit panel updates when selection changes.
- [x] Radial/context menu never invents options; it only displays engine-provided options.
- [x] Tests verify hit detection and selection priority.
- [x] Tests verify menu options are derived from pending decision data, not hard-coded rule assumptions.
- [x] Tests verify selection behavior consumes typed preferences and ignores inactive future-facing
  preference fields.

## Closeout milestone

**Milestone 5: “Selectable Tactical View”**

A user can select a unit, inspect it, and see context-sensitive options provided by the engine.

## Implementation notes

Implemented in Phase 5:

- `warhammer40k_arcade_ui.state.selection` owns local-only `SelectionState`, model-base hit
  detection, overlap cycling, active overlay defaults, panel visibility, and context/debug toggles.
- `warhammer40k_arcade_ui.input.commands` maps Phase 4 hotkey bindings into local command
  invocations.
- `warhammer40k_arcade_ui.hud.view_models` derives selected-unit panels, finite-option context
  menus, and debug inspector lines from projection data, local selection state, and current pending
  decisions.
- `warhammer40k_arcade_ui.render.primitives` renders selected-unit/model overlays plus unit panel,
  context menu, and debug inspector text primitives.
- `ArcadeWarhammerWindow` loads preferences, selects projected model bases with the configured
  default mouse button, applies configured hotkeys, and keeps decision context menu actions
  display-only.

Phase 5 activates the `selected_model` and `selected_unit` overlay IDs. Planned overlays and
future-facing settings remain ignored until their implementing phases provide data and behavior.

This phase did not update the core adapter decision contract because it does not add or submit any
player-facing decisions. The context menu displays only existing engine-provided finite options for
the selected unit.

## Verification

Ran the following checks after implementation:

- `uv run ruff format .`
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run pyright`
- `uv run mypy src tests`
- `uv run pytest`
- `uv run pre-commit run --all-files`
