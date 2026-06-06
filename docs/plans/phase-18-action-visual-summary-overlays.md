# Phase 18 - Action visual summary overlays

## Goal

Add togglable battlefield overlays that summarize the current workspace assignment visually.

In plain language: the Generic Assignment HUD tells the player what is assigned in a list. This
phase adds the matching picture on the battlefield. The player should be able to press a button and
see "what is about to happen" drawn directly over the table.

Examples:

- movement: green or grey model path lines with final ghost bases;
- shooting: red lines from firing models or weapon groups to the target unit;
- Stratagems: a Stratagem marker or icon over the battlefield with lines to affected units;
- placement: candidate placement ghosts and relationship lines to the source unit/transport;
- future allocation/damage choices: focused lines or highlights from the current attack pool to the
  relevant target/allocation group.

The summary is advisory. It is a view of the local workspace and engine-returned diagnostics. It is
not game state and it does not validate rules.

## User-Facing Behavior

The visual summary has two intensity modes:

- **Dim summary:** a low-emphasis version that can remain visible while the player is working. It
  should not compete with ordinary selection, terrain, objectives, or model labels.
- **Review summary:** a bright, high-emphasis version shown when the player actively toggles review
  mode or opens the assignment review HUD. This is the "check my work before I submit" view.

The same assignment data should drive both the HUD list and the battlefield summary. If the HUD says
model 1 has movement path A, the table should show model 1's path A. If the HUD says three weapons
target an enemy unit, the table should show the corresponding target links when the shooting tool
exists.

## Placement In Roadmap

This phase comes after Phase 17 because it depends on the Generic Assignment HUD/workspace data and
the configurable HUD zone framework. The summary overlays draw on the battlefield, but their review
controls and diagnostics should live in the stable HUD regions created by Phase 17 instead of adding
more independently positioned text panels.

Earlier phases should prepare for this by preserving visual summary-friendly data, but they should
not implement the full overlay system before the HUD/workspace is stable.

## Phase 18 Implementation Scope

Plan review found the goals complete, but the original task list intentionally spans future
shooting, Stratagem, placement, charge, and fight tools that do not yet have concrete UI workspaces.
This implementation therefore keeps Phase 18 to the first safe slice:

- preference-backed action-summary visibility and review intensity controls;
- generic advisory summary view models;
- movement summary adapter from the existing movement assignment workspace;
- dim/review movement path, ghost-base, and capped label primitives;
- debug/HUD visibility of active summary mode;
- explicit unsupported summary diagnostics for request families that do not yet have their own
  operation-specific workspace.

Later phases should add shooting target links, Stratagem icons, charge-specific summaries, and
fight-order highlights only when those tools expose concrete workspace data. The UI must not infer
those geometries from rules knowledge or from private interpretation of core requests.

## Core Update Impact Notes

Reviewed `Warhammer_40k_AI` `main` at `2d4d730` on 2026-06-05.

- Normalized `pending_proposal` metadata gives every parameterized summary a stable request anchor.
  Summary overlays should key request drift and trace/debug labels from `pending_proposal.request_id`
  and `pending_proposal.decision_type`.
- Charge Move is now a separate movement proposal family. Its summary must include target context
  and the deliberate no-move state when supported; until then, the summary layer should draw no
  guessed charge paths and should rely on the Phase 16 HUD diagnostic.
- Fight activation and fight interrupt are finite decisions. Their future visual summaries should
  highlight engine-provided eligible options, ordering band, pass/decline status, and interrupt
  context. They should not infer engagement eligibility, pass distance, or interrupt availability.

## Design Principles

1. **One data source.** The visual summary derives from the assignment workspace/HUD view model, not
   from a second private interpretation of the action.
2. **Advisory only.** Visual summaries show declared intent and engine diagnostics. They do not
   decide legality.
3. **Viewer-scoped.** Summaries must not expose hidden opponent data or hidden option counts.
4. **Togglable and preference-backed.** Users can turn the summary off, keep a dim summary on, or
   show a bright review summary.
5. **Operation-specific render adapters.** The generic summary model is shared, but movement,
   shooting, Stratagem, placement, and future tools own their own summary primitives.
