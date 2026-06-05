# Preliminary - Shooting declaration assignment tool

## Status

Preliminary plan. Do not treat this as a numbered implementation phase until the current
`Warhammer_40k_AI` shooting proposal request shape is reviewed again immediately before work starts.

## Goal

Use the entity selection and assignment workspace to build shooting declarations where different
models or weapons in the same friendly unit can be assigned to different enemy target units.

In plain language: this is the future tool for saying "these models fire here, those models fire
there" before submitting one shooting declaration to the engine.

## Current Contract Assumptions

Based on the local core checkout reviewed on 2026-06-04:

- Shooting declaration uses `submit_shooting_declaration` with proposal kind
  `shooting_declaration`.
- The request payload includes `available_weapons` with model, wargear, profile, and optional
  Firing Deck source identity.
- The request payload includes `target_candidates` with engine-provided target legality,
  visibility/range evidence, allowed shooting types, and targeting rule IDs.
- The submitted payload must preserve engine-issued request IDs, unit IDs, shooting type tokens,
  visibility cache keys, weapon IDs, profile IDs, and target IDs.
- The UI must not invent targets, visibility evidence, shooting types, or weapon/profile IDs.

## Proposed User Flow

1. The engine emits `submit_shooting_declaration`.
2. The UI opens a shooting assignment workspace.
3. The player selects attacker models or weapon rows from `available_weapons`.
4. The player clicks an enemy model or unit; the workspace aliases that click to a target unit only
   if the current target candidate set allows that target unit.
5. The selected attacker models/weapons are assigned to that target.
6. The player repeats until the declaration is complete.
7. The assignment HUD shows assigned and unassigned weapons/models.
8. The UI builds a `ShootingDeclarationProposal` preview.
9. A later concrete phase submits through the parameterized path.

## Preliminary Tasks

- [ ] Refresh the core shooting declaration contract before implementation.
- [ ] Build an `EntitySelectionProfile` for `submit_shooting_declaration`.
- [ ] Convert `available_weapons` into selectable attacker model/weapon refs.
- [ ] Convert `target_candidates` into target-unit refs and diagnostics.
- [ ] Add shooting assignment groups:
  - attacker model ID;
  - wargear ID;
  - weapon profile ID;
  - target unit ID;
  - shooting type;
  - optional Firing Deck source unit/model IDs.
- [ ] Add target assignment interactions using the generic selection workspace.
- [ ] Add payload preview generation for `ShootingDeclarationProposal`.
- [ ] Add unsupported diagnostics if the request payload lacks required candidate metadata.
- [ ] Add assignment HUD rows for attacker model/weapon to target-unit bindings.

## Preliminary Acceptance Criteria

- [ ] UI can assign different model/weapon subsets to different target units.
- [ ] UI preserves all engine-issued IDs and evidence.
- [ ] UI refuses to assign a target not present in the request candidate set.
- [ ] UI distinguishes unassigned weapons/models from assigned ones.
- [ ] UI can build a JSON-safe shooting declaration preview.
- [ ] UI does not submit or mutate authoritative shooting state until the concrete submission phase.

## Contract Questions To Revisit

- Does the request expose enough information to group duplicate weapons ergonomically without losing
  weapon/profile identity?
- Should the UI assign by model first, weapon row first, or both depending on preference?
- Are target candidates always unit-level, or will future requests expose model-level target roles?
- How should optional Hazardous or one-shot obligations appear in the assignment HUD?
- Does out-of-phase shooting such as Fire Overwatch require additional chain context display?
