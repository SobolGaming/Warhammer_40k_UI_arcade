# HUD Customization Guide

This guide explains how to customize the Arcade UI HUD with YAML files.

HUD customization is presentation-only. It changes where information appears, how widgets are
styled, how text overflows, and which known icons are used. It does not create legal game actions,
engine decisions, proposal kinds, option IDs, request IDs, validation rules, or hidden-information
visibility.

## Mental Model

The HUD is built in layers:

1. Preferences choose the overall HUD layout and zone sizes.
2. A HUD composition file places widgets into those zones.
3. Widgets bind to known presentation data references.
4. The renderer measures, allocates, clips, and draws the widget tree.

Think of the screen as a set of sockets called zones. A composition file drops widget trees into
those zones. A widget may be a visible panel, a status chip, a text row, a gauge, a datasheet-like
card, or a non-rendering container that only arranges child widgets.

Runtime game state is adapted into safe presentation view models by Python before the HUD YAML sees
it. YAML can choose placement and styling for known data, but it cannot query raw engine state or
express gameplay logic.

The live game UI and `warhammer40k-hud-preview` use the same composition renderer. Preview files
provide `sample_data`; the game provides runtime presentation data built from the Phase 20 HUD view
models. The configured `composition_profile` is therefore the game HUD, not an alternate preview-only
path.

## File Split

Preferences and HUD composition are intentionally separate.

Preferences YAML controls global UI choices:

- active layout preset;
- active HUD composition profile;
- zone visibility;
- zone sizes;
- text scale;
- high-contrast mode;
- movement budget ring presentation;
- local HUD feature toggles.

HUD composition YAML controls presentation inside zones:

- widget types;
- child layout;
- data bindings;
- labels;
- known icons;
- size hints;
- overflow behavior;
- status-chip shape;
- widget color roles.

Example preferences reference:

```yaml
hud:
  layout_preset: compass_ring
  composition_profile: default-hud
  movement_budget_ring_mode: total
  assignment_target_highlight_color: [220, 54, 64, 72]
  zones:
    right_inspector:
      visible: true
      size_px: 276
      collapsed: false
```

`movement_budget_ring_mode` controls the world-space movement budget overlay when the
`movement_budget` overlay is active:

- `total` draws one ring at the total engine-projected movement budget for each active selected
  model.
- `split` draws a base movement ring plus a larger enhanced/total ring when the proposal or visible
  datasheet data exposes a base movement hint and the total budget is larger than that base value.
  If the UI cannot resolve a base movement hint, it falls back to the single total ring.

`assignment_target_highlight_color` controls the advisory battlefield fill used when a selectable
assignment row targets a visible unit. It is an `[R, G, B, A]` list with integer channels from 0 to
255. The highlight is local UI feedback only; engine validation still owns whether the assignment is
legal.

The `composition_profile` value can be:

- a built-in profile ID, such as `default-hud`;
- a relative path resolved against the preferences file, such as `hud/my-custom.yaml`;
- a package-resource-relative path when loaded from packaged built-ins, such as
  `../hud/default-hud.yaml`;
- an absolute path.

Built-in IDs resolve to packaged resources under `warhammer40k_arcade_ui.resources`, not to the
editable `docs/hud/` examples. For example, `composition_profile: default-hud` loads the packaged
`hud/default-hud.yaml`. To test an edited docs file directly from `docs/preferences/default.yaml`,
use a relative reference such as:

```yaml
composition_profile: ../hud/default-hud.yaml
```

Launch examples:

```bash
uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/default.yaml
uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/command-bench.yaml
```

Changing `hud.composition_profile` changes the live HUD composition used by those commands. Changing
the referenced HUD YAML changes the same widget tree that the preview command renders.

## Layout Presets And Zones

The current built-in layout presets are:

- `compass_ring`
- `command_bench`

Zone sizing belongs in preferences, not HUD composition files. Composition files fill whatever zone
rectangle the active preferences/layout provide.

### `compass_ring` Zones

- `top_ribbon`: top status and summary area.
- `left_rail`: left roster or navigation rail.
- `right_inspector`: selected unit/model inspector area.
- `bottom_workbench`: decision, assignment, and review workbench.

### `command_bench` Zones

- `top_ribbon`: compact top status row.
- `left_player_bench`: player-side bench area.
- `right_opponent_bench`: opponent-side bench area.
- `bottom_command_bench`: broader command/workbench area.

## Composition File Shape

Every HUD composition file is a YAML object:

