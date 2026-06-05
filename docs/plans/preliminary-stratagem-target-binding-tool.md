# Preliminary - Stratagem target-binding assignment tool

## Status

Preliminary plan. Do not treat this as a numbered implementation phase until the core
Stratagem target-binding contract exposes stable target role and candidate metadata.

## Goal

Use the entity selection and assignment workspace for Stratagems that require one or more targets
that cannot be safely represented as fully enumerated finite options.

In plain language: this is the future tool for filling target slots such as "choose two friendly
units and one enemy unit" or "choose an eligible objective and a unit" when the engine asks for a
parameterized Stratagem target proposal.

## Current Contract Assumptions

Based on the local core checkout reviewed on 2026-06-04:

- Fully bound `use_stratagem` finite options should remain finite options. The UI should display
  and submit the engine option; it should not decompose the target binding into editable local
  selections.
- Parameterized target binding uses `submit_stratagem_target_proposal` with proposal kind
  `stratagem_target_binding`.
- Some Stratagem proposals may not yet expose enough structured role/candidate metadata for a rich
  GUI tool.
- The UI must not infer target legality, target counts, CP spend, affected-unit IDs, or restriction
  policy locally.

## Target Schema Need

A concrete implementation likely needs a request-visible target schema, for example:

```text
target_slots:
  - slot_id
    label
    entity_kinds
    min_count
    max_count
    candidates
    additive_allowed
    required
```

This schema should come from the core adapter contract, not from UI preference files or local
hard-coded Stratagem names.

## Proposed User Flow

1. The engine emits `submit_stratagem_target_proposal`.
2. The UI checks whether the request exposes a supported target schema.
3. If not, the UI shows an unsupported target-binding tool state.
4. If supported, the UI opens a Stratagem assignment workspace.
5. The player selects entities for the active target slot.
6. The player switches slots and repeats until required slots are complete.
7. The assignment HUD shows each slot, selected entities, missing required selections, and preview
   hints.
8. The action visual summary can show a Stratagem marker/icon and lines to selected target
   entities.
9. The UI builds the exact target-binding payload shape required by the request.

## Preliminary Tasks

- [ ] Refresh the core Stratagem target-binding contract before implementation.
- [ ] Identify or propose a standard target-slot schema in the core adapter contract.
- [ ] Build an `EntitySelectionProfile` from target slots and candidates.
- [ ] Support slot-specific additive/subtractive selection.
- [ ] Support target aliases only when the slot permits them:
  - model click to owning unit;
  - objective marker click to objective ID;
  - card click to card ID.
- [ ] Add target-slot assignment HUD rows.
- [ ] Add action visual summary adapter:
  - Stratagem marker/icon;
  - lines to selected target entities;
  - distinct friendly/enemy/objective/card slot treatments;
  - dim and review modes.
- [ ] Add incomplete/unsupported diagnostics.
- [ ] Build target-binding payload previews without spending CP or applying effects.

## Preliminary Acceptance Criteria

- [ ] Fully bound finite Stratagem options remain finite and are not locally decomposed.
- [ ] Parameterized Stratagem target requests without metadata are visibly unsupported.
- [ ] Supported target-slot requests can be filled with additive/subtractive selection.
- [ ] Target slot cardinality is displayed as a local completeness hint.
- [ ] The UI preserves all engine-issued context and submits no invented target IDs.
- [ ] Supported target-slot assignments can produce a visual summary from the same workspace data.

## Contract Questions To Revisit

- Should target-slot metadata be standardized across all parameterized target proposals, not only
  Stratagems?
- How should attached-unit canonicalization be displayed without letting the UI enforce the rule?
- Should affected-unit IDs be supplied by the engine after validation or previewed from target
  schema metadata?
- How should optional decline for parameterized Stratagem windows appear in the assignment HUD?
- Do hidden or secret Stratagem target policies require redacted candidate counts?
