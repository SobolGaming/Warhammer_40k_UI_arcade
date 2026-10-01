# Current Phase Plan Index

This folder contains the active forward-looking implementation plans. Finished implementation plans
live under `docs/plans/finished/`; older superseded planning notes live under `docs/legacy/plans/`.

## Immediate Thin-Skeleton Sequence

The next implementation sequence is aimed at getting a complete but thin gameplay skeleton through
the current core engine decision lifecycle as quickly as possible. Each phase must preserve the UI
boundary: the engine owns legality, mutation, events, and replay; the UI renders viewer-scoped
projection data, collects intent, submits engine requests, and displays diagnostics.

1. [Phase 25: Legacy UI Cleanup](finished/phase-25-legacy-ui-cleanup.md)
2. [Phase 26: Generic Finite Decision Workbench Polish](finished/phase-26-generic-finite-decision-workbench.md)
3. [Phase 27: Current Action View And Clickable HUD Buttons](finished/phase-27-current-action-view-and-clickable-hud-buttons.md)
4. [Phase 28: Generic Placement Proposal Editor](finished/phase-28-generic-placement-proposal-editor.md)
5. [Phase 29: Movement Proposal Family Generalization](finished/phase-29-movement-proposal-family-generalization.md)
6. [Phase 30: Generic Assignment Proposal Editors](phase-30-generic-assignment-proposal-editors.md)
7. [Phase 31: Scrollable Player Units Roster](finished/phase-31-scrollable-player-units-roster.md)
8. [Phase 32: Opportunity Window And Interface Intent Tray](phase-32-opportunity-window-and-interface-intent-tray.md)
9. [Phase 33: Typed Terrain Area Projection Adaptation](finished/phase-33-typed-terrain-area-projection-adaptation.md)
10. [Phase 34: Core Contract 10.2 Adapter And Projection Adaptation](finished/phase-34-core-contract-10-adaptation.md)
11. [Phase 35: Core Contract 42 Adaptation And Live Smoke Simplification](phase-35-core-contract-42-adaptation.md)

Phase 34 completed the compatibility gate for the pinned core Contract 10.2. Phase 35 plans the
next pin update to Contract 42.0.0. Further Phase 32 work should use Phase 35's version-matched
projection and decision path rather than build against the older payload assumptions.

## Core Drift Adaptation

Phase 33 was a projection-drift adaptation introduced after reviewing `Warhammer_40k_AI`
`f01293fb4d83249482ecee1c304e21f18e57055e`. It restored visual terrain parity for live core
layouts that expose typed `terrain_areas` instead of feature-level `terrain_features`.

Phase 34 tracks the larger migration from that baseline to `Warhammer_40k_AI`
`dbfcc3a99e9d560d1354506352a09d48ca555a94` and external contract `10.2.0`. It covers the shared
adapter facade, strict interaction descriptors, canonical battlefield projection, spatial-context
hashes, capability/mission projection, and removal of authoritative live-smoke mutations.

Phase 35 reviews `Warhammer_40k_AI` `6e86f44b87c4559a9297596d5d18dc4247b8cbc3` and external
contract `42.0.0`. It covers the next compatibility update, changed shooting and placement
payloads, contract-matched fixtures, and measured live-smoke simplification.

## Preliminary Setup-Flow Plans

These plans intentionally have no phase number yet. They should be concretized only if the core
engine owner decides to expose the corresponding setup concepts as `DecisionRequest` surfaces.

- [Preliminary: Army Mustering Decision Flow](preliminary-army-mustering-decision-flow.md)
- [Preliminary: Mission And Layout Selection Flow](preliminary-mission-layout-selection-flow.md)
- [Preliminary: Attacker And Defender Decision Flow](preliminary-attacker-defender-decision-flow.md)
- [Preliminary: First Turn Decision Flow](preliminary-first-turn-decision-flow.md)
