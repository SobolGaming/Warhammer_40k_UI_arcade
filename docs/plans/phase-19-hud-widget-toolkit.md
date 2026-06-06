# Phase 19 - HUD widget toolkit

## Goal

Create a reusable Arcade-native HUD widget toolkit before the HUD ergonomics pass starts composing
player-facing panels in earnest.

In plain language: Phase 17 created the empty screen regions. This phase creates the reusable HUD
"lego bricks" that can be placed inside those regions: panels, bars, chips, icon slots, cards,
rails, stat strips, rings, and containers. Phase 20 can then improve ergonomics by arranging stable
components instead of hand-positioning one-off text blocks.

The toolkit is presentation-only. It must not create rules, legal actions, decision IDs, option IDs,
proposal kinds, validation behavior, or hidden-information exceptions.

## Guidance Basis

This phase should use the guidance in:

- `docs/guidance/UI_HUD_DESIGN.md`
- `docs/guidance/ICON_GRAPHICS_SYSTEM.md`

The guidance points toward:

- stable screen geography with a top ribbon, side rails/benches, inspector, and bottom workbench;
- card-first information for missions and datasheets;
- progressive disclosure for full rules text;
- battlefield overlays for spatial facts only;
- Arcade-native widgets/layouts instead of embedded browser UI;
- SVG icons treated as source art, rasterized and cached as Arcade textures;
- theme tokens that can recolor icons, chips, and panel states consistently.

## Relationship To Adjacent Phases

Phase 17 owns named HUD zones and layout presets. Phase 18 owns battlefield action-summary overlays.
This phase owns reusable HUD components inside the zones.

Phase 20 should consume this toolkit to polish movement usability, selected-unit actions, keyboard
workflow, accessibility toggles, and information placement.

This phase should not:

- implement final command points, scoring, army roster, mission, datasheet, Stratagem, shooting,
  dice, or fight content;
- add authoritative game logic;
- change core adapter payloads;
- make preferences define rules;
- depend on mutable engine internals.

## Toolkit Architecture

### Theme and tokens

Add a typed HUD theme layer that maps preferences and built-in defaults to stable visual tokens.

Tunable attributes:

- color roles: `player`, `opponent`, `neutral`, `active`, `selected`, `warning`, `invalid`,
  `disabled`, `preview`, `authoritative`, `debug`;
- panel fills: background color, alpha, border color, border alpha, border width;
- typography: font family, base size, compact size, title size, line height, emphasis weight where
  Arcade supports it;
- spacing: `gap_x`, `gap_y`, inner padding, outer margin, divider spacing;
- density: `compact`, `standard`, `detailed`;
- icon defaults: size, color role, disabled opacity, active opacity, padding;
- state treatments: normal, hover, focus, selected, active, disabled, invalid, warning;
- high-contrast override tokens;
- debug/evidence tokens for headless captures.

### Component model

Each reusable component should have:

- a pure view-model/dataclass with JSON-safe state where practical;
- a rendering adapter that can create Arcade GUI widgets or deterministic render primitives;
- a stable component ID for tests and diagnostics;
- an optional icon slot using icon IDs from the future icon registry;
- predictable state styles;
- no direct engine mutation or rule validation.

The toolkit should preserve the current testable primitive path. If a live Arcade GUI widget is used,
headless evidence must still have a deterministic primitive or offscreen-rendered equivalent.

### Layout composition model

Add parent/child placement structures so a large region can host nested subpanels without every
component knowing absolute screen coordinates.

Required layout concepts:

- `HudContainer`: non-renderable or renderable parent box with padding, gap, alignment, clipping,
  and z-order.
- `HudStack`: vertical or horizontal ordered children with spacing, alignment, and optional wrap.
- `HudGrid`: row/column slots for stats, weapon rows, dice pipeline steps, mission-card grids, and
  datasheet fields.
- `HudAnchor`: child pinned to top/bottom/left/right/center within a parent.
- `HudOverlayLayer`: transient layer for tooltips, hover previews, modal pickers, and debug overlays.

Arcade GUI has parent/child layout support through widgets/layouts, but it is not a browser DOM.
Clipping and scroll behavior must be implemented and tested explicitly. Do not assume every child is
automatically clipped by its parent unless the specific Arcade widget/layout path proves it in
headless and live rendering.

## Widget Inventory And Tunable Attributes