```yaml
schema_version: 1
profile_id: my_custom_hud
layout_preset: compass_ring
theme: default
regions:
  right_inspector:
    widget:
      type: HudContainer
      id: selected_inspector_root
      render_mode: none
      layout: {kind: stack, orientation: vertical, gap_px: 8, padding_px: 8}
      children:
      - type: DatasheetPanel
        id: selected_unit_datasheet
        data_ref: selected_unit
        title: Selected Unit
```

Preview-only files may include `sample_data` so the widgets can be rendered without launching a game:

```yaml
sample_data:
  selected_unit:
    name: Intercessor Squad Alpha
    stats: {M: 6, T: 4, SV: 3+, W: 2, LD: 6+, OC: 2}
```

Production composition files must not include `sample_data`.

## Preview Workflow

Preview an entire composition:

```bash
uv run warhammer40k-hud-preview docs/hud/examples/unit-datasheet-preview.yaml
```

Preview one component:

```bash
uv run warhammer40k-hud-preview docs/hud/examples/workbench-preview.yaml --component movement_budget_ring
```

Render a headless PNG and metadata bundle:

```bash
uv run warhammer40k-hud-preview docs/hud/examples/overflow-stress-preview.yaml --headless --artifact-dir /tmp/hud-stress
```

The stress preview intentionally uses long labels, round and square status chips, and constrained
rows so you can check clipping and ellipsis behavior quickly.

## Data Bindings

Widgets use `data_ref` to bind to known presentation data. These are safe display references, not
raw engine payload access.

Current runtime/preview data references:

- `active_player`
- `assignment_groups`
- `command_points`
- `current_action`
- `current_assignment`
- `debug_status`
- `dice_tray`
- `mission_summary`
- `movement_budget`
- `opponent_roster`
- `phase_state`
- `player_roster`
- `selected_model`
- `selected_unit`
- `selection_status`

Phase 23 also reserves named HUD presentation groups for runtime view-model output:

- `hud.status_chips`
- `hud.status_chips.phase`
- `hud.status_chips.active_player`
- `hud.status_chips.pending`
- `hud.selected_unit.card`
- `hud.selected_unit.rows`
- `hud.player_units.roster`
- `hud.workbench.actions`
- `hud.workbench.assignments.groups`
- `hud.workbench.assignments.notices`
- `hud.dice_tray.active`
- `hud.workbench.review.diagnostics`
- `hud.workbench.review.events`
- `hud.workbench.review.hotkeys`

Not every reserved group is populated by every current runtime screen. The renderer treats missing
data as absent display data, not as a gameplay fallback.

The live selected-unit datasheet binding uses the core engine's viewer-safe display projection.
When a unit is selected, `selected_unit.stats` is populated from
`model_display_by_id[model_instance_id].current_characteristics` for the standard stat labels `M`,
`T`, `SV`, `W`, `LD`, and `OC`. The widget uses the engine-provided `display_value` strings, so the
HUD can show values such as `3+`, `6+`, or `-` without recomputing rules. Static fixtures or older
core projections that do not expose model display records still render `?` placeholders so the card
keeps the same shape as previews.

## Available Icons

Composition YAML may use known icon IDs. Icons currently render as placeholder glyphs or simple
symbol chips; later asset-pack work can replace their visuals.

Current known icon IDs:

- `action.cancel`
- `action.confirm`
- `action.inspect`
- `action.measure`
- `action.movement`
- `action.summary`
- `decision.attack_resolution`
- `decision.complete_phase`
- `decision.melee`
- `decision.stratagem`
- `dice.damage`
- `dice.aeldari.d6.face_1`
- `dice.aeldari.d6.face_2`
- `dice.aeldari.d6.face_3`
- `dice.aeldari.d6.face_4`
- `dice.aeldari.d6.face_5`
- `dice.aeldari.d6.face_6`
- `dice.hit`
- `dice.save`
- `dice.wound`
- `entity.model`
- `entity.objective`
- `entity.terrain`
- `entity.unit`
- `mission.primary`
- `mission.secondary`
- `phase.command`
- `phase.movement`
- `status.active`
- `status.invalid`
- `status.selected`
- `status.warning`
- `stratagem.generic`
- `unit.battleline`

Unknown icon IDs are diagnostics. They are not ignored.

## Layout

Every widget can have a `layout` object when it has children:

```yaml
layout:
  kind: stack
  orientation: horizontal
  gap_px: 8
  padding_px: 8
  alignment: stretch
```

Layout fields:

- `kind`: `stack`, `grid`, `anchor`, or `overlay`.
- `orientation`: `vertical` or `horizontal`.
- `columns`: grid column count, from 1 to 12.
- `gap_px`: spacing between children.
- `padding_px`: inset inside the parent before children are placed.
- `alignment`: `start`, `center`, `end`, or `stretch`.

