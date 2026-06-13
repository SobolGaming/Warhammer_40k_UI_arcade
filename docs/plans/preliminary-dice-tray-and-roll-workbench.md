# Preliminary Dice Tray And Roll Workbench

## Goal

Design a player-facing dice tray and roll workbench that can present engine-owned dice results,
support legal engine-provided reroll decisions, and scale from single Advance/Charge rolls through
high-volume shooting, saves, damage, Hazardous, Feel No Pain, and future Fight phase rolls.

The dice tray is presentation and interaction scaffolding only. The core engine owns every roll,
reroll permission, legal selected die set, mutation, event record, replay payload, and hidden-data
visibility rule.

## Current Core Capability Snapshot

The core already has useful dice plumbing:

- `DiceRollManager` can roll arbitrary `DiceExpression(quantity, sides, modifier)` values, records a
  deterministic `dice_rolled` event, and supports fixed or injected results for tests/replay.
- `DiceRollResultPayload` contains `roll_id`, `spec`, ordered `values`, `total`, and `source`.
- `DiceRollStatePayload` contains the original result, current values, current total, and reroll
  records.
- `select_dice_reroll` requests expose `roll_id`, `roll_type`, `allowed_selections`,
  `current_values`, optional `permission`, and engine-provided options such as `decline` or
  `reroll:0,2,5`.
- `RerollPermission` supports whole-roll and component-selection policies. Component selection is
  index-based today.
- `DiceRollInstance` and `DiceRollComponent` exist in core domain code and can derive stable
  component IDs like `roll-000001:component-0`, but the normal `dice_rolled` event payload currently
  exposes ordered values rather than a component list.
- Attack resolution uses `HitRollPayload`, `WoundRollPayload`, saving throw payloads, Hazardous
  payloads, random characteristic rolls, D3 source rolls, and other roll-state-bearing payloads.
- Attack resolution has `FastDiceGroup` plumbing for grouping identical attack pools when fast dice
  are safe, but hit and wound specs currently model one D6 per resolved attack context.
- `LocalGameSession.events_since(...)` exposes viewer-scoped event deltas. The UI facade preserves
  those as raw JSON objects through `UiEventDelta`.

Current gaps for a polished dice tray:

- The UI does not yet have a typed dice-roll view model or dice-specific event reducer.
- The UI does not yet have a dice-specific submission helper for `select_dice_reroll`; it only has
  the generic finite decision path.
- `dice_rolled` events do not currently include per-component IDs. A tray can synthesize stable
  presentation IDs from `roll_id` and index, but those IDs are not adapter-contract handles.
- Engine reroll requests currently select by index/options, not by semantic shortcuts such as
  "reroll all 1s". The UI may offer a convenience selection, but it must submit only an
  engine-provided option ID for the current request.
- The existing HUD toolkit has a placeholder `DicePipeline`; it does not yet implement the full
  tray, buckets, columns, selection state, animations, or roll history.

## Source Interfaces

Initial UI work should consume only these engine-facing surfaces:

- `UiCoreClient.get_events_since(cursor, viewer_player_id)` for viewer-scoped roll events and
  resolved roll records.
- `UiClientStatus.decision` for pending `select_dice_reroll` decisions.
- `UiDecision.options` for legal reroll option IDs.
- `UiDecision.payload` for `roll_id`, `roll_type`, `current_values`, `allowed_selections`, and
  permission metadata.
- Existing `submit_finite(...)` for submitting the selected engine-provided reroll option.

The first implementation should not require direct mutable engine imports outside `core_client`.

## Workflow Model

The dice tray should model a roll as a small immutable UI snapshot:

- roll identity: `roll_id`;
- roll class: `roll_type`, reason, actor ID, phase/step context when available;
- dice expression: quantity, sides, modifier;
- source: `rng`, `fixed`, or `injected`;
- ordered die entries with index, value, side count, rerolled flag, and optional presentation
  component ID;
- total and current total;
- result semantics when the roll payload provides them, such as success, critical, generated hits,
  wound target, save target, damage, mortal wounds, or failure count;
- pending action context, such as a current reroll request ID and legal selected-index sets.

The tray should model a pending reroll as a separate immutable UI snapshot:

- request ID and actor ID;
- source roll ID and roll type;
- current values from the request payload;
- allowed selections as exact index tuples;
- option IDs for each allowed selection;
- permission source ID and component-selection policy when present;
- declined option ID when present.

The UI must fail closed if a pending reroll request cannot be mapped back to a known roll snapshot.
It may still display the raw request as a diagnostic panel, but it must not invent legal selections.

## Dice Tray Layout Requirements

### Fixed D6 Columns

The primary D6 tray should use fixed columns:

- column 1 through column 6, one for each D6 face;
- one separate roll bucket column for selected dice or pending action targets;
- optional "other" column for non-D6 expressions until richer die-type layouts are designed;
- stable column widths so counts, hover outlines, selected dice, and animations do not resize the
  tray.

Each face column should support:

- a face icon row using selectable art assets;
- a count row showing how many dice currently show that face;
- a sorted dice stack/list for individual selectable dice;
- disabled/locked treatment for dice that are no longer selectable;
- rerolled marker for dice whose current value came from a reroll;
- success/critical/failure treatment supplied by engine roll semantics, not inferred from local
  rules.

The bucket column should support:

- selected dice staged for the next pending action;
- count of staged dice;
- action label such as "Reroll selected", "Allocate", or "Review";
- rejected/unsupported state when the staged set does not match an engine-provided option;
- clear-selection affordance.

### Roll Summary Rows

The tray should render:

- roll title: "Hit roll", "Wound roll", "Saving throw", "Advance roll", "Charge roll", or the
  engine-provided reason when no friendly label exists;
- unit/weapon/target context when present in viewer-scoped payloads;
- expression text such as `15D6`, `2D6`, `D3 source D6`, or `D6+modifier`;
- total/current total for sum-based rolls;
- face counts for D6 pools;
- result count chips such as hits, wounds, saves failed, damage, mortal wounds, criticals, or
  generated hits when those values are present in engine payloads;
- source marker for `rng`, `fixed`, or `injected` in diagnostics/debug density.

For a roll with more than one die, the count row should summarize face counts. The tray should not
collapse away individual dice when a pending component-selection decision exists.

### Sorted Columns

Dice should render in neat sorted columns:

- face columns ordered 1 to 6;
- dice within each column ordered by original component index unless a pending action explicitly
  prefers another order;
- replacement/rerolled dice keep their original component position and show reroll state;
- animations should not reorder dice while a selection is in progress.

### Attention Animation

The tray should support an attention flash when a new roll or pending dice decision appears.

Configuration should include:

- enabled/disabled flag;
- outline flash color role;
- interior flash color role;
- outline flash count;
- interior flash count;
- total duration;
- easing profile;
- reduced-motion override;
- high-contrast override;
- animation suppression for deterministic headless evidence unless explicitly enabled.

Attention animation must never hide text, counts, action buttons, diagnostics, or selected-die
state. It should be a cue, not a modal interruption.

### SVG And Asset Requirements

The dice tray should use the Phase 19 icon/art pipeline:

- face icons for D6 values 1 through 6;
- roll bucket icon;
- optional lock, reroll, critical, success, failure, warning, and source icons;
- asset IDs configurable through presentation-only profiles;
- missing art represented by explicit placeholder icons or typed diagnostics, not silent blank
  space;
- color tinting through theme roles where the art supports it.

Preferences may choose known art asset IDs and presentation settings. Preferences must not define
roll legality, reroll permissions, option IDs, target numbers, or hidden visibility.

## Interaction Requirements

### Selection

The tray should support:

- click a die to toggle its staged selection when selectable;
- click a face column count to stage every currently selectable die in that face;
- Shift-click to add a die or column to the current staged set;
- Ctrl-click to remove a die or column from the current staged set;
- click the bucket clear icon to clear staged dice;
- keyboard focus traversal through columns, dice, and action buttons;
- deterministic selection order by component index.

Selection rules:

- only dice whose indices appear in at least one `allowed_selections` tuple may be selectable;
- the staged selection must match an exact allowed tuple before the confirm action enables;
- a convenience action like "reroll 1s" may only enable when the corresponding index tuple maps to
  an engine-provided option;
- if the engine emits only whole-roll reroll, individual dice may be highlighted as part of the
  whole roll but cannot be independently toggled into an unsupported selection.

### Actions

The action row should support:

- decline;
- confirm selected reroll;
- select all legal dice for a face value;
- select all legal failures when the core exposes failure semantics;
- select all legal successes when a future flow needs it;
- inspect permission/source;
- pin roll to history;
- copy diagnostic payload in debug builds only.

Every game-affecting action must submit through the existing decision path:

```text
DecisionRequest -> UI staging -> engine-provided option ID -> DecisionResult -> engine validation
```

The UI may preselect a likely option, but it must not submit until the user confirms or an explicit
autoplay preference is later designed and approved against the adapter contract.

### Reroll Workflow

Expected flow:

1. Core emits roll events or a status payload containing roll state.
2. Dice tray displays the roll and flashes attention.
3. If core emits a pending `select_dice_reroll` request, the tray enters action mode.
4. Tray highlights legal dice and legal shortcut groups.
5. User selects dice or a shortcut that maps to an exact engine option.
6. User confirms, or declines.
7. UI submits the selected engine option ID.
8. Core emits `dice_reroll_declined` or `dice_reroll_resolved`.
9. Tray updates current values and reroll markers from the authoritative event/result.