### 1. `HudContainer`

Purpose: General parent container for nesting subpanels. It may draw nothing and only guide child
placement.

Tunable attributes:

- `container_id`;
- `render_mode`: `none`, `panel`, `outline`, `debug_bounds`;
- `rect` or parent-relative constraints;
- `anchor`, `offset`, `size_policy`, `min_size`, `max_size`;
- `padding`, `gap`, `alignment`;
- `clip_children`;
- `scroll_policy`: `none`, `vertical`, `horizontal`, `both`;
- `z_order`;
- `state`: normal, hover, focus, selected, disabled, warning, invalid;
- background fill, alpha, border color, border alpha, border width.

Expected uses:

- invisible parent inside a right inspector;
- two adjacent subpanels inside a bottom workbench;
- debug-only bounding boxes for diagnosing layout collisions.

### 2. `HudPanel`

Purpose: Renderable framed panel for cards, inspectors, workbenches, rails, and popovers.

Tunable attributes:

- title text and optional subtitle;
- background alpha and color role;
- border style, width, color role, alpha;
- padding, title padding, content gap;
- header visibility;
- footer/action row visibility;
- collapse state and collapsed size;
- clipping/scroll behavior;
- density and high-contrast mode;
- debug label visibility.

Expected uses:

- selected-unit inspector;
- assignment review panel;
- mission-card popover;
- bottom command bench section.

### 3. `IconSlot`

Purpose: Single icon rendering unit that uses the icon system once available.

Tunable attributes:

- `icon_id`;
- size in pixels;
- color role or explicit RGBA/tint;
- opacity;
- disabled/active/selected state treatment;
- optional background disc/square;
- badge text/count;
- tooltip key;
- fallback glyph or placeholder behavior for missing icons.

Expected uses:

- status chips;
- datasheet headers;
- action buttons;
- stratagem buttons;
- warning/invalid markers.

### 4. `IconTextBar`

Purpose: Compact bar with an icon on the left or right and one or more text fields. This is the
building block for unit-card headers, mission-card headers, action rows, and notification bars.

Tunable attributes:

- icon side: left, right, both, none;
- primary label;
- secondary label;
- value/counter text;
- hotkey hint text;
- icon size and color role;
- text alignment and truncation policy;
- background alpha;
- border/underline style;
- height;
- density;
- state treatment.

Expected uses:

- top of a unit datasheet card;
- selected unit name/status bar;
- action workbench step title;
- event log row header.

### 5. `StatusChip`

Purpose: Small scalar status/counter element.

Tunable attributes:

- label;
- value;
- icon ID;
- color role;
- threshold state: normal, low, warning, exhausted, invalid;
- shape: rectangular, pill, compact square;
- fill alpha, border alpha;
- minimum width;
- tooltip key;
- optional progress fraction.

Expected uses:

- CP;
- round;
- phase;
- score;
- model count;
- wounds remaining;
- action readiness.

### 6. `EntityChip`

Purpose: Compact reference to a unit, model, objective, terrain feature, or other selectable
entity.

Tunable attributes:

- entity reference key;
- display label;
- entity kind icon ID;
- owner/player color role;
- state: selected, target, source, assigned, unavailable, hidden_if_not_visible, invalid;
- compact/expanded mode;
- badge count;
- warning/invalid marker;
- tooltip/detail expansion;
- max width and truncation policy.

Expected uses:

- assignment source/target summaries;
- selected-vs-target comparison;
- shooting target declarations;
- stratagem target slots;
- event log entity references.

### 7. `DonutGauge`

Purpose: Ring/donut visual for bounded scalar values and readiness progress.

Tunable attributes:

- center or parent-relative placement;
- inner diameter;
- outer diameter;
- start angle;
- sweep angle;
- progress fraction;
- segment count;
- gap between segments;
- fill color/alpha;
- background ring color/alpha;
- outline color/alpha;
- label text;
- center icon ID;
- warning threshold colors;
- animation disabled by default for deterministic tests.

Expected uses:

- command point spend/readiness;
- objective control progress;
- wound/resource ring;
- activation readiness;
- turn timer ring.

### 8. `UnitRailCard`

Purpose: Compact unit tab/card for the left rail or player bench.

Tunable attributes:

- unit label;
- short label;
- player color role;
- model count summary;
- wounds/status summary;
- activation state: ready, moved, shot, fought, destroyed, in reserves, embarked;
- selection/hover/focus state;
- model/bodyguard/leader badges;
- warning/invalid marker visibility;
- icon IDs for role, status, transport/reserves;
- compact/expanded density;
- width/height;
- click target padding;
- tooltip/detail expansion behavior.

Expected uses:

- army rolodex rail;
- player/opponent bench roster cards;
- quick keyboard cycle targets.

### 9. `DatasheetHeader`

Purpose: Header area for selected-unit/model datasheets.

Tunable attributes:

- title;
- subtitle;
- faction/role icon;
- player color role;
- status chips to show in header;
- leader/bodyguard/attached-unit badges;
- collapse/expand control visibility;
- selection/target comparison mode;
- icon placement and size;
- header height and density.

Expected uses:

- top section of right inspector;
- selected-vs-target comparison card;
- expanded unit datasheet modal.

### 10. `DatasheetPanel`

Purpose: Composed unit/model datasheet card made from a header, stat strips, weapon/ability zones,
keyword rows, and footer actions.

Tunable attributes:

- header component;
- stat zone visibility;
- weapon zone visibility;
- ability/rules zone visibility;
- keyword zone visibility;
- footer/action row visibility;
- zone order;
- zone collapse states;
- zone height constraints;
- scroll policy for dense text zones;
- compact/standard/detailed density;
- selected-vs-target comparison mode;
- debug source-field visibility.

Expected uses:

- right inspector selected-unit panel;
- full datasheet popover;
- selected-vs-target comparison inspector;
- future army roster deep inspection.

### 11. `StatStrip` And `StatCell`

Purpose: Compact labeled stats for datasheets and target comparisons.

Tunable attributes:

- stat labels and values;
- icon IDs per stat;
- grid columns;
- cell width/height;
- emphasis state;
- delta/compare state: better, worse, same, unknown;
- tooltip key;
- compact/standard/detailed density.

Expected uses:

- Move, Toughness, Save, Wounds, Leadership, OC;
- weapon profile rows once shooting arrives;
- target comparison summary.

### 12. `MissionCard`

Purpose: Card-like presentation for primary/secondary/tactical mission information.

Tunable attributes:

- title;
- subtitle;
- card type;
- owner/player color role;
- score/progress chips;
- reveal state: hidden, revealed, held, scored, discarded;
- compact/expanded display;
- icon IDs for mission type/status;
- border color role;
- stack/hand placement;
- tooltip/detail expansion.

Expected uses:

- top ribbon mission summaries;
- player/opponent mission hand;
- mission popover.

### 13. `ActionButton`

Purpose: Clickable command element for known UI commands.

Tunable attributes:

- command ID;
- icon ID;
- label;
- hotkey hint;
- enabled/disabled state;
- disabled reason text;
- selected/active state;
- warning/invalid marker;
- button size;
- icon side;
- tooltip key;
- confirmation requirement flag.

Expected uses:

- movement action menu;
- confirm/cancel draft;
- inspect/measure;
- summary toggle;
- debug toggle.

### 14. `StratagemButton`

Purpose: Specialized action button shape for Stratagem-like options once the engine exposes those
flows.

Tunable attributes:

- title;
- CP cost badge;
- phase/timing badge;
- eligibility state: eligible, unavailable, already_used, insufficient_cp, unknown;
- target summary text;
- icon ID;
- color role;
- hotkey hint;
- tooltip/detail expansion;
- compact/expanded mode.

Expected uses:

- filtered stratagem tray;
- reactive-stratagem prompt;
- future stratagem target-binding workspace.

### 15. `AssignmentGroupRow`

Purpose: Row summarizing one generic assignment group in the assignment HUD/workbench.

Tunable attributes:

- group label;
- source entity chips;
- target entity chips;
- state: active, assigned, unassigned, warning, invalid;
- operation kind;
- summary lines;
- icon IDs for source/target/entity type;
- expand/collapse state;
- highlight color;
- row height;
- detailed/compact mode.

Expected uses:

- movement model assignment summaries;
- shooting model-to-target declarations;
- stratagem multi-target assignments.

### 16. `DicePipeline`

Purpose: Placeholder-ready component for future attack resolution.

Tunable attributes:

- pipeline steps;
- current step;
- dice pool summaries;
- modifier chips;
- reroll/action buttons;
- result state per step;
- icon IDs for hit/wound/save/damage;
- compact/expanded mode;
- history visibility.

