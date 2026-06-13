# Phase 23 - HUD toolkit customizability and overflow control

## Status

Implemented in PR `codex/phase23-hud-toolkit-customizability`.

This phase is presentation-only. It must not change core-client payloads, decision submission,
engine validation, request IDs, option IDs, proposal kinds, visibility rules, or authoritative game
state.

## Goal

Make HUD toolkit widgets configurable enough to tune real player-facing layouts without editing
Python code for every panel, chip, bar, row, or workbench iteration.

The immediate motivation is Phase 20 live-core smoke testing: status chips are directionally good,
but several toolkit-backed rows overflow their visible bounds. Examples include selected-unit rows,
position rows, selected-model rows, decision rows, hotkey rows, and long assignment/advisory rows.

A later `Warhammer_40k_AI` review at `643a99385e95` also broadened the kinds of
engine-authored decision summaries the HUD will need to present. Fight movement, melee declarations,
Stratagem target bindings, attack-resolution choices, and completion gates can all produce long
labels, multi-field summaries, and nested model, weapon, and target data. The HUD needs explicit
overflow, density, sizing, slot, and icon-substitution controls before those flows become
player-facing.

## Resolved Design Decisions

### Preferences Versus HUD YAML

Keep the current split.

- Preferences YAML owns global UI choices and zone sizing, such as which layout preset is active,
  which zones are visible, and zone-level sizes.
- HUD composition YAML owns widget composition, child placement, slot sizing, overflow policy,
  icon choice, color role, typography, and presentation density.

### Runtime Data Binding

Keep Phase 20 view models as the adapter between runtime state and toolkit components.

Runtime state should not bind directly into arbitrary YAML expressions. Python view models continue
to produce named, already-safe presentation data such as:

- `status_chips`
- `selected_unit_card`
- `selected_unit_rows`
- `action_rows`
- `assignment_rows`
- `assignment_notice_rows`
- `diagnostic_lines`
- `event_lines`
- `hotkey_hints`

HUD YAML may place, style, size, clip, and choose icons for those named presentation groups. It must
not query engine state directly, format raw decision payloads, create conditionals that imply rule
logic, or define legality.

The intended data path is:

```text
Core projection + UI state + preferences
        -> Python HUD view models
        -> named presentation groups
        -> HUD composition YAML placement/styling
        -> toolkit layout allocation
        -> Arcade primitives/widgets
```

This avoids turning HUD YAML into a rules-adjacent scripting language while still allowing power-user
layout customization.

### Clipping Strategy

Prefer Arcade scissor clipping first, with deterministic string truncation and omission still used
for cheap text shaping before render.

Small local experiment run during plan concretization:

```bash
env UV_CACHE_DIR=/tmp/uv-cache PYGLET_HEADLESS=true ARCADE_HEADLESS=true uv run python - <<'PY'
import arcade

window = arcade.Window(64, 64, visible=False)
try:
    framebuffer = window.ctx.screen
    framebuffer.use()
    window.clear(color=(0, 0, 0, 255))
    window.ctx.scissor = (0, 0, 32, 64)
    arcade.draw_polygon_filled(((0, 0), (64, 0), (64, 64), (0, 64)), (255, 0, 0, 255))
    window.ctx.scissor = None
    window.ctx.finish()
    rgba = framebuffer.read(viewport=(0, 0, 64, 64), components=4, attachment=0, dtype="f1")
finally:
    window.close()

def pixel(x: int, y: int) -> tuple[int, int, int, int]:
    index = ((y * 64) + x) * 4
    return tuple(rgba[index:index + 4])

left = pixel(8, 32)
right = pixel(56, 32)
print({"left": left, "right": right, "passed": left[:3] == (255, 0, 0) and right[:3] == (0, 0, 0)})
PY
```

Observed result with Arcade 3.3.3:

```text
{'left': (255, 0, 0, 255), 'right': (0, 0, 0, 255), 'passed': True}
```

Implementation guidance:

- add a small scissor stack helper around `window.ctx.scissor`;
- intersect nested child clips with the current parent clip;
- restore the previous scissor after each component subtree;
- use integer lower-left screen pixel rectangles;
- include headless framebuffer tests that prove content outside a clipped widget is not drawn.

