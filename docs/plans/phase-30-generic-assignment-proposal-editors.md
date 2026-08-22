# Phase 30: Generic Assignment Proposal Editors

Status: Implemented

## Purpose

Build generic assignment HUD-backed proposal editors for the current non-movement parameterized
assignment families:

- `shooting_declaration`;
- `melee_declaration`;
- `stratagem_target_binding`.

These editors should reuse the assignment workspace concept so the player can bind sources to
targets, review the current assignments, and submit one engine proposal without each mechanic
requiring a bespoke UI.

## Scope

In scope:

- common assignment workspace state for source entities, target entities, slots, counts, and
  selected assignment rows;
- family adapters for shooting declaration, melee declaration, and Stratagem target binding;
- HUD review of current assignments and submit readiness;
- visual action-summary overlays fed by assignment workspace data;
- typed invalid diagnostics and retry behavior from the engine.

Out of scope:

- attack resolution after declaration acceptance;
- finite `use_stratagem` windows, Command Re-roll opportunities, generic reaction trays, and
  adapter-captured `InterfaceIntent` materialization; those belong to Phase 32;
- local weapon, target, visibility, Precision, engagement, or Stratagem legality;
- local CP spending or effect mutation;
- non-enumerated setup flows not exposed by the engine.

## Current Core Support

The core catalog exposes:

- `submit_shooting_declaration` with proposal kind `shooting_declaration`, after the engine selects
  a shooting unit and shooting type;
- `submit_melee_declaration` with proposal kind `melee_declaration`, after fight activation and any
  fight activation ability choice;
- `submit_stratagem_target_proposal` with proposal kind `stratagem_target_binding`, for
  non-enumerable Stratagem target policies and optional decline payloads when the request marks the
  window declinable.

All three use the parameterized submission path with the fixed `submit_parameterized_payload`
option. The engine supplies target candidates, available weapons or policy context, and validates
the submitted payload.

Core revision `0531ebe` adds Phase 18B opportunity windows for finite optional actions such as
Shooting/Fight Command Re-roll. Those requests may use `decision_type: "use_stratagem"` with
`submission_family: "opportunity_window"` and nested `opportunity_submission` option payloads. That
path is distinct from parameterized `stratagem_target_binding`: Phase 30 should not try to lower
finite opportunity-window options into assignment rows. It should hand those requests to the
current-action/finite workbench and the future Phase 32 opportunity-window tray.

Reviewed against `Warhammer_40k_AI`
`f01293fb4d83249482ecee1c304e21f18e57055e` on 2026-06-16. That update changes
terrain/deployment-layout projection data, not the shooting, melee, or Stratagem assignment
proposal families. Phase 30 remains focused on parameterized assignment requests and should not
absorb the terrain-area projection work; see Phase 33 for that drift.

## UX Model

The assignment workspace is the user's staging area for "this source applies this effect to that
target." It should support:

- selecting one or more source entities from the engine-provided candidate set;
- selecting valid target entities from the engine-provided candidate set;
- creating assignment rows;
- editing counts or optional selectors when the pending request exposes them;
- reviewing the proposed assignments in the HUD;
- toggling a bright visual summary overlay to inspect source-to-target lines.

The Generic Assignment HUD should show the current proposal as a human-readable ledger:

- assignment family;
- source summary;
- target summary;
- selected weapon/effect/slot when applicable;
- count or completeness;
- invalid diagnostics and submit readiness.

## Implementation Slices

1. **Common assignment workspace**
   - Add request-keyed local workspace state for source IDs, target IDs, assignment rows, optional
     slot IDs, count fields, and selected row.
   - Keep the workspace entirely advisory until submission.
   - Reset only on request ID change, explicit clear, or accepted authoritative result.

2. **Candidate projection helpers**
   - Parse engine-provided proposal request fields into family-neutral source and target candidate
     descriptors.
   - Preserve raw payload fragments for serialization without losing unknown future fields.
   - Avoid deriving target legality from visible models or battlefield geometry.

3. **Shooting declaration editor**
   - Let the user assign source models/weapons/profiles to target candidates exposed by the request.
   - Represent split fire as multiple assignment rows.
   - Surface duplicate weapon ability selections when the request exposes them.
   - Generate `shooting_declaration` payloads from workspace rows.

4. **Melee declaration editor**
   - Let the user assign fighting models and melee weapons to engaged target units or models exposed
     by the request.
   - Support split attack counts when a model's weapon targets more than one enemy unit.
   - Generate `melee_declaration` payloads from workspace rows.