Expected uses:

- bottom workbench once shooting/fight resolution is implemented;
- debug replay of attack-resolution events.

### 17. `Tooltip`

Purpose: Small overlay for explanations and debug details.

Tunable attributes:

- title;
- body lines;
- anchor target;
- placement preference;
- max width;
- delay;
- icon ID;
- color role;
- debug/source marker visibility;
- clipping against viewport.

Expected uses:

- action descriptions;
- invalid diagnostic explanation;
- model/unit ID debug mode;
- icon meaning help.

### 18. `Separator` And `Divider`

Purpose: Lightweight grouping elements.

Tunable attributes:

- orientation;
- thickness;
- color/alpha;
- margin;
- label text;
- icon ID;
- collapse behavior.

Expected uses:

- datasheet zones;
- workbench sections;
- event log groups;
- stat table subdivisions.

## Preferences And Customization

The toolkit should define presentation-only preferences for:

- active HUD theme;
- density;
- high-contrast mode;
- default icon size;
- panel opacity;
- text scale;
- tooltip delay;
- debug bounds visibility;
- component-specific defaults where safe, such as `donut_gauge.inner_diameter_px` or
  `unit_rail_card.compact_height_px`.

Preferences must be validated against known component IDs, known command IDs, known overlay IDs,
known icon IDs where available, and known color roles. Unknown values should produce typed
diagnostics rather than silently falling back.

## Icon System Requirements

The toolkit should be icon-ready without requiring final icon art in this phase.

Tasks:

- define an `icon_id` vocabulary for placeholder uses;
- create an icon-slot view model that can render a placeholder if no texture exists;
- reserve a rasterization/cache seam for future SVG `currentColor` source assets;
- allow icons to be tinted by theme color role;
- add tests proving missing icons are represented as explicit placeholders or diagnostics, not
  hidden failures.

## Implementation Tasks

- [ ] Create typed HUD theme tokens and default theme values.
- [ ] Create reusable component view models for the inventory above.
- [ ] Create layout composition view models for container, stack, grid, anchor, and overlay layer.
- [ ] Create primitive render adapters for the components needed by the current HUD.
- [ ] Keep live Arcade widget paths and headless primitive evidence paths visually aligned.
- [ ] Add icon-slot placeholder support and future SVG texture-cache interface.
- [ ] Add clipping/overflow proof for nested containers.
- [ ] Add component state style tests for normal, selected, disabled, warning, and invalid states.
- [ ] Add documentation examples showing how a right-inspector datasheet and bottom workbench can be
  assembled from toolkit components.

## Acceptance Criteria

- [ ] A parent container can host adjacent child panels without each child using absolute screen
  coordinates.
- [ ] A non-renderable container can guide child placement without drawing a visible panel.
- [ ] A renderable panel can draw fill, border, title, and clipped content in live and headless
  render paths.
- [ ] An `IconTextBar` can place an icon on the left or right and truncate or clip long labels
  predictably.
- [ ] A `DonutGauge` can render with configurable inner diameter, outer diameter, alpha, progress,
  and segment settings.
- [ ] Unit rail, datasheet header, datasheet panel, stat strip, entity chip, status chip, action
  button, mission card, and assignment row view models have explicit tunable attributes and
  deterministic tests.
- [ ] Toolkit preferences are presentation-only and cannot define legal actions or validation.
- [ ] Headless render evidence shows toolkit panel fills, labels, icons/placeholders, and clipping
  behavior close enough to the player-facing view to diagnose layout issues.

## Manual Validation Checklist

- [ ] Launch the default HUD layout and confirm toolkit placeholder panels match the configured
  theme opacity and borders.
- [ ] Switch between `compass_ring` and `command_bench` layouts and confirm child components remain
  parent-relative.
- [ ] Enable debug bounds and confirm invisible containers show diagnostic outlines only in debug
  mode.
- [ ] Increase text scale and confirm bars/cards preserve stable dimensions or clip predictably.
- [ ] Toggle high-contrast mode and confirm icon slots, warnings, and invalid states remain
  color-independent.

## Closeout Milestone

**Milestone 14: "HUD Component Toolkit"**

The UI has reusable, testable HUD components that can be composed into richer player-facing panels
without creating one-off render code for each future feature.
