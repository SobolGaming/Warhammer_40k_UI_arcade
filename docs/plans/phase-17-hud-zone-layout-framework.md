# Phase 17 - HUD zone layout framework

## Goal

Create a configurable Arcade-native HUD layout framework made of named screen zones, regions, and
panels, without yet filling those panels with rich gameplay content.

In plain language: this phase builds the empty sockets that future HUD content can plug into. The
player-facing window should stop being a collection of independently positioned debug text blocks
and start becoming a stable layout made of reusable regions. Later phases can place command points,
mission cards, unit rails, inspectors, dice workbenches, assignment summaries, icons, and debug
surfaces into those regions.

The immediate motivation is the Phase 16 Assignment Review HUD colliding with movement/proposal
draft text. Both information sets are useful, but they should not compete for the same pixels. The
layout framework should make those collisions structurally harder by giving each class of
information an explicit home.

## Guidance Basis

This phase should follow the guidance in:

- `docs/guidance/UI_HUD_DESIGN.md`
- `docs/guidance/ICON_GRAPHICS_SYSTEM.md`

The design guidance points toward stable HUD geography:

- fixed top ribbon for persistent game state;
- left and right rails for roster/mission/inspection information;
- bottom workbench or command bench for current action resolution;
- battlefield center reserved for spatial overlays;
- Arcade-native widgets and layouts instead of an embedded browser;
- design tokens and icon slots that can later receive rasterized SVG textures.

## Relationship To Later Phases

This phase is deliberately only about structure:

- build named regions, layout presets, style tokens, and empty placeholder widgets;
- do not implement the real CP display, army list, mission cards, datasheet inspector, dice
  resolver, Stratagem tray, or unit rolodex content;
- do not change decision submission, engine payloads, rule validation, or authoritative state;
- do not move action visual summary overlays into this phase.

Phase 18 can then draw action visual summaries on the battlefield without fighting panel placement.
Phase 19 can populate and polish HUD ergonomics using these stable regions.

## Terminology

- **HUD zone:** a named high-level area of the screen, such as `top_ribbon`, `left_rail`,
  `right_inspector`, `bottom_workbench`, `player_bench`, or `opponent_bench`.
- **HUD region:** a specific rectangular allocation within a zone, such as `score_cluster`,
  `mission_hand`, `unit_rail`, `selected_unit_summary`, or `assignment_review`.
- **HUD panel:** the Arcade widget container that can later hold real widgets, text, icons, buttons,
  or render primitives.
- **Layout preset:** a complete arrangement of zones and regions, selected by preferences.
- **Zone content key:** a stable label for what a region is intended to hold later, such as
  `placeholder.assignment_review`, `placeholder.unit_rail`, or `placeholder.action_workbench`.

## Arcade Widget Notes

Arcade GUI widgets have useful parent/child composition, but they are not a browser DOM:

- `UIManager` owns widgets and event routing.
- `UIWidget`, `UIAnchorLayout`, `UIBoxLayout`, and `UIGridLayout` expose child relationships.
- `UIAnchorLayout` maps well to fixed screen edges.
- `UIBoxLayout` maps well to rails, ribbons, and benches.
- `UIGridLayout` maps well to regular stat/card grids.
- The installed Arcade package exposes `arcade.gui.experimental.UIScrollArea`; use it only after
  proving it works in the current version and headless tests.
- Clipping should be treated as an explicit implementation requirement, not an assumed DOM-like
  property. Use Arcade GUI scroll/viewport support where stable, or a tested render-surface/scissor
  approach for dense future panels.

Acceptance for this phase should include a small clipping/overflow proof so future panels can rely
on known behavior.

## Layout Presets

### Compass Ring

This preset keeps the battlefield dominant and uses all four edges as an instrument cluster.

```text
top_ribbon:
  opponent_missions | score_phase_timer | player_missions

left_rail:
  army_rolodex / reserves tabs / unit state placeholders

center_viewport:
  battlefield and spatial overlays only

right_inspector:
  selected unit / target comparison / rules lookup placeholders

bottom_workbench:
  action workbench / dice resolver / stratagem tray placeholders
```