Current implementation notes:

- `stack` honors child size specs for the active axis.
- `grid` currently keeps equal cells.
- `anchor` and `overlay` are accepted layout kinds for composition stability, but advanced
  placement behavior is intentionally still limited.

## Sizing

Size hints can be used on child widgets:

```yaml
width: 2fr
min_width: 220px
height: fit-content
max_height: 72px
```

Supported size forms:

- `48px`: absolute pixels.
- `35%`: percentage of available parent space.
- `2fr`: fraction of remaining sibling space.
- `fill`: consume remaining sibling space.
- `fit-content`: estimate size from label/icon content.
- `auto`: flexible default behavior.
- numeric values: treated as pixels where accepted.

Constraint fields:

- `min_width`
- `max_width`
- `min_height`
- `max_height`
- `aspect_ratio`

Invalid sizes produce diagnostics. Examples include negative values, malformed units, percentages
above `100%`, `fr` outside supported allocation contexts, and impossible pixel constraints such as
`min_width: 200px` with `max_width: 100px`.

## Overflow

Text and child rendering can be bounded with `overflow`:

```yaml
overflow:
  mode: ellipsis
  max_lines: 2
  min_font_size_px: 10
  preserve_icon: true
  debug_bounds: false
```

Modes:

- `ellipsis`: truncate text and add `...` where space is limited.
- `clip`: keep text as-is but clip drawing to the widget rectangle.
- `wrap`: allow a bounded number of estimated text lines.
- `shrink_to_fit`: reduce font size down to `min_font_size_px`.
- `visible`: allow content to draw without text truncation, though parent scissor clipping may still
  bound pixels.
- `scroll`: keep text as-is; use widget `scroll` settings for interactive child/panel scrolling.

The live renderer and HUD preview apply Arcade scissor clipping to widget primitives so text and
children do not spill into neighboring panels.

## Scrollable Widgets

Widgets can opt into interactive scrolling with a `scroll` object. This is separate from
`overflow.mode`; use `overflow` for text behavior and `scroll` for child or row content that can
move inside a fixed panel.

```yaml
scroll:
  enabled: true
  axes: y
  wheel_axis: y
  show_scrollbars: auto
  wheel_step_px: 48
  clamp_to_content: true
```

Fields:

- `enabled`: boolean. Disabled or absent widgets do not intercept wheel input.
- `axes`: `x`, `y`, or `both`.
- `wheel_axis`: `x`, `y`, or `auto`. `auto` uses horizontal wheel input when available and vertical
  wheel input for vertical scrolling.
- `show_scrollbars`: `never`, `auto`, or `always`.
- `wheel_step_px`: positive pixel distance per wheel notch.
- `drag_scrollbars`: accepted for schema stability, but dragging is not implemented yet.
- `clamp_to_content`: keep offsets within the measured content extent.

The default HUD enables scrolling only on the `PlayerUnitsRoster` in the left rail. Wheel input over
that roster is consumed by the HUD and does not zoom the battlefield.

## Status Chip Shapes

`StatusChip` supports rectangular and compact badge shapes:

```yaml
type: StatusChip
id: round_phase_chip
data_ref: hud.status_chips.phase
icon_id: phase.command
label: Phase
shape: {shape: round, diameter_px: 48}
width: 48px
height: 48px
```

```yaml
type: StatusChip
id: square_active_player_chip
data_ref: hud.status_chips.active_player
icon_id: status.active
label: Active
shape: {shape: square, size_px: 52, corner_radius_px: 4}
width: 52px
height: 52px
```

Shape fields:

- `shape`: `round`, `square`, `rounded_rect`, or `pill`.
- `diameter_px`: round chip diameter.
- `size_px`: square chip size.
- `corner_radius_px`: corner radius for square or rounded rectangle chips.
- `preserve_aspect_ratio`: keep round/square chips from stretching in flexible slots.
- `content_alignment`: `start`, `center`, `end`, or `stretch`.

Current rendering behavior:

- `round` renders as a circular badge.
- `square` renders as an equal-width/equal-height tile.
- `rounded_rect` and `pill` use the standard labelled-box presentation for now.

## Common Widget Properties

Most widgets accept shared presentation properties:

- `width`
- `height`
- `min_width`
- `max_width`
- `min_height`
- `max_height`
- `aspect_ratio`
- `overflow`
- `scroll`
- `shape`
- `text`
- `icons`
- `slots`
- `color_role`
- `fill_color_role`
- `border_color_role`
- `background_alpha`
- `border_alpha`
- `border_width`
- `clip_children`
- `density`
- `state`
- `opacity`
- `padding`
- `tooltip_key`
- `z_order`

