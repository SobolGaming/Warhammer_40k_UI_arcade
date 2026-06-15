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

## Manual validation checklist

Run the UI:

```bash
uv run warhammer40k-arcade-ui
```

Use the default fixture-backed battlefield and validate:

- [x] Left-click an Intercessor model base on the left side of the table.
  - Expected: the clicked model and owning unit are highlighted.
  - Expected: the selected-unit panel appears with `Intercessors`, `intercessor_squad`, model
    count, center position summary, and no available actions for the selected unit.
- [x] Left-click a Guardian model base on the right side of the table.
  - Expected: selection moves from Intercessors to Guardians.
  - Expected: the panel updates to `Guardians` / `guardian_squad`.
- [x] Left-click empty table space.
  - Expected: selection highlight clears.
  - Expected: selected-unit panel disappears.
- [x] Pan with right- or middle-mouse drag after selecting a unit.
  - Expected: camera moves while selection remains on the same projected unit.
- [x] Zoom with the mouse wheel after selecting a unit.
  - Expected: selection overlay scales with the battlefield and remains aligned to the model/unit.
- [x] Press `Ctrl+D`.
  - Expected: debug inspector toggles on/off.
  - Expected when on: request is `none`, selected unit matches the clicked unit or `none`, proposal
    kind is `none`, cursor coordinates update as the mouse moves, and event cursor is shown.
- [x] Press `U` after selecting a unit.
  - Expected: selected-unit information panel is visible. In the default profile this panel is
    already enabled, so this is mostly a smoke check that the configured hotkey does not disturb
    selection.
- [x] Press `M` after selecting a model.
  - Expected: selected model information is visible in the panel. In the default profile this is
    already enabled, so this is mostly a smoke check that the configured hotkey does not disturb
    selection.
- [x] Press `Esc` after selecting a unit.
  - Expected: any open local context menu closes. In the default launch there is no pending finite
    decision, so this is currently a no-op smoke check.

Automated-only or currently limited manual checks:

- [x] Overlap cycling is covered by `tests/test_selection_state.py` with overlapping model bases.
  The default launch fixture has no overlapping bases, so there is no quick manual overlap-cycling
  scenario yet.
- [x] Context menu option derivation is covered by `tests/test_hud_selection.py` with fake pending
  finite decisions. The default launch fixture has no pending finite decision, so there are no
  engine-provided options to show manually yet.
- [x] Disabled action reasons are covered by `tests/test_hud_selection.py`. Manual validation needs
  either live pending finite decisions with disabled options or a future debug fixture/harness.
