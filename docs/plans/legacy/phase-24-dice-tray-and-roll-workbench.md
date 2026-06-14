# Phase 24 - Dice tray and roll workbench

## Status

Initial implementation in progress in PR for Phase 24.

This phase is presentation and decision-submission scaffolding only. It must not change core-client
payloads, engine validation, dice generation, reroll permission rules, hidden-information visibility,
event replay authority, or authoritative game state.

## Goal

Add a player-facing dice tray and roll workbench that can show engine-owned dice results, display
the roll context that the engine exposes, and support legal engine-provided dice reroll choices.

The workbench should make Advance, Charge, and Command Re-roll flows understandable in the live UI,
while also establishing reusable presentation machinery for the engine's current shooting, fight,
Hazardous, Feel No Pain, random characteristic, damage, roll-off, and other roll-state-bearing
workflows.

The engine remains the only authority for:

- when dice are rolled;
- which random or fixed values are used;
- which rerolls are legal;
- which dice indices may be selected;
- which option IDs may be submitted;
- what the final roll result means;
- which roll data is visible to a viewer.

## Current Core Dice Workflows To Support

The UI should be designed around the adapter-visible surfaces that already exist in
`Warhammer_40k_AI`.

### Movement Phase

- Selecting `advance` from `select_movement_action` rolls an engine-owned D6 Advance roll before the
  `submit_movement_proposal` request is emitted.
- The engine records `advance_roll_requested`, `dice_rolled`, and `advance_roll_resolved` events
  when no reroll window is pending.
- When a legal reroll source exists, the engine can emit a finite `select_dice_reroll` request with
  `phase_body_status: advance_roll_reroll_pending`.
- The later movement proposal context carries `movement_mode: "advance"` and the authoritative
  `advance_roll` payload that defines the movement budget.
- Desperate Escape and Fall Back hazard-style dice records are also engine-owned roll workflows and
  should be displayable through the generic dice reducer even if they are not the first manual demo.

### Charge Phase

- Selecting a charging unit through `select_charging_unit` immediately resolves an engine-owned 2D6
  `charge_roll`.
- The engine emits `charge_roll_resolved`.
- If a target is reachable, the later Charge Move proposal carries `movement_mode: "charge"`,
  `maximum_distance_inches`, reachable target context, and the source `charge_roll` payload.
- Phase 15A Charge rolls currently forbid Command Re-roll through a source rule, so the tray must
  not offer a reroll unless the engine emits an actual reroll request.

### Command Re-roll And Nested Dice Decisions

- The engine uses finite `select_dice_reroll` decisions for eligible dice rerolls.
- Legal options are engine-emitted, such as `decline` or `reroll:<index>[,<index>...]`.
- Single-die rolls and Charge rolls can resolve through whole-roll reroll semantics.
- Non-Charge multi-dice rolls can emit one legal reroll option per authorized component selection.
- The UI may stage dice by click, face column, or keyboard shortcut, but confirm must enable only
  when the staged index tuple maps exactly to an engine-provided option ID for the current request.

### Attack, Save, Hazard, Damage, And Other Roll Families

The first implementation should provide generic display coverage for current engine payloads before
trying to build a fully optimized shooting/fight workbench. The reducer should recognize and display
roll-state-bearing payloads from:

- random attack count and random characteristic rolls;
- hit rolls;
- wound rolls;
- armour or invulnerable saving throws;
- damage rolls;
- Hazardous tests;
- Feel No Pain style rolls when exposed by the engine flow;
- D3 source rolls;
- roll-offs;
- destroyed transport and other hazard/disembark rolls;
- Fight phase attack-resolution rolls.

For these flows, Phase 24 should show available roll values, totals, source, and engine-provided
context. It must not infer local hit targets, wound targets, saves, criticals, generated hits, damage
rules, or reroll eligibility unless those semantics are present in the viewer-scoped payload.

## Source Interfaces

Initial work should consume only UI-facing adapter surfaces:

- `UiCoreClient.get_events_since(cursor, viewer_player_id)` for viewer-scoped roll events;
- `UiClientStatus.decision` for pending `select_dice_reroll` decisions;
- `UiDecision.options` for legal finite reroll option IDs;
- `UiDecision.payload` for `roll_id`, `roll_type`, `current_values`, `allowed_selections`, and
  permission metadata;
- existing finite decision submission for the selected engine-provided reroll option.

The implementation must not import mutable engine internals outside `core_client`.

## Dice Art And Asset Requirements