Some properties are accepted ahead of full renderer support so profiles can stabilize before the
visual system is complete. Unsupported behavior should be documented as a current limitation rather
than used as a gameplay fallback.

## Widget Reference

### `HudContainer`

Purpose: non-rendering or lightly rendered parent for grouping child widgets.

Important properties:

- `render_mode`: `none`, `panel`, `outline`, or `debug_bounds`.
- `layout`: child placement.
- `clip_children`: whether child primitives should be clipped to the container rectangle.

Use it for columns, rows, nested groups, and invisible placement scaffolding.

### `HudPanel`

Purpose: framed panel with title/subtitle areas.

Important properties:

- `title`
- `subtitle`
- `header_visible`
- `footer_visible`
- `collapse_state`
- `content_gap`

Use it for inspector or workbench areas that need a visible frame.

### `IconSlot`

Purpose: one icon or placeholder glyph.

Important properties:

- `icon_id`
- `size`
- `icon_size`
- `badge_text`
- `fallback_glyph`

### `IconTextBar`

Purpose: compact row with icon, primary text, secondary text, and optional value text.

Important properties:

- `primary_label`
- `secondary_label`
- `value_text`
- `icon_id`
- `icon_side`
- `icon_size`
- `text_alignment`
- `overflow`

Use it for decision rows, hotkey hints, selected model rows, position rows, and compact summaries.

### `StatusChip`

Purpose: compact scalar status or badge.

Important properties:

- `label`
- `value`
- `icon_id`
- `shape`
- `progress_fraction`
- `color_role`
- `overflow`

Use it for phase, active player, pending decision, command points, or compact alert state.

### `EntityChip`

Purpose: compact reference to a model, unit, objective, terrain piece, or future assignable entity.

Important properties:

- `entity_ref`
- `display_label`
- `badge_count`
- `compact_mode`
- `expanded_mode`
- `warning_marker`

### `DonutGauge`

Purpose: ring/donut gauge for bounded values.

Important properties:

- `inner_diameter`
- `outer_diameter`
- `progress_fraction`
- `segment_count`
- `label_text`
- `center_icon_id`

Use it for movement budget, readiness, or future bounded resource displays.

### `UnitRailCard`

Purpose: compact unit card for rails or benches.

Important properties:

- `unit_label`
- `short_label`
- `model_count_summary`
- `activation_state`
- `status_summary`
- `compact`
- `expanded`

### `PlayerUnitsRoster`

Purpose: scrollable viewer-scoped player-unit roster.

Important properties:

- `data_ref`: usually `hud.player_units.roster`.
- `title`
- `subtitle`
- `button_height`
- `button_min_width`
- `button_gap`
- `button_shape`
- `status_icon_text`
- `scroll`

Runtime rows are generated from the viewer player's projected units. Each row is a button with a
placeholder circular status icon and unit name. Clicking a row selects the corresponding battlefield
unit locally; it does not submit an engine decision. Battlefield selection and Current Action focus
also update the selected roster-row visual through the same local selection state.

### `DatasheetHeader`

Purpose: header area for a selected unit or model datasheet.

Important properties:

- `title`
- `subtitle`
- `faction_icon_id`
- `badges`
- `status_chips`

### `DatasheetPanel`

Purpose: composed selected unit/model card.

Important properties:

- `title`
- `stat_zone_visible`
- `weapon_zone_visible`
- `ability_zone_visible`
- `keyword_zone_visible`
- `stat_cell_height`
- `stat_cell_min_width`
- `stat_cell_gap`
- `zone_order`

Current preview support renders the header and stat strip. Weapon, ability, keyword, and footer
zones are planned presentation areas.

### `StatStrip` And `StatCell`

Purpose: compact stat displays.

Important properties:

- `cells`
- `columns`
- `stat_labels`
- `stat_values`
- `label`
- `value`
- `delta_state`
- `emphasis_state`

### `MissionCard`

Purpose: mission or score summary card.

Important properties:

- `title`
- `subtitle`
- `card_type`
- `score`
- `reveal_state`
- `progress_chips`

### `ActionButton`

Purpose: UI command button presentation.

Important properties:

- `command_id`
- `label`
- `icon_id`
- `hotkey_hint`
- `enabled`
- `disabled_reason`
- `confirmation_required`

Action buttons may reference known UI commands. They do not create engine actions.