The tray should be able to keep the original roll and replacement roll visible together for review.

## Warhammer 40,000 Workflow Coverage

The dice tray should be designed for these whole-game roll families:

- movement: Advance, Desperate Escape, random Movement characteristic, triggered movement rolls;
- charge: Charge rolls and Heroic Intervention charge-like rolls;
- shooting: random attacks, hit rolls, wound rolls, saving throws, damage rolls, Hazardous tests,
  mortal-wound routing, Feel No Pain;
- fight: melee random attacks, hit rolls, wound rolls, saves, damage, Fight phase special effects;
- command and morale-like flows: Battle-shock and other command-phase tests;
- transports: destroyed transport disembark rolls, transport hazard rolls;
- missions and stratagems: source-backed mission/action rolls, Command Re-roll, faction-specific
  reroll windows;
- sequencing: roll-offs where the tray may show both players' dice without exposing hidden data.

The first implementation should target Advance/Charge/reroll and generic event display before the
full shooting/fight workbench. The design should still reserve space for attack pipeline context so
the tray does not need to be rewritten when shooting/fight become first-class UI workflows.

## HUD Placement

Preferred placement:

- bottom workbench as the primary dice tray during active roll or reroll decisions;
- compact top-ribbon or event-log summary for recent roll totals;
- right inspector detail pane for pinned roll breakdowns and source permissions;
- optional popover for full roll history and debug payload inspection.

The center battlefield should remain reserved for spatial facts. Dice should not cover movement
paths, target lines, or model placement previews except as a transient attention cue.

## View-Model Requirements

Introduce presentation-only UI view models when implemented:

- `DiceRollView`: immutable roll snapshot from event/status payloads.
- `DiceComponentView`: one die/component, with index, value, side count, selection state, and
  optional presentation component ID.
- `DiceFaceColumnView`: face value, count, component refs, enabled/disabled state, and semantic
  badges.
- `DiceBucketView`: staged component refs, selected count, action state, and diagnostic line.
- `DiceRerollRequestView`: pending request, allowed selections, option mapping, permission summary,
  and current staged selection.
- `DiceTrayView`: full tray state, attention animation spec, active/pinned/history rolls, action
  row, diagnostics, and source cursor.

These view models should be JSON-safe where practical so they can be previewed and used in
headless evidence.

## Reducer Requirements

Add a pure dice event reducer before rendering:

- consume viewer-scoped `UiEventDelta` rows;
- recognize `dice_rolled`, `dice_reroll_declined`, `dice_reroll_resolved`, `d3_roll_resolved`,
  `roll_off_resolved`, `advance_roll_resolved`, `charge_roll_resolved`, `hazardous_test_resolved`,
  attack-sequence roll events, and future roll-state-bearing events;
- keep only viewer-visible events;
- retain enough recent rolls for history without unbounded memory growth;
- associate pending `select_dice_reroll` requests with the matching roll ID;
- detect stale or unmatched reroll requests and surface typed diagnostics;
- avoid deriving hidden or rule-sensitive semantics not present in payloads.

The reducer should not decide target numbers, failures, successes, criticals, generated hits, or
reroll eligibility locally. It may categorize dice by face value and by explicit core-provided
semantic fields.

## Rendering Requirements

Rendering should use Phase 19 toolkit concepts:

- `HudContainer` for the tray shell;
- `HudGrid` or equivalent fixed-column layout;
- `IconSlot` for dice faces, bucket, reroll, lock, warning, and result icons;
- `StatusChip` for totals and counts;
- `ActionButton` for decline/confirm/clear;
- `Tooltip` for permission and diagnostics;
- `DicePipeline` extended or replaced by richer `DiceTray` and `RollHistory` widgets.

The tray should have stable dimensions and responsive constraints:

- no column resizing when counts change;
- no text overlap at compact density;
- predictable clipping or wrapping for long roll reasons;
- deterministic primitive render evidence for headless tests;
- animation disabled by default in automated evidence unless the test is specifically about
  animation states.

## Configuration Requirements

Presentation-only configuration should cover:

- tray visibility policy: hidden, compact, active-roll, always;
- default workbench region;
- max visible dice per face column before compact stacking;
- count-only threshold for very large pools;
- attention flash settings;
- reduced-motion and high-contrast behavior;
- dice face art asset IDs;
- bucket icon asset ID;
- source/debug metadata visibility;
- roll history length;
- sound/haptics placeholder settings only if future platform support is approved.

Configuration must not cover:

- legal reroll policies;
- target numbers;
- success/failure rules;
- option IDs;
- timing windows;
- visibility exceptions;
- auto-submission of game-affecting decisions unless explicitly approved by a later contract review.

## Forward-Looking Core Needs