6. **Readable under clutter.** Multiple lines and icons should be visually grouped, muted, or
   bundled when needed rather than producing unreadable noise.

## Pre-Plumbing Required In Earlier Phases

Phase 8 should make `EntityRef` summary-friendly:

- include display labels;
- include optional owner player IDs;
- expose current visual anchor points when available;
- expose parent refs for useful relationship summaries;
- make unavailable visual anchors a typed diagnostic, not a fallback guess.

Phase 9 should make movement assignments summary-friendly:

- keep per-model path groups;
- expose active, assigned, unassigned, and warning states;
- expose path points and final ghost-base poses through a stable view model;
- preserve enough grouping information to draw one path per model or one bundled path per selected
  subset.

Phase 16 should make the Generic Assignment HUD export summary data:

- assignment group IDs;
- assigned entity refs;
- target/result refs when present;
- advisory hint severity;
- authoritative diagnostic severity;
- readiness state;
- preferred summary style for the operation.

## Proposed Data Model

Add a generic view model, likely in the HUD or render-adjacent layer:

```text
ActionVisualSummary
  request_id
  operation_kind
  intensity: dim | review
  groups
  diagnostics
  ready
```

Each group can carry:

```text
ActionVisualSummaryGroup
  group_id
  label
  source_refs
  target_refs
  path_points
  icon_id
  color_role
  advisory_state
  diagnostic_state
```

The summary model should remain generic enough for HUD/render code, but payload construction stays
in operation-specific modules.

## Operation-Specific Visual Summaries

### Movement

- Draw model movement paths from each model's assigned path.
- Show final ghost bases.
- Use dim grey/green for ordinary previews.
- Use brighter green for active review.
- Use warning color only for advisory local hints or authoritative invalid diagnostics.
- Support grouped display when several models share the same translated path.

### Charge Move

Preliminary until the charge move tool is concrete:

- Draw charge move paths only from a supported `charge_move` workspace.
- Draw charge target links or highlights from engine-provided target context.
- Represent the no-move choice explicitly instead of drawing a path.
- Preserve the rolled charge distance and reachable target context as labels only when the request
  exposes them.
- Do not reuse Normal Move/Fall Back summaries without a charge-specific adapter.

### Fight Activation And Interrupt

Preliminary finite-decision summaries:

- Highlight the units represented by `fight:<fight_type>:<unit_instance_id>` options.
- Show the ordering band, such as Fights First or Remaining Combats, when the request payload
  exposes it.
- Show `eligible_to_fight_pass` and `decline_fight_interrupt` as explicit non-movement choices.
- Use a distinct interrupt review treatment when the request is a reaction-window interrupt.
- Do not draw pile-in, consolidation, or attack links until the engine exposes the relevant
  request-specific data.

### Shooting

Preliminary until the shooting assignment tool is concrete:

- Draw red or orange lines from attacker model/weapon groups to target units.
- Bundle repeated lines when many models target the same unit.
- Show target unit highlight and weapon/model count labels.
- Preserve target candidate legality from the engine request.

### Stratagems

Preliminary until the target-binding tool is concrete:

- Show a Stratagem marker/icon near the source or center of affected entities.
- Draw lines from the marker to selected target entities.
- Distinguish friendly and enemy target slots.
- Show incomplete target slots in the HUD rather than inventing map locations.

### Placement And Transport

Preliminary:

- Show placement ghosts and source relationship lines.
- For disembark, show transport-to-placement context.
- For reserves, show table-edge or zone context only if the projection/request exposes it.

## Tasks

- [x] Add action visual summary command and preferences:
  - toggle action summary;
  - force review summary;
  - dim summary default;
  - hide summary default.
- [x] Add action visual summary view models:
  - generic summary;
  - generic summary group;
  - diagnostic/advisory severity;
  - source/target/path/icon fields.
- [x] Add movement summary adapter from movement assignment workspace.
- [ ] Add render primitives for:
  - [x] dim path lines;
  - [x] review path lines;
  - [ ] source-to-target links;
  - [ ] icon markers;
  - [ ] grouped/bundled links;
  - [x] warning/diagnostic highlights.
- [x] Add HUD integration:
  - preference-backed hotkey can request review summary mode;
  - debug inspector can show active summary state;
  - summary state resets/reconciles on request drift.