### `CurrentActionPanel`

Purpose: compact workbench panel for the current GUI action or engine request.

Important properties:

- `title`
- `show_actor`
- `show_request`
- `button_shape`
- `button_height`
- `button_min_width`
- `button_gap`
- `max_buttons`
- `confirm_hint`
- `cancel_hint`

Runtime data normally comes from `current_action`. The binding supplies the current actor/request
summary, advisory status text, and a `buttons` list. For finite engine decisions each button carries
the exact engine `request_id` and `option_id`; clicking the button only changes the highlighted
option, and `ENTER` still performs the actual submission through the engine decision path.

Use `CurrentActionPanel` for the bottom workbench action surface. Use `ActionButton` for a single
standalone local UI command.

### `StratagemButton`

Purpose: future Stratagem-like command presentation.

Important properties:

- `title`
- `cp_cost_badge`
- `eligibility_state`
- `phase_badge`
- `target_summary`
- `hotkey_hint`

### `AssignmentGroupRow`

Purpose: summarize one local assignment group or action workspace row.

Important properties:

- `group_label`
- `operation_kind`
- `summary_lines`
- `button_shape`
- `source_entity_chips`
- `target_entity_chips`
- `detailed`
- `expanded`

Use it for movement assignments now and future shooting, Stratagem target, or multi-entity
assignment summaries. Runtime assignment rows can also behave as buttons: selecting a row focuses
its target unit where that target is visible and paints the advisory target highlight configured by
`assignment_target_highlight_color`.

### `DicePipeline`

Purpose: future attack/dice-resolution presentation.

Important properties:

- `pipeline_steps`
- `current_step`
- `dice_pool_summaries`
- `modifier_chips`
- `history_visible`

### `DiceTray`

Purpose: display recent engine-owned dice rolls and pending engine-emitted dice reroll requests.

Important properties:

- `title`
- `data_ref`
- `face_icon_size`
- `dice_face_asset_ids`
- `bucket_label`
- `show_source`
- `max_visible_dice_per_face`
- `count_only_threshold`
- `history_visible`
- `compact`

Use it with `data_ref: dice_tray` or `data_ref: hud.dice_tray.active`. The runtime binding includes
the active roll title, roll type, values, total, source, D6 face counts, pending reroll request
metadata, exact legal option summaries, and presentation diagnostics.

The built-in default D6 skin is addressed through these presentation-only icon IDs:

- `dice.aeldari.d6.face_1`
- `dice.aeldari.d6.face_2`
- `dice.aeldari.d6.face_3`
- `dice.aeldari.d6.face_4`
- `dice.aeldari.d6.face_5`
- `dice.aeldari.d6.face_6`

The current composition primitive renderer shows those face IDs as deterministic face placeholders.
The SVG files are packaged under `warhammer40k_arcade_ui.resources.art.icons` for the future texture
renderer, but Phase 24 does not yet draw the SVG art directly.

Example:

```yaml
- type: DiceTray
  id: bottom_dice_tray
  data_ref: dice_tray
  title: Dice Tray
  width: fill
  face_icon_size: 28
  bucket_label: Reroll
  show_source: true
```

### `Tooltip`

Purpose: bounded detail text or transient help.

Important properties:

- `title`
- `body`
- `overflow`

### `Separator`

Purpose: simple horizontal or vertical separator.

Important properties:

- `orientation`

## Diagnostics And Safety

The HUD composition loader reports typed diagnostics for:

- unknown widget types;
- unknown widget attributes;
- unknown icon IDs;
- unknown data refs;
- invalid layout kinds;
- invalid layout orientations;
- invalid sizes;
- impossible size constraints;
- invalid overflow policies;
- invalid status-chip shapes;
- preview files missing required `sample_data`;
- production files that contain preview-only `sample_data`.

Fix diagnostics in the YAML. Do not rely on permissive fallback.

## Current Limits

- HUD YAML cannot create conditions, loops, rules, or scripts.
- Repeated collection binding is planned but not yet a general-purpose runtime templating system.
- Interactive widget scrolling is implemented for configured scrollable viewports, but scrollbar
  dragging is not implemented yet.
- `grid` layout uses equal cells in the current implementation.
- `rounded_rect` and `pill` are schema-supported status-chip shapes, but current rendering is the
  standard labelled-box presentation.
- Icon rendering still uses placeholders until the future asset/icon customization work lands.
- Dice face SVG assets are packaged and addressable, but the current composition renderer still uses
  face-number placeholders until texture-backed widget primitives land.

These limits are intentional. The HUD can become more configurable without becoming a second rules
engine.
