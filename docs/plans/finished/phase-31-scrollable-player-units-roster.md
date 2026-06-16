# Phase 31: Scrollable Player Units Roster

Status: Implemented

## Purpose

Replace the current left-rail roster placeholder with a useful, scrollable Player Units panel.

The panel should show the viewer player's projected units as clickable roster buttons. Clicking a
roster button should select the matching battlefield unit, and selecting a battlefield unit should
highlight the matching roster button. This creates a reusable reciprocal-selection pattern for
future panels that need to mirror battlefield entities.

This phase also introduces generic two-axis scroll support for HUD panels and containers, but the
default live HUD should enable scrolling only for the Player Units panel.

## Scope

In scope:

- configurable scroll capability for HUD containers and panels in the x and y directions;
- scroll state keyed by stable widget/component ID;
- mouse wheel, shifted wheel, and test-driver scroll routing for HUD scroll regions;
- scissor-clipped scroll rendering that keeps child content inside the panel bounds;
- runtime player roster data built from the current viewer-scoped battlefield projection;
- Player Units roster buttons with a placeholder circular status icon and unit name;
- click-to-select behavior from roster button to battlefield unit;
- reciprocal highlight behavior from battlefield unit selection to roster button state;
- default HUD composition change so Player Units is the only scroll-enabled element;
- tests and preview evidence for overflowing roster content.

Out of scope:

- full army-list, wargear, enhancements, reserves, or attachment display;
- local game-rule status such as "moved", "battle-shocked", "eligible to shoot", or Stratagem
  eligibility unless the core projection already exposes safe viewer-scoped presentation data;
- opponent roster browsing beyond existing visible projection data;
- changing engine decisions, finite option IDs, proposal payloads, or authoritative state;
- pan/zooming the battlefield when the pointer is over a scrollable HUD element.

## Current State

`default-hud` currently places two related elements in `left_rail`:

- `Player Units`, an unbound static `IconTextBar` header;
- `Player roster`, a placeholder `UnitRailCard` bound to `player_roster`.

The `player_roster` runtime binding is not a real roster. It summarizes the selected unit or prompts
the user to select a unit. That makes the panel look like a roster while behaving more like a
selection status label.

The HUD customization guide already accepts `overflow.mode: scroll` in YAML, but current rendering
treats it as clipped content. This phase turns scroll into real behavior for configured containers
and panels.

## Core And Projection Assumptions

The UI already receives viewer-scoped `BattlefieldView.units`, where each `UnitView` includes:

- `unit_id`;
- `player_id`;
- `label`;
- model base projections.

For `--live-core-smoke`, the viewer player is known from startup and the projection contains player
and opponent units. The Player Units panel must filter the roster to units whose `player_id` matches
the current viewer player when that information is available.

If a future projection changes how viewer ownership is represented, the UI should adapt in the
runtime data adapter. The HUD YAML must not filter hidden information or infer ownership rules.

## Configuration Model

Add a reusable scroll configuration to HUD composition YAML. The recommended shape is a dedicated
`scroll` object on widgets that can contain children:

```yaml
type: HudContainer
id: player_units_panel
scroll:
  enabled: true
  axes: y
  wheel_axis: y
  show_scrollbars: auto
  wheel_step_px: 48
  clamp_to_content: true
```

Required scroll fields:

- `enabled`: boolean flag. When false or absent, the widget is not scrollable.
- `axes`: `x`, `y`, or `both`.

Optional scroll fields:

- `wheel_axis`: `x`, `y`, or `auto`. Default `y`.
- `show_scrollbars`: `never`, `auto`, or `always`.
- `wheel_step_px`: positive pixel distance per wheel notch.
- `drag_scrollbars`: boolean, default false for the first implementation unless dragging is added in
  the same slice.
- `clamp_to_content`: boolean, default true.

Compatibility rule:

- `overflow.mode: scroll` may remain accepted as schema, but real interactive scrolling should be
  driven by `scroll.enabled` so text overflow behavior and child-container scroll behavior stay
  separate.

Default HUD requirement:

- `left_rail` should contain one Player Units roster container or panel with `scroll.enabled: true`.
- Other default HUD panels should keep `scroll.enabled` absent or false.

