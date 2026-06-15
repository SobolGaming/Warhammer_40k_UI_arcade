# Preliminary: Army Mustering Decision Flow

Status: Preliminary - waiting on core DecisionRequest support

## Desired Outcome

If the core engine owner decides that army mustering should become a user-facing decision flow, the
UI should provide a thin skeleton that lets players choose or confirm rosters through engine-emitted
requests instead of editing configuration files by hand.

The end state is a UI flow where the engine asks for mustering choices, the player answers with one
engine-provided option or proposal, and the engine records the authoritative result.

## Current State

Army setup is currently treated as configuration/input data outside the UI decision lifecycle. The UI
should not invent mustering decisions or mutate core army state locally.

## Core Dependency

Concretize this plan only after the core exposes mustering as one or more `DecisionRequest`
surfaces with:

- actor/player identity;
- legal roster or detachment options;
- any required validation context;
- a JSON-safe result shape;
- viewer-scoped visibility rules for private list data if needed.

## Future UI Slices

1. Read and display the mustering request.
2. Show legal roster/detachment options from engine data.
3. Provide import/selection affordances for player-owned roster files only when the core supports
   that submission shape.
4. Submit selected engine option/proposal through the standard lifecycle.
5. Display typed diagnostics and retry requests.

## Non-Goals

- No local points validation.
- No local detachment legality engine.
- No hidden roster leak across viewers.
- No authoritative army mutation outside core requests.

