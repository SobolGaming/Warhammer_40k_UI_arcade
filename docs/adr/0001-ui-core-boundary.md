# ADR 0001 - UI/Core Boundary

## Status

Accepted.

## Context

The Arcade UI is a companion client for `Warhammer_40k_AI`, not a rules engine. The UI must render
viewer-scoped projections, collect user intent, and submit decisions without mutating authoritative
game state or inventing legal choices.

## Decision

Only `warhammer40k_arcade_ui.core_client` may import approved core adapter/session APIs directly.
Render, HUD, input, preference, diagnostics, and local state modules consume UI-facing dataclasses
and protocols instead of mutable engine internals.

The UI may keep local advisory state for selection, drafting, previews, diagnostics, and event
traces. That state is not authoritative. All game-effecting choices still flow through the current
engine `DecisionRequest` and engine validation.

## Consequences

- Future network, replay, and local-session clients can share the same UI-facing facade.
- The UI can add rich interaction workflows without becoming a private rule implementation.
- Import-boundary checks are part of CI and pre-commit so direct core imports outside
  `core_client` fail review.
- New adapter-visible decision/proposal shapes must be handled by the facade or planned with an
  explicit core contract review.