5. **Stratagem target-binding editor**
   - Render target binding slots from the pending Stratagem proposal request.
   - Support affected unit/card/target IDs and handler-owned `effect_selection` where exposed.
   - Show and submit the decline payload only when the engine marks the request declinable.
   - Treat finite `use_stratagem` opportunity-window requests as out of scope for this editor; do
     not infer target-binding rows from `opportunity_submission` payloads.

6. **HUD and visual summary**
   - Bind assignment workspace rows into the existing Assignments HUD area.
   - Render source-to-target overlays for active review.
   - Keep dimmed always-on summaries optional and preference-controlled.

7. **Submission and diagnostics**
   - Submit through parameterized decision requests with the current request ID.
   - Display stale/malformed/rule-invalid diagnostics from the engine.
   - Preserve draft context across retry requests when doing so does not hide the new request ID.

## Acceptance Criteria

- The assignment HUD can display source, target, family, and completeness for all three families.
- Shooting declaration, melee declaration, and Stratagem target-binding fixtures can produce
  JSON-safe proposal payloads using the current request ID.
- Stratagem decline is available only when the request explicitly exposes an optional decline.
- Finite `use_stratagem` opportunity-window requests remain finite choices and are not accidentally
  parsed as parameterized target-binding requests.
- The UI does not compute weapon legality, target legality, CP spending, attack pools, or source
  effects locally.
- Assignment visual summaries are driven by workspace data and can be toggled.

## Automated Verification

Add or update tests for:

- common assignment workspace lifecycle;
- source/target candidate parsing for shooting, melee, and Stratagem requests;
- payload generation for representative declaration/binding fixtures;
- declinable and non-declinable Stratagem target windows;
- guard tests that `submission_family: "opportunity_window"` finite requests are routed away from
  assignment editors;
- HUD runtime data and overlay primitive generation from assignment rows;
- invalid diagnostics and retry behavior.

Run the normal gates:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pyright
uv run pytest tests/
uv run pre-commit run --all-files
```

## Manual Validation Checklist

- In Shooting phase, select a shooting unit and shooting type, then assign source models/weapons to
  targets and submit the declaration.
- Split fire across at least two target units when the core request exposes those targets.
- In Fight phase, select a fight activation and create melee target assignments.
- Trigger a parameterized Stratagem target window and bind the requested target slots.
- Toggle assignment visual summaries and confirm lines/icons match the assignment ledger.
- Submit an intentionally invalid binding and confirm the engine diagnostic appears in the HUD.

## Reviewer Notes

Review should focus on whether assignment editing is data-driven from the pending request. The UI
can make assignment entry ergonomic, but it must not become a shooting, melee, or Stratagem rule
engine.

## Implementation Notes

Implemented in the Phase 30 PR.

- Added `AssignmentWorkspace` state for request-keyed generic assignment payload previews.
- Added assignment adapters for `shooting_declaration`, `melee_declaration`, and
  `stratagem_target_binding`.
- Added `submit_assignment_workspace(...)` so generic assignment proposals use the same
  parameterized submission lifecycle as movement and placement.
- Wired `ArcadeWarhammerWindow` to start and clear assignment workspaces on pending-request changes.
- Added Current Action panel buttons for assignment `Submit`, optional `Decline`, and `Clear`.
- Bound assignment rows into the existing Assignments HUD area and action visual summaries.
- Rendered source-to-target assignment summary lines when referenced units/models are visible.
- Preserved finite `use_stratagem` opportunity-window handling as finite Current Action choices
  rather than assignment workspaces.
- Converted malformed or incomplete assignment request data into assignment diagnostics where the
  request can be reviewed but not safely submitted.

Reviewer-visible HUD element:

- The assignment UX is visible in the `Current Action` HUD panel and the `Current Assignment`
  panel. `Current Action` exposes assignment submit/decline/clear buttons; `Current Assignment`
  shows the assignment ledger, readiness, advisory lines, and diagnostics.

Additional smoke-test note:

- The live-core smoke Monster movement nudge was moved deeper into the current core movement bridge
  area so the existing Monster advance smoke test remains valid while the core movement resolver
  still applies its bridge edge assumptions.

Automated verification completed locally:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pyright
uv run pytest tests/
```

Manual validation checklist for this phase:

- Trigger a shooting declaration request and confirm `Current Action` shows assignment Submit/Clear.
- Trigger a melee declaration request and confirm the Assignments panel shows model-to-target rows.
- Trigger a parameterized Stratagem target-binding request and confirm optional Decline appears only
  when the engine marks the request declinable.
- Toggle action summary review and confirm source-to-target lines appear for visible refs.
- Trigger a finite `use_stratagem` opportunity window and confirm it remains a finite option list,
  not an assignment workspace.
