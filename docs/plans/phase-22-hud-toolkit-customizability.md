# Phase 22 - HUD toolkit customizability

## Status

Preliminary. This phase records follow-on HUD toolkit customization needs discovered during Phase
20 manual testing. It should be revisited after Phase 21 packaging, CI, regression fixtures, and
import-boundary hardening.

## Goal

Make HUD toolkit widgets configurable enough to tune real player-facing layouts without editing
Python code for every panel, chip, bar, or workbench iteration.

The immediate motivation is Phase 20 live-core smoke testing: the status chips are directionally
good, but several toolkit-backed rows overflow their visible bounds. Examples include selected-unit
rows, position rows, selected-model rows, decision rows, and hotkey rows where the widget frame only
comfortably fits the title line while secondary/value text extends past the intended box.

## Desired Outcome

Power users and developers should be able to tune HUD composition YAML to control how widgets size,
position, clip, shrink, truncate, and align themselves while preserving the UI/core boundary:

- preferences and HUD YAML can change presentation only;
- widgets may describe layout and overflow policy;
- widgets must not define legal actions, rule validation, proposal kinds, request IDs, hidden
  visibility, or engine behavior.

## Current Expectations

Phase 19 and Phase 20 established the right conceptual pieces:

- reusable toolkit widgets such as `StatusChip`, `IconTextBar`, `UnitRailCard`,
  `AssignmentGroupRow`, `Tooltip`, `DatasheetPanel`, and `HudContainer`;
- parent-relative HUD zones and regions;
- preview YAML that can render isolated compositions with placeholder data;
- player-facing ergonomic panels that can be represented as toolkit components.

The next issue is control granularity. Layout needs more explicit sizing behavior and overflow
semantics before the toolkit can support rapid iteration on polished player HUDs.

## Preliminary Requirements

### Size Specifications

Support a stable size syntax for widget and child layouts:

- absolute pixels, such as `height: 48px` or `width: 240px`;
- parent-relative percentages, such as `width: 35%`;
- fraction/flex units for sibling distribution, such as `width: 2fr`;
- min/max constraints, such as `min_width`, `max_width`, `min_height`, and `max_height`;
- `fit-content` for dimensions derived from estimated text/icon/content needs;
- `fill` for consuming the remaining available parent space;
- optional aspect-ratio constraints for chips, gauges, icons, and card-like elements.

### Position And Anchor Control

Allow both zone-relative and parent-relative placement:

- anchor presets, such as `top_left`, `top_right`, `center`, `bottom_left`, `bottom_right`;
- explicit offsets from an anchor;
- grid row/column placement;
- stack placement with gap, padding, and alignment;
- overlay placement with z-order;
- inset/margin controls at parent and child levels;
- named slot placement so compound widgets can expose internal areas without hard-coding geometry.

### Content Measurement Model

`fit-content` and shrink-to-fit require content-size estimates. The plan should start with a
deterministic estimator rather than measuring live Arcade render output:

- estimate text width from character count, font size, and a conservative per-character width
  factor;
- estimate text height from font size, line height, and line count;
- include icon size, padding, border width, and configured gaps;
- cache estimates per text/font-size/widget configuration where useful;
- keep estimates deterministic in tests and headless render evidence;
- avoid render-and-probe loops in the live UI because they are too expensive and can vary by driver
  or font backend.

Future precise text metrics can be considered only if they are cheap, deterministic enough for
tests, and cached. They should be an enhancement, not a requirement for `fit-content`.

### Overflow Policies

Each text-capable widget should have an explicit overflow policy:

- `clip` to hide content outside the widget bounds;
- `ellipsis` to truncate long text;
- `wrap` with a maximum line count;
- `shrink_to_fit` with minimum font-size guardrails;
- `scroll` only for future interactive panels where appropriate;
- `debug_bounds` to render layout boxes and measured/estimated extents for visual tuning.

The default player-facing behavior should prefer `ellipsis` or `clip` over uncontrolled overlap.
Debug profiles may choose `wrap` or `debug_bounds` when diagnosing layout pressure.

### Text And Icon Controls

Expose widget-level and theme-level knobs:

- primary, secondary, and value font sizes;
- line height;
- icon size and icon-side placement;
- text alignment and anchor;
- maximum primary/secondary/value line counts;
- value-column width for label/value rows;
- state/color-role overrides;
- high-contrast token overrides;
- per-widget padding and gap controls.
- ability to use icons instead of raw text for chips contents

### Compound Widget Layout

Support richer parent/child composition for reusable HUD elements:

- non-renderable containers that only place children;
- renderable panels with header/body/footer slots;
- icon-text bars with optional left/right icons and a dedicated value column;
- datasheet panels with header, stat strip, weapon, ability, keyword, and footer slots;
- assignment rows with source, target, state marker, and summary slots;
- status chips with icon, label, value, and optional progress/alert slots.

### YAML Dialect Expectations

HUD composition YAML should be able to express this without becoming a rules language:

```yaml
type: IconTextBar
id: movement_draft_row
height: fit-content
min_height: 42px
max_height: 72px
overflow: ellipsis
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
```

This example is illustrative only. The final schema should be designed after Phase 21 hardening and
after reviewing the existing Phase 19 composition parser.

## Performance Guardrails

- Layout computation should be a deterministic pure function over viewport size, theme tokens,
  widget attributes, and JSON-safe sample/runtime data.
- Recompute layout only when inputs change, not every draw call where possible.
- Avoid GPU readback, render probes, or driver-dependent measurements for ordinary widget sizing.
- Prefer bounded layout passes: measure, allocate, render. Avoid iterative reflow loops unless there
  is a strict maximum pass count and tests cover it.
- Keep headless render evidence and GUI driver tests able to assert layout behavior without relying
  on pixel-perfect font rendering.

## Testing Strategy

- Unit-test parsing and validation of size specifications.
- Unit-test deterministic content-size estimates for representative text/icon combinations.
- Unit-test layout allocation for stack, grid, overlay, fit-content, fill, and fraction cases.
- Regression-test long labels in `StatusChip`, `IconTextBar`, `AssignmentGroupRow`, and
  `DatasheetPanel` so they clip, ellipsize, wrap, or shrink according to configuration.
- Add headless render evidence tests for at least one overflow-heavy HUD profile.
- Add preview YAML examples that intentionally stress long unit names, long decision labels, long
  diagnostic text, and small viewport sizes.

## Non-Goals

- No engine contract changes.
- No new player decisions or proposal payload shapes.
- No client-side rule validation.
- No live-render probing as the default sizing mechanism.
- No attempt to finish final visual styling in this preliminary phase.

## Open Questions

- How much of the sizing syntax should live in preferences versus HUD composition YAML?
- Should runtime HUD data bind into named widget slots directly, or should Phase 20 view models
  remain the adapter between runtime state and toolkit components?
- Should the toolkit renderer implement clipping through primitive omission/truncation first, then
  add GPU/scissor clipping later if Arcade support is reliable?
- How many layout presets should be considered canonical once this flexibility exists?

## Acceptance Criteria

- [ ] The final plan defines a concrete schema for size, position, overflow, and slot controls.
- [ ] The implementation prevents uncontrolled text overlap in the Phase 20 selected-unit and
  workbench rows.
- [ ] The preview entrypoint can load a stress-test HUD YAML file with long placeholder content.
- [ ] Automated tests cover deterministic layout estimates and overflow policies.
- [ ] The implementation remains presentation-only and does not change core-client or decision
  submission behavior.