## UX Model

The left rail should show one Player Units panel:

```text
Player Units

(status) Intercessor Unit 1
(status) Intercessor Unit 3
(status) Infernus Unit 5
...
```

Each row is a clickable button:

- left side: placeholder circular status icon;
- body: unit name;
- optional compact secondary text later, such as model count or status;
- selected unit: selected/highlight visual matching the current HUD theme;
- hovered row: hover visual;
- unavailable/hidden rows: not rendered unless the projection exposes them to the viewer.

Click behavior:

- clicking a roster row selects the matching battlefield unit;
- the selection should choose a stable representative model only if the existing selection model
  rules require one, otherwise it can select the unit without forcing a model;
- clicking a roster row does not submit an engine decision by itself;
- clicking a roster row may update a pending finite option only through the existing reciprocal
  selection mechanism, when the highlighted request exposes a matching option.

Reciprocal behavior:

- selecting a unit on the battlefield highlights the corresponding roster button;
- selecting or cycling a Current Action button that focuses a unit also highlights the roster
  button;
- after an authoritative state transition selects/focuses a different unit, the roster highlight
  follows that selected unit;
- if the selected unit is outside the current scroll viewport, the first implementation should at
  least support a deterministic helper to bring it into view. Auto-scroll-on-selection may be added
  in the same phase if it does not cause distracting jumps.

## Implementation Slices

1. **Scrollable widget schema**
   - Add a typed scroll configuration model for HUD widgets that can own children.
   - Validate `enabled`, axes, scrollbar mode, wheel step, and clamp behavior.
   - Emit composition diagnostics for malformed scroll config instead of ignoring it.

2. **Scroll layout measurement**
   - Teach the toolkit renderer to distinguish viewport rect from content rect.
   - Measure child content extent for vertical stacks, horizontal stacks, and grids enough to know
     whether scrollbars are needed.
   - Keep existing non-scroll layout behavior unchanged when scroll is disabled.

3. **Scroll rendering**
   - Apply x and y scroll offsets before rendering child primitives.
   - Keep scissor clipping active so scrolled children cannot draw outside the panel.
   - Render optional simple scrollbars when configured as `auto` or `always`.
   - Ensure HUD preview and live game use the same rendering path.

4. **Scroll input routing**
   - Add HUD scroll hit regions with component ID, viewport rect, content extent, enabled axes, and
     current offset.
   - Route mouse wheel events to the topmost scrollable HUD region under the pointer before
     battlefield zoom.
   - Support y scrolling by default and x scrolling through horizontal wheel or shifted wheel.
   - Add deterministic event-driver methods for scroll input.

5. **Roster runtime data**
   - Replace the placeholder `player_roster` binding with a real viewer-unit list built from
     `BattlefieldView.units`.
   - Filter by current viewer player where `player_id` is known.
   - Include unit ID, unit label, model count, selected flag, focused flag, placeholder status icon,
     and optional compact status text.
   - Keep the data JSON-safe and presentation-only.

6. **Roster button widget**
   - Reuse the Phase 27 HUD button infrastructure where possible.
   - Add or configure a roster row button that renders a circular placeholder icon plus unit label.
   - Store hit regions with action kind such as `select_unit`, plus unit ID in diagnostic metadata.
   - Keep the visual implementation generic enough to support future roster-like panels.

7. **Selection routing**
   - On roster row click, update local `SelectionState` to the matching unit.
   - Keep the existing finite-option reciprocal focus behavior intact.
   - If a pending finite request has exactly one option matching the selected unit, let the existing
     finite highlight synchronization select that option.
   - Trace roster click and selection events in the forensic event log without introducing an
     engine decision result.

8. **Reciprocal highlight**
   - Highlight the roster row that matches `SelectionState.selected_unit_id`.
   - Ensure battlefield clicks, Current Action button focus, keyboard option cycling, and
     authoritative finite-state transitions all update the roster selected visual through the same
     selected-unit source of truth.
   - Add a small helper for optional scroll-to-selected behavior if implemented.