Expected empty-zone outcome:

- visible top ribbon;
- visible left rail;
- visible right inspector;
- visible bottom workbench;
- center board area remains visibly clear;
- region labels are placeholder/debug labels only until later content phases fill them.

### Command Bench

This preset gives the bottom command surface more space and splits player/opponent planning rails.

```text
top_ribbon:
  compact active player / round / phase / timer / score placeholders

left_player_bench:
  player roster / CP / missions / reserves placeholders

center_viewport:
  battlefield and spatial overlays only

right_opponent_bench:
  opponent missions / roster / visible status placeholders

bottom_command_bench:
  selected unit / target / weapons / stratagems / dice pipeline / action history placeholders
```

Expected empty-zone outcome:

- visible compact top ribbon;
- visible player and opponent benches;
- larger full-width bottom command bench;
- center board area remains cleaner than in the Compass Ring preset;
- bottom bench is ready for later mode-specific content.

## Preferences And Configuration

Add configuration for layout selection and zone characteristics through the existing preferences
framework. Preferences remain presentation-only.

Suggested schema direction:

```yaml
hud:
  layout_preset: compass_ring
  zones:
    top_ribbon:
      visible: true
      size_px: 64
      collapsed: false
    left_rail:
      visible: true
      size_px: 220
      collapsed: false
    right_inspector:
      visible: true
      size_px: 260
      collapsed: false
    bottom_workbench:
      visible: true
      size_px: 150
      collapsed: false
```

Configuration must not:

- define legal actions;
- invent engine request or option IDs;
- change hidden-information visibility;
- mutate game state;
- select engine-side validation behavior.

Unknown layout presets, unknown zone IDs, and invalid dimensions should produce typed preference
diagnostics instead of silent fallback.

## Implementation Slices

### Slice A - Zone Model And Presets

- [x] Add typed HUD zone/region/panel configuration models.
- [x] Add a layout preset registry with `compass_ring` and `command_bench`.
- [x] Define default dimensions, minimum dimensions, visibility, collapse state, and safe labels.
- [x] Add preference parsing and export support for layout preset and zone overrides.
- [x] Add config diagnostics for unknown presets, unknown zones, and invalid sizes.

### Slice B - Arcade Widget Containers

- [x] Add an Arcade GUI root layout that can host named zone containers.
- [x] Add placeholder panel widgets for each configured region.
- [x] Keep placeholder panels visually quiet and clearly temporary.
- [x] Prove resizing/rebuilding works when the window size changes.
- [x] Prove panels do not overlap the center battlefield viewport.

### Slice C - Two Preset Layouts

- [x] Implement the Compass Ring preset.
- [x] Implement the Command Bench preset.
- [x] Add built-in preference profiles or example YAML files for both presets.
- [x] Add a debug label or preference-visible name so reviewers can confirm which preset is active.
- [x] Ensure existing debug/proposal/assignment text can be parked in placeholder regions or hidden
  while the region skeleton is visible.

### Slice D - Clipping And Overflow Proof

- [x] Add a small overflow test widget with deliberately too much placeholder text.
- [x] Verify whether `UIScrollArea`, Arcade surfaces, or another tested approach provides the
  clipping behavior needed for future dense panels.
- [x] Record the chosen clipping policy in this plan or architecture docs.
- [x] Add deterministic tests for region bounds and overflow behavior where possible.

### Slice E - Test And Evidence Support

- [x] Add pure tests for layout preset geometry at multiple window sizes.
- [x] Add preference tests for layout profile parsing and diagnostics.
- [x] Add render primitive or headless render tests confirming the two skeleton layouts produce
  expected screen regions.
- [x] Add a manual validation checklist for toggling between layout profiles.

## Acceptance Criteria