### Canonical Layout Presets

Do not add new canonical layout presets in this phase. The current presets are enough. This phase
improves the widget and slot controls inside those presets.

## Concrete Scope

Phase 23 will add a deterministic layout and overflow layer to the existing HUD toolkit.

It will not redesign the whole HUD, replace Phase 20 ergonomics, or introduce new gameplay
workflows. It should make the current widgets configurable enough that later HUD iteration can happen
primarily in HUD YAML.

## Presentation Data Contract

Create a small presentation data registry for the Phase 20 ergonomic HUD output. The registry maps
stable names to view-model data groups. Example names:

- `hud.status_chips`
- `hud.selected_unit.card`
- `hud.selected_unit.rows`
- `hud.workbench.actions`
- `hud.workbench.assignments.groups`
- `hud.workbench.assignments.notices`
- `hud.workbench.review.diagnostics`
- `hud.workbench.review.events`
- `hud.workbench.review.hotkeys`

The registry should expose only JSON-safe or toolkit-view-model-safe presentation fields. It should
not expose raw engine payloads unless they have already been redacted and explicitly labeled as
debug-only by existing forensic tooling.

HUD composition YAML may bind a widget collection to one of these names:

```yaml
type: HudContainer
id: assignments_column
data_ref: hud.workbench.assignments.groups
repeat:
  as: assignment
  widget:
    type: AssignmentGroupRow
    id: assignment_row
    data_ref: assignment
```

The exact syntax can be adjusted during implementation, but the data source must remain the Python
view-model adapter, not raw runtime state.

## Schema Additions

### Size Specifications

Add a typed `SizeSpec` parser supporting:

- pixels: `48px`, `240px`;
- percentages: `35%`;
- fractional units: `2fr`;
- named modes: `fit-content`, `fill`, `auto`;
- numeric shorthand interpreted as pixels only where existing schemas already accept numbers;
- `min_width`, `max_width`, `min_height`, `max_height`;
- optional `aspect_ratio` for chips, icons, gauges, and card-like elements.

Invalid examples must produce typed diagnostics instead of silent fallback:

- negative sizes;
- malformed units;
- percentage outside `0%` to `100%` where a bounded percentage is required;
- `fr` units outside flex/grid sibling allocation contexts;
- impossible constraints such as `min_width > max_width`.

### Position And Anchor Control

Add typed placement fields for parent-relative positioning:

- `anchor`: `top_left`, `top_right`, `center`, `bottom_left`, `bottom_right`;
- `offset_x`, `offset_y`;
- `margin_px` or directional margins;
- `padding_px` or directional padding;
- stack layout with orientation, gap, and alignment;
- grid layout with rows, columns, gap, and child row/column spans;
- overlay layout with z-order;
- named slots for compound widgets.

### Overflow Policy

Add an `OverflowPolicy` model with:

- `mode`: `clip`, `ellipsis`, `wrap`, `shrink_to_fit`, `scroll`, or `visible`;
- `max_lines`;
- `min_font_size_px` for shrink-to-fit;
- `preserve_icon` so text can shrink/truncate before icons disappear;
- `debug_bounds` to render widget allocation and estimated content extents.

Default player-facing behavior:

- text widgets default to `ellipsis`;
- child render output defaults to clipping to the widget content rect;
- debug/stress profiles may opt into `debug_bounds`;
- `scroll` is schema-only or preview-only until interactive scroll containers exist.

### Text And Icon Controls

Expose widget-level and theme-level controls:

- primary, secondary, and value font sizes;
- line height;
- text alignment and anchor;
- maximum primary, secondary, and value line counts;
- value-column width for label/value rows;
- icon size;
- icon side: left, right, both, or none;
- icon-only chip mode;
- status-chip shape: `round`, `square`, `rounded_rect`, or `pill`;
- status-chip shape sizing controls such as `diameter_px`, `corner_radius_px`, and optional
  equal-width/equal-height enforcement for round and square chips;