9. **Default composition cleanup**
   - Replace the current left-rail header-plus-placeholder pair with one Player Units roster panel.
   - Enable scrolling only for that panel in the built-in default HUD composition.
   - Keep command-bench composition unchanged unless it also has an explicit Player Units roster
     region.

10. **Preview and documentation**
   - Add a HUD preview sample with enough units to overflow the Player Units panel.
   - Update `docs/hud-customization.md` with scroll config fields and the Player Units roster data
     binding.

## Acceptance Criteria

- HUD composition YAML can mark a panel/container scrollable in `x`, `y`, or `both` directions.
- Scroll-disabled panels behave as they do today.
- The built-in default HUD enables scrolling only for the Player Units panel.
- The Player Units panel is populated from viewer-scoped projected units at startup in
  `--live-core-smoke`.
- Each player unit row is a clickable button with a placeholder circular status icon followed by
  the unit name.
- Clicking a roster button selects the matching battlefield unit without submitting an engine
  decision.
- Battlefield selection highlights the matching roster button.
- Current Action focus that selects a unit also highlights the matching roster button.
- The roster remains viewer-scoped and does not expose hidden or opponent-only information.

## Automated Verification

Add or update tests for:

- scroll config parsing and diagnostics;
- scroll-enabled versus scroll-disabled render behavior;
- scissor clipping of scrolled child content;
- y scrolling and x scrolling input routing;
- battlefield zoom not firing when the pointer scrolls over a HUD scroll region;
- Player Units roster runtime data filtered by viewer player;
- roster row hit regions and click-to-select behavior;
- reciprocal highlight from battlefield selection to roster button state;
- reciprocal highlight from Current Action option focus to roster button state;
- a headless preview/render evidence test with enough roster rows to overflow.

Run the normal gates:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pyright
uv run pytest tests/
uv run pre-commit run --all-files
```

## Manual Validation Checklist

- Launch `uv run warhammer40k-arcade-ui --live-core-smoke --ui-prefs docs/preferences/default.yaml`.
- Confirm the left rail has a Player Units panel, not separate Player Units and Player roster
  placeholders.
- Confirm player units appear at startup.
- Scroll the Player Units panel when there are more units than fit.
- Click a roster row and verify the matching battlefield unit is selected/highlighted.
- Click a battlefield unit and verify the matching roster row highlights.
- Use Current Action buttons or `TAB` during movement unit selection and verify the roster highlight
  follows the focused unit.
- Scroll over a non-scrollable HUD panel and verify it does not scroll.
- Scroll over the battlefield and verify battlefield zoom still works when the pointer is not over
  the Player Units panel.

## Reviewer Notes

Review should focus on keeping scroll and roster selection local and presentation-only. Roster
buttons are navigation and selection affordances, not gameplay decisions. They must not submit
engine results, invent unit legality, or reveal units outside the viewer-scoped projection.

## Implementation Notes

- Added typed HUD scroll configuration (`scroll.enabled`, axes, wheel behavior, scrollbar
  visibility, step size, and content clamping).
- Added frame-local HUD scroll hit regions and routed mouse wheel input over scrollable HUD regions
  before battlefield zoom.
- Added `PlayerUnitsRoster` as a first-class HUD toolkit widget using existing HUD button
  primitives and hit regions.
- Replaced the default left-rail header/placeholder pair with one scroll-enabled Player Units
  roster panel in both packaged and docs HUD profiles.
- Added viewer-scoped player-unit roster runtime data under `hud.player_units.roster` while keeping
  the legacy `player_roster` key mapped to the same data.
- Added local roster-row click selection through the existing `SelectionState` and finite-option
  highlight synchronization path.
- Added a standalone overflowing roster preview in
  `docs/hud/examples/player-units-roster-preview.yaml`.
- Updated `docs/hud-customization.md` with scroll configuration and PlayerUnitsRoster guidance.

## Verification Notes

- Added toolkit tests for scroll config parsing, invalid scroll diagnostics, PlayerUnitsRoster
  rendering, row hit regions, and scroll-region metadata.
- Added ergonomic HUD tests proving the player roster filters to the viewer player and marks the
  selected unit row.
- Added GUI event-driver tests proving roster buttons select matching battlefield units and roster
  wheel input does not zoom the battlefield.
