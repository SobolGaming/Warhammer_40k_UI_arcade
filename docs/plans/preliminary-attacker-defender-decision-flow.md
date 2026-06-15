# Preliminary: Attacker And Defender Decision Flow

Status: Preliminary - waiting on core DecisionRequest support

## Desired Outcome

If attacker/defender choice becomes a user-facing core decision, the UI should present the deciding
player, available choices, roll-off context if any, and selected result through the generic finite
decision workbench.

## Current State

Attacker/defender assignment may be derived from setup configuration or engine internal flow. The UI
should display the authoritative assignment once projected, but should not create a private selection
path.

## Core Dependency

Concretize this plan only after the core exposes attacker/defender assignment as a
`DecisionRequest` with:

- the deciding actor;
- legal option IDs;
- any dice/roll-off result or priority context;
- authoritative result events and viewer-scoped projection fields.

## Future UI Slices

1. Show attacker/defender request in the finite decision workbench.
2. Display deciding player and roll-off/source context.
3. Submit the selected engine option.
4. Render the resulting attacker/defender assignment in setup status HUD.
5. Include event trace and crash-bundle evidence for the selected setup path.

## Non-Goals

- No local roll-off.
- No local option synthesis.
- No hidden setup data leak.