- state/color-role overrides;
- high-contrast token overrides;
- per-widget padding and gap controls;
- decision-family icon mappings for long labels such as `submit_melee_declaration`,
  `stratagem_target_binding`, `complete_charge_phase`, and `eligible_to_fight_pass`.

Decision-family icon mappings are presentation-only. They must not create, rename, filter, or
validate decision types or option IDs.

### Compound Widget Slots

Support reusable slot names for compound widgets:

- `HudPanel`: `header`, `body`, `footer`, `actions`;
- `IconTextBar`: `icon`, `primary`, `secondary`, `value`;
- `StatusChip`: `icon`, `label`, `value`, `alert`, `progress`;
- `UnitRailCard`: `header`, `badge`, `body`, `status`;
- `AssignmentGroupRow`: `state_marker`, `source`, `target`, `summary`;
- `DatasheetPanel`: `header`, `stat_strip`, `weapons`, `abilities`, `keywords`, `footer`;
- `Tooltip`: `title`, `body`, `footer`;

Slots are placement hooks only. Slot YAML cannot define game semantics.

### Status Chip Shape Controls

Status chips need first-class shape controls because different HUD layouts may want compact circular
badges, square command tiles, long rounded rectangles, or pill-like phase/status banners.

Add a `StatusChipShape` model with:

- `shape`: `round`, `square`, `rounded_rect`, or `pill`;
- `diameter_px` for round chips;
- `size_px` for square chips;
- `corner_radius_px` for square and rounded-rectangle chips;
- `preserve_aspect_ratio` to keep icon-only round/square chips from stretching inside flex layouts;
- `content_alignment` for icon/label/value placement inside non-rectangular chips.

Round and square status chips should remain normal toolkit widgets. They may display an icon only or
an icon plus short text if space allows, but their shape must not imply status semantics. The view
model still provides the same chip label, value, icon token, and color role.

## YAML Dialect Target

The final schema should support YAML like this:

```yaml
type: IconTextBar
id: movement_draft_row
data_ref: hud.workbench.actions.movement_draft
height: fit-content
min_height: 42px
max_height: 72px
overflow:
  mode: ellipsis
  max_lines: 2
shrink_to_fit:
  enabled: true
  min_font_size_px: 10
layout:
  padding_px: 8
  gap_px: 6
slots:
  icon:
    width: 28px
  value:
    width: 34%
text:
  primary_font_size_px: 15
  secondary_font_size_px: 12
  value_font_size_px: 12
icons:
  default: action.movement
```

And compact status chips like this:

```yaml
type: StatusChip
id: command_phase_badge
data_ref: hud.status_chips.phase
shape:
  shape: round
  diameter_px: 44
overflow:
  mode: ellipsis
icons:
  default: phase.command
```

Or square command tiles like this:

```yaml
type: StatusChip
id: active_player_tile
data_ref: hud.status_chips.active_player
shape:
  shape: square
  size_px: 52
  corner_radius_px: 4
text:
  primary_font_size_px: 11
```

And repeated assignment rows like this:

```yaml
type: HudContainer
id: assignment_group_rows
data_ref: hud.workbench.assignments.groups
layout:
  kind: stack
  gap_px: 6
repeat:
  as: assignment
  limit: 4
  overflow:
    mode: ellipsis
  widget:
    type: AssignmentGroupRow
    id: assignment_group_row
    data_ref: assignment
    height: fit-content
    min_height: 38px
    overflow:
      mode: ellipsis
      max_lines: 2
```

These examples are acceptance targets, not necessarily the exact first implementation syntax. If the
implementation chooses different field names, it must document the final dialect in
`docs/ui-configuration.md` or `docs/hud/README.md`.

## Implementation Slices

### Slice 1 - Schema And Diagnostics

- Add typed schema models for `SizeSpec`, constraints, overflow policy, text controls, icon
  controls, slot sizing, and placement hints.
- Add parser diagnostics with stable codes.
- Keep backward compatibility for current HUD YAML examples.
- Update docs with the accepted syntax.

Acceptance:

- invalid size and overflow values produce typed diagnostics;
- existing `default-hud` and preview YAML files still load;
- no schema field can define rules, decisions, proposal kinds, legal actions, or visibility
  exceptions.

### Slice 2 - Deterministic Content Measurement

- Add a pure content estimator for text/icon/widget needs.
- Estimate text width from character count, font size, and a conservative width factor.
- Estimate text height from line height and line count.
- Include icon size, padding, border width, and gaps.
- Cache estimates for stable inputs if profiling shows value.

Acceptance:

- unit tests cover representative labels, long decision names, icons, and multi-line text;
- estimates are deterministic and do not call Arcade render APIs;
- `fit-content` can use these estimates without live GPU probing.

### Slice 3 - Layout Allocation

- Implement a bounded layout pass over `HudComponentNode` trees.
- Support stack, grid, overlay, fill, fraction, fit-content, min/max, margin, padding, and named
  slots.
- Produce a layout tree of allocated `ScreenRect`s before rendering.
- Keep all calculations pure over viewport size, theme, widget attributes, and presentation data.

Acceptance:

- unit tests cover stack/grid/overlay/fill/fraction allocation;
- impossible constraints produce diagnostics or deterministic clamping according to documented
  rules;
- layout allocation is not repeated every draw frame unless inputs changed.

### Slice 4 - Clipping And Overflow Rendering

- Add a scissor-stack helper to the Arcade render path.
- Clip child rendering to allocated widget content rects by default.
- Implement text overflow modes: ellipsis, clip, wrap with max lines, and shrink-to-fit with a
  minimum font-size.
- Keep primitive truncation for text shaping before render, but rely on scissor clipping to prevent
  any remaining visual spill.
- Add `debug_bounds` overlays for layout tuning.

Acceptance:

- headless framebuffer test proves scissor clipping keeps pixels outside a widget rect unchanged;
- long labels no longer overlap neighboring rows in selected-unit and workbench panels;
- `debug_bounds` can be enabled from a preview/stress YAML profile.

### Slice 5 - Phase 20 Ergonomic HUD Integration

- Convert current hard-coded row sizing in `render/hud_ergonomics.py` to the new layout allocator.
- Keep Phase 20 view models as the runtime adapter.
- Let HUD YAML place and style the ergonomic presentation groups.
- Ensure selected unit, decision, assignments, review, status chips, and hotkeys all render through
  the same toolkit layout path.

Acceptance:

- existing ergonomic HUD tests still pass after updating expected layout behavior;
- no legacy direct panel text paths are reintroduced;
- all player-facing text goes through toolkit widgets or intentionally narrow direct annotations
  such as context menus and mouse readout.

### Slice 6 - Stress Profiles And Preview Workflow

- Add a stress-test HUD YAML profile with intentionally long data.
- Include long unit names, long model IDs, long decision types, long option IDs, long diagnostics,
  long assignment labels, and small viewport examples.
- Update `warhammer40k-hud-preview` docs with commands for stress profiles and component-specific
  review.

Acceptance:

- preview can render the stress profile headlessly;
- metadata identifies overflow/debug-bound settings;
- generated artifacts make it easy to inspect clipping and ellipsis behavior.

## Engine Decision Summary Stress Cases

Tests and preview data should include examples derived from current engine decision families:

- fight movement rows with proposal kind, selected unit, mode/action, target-unit IDs, objective
  context, and no-move state;
- melee declaration rows with model, weapon, and target allocation summaries;
- Stratagem target-binding rows with Stratagem ID, declinable state, timing window, selected target,
  and handler-owned `effect_selection` hints;
- completion-gate rows with skipped-unit summaries and exact finite option IDs;
- attack-resolution rows such as target-unit and weapon-group selection where deterministic option
  IDs can be long but player-facing labels should remain compact.

These examples remain presentation-only. YAML may choose icons, labels, truncation, and
detail-disclosure behavior, but it must not define new proposal kinds, option IDs, legality, target
filters, or hidden-information visibility.

## Performance Guardrails

- Layout computation is a deterministic pure function over viewport size, theme tokens, widget
  attributes, and presentation data.
