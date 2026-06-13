# Documentation

This folder mirrors the core repository's documentation-first workflow while keeping the Arcade UI
plans separate from engine/core documentation.

## Structure

- `plans/` — phase-by-phase implementation plans split from `OverallPlan.md`.
- `adr/` — architecture decision records for durable UI/core-boundary and quality-gate decisions.
- `protocol-notes.md` — future UI-facing notes about the engine adapter/session protocol.
- `movement-ui-flow.md` — future detailed movement interaction flow.
- `ui-configuration.md` — Phase 4 notes for the shareable UI preferences framework.
- `hud-customization.md` — user-level guide for HUD zones, composition files, widgets, bindings,
  sizing, overflow, and shape customization.
- `preferences/` — documented portable example profiles for the default, dense-debug,
  keyboard-heavy, and command-bench configurations.
- `hud/` — Phase 19 HUD composition YAML profiles and preview-only examples for widget review.
- Crash diagnostic bundle usage is documented in the root `README.md` under
  "Crash diagnostic bundles".

The active documentation foundation is `plans/`, `adr/`, `README.md`, `architecture.md`,
`ui-configuration.md`, and `preferences/`. Add detailed protocol notes and movement flow notes as
later phases introduce those implementation decisions.
