# Phase 11 - Generic assignment HUD

## Goal

Add a reusable HUD surface for reviewing request-scoped entity selections and assignments before
submission.

In plain language: the Generic Assignment HUD is the checklist and workbench for "what am I about
to submit?" It should show the player which things are selected, which things already have an
assigned job, which things are still unassigned, and what the current engine request is asking for.

For movement, it might show:

- this unit is making a Normal Move;
- models 1 and 2 have path A;
- model 3 has path B;
- models 4 and 5 have not been assigned a path yet;
- the preview is ready or incomplete;
- any warnings are preview-only and the engine will validate after submission.

For future shooting, the same HUD idea can show:

- these models/weapons are assigned to target unit A;
- these models/weapons are assigned to target unit B;
- these weapons are not assigned yet;
- the declaration is incomplete until every required weapon choice is resolved.

For future Stratagems, it can show:

- friendly target slot: two units selected;
- enemy target slot: one unit selected;
- objective slot: none selected yet;
- the target binding is incomplete or ready.

The HUD is "generic" because the layout and review behavior are reusable. The payload builders
remain operation-specific so this HUD does not become a private rules engine.

The same backing data should also be usable by later visual action summaries. The HUD is the list
view of the workspace; Phase 12 adds the battlefield picture view of the same workspace.

## Workspace Concept In Plain Language

A workspace is temporary local scratch space for one pending engine request. It is like a tray where
the player collects pieces before sending one answer to the engine.

The workspace remembers:

- what request it belongs to;
- what kind of operation is being built, such as movement or shooting;
- which entities the player has selected for the current step;
- which entities have already been assigned to an outcome;
- what is still missing;
- a preview of the JSON-safe payload that will eventually be submitted.

The workspace disappears or rebuilds when the engine request changes. It does not mutate the game
state. The engine remains the only authority after submission.

## Prerequisites

- Phase 8 entity selection foundation.
- Phase 9 movement model assignments.
- Phase 10 movement submission diagnostics can be implemented before or after this phase, but this
  HUD should consume the same movement assignment data model.

## Tasks

- [ ] Add generic assignment HUD view models:
  - request ID;
  - actor ID;
  - operation kind;
  - active layer;
  - active selection refs;
  - assignment groups;
  - assigned refs;
  - unassigned refs;
  - readiness state;
  - advisory hints;
  - authoritative diagnostics, when present;
  - summary group IDs and refs for later visual summary overlays.
- [ ] Add movement-specific adapters into the generic HUD:
  - movement action;
  - proposal kind;
  - movement mode;
  - Fall Back mode;
  - model path assignment groups;
  - per-group path length summaries;
  - unassigned/unchanged model hints.
- [ ] Add render primitives for multi-selection and assignment states:
  - ordinary inspect selection;
  - request-selected entities;
  - active assignment group;
  - assigned but inactive entities;
  - unassigned candidate entities;
  - invalid or warning-highlighted preview entities.
- [ ] Add visual-summary pre-plumbing:
  - expose assignment groups in a stable order;
  - expose safe source and target refs;
  - expose advisory/diagnostic severity;
  - expose readiness state;
  - do not draw the full action summary yet.
- [ ] Add compact HUD layout:
  - current request header;
  - assignment list;
  - active selection summary;
  - completeness/readiness line;
  - diagnostic/warning lines;
  - preference source and debug fields when the debug inspector is visible.
- [ ] Add preference-backed display settings:
  - show/hide assignment HUD;
  - compact/detailed assignment rows;
  - color-independent warning markers;
  - optional auto-follow chain display.
- [ ] Add keyboard/mouse affordance labels only where they are normal control labels, not tutorial
  prose.
- [ ] Keep all warnings marked as preview/advisory unless they are engine-returned diagnostics.
- [ ] Ensure the HUD can represent unsupported workspaces without failing:
  - unsupported proposal tool;
  - missing candidate metadata;
  - request changed while local assignments existed.

## Acceptance Criteria

- [ ] Movement assignment state is visible in the generic HUD.
- [ ] The player can distinguish active selection, assigned models, and unassigned models.
- [ ] The HUD clearly distinguishes local preview hints from authoritative engine diagnostics.
- [ ] The HUD can show an incomplete assignment and a ready assignment.
- [ ] The HUD can show request-scoped state without clearing ordinary inspect selection.
- [ ] Preference settings can hide or compact the HUD without changing behavior or legality.
- [ ] Unsupported workspaces produce visible diagnostics rather than blank panels.
- [ ] The HUD view model contains enough stable group/ref data for Phase 12 to build visual summary
  overlays from the same workspace state.

## Tests

- [ ] HUD view-model tests for empty, incomplete, ready, and invalid movement workspaces.
- [ ] HUD view-model tests for active/assigned/unassigned entity refs.
- [ ] Render primitive tests for assignment highlights.
- [ ] Preference tests for assignment HUD settings.
- [ ] Regression tests proving authoritative diagnostics are visually distinct from local hints.
- [ ] Fake-client chained request tests for the optional chain breadcrumb display.
- [ ] Tests that assignment HUD summary groups remain stable across selection focus changes.

## Manual Validation Checklist

- [ ] Draft a path for one model and confirm the HUD shows only that model as assigned.
- [ ] Add another selected model to the same assignment group and confirm the HUD updates.
- [ ] Draft a second path for another model and confirm the HUD shows two assignment groups.
- [ ] Leave one model unassigned and confirm the HUD makes that visible.
- [ ] Mark the draft ready and confirm the HUD readiness state changes.
- [ ] Trigger an invalid fake diagnostic and confirm it appears separately from preview hints.
- [ ] Toggle compact/detailed assignment HUD settings in preferences.

## Closeout Milestone

**Milestone 11: "Assignment Review HUD"**

The UI has a reusable review surface for request-scoped selections and assignments, starting with
movement and ready to be adapted for shooting and Stratagem tools later.
