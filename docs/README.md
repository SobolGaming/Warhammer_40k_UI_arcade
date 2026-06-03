# Documentation

This folder mirrors the core repository's documentation-first workflow while keeping the Arcade UI
plans separate from engine/core documentation.

## Structure

- `plans/` — phase-by-phase implementation plans split from `OverallPlan.md`.
- `adr/` — future architecture decision records once implementation decisions need durable history.
- `protocol-notes.md` — future UI-facing notes about the engine adapter/session protocol.
- `movement-ui-flow.md` — future detailed movement interaction flow.
- `ui-configuration.md` — future detailed notes for shareable UI preferences, overlays, and
  hotkeys.

The active documentation foundation is `plans/`, `README.md`, and `architecture.md`. Add detailed
protocol notes, movement flow notes, UI configuration notes, and ADRs as the later phases introduce
those implementation decisions.