The initial D6 skin should use the built-in Aeldari SVG dice faces:

- `src/warhammer40k_arcade_ui/resources/art/icons/aeldari_die_face_1.svg`
- `src/warhammer40k_arcade_ui/resources/art/icons/aeldari_die_face_2.svg`
- `src/warhammer40k_arcade_ui/resources/art/icons/aeldari_die_face_3.svg`
- `src/warhammer40k_arcade_ui/resources/art/icons/aeldari_die_face_4.svg`
- `src/warhammer40k_arcade_ui/resources/art/icons/aeldari_die_face_5.svg`
- `src/warhammer40k_arcade_ui/resources/art/icons/aeldari_die_face_6.svg`

The user-facing asset IDs should be presentation-only aliases such as:

- `dice.aeldari.d6.face_1`
- `dice.aeldari.d6.face_2`
- `dice.aeldari.d6.face_3`
- `dice.aeldari.d6.face_4`
- `dice.aeldari.d6.face_5`
- `dice.aeldari.d6.face_6`

Implementation guidance:

- load built-in SVGs through the Phase 22 resource source model, not raw filesystem assumptions;
- support package-zip-safe access through `importlib.resources` helpers;
- rasterize/cache SVGs to Arcade textures when the renderer needs bitmap textures;
- keep the cache keyed by source, face, color role or tint, and target size;
- emit an explicit placeholder and diagnostic when a configured dice face cannot resolve;
- allow later preferences or HUD composition YAML to choose a different named dice skin or explicit
  face asset IDs;
- keep dice art selectable strictly as presentation. Preferences must not define die values, roll
  legality, target numbers, reroll options, or visibility exceptions.

## Presentation Model

Introduce immutable, JSON-safe view models:

- `DiceRollView`: roll ID, type, title, actor, phase context, source, expression, values, total,
  current total, semantic chips, and diagnostics.
- `DiceComponentView`: one die/component with original index, current value, sides, selectable
  state, rerolled state, and optional presentation component ID.
- `DiceFaceColumnView`: face value, face icon asset ID, count, component refs, and disabled or
  semantic styling flags.
- `DiceBucketView`: staged component refs, selected count, confirm state, target option ID when
  matched, and diagnostic text for unsupported staged selections.
- `DiceRerollRequestView`: request ID, actor ID, source roll ID, roll type, current values,
  allowed index tuples, option mapping, decline option ID, and permission summary.
- `DiceTrayView`: active roll, pending reroll request, bucket, recent history, pinned roll,
  attention state, cursor, and diagnostics.

The tray should synthesize presentation component IDs from `roll_id` plus ordered index until the
engine exposes adapter-visible component IDs. Synthetic presentation IDs must never be submitted to
the engine.

## Reducer Requirements

Add a pure dice reducer before rendering. It should:

- consume viewer-scoped `UiEventDelta` rows;
- retain a bounded recent roll history;
- preserve event cursor information;
- recognize `dice_rolled`, `dice_reroll_declined`, `dice_reroll_resolved`, `advance_roll_resolved`,
  `charge_roll_resolved`, `d3_roll_resolved`, `roll_off_resolved`, Hazardous events, attack-sequence
  roll events, and other roll-state-bearing events;
- normalize roll values into `DiceRollView` without deriving hidden or rule-sensitive semantics;
- associate pending `select_dice_reroll` decisions with the matching roll ID;
- produce typed diagnostics for unmatched reroll requests, stale current values, missing roll IDs,
  unsupported die side counts, or missing dice art;
- fail closed for game-affecting actions when a request cannot be mapped to engine-emitted options.

The reducer should categorize dice by face value and explicit core-provided semantic fields only.
It must not decide success, failure, criticals, wound targets, save targets, damage rules, generated
hits, or reroll eligibility locally.

## HUD And Rendering Requirements

Use the Phase 19/23 HUD toolkit and composition model. The dice tray should be a configurable
workbench widget, not a separate legacy overlay path.

Required widgets or widget extensions:

- `DiceTray`: shell for active roll, face columns, bucket, action row, and diagnostics;
- `DiceFaceColumn`: fixed D6 face column with icon, count, dice stack, and selected/disabled state;
- `DiceBucket`: staged dice and confirmability state;
- `DiceRollSummary`: title, context, expression, total/current total, source, and result chips;
- `DiceActionRow`: decline, clear, and confirm controls;
- `RollHistory`: compact recent-roll list or pinned detail view.

Layout requirements:

- fixed D6 columns for faces 1 through 6;
- one bucket column for staged dice;
- an optional "other" column for non-D6 expressions;
- stable column widths as counts change;
- deterministic clipping or ellipsis for long roll reasons;
- no overlap with movement paths, target lines, or model placement previews;
- animation disabled by default in headless evidence unless an animation test explicitly enables it.

The preferred live placement is the bottom workbench during active roll/reroll decisions, with a
compact recent-roll summary available in a top ribbon or review panel.

## Interaction Requirements

The tray should support:

- click a die to toggle it when selectable;
- click a face column count to stage every currently selectable die with that face value;
- Shift-click to add dice or a face column to the staged set;
- Ctrl-click to remove dice or a face column from the staged set;
- clear bucket;
- keyboard traversal across face columns, dice, bucket, and action buttons;
- deterministic staged selection order by component index;
- confirm only when the staged tuple exactly maps to an engine option ID;
- decline only when the engine emits a decline option.

Convenience shortcuts such as "reroll all 1s" are allowed only when the resulting index tuple maps
exactly to an engine-emitted option. The UI must surface "unsupported selection" as presentation
diagnostic text instead of trying to submit an invented choice.

## Configuration Requirements

Presentation-only configuration should cover:

- tray visibility policy: hidden, compact, active-roll, always;
- default HUD zone or workbench region;
- dice skin ID;
- per-face asset IDs for the initial Aeldari D6 skin and future skins;
- icon size;
- max visible dice per face before compact stacking;
- count-only threshold for very large pools;
- attention flash settings;
- reduced-motion behavior;
- high-contrast behavior;
- source/debug metadata visibility;
- roll history length;
- pinned-roll behavior.

Configuration must not cover:

- legal reroll policies;
- target numbers;
- success/failure rules;
- option IDs;
- timing windows;
- visibility exceptions;
- auto-submission of game-affecting decisions.

## Implementation Tasks

1. Add dice view models and a pure reducer.
2. Add built-in dice art asset aliases for the six Aeldari D6 SVG faces.
3. Add SVG-to-texture loading/caching or integrate the faces into the existing icon slot pipeline.
4. Add read-only `DiceTray` rendering for recent roll events.
5. Display Advance and Charge roll results from live engine events and proposal contexts.
6. Detect pending `select_dice_reroll` decisions and render legal choices.
7. Add bucket selection state for exact allowed index tuples.
8. Submit reroll/decline choices through the existing finite decision path.
9. Add generic extraction for current attack/save/hazard/damage/random/roll-off roll payloads.
10. Add HUD composition examples and a preview fixture using sample roll and reroll data.
11. Add deterministic unit tests for reducer behavior, option mapping, and selection state.
12. Add render primitive/headless evidence tests for D6 columns, bucket state, missing art, and
    compact overflow.
13. Update `docs/hud-customization.md` with dice tray configuration and data refs.
14. Update this phase plan with implementation progress and manual validation notes.

## Non-Goals

- Do not implement dice generation or randomization in the UI.
- Do not implement local roll validation or target-number rules.
- Do not add UI-owned reroll permission logic.
- Do not infer hidden enemy or mission data from raw events.
- Do not add auto-submit/autoplay dice decisions.
- Do not build a full shooting/fight declaration UI in this phase.
- Do not require new core adapter fields before displaying current engine roll payloads.

## Acceptance Criteria

- Advance rolls from the live core appear in the dice tray with the Aeldari D6 face art and the
  resulting movement proposal still uses the engine-provided movement budget.
- Charge rolls appear as a 2D6 result without exposing unsupported reroll controls.
- A pending `select_dice_reroll` request renders the current values, legal selectable indices,
  decline option when present, and exact engine option mapping.
- Confirm remains disabled until staged dice exactly match an engine-emitted option.
- Reroll and decline submissions preserve request IDs and option IDs through the existing finite
  decision path.
- Reroll results update from authoritative engine events/status, not UI prediction.
- Generic `dice_rolled` and known roll-state-bearing events appear as read-only roll history.
- Missing dice face art produces a visible placeholder plus a typed diagnostic.
- Headless render evidence proves face columns, counts, bucket, disabled dice, selected dice, and
  compact overflow fit without text overlap.
- Preferences and HUD YAML remain presentation-only.

## Manual Validation Checklist

- Run `uv run warhammer40k-arcade-ui --live-core-smoke` and select an Advance action. Confirm the
  tray shows the engine D6 result and the movement proposal budget reflects Movement plus the roll.