The current core is usable for an initial tray, but the following core-facing enhancements would make
the UI cleaner and less lossy:

- Adapter-visible `DiceRollInstancePayload` for roll events, including `components` with stable
  `component_id`, index, value, sides, and rerolled state.
- A normalized roll-event envelope that identifies phase, step, actor, source unit, target unit,
  weapon profile, and attack context where applicable.
- A standard mapping from pending `select_dice_reroll` requests back to the source roll event and
  component IDs.
- Optional semantic groups in reroll requests, such as "all ones" or "failed hits", where the core
  still emits exact selected indices and option IDs.
- Batch roll summaries for safe fast dice groups, including face counts, per-component IDs, and
  per-component semantic result when available.
- Viewer-scoped redaction rules for dice tied to hidden mission cards, secret actions, or hidden
  target information.
- Contract documentation for which dice event payloads are stable adapter surfaces versus internal
  replay records.

These are core contract needs, not UI workarounds. The UI should adapt as these surfaces appear.

## Implementation Slices

### Slice 1: Read-only dice event tray

- Add dice event reducer and typed view models.
- Display recent `dice_rolled` events as fixed D6 face counts and ordered dice.
- Show roll ID, roll type, reason, values, total, and source in debug density.
- Add headless render evidence and preview sample data.
- No player-facing dice decisions yet.

### Slice 2: Pending reroll request display

- Detect pending `select_dice_reroll`.
- Associate request to the current roll by `roll_id`.
- Highlight legal indices based on `allowed_selections`.
- Render decline and exact allowed option choices.
- Keep submission through generic `submit_finite`.

### Slice 3: Bucket selection and shortcut staging

- Add staged-selection state.
- Support click dice, click face column, clear bucket, and keyboard navigation.
- Enable confirm only when staged indices map to an engine option.
- Add diagnostics for unmatched selections and stale current values.

### Slice 4: Attack pipeline integration

- Connect hit/wound/save/damage roll-state-bearing events into tray semantics.
- Show step chips for hit, wound, save, damage, Hazardous, Feel No Pain.
- Pin current attack context in the workbench.
- Keep fast-dice and per-attack events visually coherent.

### Slice 5: Full roll history and review tools

- Add compact roll history with filters by phase, actor, unit, weapon, roll type, and decision.
- Add pinned roll detail view.
- Add replay/debug payload inspection in diagnostic mode.
- Add screenshot/headless evidence fixtures for dense shooting pools.

## Acceptance Criteria

- The tray can render a multi-die D6 roll as fixed 1 through 6 columns plus a bucket column.
- Counts remain stable and readable for small, medium, and large rolls.
- The tray can render a pending `select_dice_reroll` request without inventing legal selections.
- A user can stage dice and confirm only when the staged set matches an engine-provided reroll
  option.
- Decline and reroll submissions use the existing finite decision path and preserve request IDs.
- Reroll results update from authoritative core events, not local prediction.
- The tray handles rolls with no pending decisions as read-only history.
- The tray handles whole-roll-only rerolls without enabling unsupported partial selection.
- Missing dice art produces explicit placeholder/diagnostic output.
- Headless render evidence proves counts, bucket state, selected dice, disabled dice, and attention
  flash states fit without overlap.
- Preferences remain presentation-only.

## Manual Validation Checklist

- Trigger a live Advance roll and confirm the tray shows the D6 result after the engine roll.
- Trigger an Advance reroll-capable fixture and confirm the tray shows the pending reroll request.
- Select one legal die and submit the engine-provided `reroll:<index>` option.
- Decline a reroll and confirm the tray records the declined state without changing values.
- Review a Charge roll and confirm a 2D6 total is shown without offering unsupported partial rerolls.
- Review a future shooting attack sequence and confirm hit/wound/save/damage steps stay readable.

## Open Questions

- Should the core promote `DiceRollInstancePayload` into the adapter event contract, or should the UI
  synthesize presentation component IDs from roll ID plus index until a contract update lands?
- Should reroll shortcut groups such as "all 1s" be formal core option metadata, or remain UI
  convenience only when they exactly match an existing option?
- How much roll history should remain visible during dense shooting without crowding the bottom
  workbench?
- Should sound or haptic cues be part of the tray profile, or deferred until visual accessibility is
  complete?
- Do attack sequence events need a normalized public roll envelope before the UI attempts the full
  shooting dice workbench?

## Verification Plan

Future implementation PRs should run:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy src tests`
- `uv run pyright`
- `uv run pytest tests/`
- `uv run pre-commit run --all-files`

Dice-tray implementation slices should also add focused tests for:

- dice payload parsing and reducer behavior;
- event-cursor preservation;
- reroll request to option mapping;
- selected bucket state transitions;
- render primitive layout and headless evidence;
- no direct mutable engine imports outside `core_client`.