- [x] Preferences can select `compass_ring` or `command_bench`.
- [x] Preferences can configure known zone visibility, size, and collapsed state.
- [x] Unknown layout presets and unknown zone IDs produce typed diagnostics.
- [x] Both layouts render visible empty placeholder zones without filling real gameplay content.
- [x] The center battlefield viewport is preserved and not covered by non-spatial panels.
- [x] Placeholder panels can later accept text, icons, buttons, and other Arcade widgets.
- [x] A clipping/overflow strategy is proven or explicitly documented as future work with the risk
  called out.
- [x] Existing player-facing controls still work when the layout skeleton is visible.
- [x] No authoritative game state, decision submission, or engine payload behavior changes.

## Tests

- [x] Unit tests for zone preset registry and geometry calculation.
- [x] Unit tests for preference parsing, export, and invalid-zone diagnostics.
- [x] Render primitive or headless evidence tests for Compass Ring bounds.
- [x] Render primitive or headless evidence tests for Command Bench bounds.
- [x] Regression test that assignment/proposal placeholder regions do not overlap.
- [x] Overflow/clipping proof test for a panel with content larger than its bounds.

## Manual Validation Checklist

- [ ] Launch with the default layout and confirm the Compass Ring zones appear.
- [ ] Launch with the Command Bench profile and confirm the bottom command bench is larger.
- [ ] Resize the window and confirm zones remain anchored and do not cover the board center.
- [ ] Confirm movement selection/drafting still receives keyboard and mouse input.
- [ ] Confirm placeholder labels are visible enough for review but not styled like final content.
- [ ] Confirm a malformed layout profile reports config diagnostics.

## Closeout Milestone

**Milestone 13: "Configurable HUD Shell"**

The UI has a configurable, Arcade-native skeleton for placing future HUD content in stable,
swappable regions. It includes two working layout presets from the HUD design guidance but does not
yet populate those regions with final player-facing content.

## Implementation Closeout

Implemented on 2026-06-05.

- Added HUD-layout geometry in `warhammer40k_arcade_ui.hud.layouts` with named
  screen-space regions, center-viewport preservation, zone collapse/visibility, and line-capacity
  helpers for overflow-aware panel text.
- Added `warhammer40k_arcade_ui.hud.widgets` as a lazy `arcade.gui.UIManager` integration that
  draws quiet placeholder widget sockets in the live Arcade window. The module is imported only
  when an actual window is constructed so ordinary headless tests do not import `arcade.gui`.
- Added preference schema support for:
  - `hud.layout_preset`
  - `hud.zones.<zone_id>.visible`
  - `hud.zones.<zone_id>.size_px`
  - `hud.zones.<zone_id>.collapsed`
- Added the `command-bench` built-in/exportable preference profile and documented
  `docs/preferences/command-bench.yaml`.
- Anchored existing technical HUD text into the configured regions:
  - top state lines in the top ribbon;
  - finite/movement panels in the left rail or command-bench columns;
  - assignment review in the action workbench or command-bench column;
  - selected-unit/debug panels in the inspector/opponent bench.
- Proved current overflow behavior with deterministic line clipping and a `... N more` marker.
  This is not the final rich scrollable widget behavior; later content phases can replace the
  text-line policy with tested scroll areas or surface/scissor clipping.

Automated tests added or updated:

- layout geometry tests for Compass Ring, Command Bench, oversized-zone scaling, and collapsed
  zones;
- preference tests for layout preset round-trip and invalid layout/zone diagnostics;
- render primitive tests for the zone skeleton and assignment-review clipping.

Manual validation checklist:

- [x] Launch `uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/default.yaml` and confirm
  the Compass Ring sockets appear.
- [x] Launch `uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/command-bench.yaml` and
  confirm the Command Bench bottom region appears.
- [x] Resize the window and confirm the sockets rebuild cleanly.
- [x] Select a model/unit and confirm ordinary selection still works.
- [x] Start a movement draft and confirm proposal, movement, and assignment text no longer occupy
  the exact same left-column stack.