- [x] Add visual clutter controls:
  - opacity tiers;
  - grouped labels;
  - maximum label count before bundling;
  - color-independent warning markers.
- [x] Add unsupported operation handling:
  - no summary for unsupported proposal tools;
  - visible diagnostic in the assignment HUD;
  - no guessed lines or icons.
- [x] Add preliminary adapters or explicit unsupported diagnostics for newly projected core
  request families:
  - `charge_move` proposal summaries;
  - `select_fight_activation` finite summaries;
  - `resolve_fight_interrupt` finite summaries.

## Acceptance Criteria

- [x] Player can toggle the current action visual summary on/off.
- [x] Player can switch between dim summary and bright review summary.
- [x] Movement assignments render from the same data shown in the Generic Assignment HUD.
- [x] Summary overlays clear or rebuild when the pending request changes.
- [x] Summary overlays do not mutate authoritative state.
- [x] Unsupported operations fail visibly in the HUD and do not draw guessed summaries.
- [x] Preferences can configure summary defaults without defining legal actions or validation.
- [x] Charge Move and fight-order request families are either summarized from explicit workspace
  data or visibly unsupported; neither silently reuses normal movement rendering.

## Tests

- [x] View-model tests for dim/review summary modes.
- [x] Movement summary adapter tests for one model, multi-model subset, and grouped paths.
- [x] Render primitive tests for movement summary lines and ghost bases.
- [ ] Render primitive tests for source-to-target links using deterministic fake assignment data.
- [x] Preference tests for summary toggle/default settings.
- [x] Request-drift tests proving summary state is cleared or reconciled.
- [x] Diagnostics tests proving local advisory warnings and authoritative invalid diagnostics are
  visually distinct.
- [x] Unsupported/placeholder summary tests for `charge_move`, `select_fight_activation`, and
  `resolve_fight_interrupt`.

## Manual Validation Checklist

- [ ] Draft per-model movement paths and toggle the visual summary.
- [ ] Confirm dim mode is visible but subdued during normal drafting.
- [ ] Confirm review mode brightens the current action summary.
- [ ] Confirm changing selected assignment groups updates the summary.
- [ ] Confirm canceling or request drift clears the summary.
- [ ] Confirm invalid diagnostics use a distinct warning treatment.
- [ ] Confirm preferences can hide the summary by default.

## Closeout Milestone

**Milestone 13: "Action Summary Overlays"**

The UI can show a battlefield-level visual summary of the current request workspace, starting with
movement and ready for later shooting, Stratagem, and placement tools.

## Implementation Notes

- Added `hud.action_summary` as the shared advisory view-model and movement adapter layer.
- Added `hud.action_summary_default` and `hud.action_summary_max_labels` as presentation-only
  preferences.
- Added `toggle_action_summary` and `review_action_summary` command IDs. Built-in profiles bind
  them to `v` and `shift+v`.
- Movement summaries render from `MovementDraft.assignment_views()`, the same source used by the
  Generic Assignment HUD.
- Unsupported future operations return explicit diagnostics and no drawable geometry.

## Automated Verification

Run at closeout:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pyright
uv run pytest tests/
uv run pre-commit run --all-files
```

Completed during implementation:

- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check .` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run mypy src tests` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pyright` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/` - 156 passed, 3 existing Arcade
  `draw_text` performance warnings.
- `PRE_COMMIT_HOME=/tmp/pre-commit-cache UV_CACHE_DIR=/tmp/uv-cache uv run pre-commit run
  --all-files` - passed after network approval to fetch configured hook repositories.

## Manual Validation Checklist

- Launch with `uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/default.yaml`.
- Select a unit and open/make a movement draft.
- Confirm the default dim action summary is visible while movement paths are assigned.
- Press `v` and confirm the action summary hides; press `v` again and confirm it returns.
- Press `shift+v` and confirm review mode draws brighter paths and final ghost-base labels.
- Press `ctrl+d` and confirm the debug inspector includes `Action summary: ...`.
- Use `docs/preferences/dense-debug.yaml` and confirm the summary starts in review intensity.
- Use a non-movement unsupported proposal fixture or live request and confirm the HUD reports
  unsupported summary behavior without guessed battlefield lines.