- In a reroll-capable fixture, trigger an Advance or Command Re-roll window. Confirm the tray shows
  the pending reroll request and only legal dice are selectable.
- Stage a legal reroll option and confirm it submits once through the finite decision path.
- Stage an unsupported combination and confirm the tray shows a diagnostic and does not submit.
- Decline a reroll and confirm the tray records the declined state without locally changing values.
- Trigger a Charge selection and confirm the tray shows the 2D6 roll and reachable-distance context
  when the engine exposes it.
- Trigger at least one current attack/save/Hazardous/damage/random roll workflow available in the
  live or test engine and confirm it appears as read-only roll history.
- Run the HUD preview fixture and confirm the Aeldari dice faces render at the configured sizes.

## Verification Commands

Implementation PRs should run:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pyright
uv run pytest tests/
uv run pre-commit run --all-files
```

Dice implementation slices should also run the GUI event harness and headless render evidence suites
that cover dice tray layout, if those suites are available in the current environment.

## Implementation Progress Notes

Initial Phase 24 implementation adds the presentation and evidence foundation:

- added immutable dice tray view models and a pure reducer over viewer-scoped event payloads;
- retained a bounded recent event-payload tail in `FiniteDecisionUiState` so HUD code can display
  recent roll evidence without adding another event pipeline;
- recognized generic `dice_rolled`, `advance_roll_resolved`, `charge_roll_resolved`, and nested
  roll-state-bearing payloads;
- detected pending `select_dice_reroll` finite decisions and exposed request ID, current values,
  allowed selections, decline option, and legal reroll option summaries;
- added `dice.aeldari.d6.face_1` through `dice.aeldari.d6.face_6` as known presentation icon IDs;
- added a `DiceTray` HUD widget and `dice_tray` / `hud.dice_tray.active` runtime bindings;
- placed the tray in the right two-thirds of the bottom HUD workbench in both built-in HUD layouts;
- added a workbench preview fixture with sample Aeldari D6 face columns and pending reroll metadata;
- documented the `DiceTray` widget in `docs/hud-customization.md`;
- added reducer, state retention, composition, and ergonomic HUD tests.

The first implementation intentionally does not add a separate direct click-to-submit dice bucket
path. Pending reroll decisions still submit through the existing finite decision path, preserving
engine-provided request IDs and option IDs. Direct face-column/bucket interaction should be added
only after the composition widget input model can route clicks and keyboard focus without creating a
second decision-submission path.

The first implementation also registers and carries the built-in Aeldari SVG face asset IDs, but the
current composition renderer still emits deterministic shape/text primitives rather than texture
primitives. Actual SVG rasterization and texture-backed widget rendering remains follow-on renderer
work.

Automated verification for the initial implementation:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .
env UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check .
env UV_CACHE_DIR=/tmp/uv-cache uv run mypy src tests
env UV_CACHE_DIR=/tmp/uv-cache uv run pyright
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/
env UV_CACHE_DIR=/tmp/uv-cache PRE_COMMIT_HOME=/tmp/pre-commit-cache uv run pre-commit run --all-files
env UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/check_import_boundaries.py
env UV_CACHE_DIR=/tmp/uv-cache uv build
```

Manual validation for the initial implementation:

- Run `uv run warhammer40k-hud-preview docs/hud/examples/workbench-preview.yaml` and confirm the
  dice tray occupies the right side of the bottom workbench with face columns, count text, selectable
  count text, and a reroll bucket column.
- Run `uv run warhammer40k-arcade-ui --live-core-smoke --ui-prefs docs/preferences/default.yaml`,
  choose an Advance action, and confirm the bottom workbench updates to show the latest visible roll
  once the engine emits roll events.
- If the engine emits `select_dice_reroll`, confirm the tray labels the reroll state and the
  existing finite option highlight/confirm flow still submits an engine-provided option ID.

## Forward-Looking Core Requests

The current engine surfaces are usable for an initial tray, but future core work would make the UI
cleaner:

- adapter-visible `DiceRollInstancePayload` with stable component IDs;
- normalized roll-event envelopes for phase, step, actor, source unit, target unit, weapon, and
  attack context;
- direct mapping from `select_dice_reroll` requests to source roll event and component IDs;
- engine-authored shortcut groups such as "all ones" or "failed hits", still backed by exact option
  IDs;
- fast-dice batch summaries with face counts and per-component semantic result data;
- explicit viewer-scoped redaction metadata for dice tied to hidden mission cards or secret actions.

These are core contract improvements, not UI workarounds. The Phase 24 UI should adapt to them when
they appear.
