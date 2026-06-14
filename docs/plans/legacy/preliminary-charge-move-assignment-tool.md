# Preliminary - Charge move assignment tool

## Status

Preliminary plan. Do not treat this as a numbered implementation phase until the current
`Warhammer_40k_AI` charge proposal request shape is reviewed again immediately before work starts.

## Goal

Use the entity selection and assignment workspace to build Charge Move proposals after the engine
has selected a charging unit, rolled charge distance, and emitted a reachable charge movement
request.

In plain language: this is the future tool for saying "these models charge these target units along
these paths" or "the unit chooses not to move" before submitting the charge movement answer to the
engine.

## Current Contract Assumptions

Based on the local core checkout reviewed on 2026-06-05:

- Charging unit selection is finite: `select_charging_unit`.
- Selecting a charging unit records the finite choice and resolves the charge roll in the core.
- If targets are reachable, the engine emits `submit_movement_proposal` with proposal kind
  `charge_move`.
- The submitted payload must preserve `proposal_request_id`, `proposal_kind: "charge_move"`,
  `unit_instance_id`, `movement_phase_action: "charge_move"`, `movement_mode: "charge"`,
  `charge_target_unit_instance_ids`, and the engine request context.
- Empty target IDs with no witness records the no-move choice.
- Rule-invalid but well-formed charge moves can record a rejected attempt and emit a fresh retry
  request.
- The UI must not infer charge eligibility, target reachability, charge distance, Fights First
  effects, or engagement rules.

## Proposed User Flow

1. The engine emits a `charge_move` proposal request.
2. The UI opens a charge assignment workspace rather than the normal movement workspace.
3. The HUD shows the charging unit, charge distance/context when provided, reachable target units,
   and the no-move option.
4. The player selects one or more engine-provided charge target units.
5. The player drafts per-model charge paths using the same model assignment foundation, but through
   a charge-specific payload adapter.
6. The action visual summary shows charge paths and target highlights.
7. The UI builds a `charge_move` payload preview.
8. The player submits through the explicit parameterized request ID.
9. Accepted results refresh projection; invalid results retain retry context only when the engine
   emits a compatible fresh request.

## Preliminary Tasks

- [ ] Refresh the core charge declaration and Charge Move proposal contract before implementation.
- [ ] Build an `EntitySelectionProfile` for `charge_move`.
- [ ] Convert engine-provided reachable target context into target-unit refs.
- [ ] Add explicit no-move selection and HUD presentation.
- [ ] Add charge-specific assignment state:
  - selected target unit refs;
  - per-model charge path drafts;
  - no-move state;
  - retry compatibility context.
- [ ] Add payload preview generation for `charge_move`.
- [ ] Add action visual summary adapter for charge target links and charge paths.
- [ ] Add authoritative invalid diagnostic display using movement proposal diagnostics.
- [ ] Keep unsupported diagnostics visible until the charge-specific adapter is complete.

## Preliminary Acceptance Criteria

- [ ] The UI does not route `charge_move` through Normal Move/Fall Back submission logic.
- [ ] The player can see and select only engine-provided charge targets.
- [ ] The player can choose the engine-supported no-move answer.
- [ ] The UI preserves charge proposal request IDs and charge-specific context.
- [ ] The UI builds JSON-safe charge payload previews without applying charge effects locally.
- [ ] Accepted and invalid charge responses use the same authoritative projection/diagnostic
  boundary as movement.

## Contract Questions To Revisit

- Which request fields expose charge distance, reachable target diagnostics, and target display
  labels?
- Are target selections always unit-level, or can future charge requests require model-level target
  detail?
- Should target selection be required before path drafting, or can the path draft imply targets
  only after explicit user confirmation?
- Does the retry request preserve enough context for the UI to safely retain paths and target
  selections after a rule-invalid charge move?
