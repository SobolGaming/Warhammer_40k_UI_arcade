# Phase 16 - Generic assignment HUD

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
view of the workspace; Phase 17 adds the battlefield picture view of the same workspace.

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

## Core Update Impact Notes

Reviewed `Warhammer_40k_AI` `main` at `2d4d730` on 2026-06-05.

- `GameViewPayload.pending_proposal` now projects normalized request metadata for parameterized
  requests: `request_id`, `decision_type`, `actor_id`, and proposal-family fields. The assignment
  HUD should treat `pending_proposal` as the primary source for request identity and should only use
  nested request payload details for operation-specific content.
- Charge movement is now a first-class `submit_movement_proposal` family with proposal kind
  `charge_move`. It is not a normal Move Units proposal: the request carries charge target context,
  `movement_mode: "charge"`, and a no-move path where empty targets/no witness can be a deliberate
  answer. Phase 16 should show unsupported `charge_move` workspaces clearly until a charge-specific
  adapter exists.
- Fight order now exposes finite decisions for `select_fight_activation` and
  `resolve_fight_interrupt`. These are not assignment workspaces yet, but the generic request header
  and finite review surfaces should preserve the engine payload so later HUD work can display
  ordering band, fight type, pass/decline choices, and interrupt context without inferring
  eligibility.

## Tasks

- [x] Add generic assignment HUD view models:
  - request ID;
  - decision type;
  - actor ID;
  - operation kind;
  - proposal kind, when present;
  - active layer;
  - active selection refs;
  - assignment groups;
  - assigned refs;
  - unassigned refs;
  - readiness state;
  - advisory hints;
  - authoritative diagnostics, when present;
  - summary group IDs and refs for later visual summary overlays.
- [x] Add movement-specific adapters into the generic HUD:
  - movement action;
  - proposal kind;
  - movement mode;
  - Fall Back mode;
  - model path assignment groups;
  - per-group path length summaries;
  - unassigned/unchanged model hints.
- [x] Add finite-decision request summaries for assignment-adjacent decisions that do not yet have
  a full workspace:
  - fight activation options;
  - fight interrupt decline/activation options;
  - ordering band or reaction context when the engine exposes it;
  - selected finite option context without local eligibility inference.
- [x] Add render primitives for multi-selection and assignment states:
  - ordinary inspect selection;
  - request-selected entities;
  - active assignment group;
  - assigned but inactive entities;
  - unassigned candidate entities;
  - invalid or warning-highlighted preview entities.
- [x] Add visual-summary pre-plumbing:
  - expose assignment groups in a stable order;
  - expose safe source and target refs;
  - expose advisory/diagnostic severity;
  - expose readiness state;
  - do not draw the full action summary yet.
- [x] Add compact HUD layout:
  - current request header;
  - assignment list;
  - active selection summary;
  - completeness/readiness line;
  - diagnostic/warning lines;
  - preference source and debug fields when the debug inspector is visible.
- [x] Add preference-backed display settings:
  - show/hide assignment HUD;
  - compact/detailed assignment rows;
  - color-independent warning markers;
  - optional auto-follow chain display.
- [x] Add keyboard/mouse affordance labels only where they are normal control labels, not tutorial
  prose.
- [x] Keep all warnings marked as preview/advisory unless they are engine-returned diagnostics.
- [x] Ensure the HUD can represent unsupported workspaces without failing:
  - unsupported proposal tool;
  - unsupported `charge_move` proposal until a charge-specific assignment adapter is added;
  - missing candidate metadata;
  - request changed while local assignments existed.

## Acceptance Criteria

- [x] Movement assignment state is visible in the generic HUD.
- [x] The player can distinguish active selection, assigned models, and unassigned models.
- [x] The HUD clearly distinguishes local preview hints from authoritative engine diagnostics.
- [x] The HUD can show an incomplete assignment and a ready assignment.
- [x] The HUD can show request-scoped state without clearing ordinary inspect selection.
- [x] Preference settings can hide or compact the HUD without changing behavior or legality.
- [x] Unsupported workspaces produce visible diagnostics rather than blank panels.
- [x] The HUD view model contains enough stable group/ref data for Phase 17 to build visual summary
  overlays from the same workspace state.
- [x] Normalized `pending_proposal` metadata is displayed and preserved for supported and
  unsupported parameterized request families.
- [x] Fight activation and fight interrupt finite requests remain selectable through the finite
  decision path while exposing enough request context for richer future HUD summaries.

## Tests

- [x] HUD view-model tests for empty, incomplete, ready, and invalid movement workspaces.
- [x] HUD view-model tests for active/assigned/unassigned entity refs.
- [x] Render primitive tests for assignment highlights.
- [x] Preference tests for assignment HUD settings.
- [x] Regression tests proving authoritative diagnostics are visually distinct from local hints.
- [x] Fake-client chained request tests for the optional chain breadcrumb display.
- [x] Tests that assignment HUD summary groups remain stable across selection focus changes.
- [x] Protocol/HUD tests using normalized `pending_proposal` metadata from the core projection.
- [x] Unsupported-workspace tests for `charge_move` proving the HUD displays the request instead of
  routing it through the normal movement adapter.
