# Preliminary: First Turn Decision Flow

Status: Preliminary - waiting on core DecisionRequest support

## Desired Outcome

If first-turn selection or confirmation becomes a user-facing core decision, the UI should make that
setup step visible and answer it through the standard engine lifecycle.

## Current State

The UI should display the active player and current phase once the engine projects them. It should
not decide first turn locally or bypass the core lifecycle.

## Core Dependency

Concretize this plan only after the core exposes first-turn selection as one or more
`DecisionRequest` surfaces with:

- deciding player or automated roll context;
- legal option IDs;
- any attacker/defender dependency;
- replay-safe result events;
- viewer-scoped visibility policy.

## Future UI Slices

1. Display first-turn request in the finite decision workbench.
2. Show roll or priority context from the engine.
3. Submit selected engine option or acknowledge an engine-forced result.
4. Render the chosen first player in the status HUD.
5. Verify event trace and crash bundles include the setup decision path.

## Non-Goals

- No local initiative roll.
- No local deployment/mission dependency logic.
- No authoritative phase advancement outside the engine.