- Recompute layout only when viewport, preferences, HUD YAML, theme, or presentation data changes.
- Avoid GPU readback, render probes, or driver-dependent measurements for ordinary sizing.
- Use a bounded measure, allocate, render flow.
- Avoid iterative reflow loops unless there is a strict maximum pass count and tests cover it.
- Keep headless render evidence and GUI driver tests able to assert layout behavior without
  pixel-perfect font assumptions.
- Use scissor clipping during render, not as a measurement mechanism.

## Testing Strategy

- Unit-test parsing and validation of size specifications.
- Unit-test deterministic content-size estimates for representative text/icon combinations.
- Unit-test layout allocation for stack, grid, overlay, fit-content, fill, and fraction cases.
- Unit-test named slot allocation in compound widgets.
- Unit-test round and square status-chip allocation, including equal width/height preservation under
  stack, grid, and flex layouts.
- Regression-test long labels in `StatusChip`, `IconTextBar`, `AssignmentGroupRow`,
  `DatasheetPanel`, and `Tooltip`.
- Regression-test long current-contract decision labels and proposal kinds.
- Add a headless framebuffer test for scissor clipping.
- Add headless render evidence tests for at least one overflow-heavy HUD profile.
- Add preview YAML examples that stress long unit names, long decision labels, long diagnostic text,
  and small viewport sizes.
- Keep import-boundary tests passing so the HUD toolkit does not import mutable engine internals.

## Manual Validation Checklist

- Launch the normal UI with `docs/preferences/default.yaml` and verify selected-unit, decision,
  assignment, review, and status-chip text stays inside its allocated panels.
- Launch `docs/preferences/command-bench.yaml` and verify the same overflow protections work in the
  alternate preset.
- Preview at least one round status chip and one square status chip and verify they stay visually
  round/square instead of stretching with their parent layout.
- Use `warhammer40k-hud-preview` on the stress profile and inspect `debug_bounds`.
- Resize the window, if resizable mode is enabled, and confirm zones and child widgets recompute
  without overlap.
- Trigger a live-core smoke movement draft and verify long movement/advisory text clips or
  ellipsizes instead of spilling into adjacent rows.

## Non-Goals

- No engine contract changes.
- No new player decisions or proposal payload shapes.
- No client-side rule validation.
- No raw runtime-state binding from YAML.
- No YAML conditionals that infer legality or visibility.
- No live-render probing as the default sizing mechanism.
- No new canonical layout presets.
- No final visual styling pass beyond making layout and overflow configurable.

## Acceptance Criteria

- [x] A concrete schema exists for size, position, overflow, text, icon, and slot controls.
- [x] `StatusChip` supports round and square shapes with deterministic sizing and preview coverage.
- [x] Existing HUD YAML remains loadable or has a documented migration.
- [x] Runtime data still flows through Phase 20 view models before toolkit binding.
- [x] Selected-unit and workbench rows no longer have uncontrolled text overlap.
- [x] Arcade scissor clipping is implemented and covered by headless framebuffer tests.
- [x] Deterministic measurement and layout allocation are covered by unit tests.
- [x] A stress-test HUD YAML profile exists and can be rendered with `warhammer40k-hud-preview`.
- [x] Automated tests cover long decision labels and proposal kinds from current engine contracts.
- [x] The implementation remains presentation-only and does not change core-client or decision
  submission behavior.

## Implementation Notes

- Added typed size, overflow, and status-chip shape parsing to the HUD toolkit and composition
  loader.
- Added deterministic stack allocation for pixel, percent, fraction, fill, and fit-content child
  sizes. Grid allocation keeps the existing equal-cell behavior for now, with shaped status chips
  preserving their aspect ratio inside the allocated cell.
- Added render-primitive clipping metadata and Arcade scissor application in both the live window and
  HUD preview draw paths.
- Added round and square status-chip rendering while keeping chip semantics in the Phase 20 view
  models.
- Added `docs/hud/examples/overflow-stress-preview.yaml` for long-label and shaped-chip review.
- `scroll` overflow remains schema-recognized but non-interactive; it renders as clipped content
  until a future scroll-container phase adds input handling.