- [x] Finite request summary tests for `select_fight_activation` and `resolve_fight_interrupt`.

## Manual Validation Checklist

- [ ] Draft a path for one model and confirm the HUD shows only that model as assigned.
- [ ] Add another selected model to the same assignment group and confirm the HUD updates.
- [ ] Draft a second path for another model and confirm the HUD shows two assignment groups.
- [ ] Leave one model unassigned and confirm the HUD makes that visible.
- [ ] Mark the draft ready and confirm the HUD readiness state changes.
- [ ] Trigger an invalid fake diagnostic and confirm it appears separately from preview hints.
- [ ] Toggle compact/detailed assignment HUD settings in preferences.

## Closeout Milestone

**Milestone 12: "Assignment Review HUD"**

The UI has a reusable review surface for request-scoped selections and assignments, starting with
movement and ready to be adapted for shooting and Stratagem tools later.

## Implementation Closeout

Implemented on 2026-06-05.

- Added `AssignmentHudPanelView` and `AssignmentHudGroupView` in `hud.view_models` as a reusable
  request-scoped checklist model. The view model carries request ID, decision type, actor ID,
  operation kind, proposal kind, active layer, selected/assigned/unassigned refs, readiness state,
  advisory hints, authoritative diagnostics, stable group IDs, and source/target refs for Phase 17
  visual summary overlays.
- Added a movement assignment HUD adapter using the existing Phase 9 `MovementDraft` assignment
  rows. The HUD shows active movement selection, moved assignment groups, unassigned/no-op models,
  readiness state, local preview hints, authoritative invalid diagnostics, and optional chain
  breadcrumb lines from existing event-log state.
- Added finite request summaries for `select_fight_activation` and `resolve_fight_interrupt`.
  These remain finite decisions; the HUD highlights engine-issued fight/pass/decline options but
  does not infer fight eligibility, pass distance, or interrupt availability.
- Added a compact screen-space Assignment Review panel in render primitives. The panel supports
  compact/detailed rows, color-independent warning markers, debug-only preferences source display,
  and chain breadcrumb display from existing event lines.
- Added preference schema fields:
  - `hud.show_assignment_hud`
  - `hud.assignment_hud_mode`
  - `hud.show_assignment_warning_markers`
  - `hud.show_chain_breadcrumbs`
- Updated built-in and documented YAML profiles with the new HUD settings.
- Tightened movement draft activation so `charge_move` is not routed through Normal Move/Advance/
  Fall Back drafting. Charge Move now shows as an unsupported proposal tool until the preliminary
  charge move assignment plan is implemented.

## Automated Verification

Focused checks during implementation:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest \
  tests/test_hud_selection.py \
  tests/test_render_primitives.py \
  tests/test_preferences.py
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check \
  src/warhammer40k_arcade_ui/hud/view_models.py \
  src/warhammer40k_arcade_ui/render/primitives.py \
  src/warhammer40k_arcade_ui/preferences/schema.py \
  tests/test_hud_selection.py \
  tests/test_render_primitives.py \
  tests/test_preferences.py
UV_CACHE_DIR=/tmp/uv-cache uv run mypy src tests
```

Full PR gates run before PR:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .
UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check .
UV_CACHE_DIR=/tmp/uv-cache uv run pyright
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/
PRE_COMMIT_HOME=/tmp/pre-commit-cache UV_CACHE_DIR=/tmp/uv-cache uv run pre-commit run --all-files
```

## Manual Validation Checklist

- [ ] Launch `uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/default.yaml`.
- [ ] Select a unit, open its action menu, choose Normal Move, and confirm the Assignment Review
  panel appears under the movement draft panel.
- [ ] Draft a path for one model and confirm the panel shows one active assignment group and the
  remaining models as unassigned.
- [ ] Shift-select another model and draft a shared waypoint; confirm the active assignment group
  lists multiple models.
- [ ] Mark the draft ready with Enter and confirm the panel shows `Ready: ready` and unchanged
  models as no-op ready.
- [ ] Trigger an invalid movement diagnostic and confirm `Invalid:` lines appear separately from
  `Hint:` lines.
- [ ] Edit a preference profile to set `hud.assignment_hud_mode: detailed` and relaunch; confirm
  assignment source refs and group summaries are visible.
- [ ] Edit a preference profile to set `hud.show_assignment_hud: false` and relaunch; confirm the
  Assignment Review panel is hidden while movement behavior remains unchanged.
- [ ] In a future live-core Charge Move request, confirm the HUD says `Unsupported proposal tool:
  charge_move` rather than opening a normal movement draft.
