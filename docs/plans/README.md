# Current Phase Plan Index

This folder contains the active forward-looking implementation plans. Historical plans live under
`docs/legacy/plans/`.

## Immediate Thin-Skeleton Sequence

The next implementation sequence is aimed at getting a complete but thin gameplay skeleton through
the current core engine decision lifecycle as quickly as possible. Each phase must preserve the UI
boundary: the engine owns legality, mutation, events, and replay; the UI renders viewer-scoped
projection data, collects intent, submits engine requests, and displays diagnostics.

1. [Phase 25: Legacy UI Cleanup](phase-25-legacy-ui-cleanup.md)
2. [Phase 26: Generic Finite Decision Workbench Polish](phase-26-generic-finite-decision-workbench.md)
3. [Phase 27: Generic Placement Proposal Editor](phase-27-generic-placement-proposal-editor.md)
4. [Phase 28: Movement Proposal Family Generalization](phase-28-movement-proposal-family-generalization.md)
5. [Phase 29: Generic Assignment Proposal Editors](phase-29-generic-assignment-proposal-editors.md)

## Preliminary Setup-Flow Plans

These plans intentionally have no phase number yet. They should be concretized only if the core
engine owner decides to expose the corresponding setup concepts as `DecisionRequest` surfaces.

- [Preliminary: Army Mustering Decision Flow](preliminary-army-mustering-decision-flow.md)
- [Preliminary: Mission And Layout Selection Flow](preliminary-mission-layout-selection-flow.md)
- [Preliminary: Attacker And Defender Decision Flow](preliminary-attacker-defender-decision-flow.md)
- [Preliminary: First Turn Decision Flow](preliminary-first-turn-decision-flow.md)

