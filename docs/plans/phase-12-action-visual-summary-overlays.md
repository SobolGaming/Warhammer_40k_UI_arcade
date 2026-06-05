# Phase 12 - Action visual summary overlays

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

This phase comes after Phase 11 because it depends on the Generic Assignment HUD and the workspace
data structures that describe selected entities, assignment groups, readiness, and diagnostics.

Earlier phases should prepare for this by preserving visual summary-friendly data, but they should
not implement the full overlay system before the HUD/workspace is stable.

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

Phase 11 should make the Generic Assignment HUD export summary data:

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

- [ ] Add action visual summary command and preferences:
  - toggle action summary;
  - force review summary;
  - dim summary default;
  - hide summary default.
- [ ] Add action visual summary view models:
  - generic summary;
  - generic summary group;
  - diagnostic/advisory severity;
  - source/target/path/icon fields.
- [ ] Add movement summary adapter from movement assignment workspace.
- [ ] Add render primitives for:
  - dim path lines;
  - review path lines;
  - source-to-target links;
  - icon markers;
  - grouped/bundled links;
  - warning/diagnostic highlights.
- [ ] Add HUD integration:
  - assignment HUD can request review summary mode;
  - debug inspector can show active summary state;
  - summary state resets/reconciles on request drift.
- [ ] Add visual clutter controls:
  - opacity tiers;
  - grouped labels;
  - maximum label count before bundling;
  - color-independent warning markers.
- [ ] Add unsupported operation handling:
  - no summary for unsupported proposal tools;
  - visible diagnostic in the assignment HUD;
  - no guessed lines or icons.

## Acceptance Criteria

- [ ] Player can toggle the current action visual summary on/off.
- [ ] Player can switch between dim summary and bright review summary.
- [ ] Movement assignments render from the same data shown in the Generic Assignment HUD.
- [ ] Summary overlays clear or rebuild when the pending request changes.
- [ ] Summary overlays do not mutate authoritative state.
- [ ] Unsupported operations fail visibly in the HUD and do not draw guessed summaries.
- [ ] Preferences can configure summary defaults without defining legal actions or validation.

## Tests

- [ ] View-model tests for dim/review summary modes.
- [ ] Movement summary adapter tests for one model, multi-model subset, and grouped paths.
- [ ] Render primitive tests for movement summary lines and ghost bases.
- [ ] Render primitive tests for source-to-target links using deterministic fake assignment data.
- [ ] Preference tests for summary toggle/default settings.
- [ ] Request-drift tests proving summary state is cleared or reconciled.
- [ ] Diagnostics tests proving local advisory warnings and authoritative invalid diagnostics are
  visually distinct.

## Manual Validation Checklist

- [ ] Draft per-model movement paths and toggle the visual summary.
- [ ] Confirm dim mode is visible but subdued during normal drafting.
- [ ] Confirm review mode brightens the current action summary.
- [ ] Confirm changing selected assignment groups updates the summary.
- [ ] Confirm canceling or request drift clears the summary.
- [ ] Confirm invalid diagnostics use a distinct warning treatment.
- [ ] Confirm preferences can hide the summary by default.

## Closeout Milestone

**Milestone 12: "Action Summary Overlays"**

The UI can show a battlefield-level visual summary of the current request workspace, starting with
movement and ready for later shooting, Stratagem, and placement tools.
