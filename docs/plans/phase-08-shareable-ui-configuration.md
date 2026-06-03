# Phase 8 — Shareable UI configuration and bindings

## Goal

Add a hand-editable, shareable UI preferences layer for presentation, overlays, HUD defaults, and
input bindings without creating a second rules path.

User configuration is allowed to control how the UI presents known information and maps local input
to known UI commands. It must not create legal actions, finite option IDs, proposal kinds, rule
validation, hidden-information visibility, or authoritative state changes.

## Tasks

- [ ] Add a `preferences` or `settings` module with versioned typed schemas:
  - `UiPreferences`
  - `OverlayPreferences`
  - `HotkeyBinding`
  - `SelectionBehaviorPreferences`
  - `HudPreferences`
- [ ] Support loading preferences from:
  - an explicit config path, planned for a future CLI flag;
  - a platform default path via `platformdirs`;
  - built-in defaults when no user file exists.
- [ ] Support hand-editable JSON and YAML files:
  - keep generated examples portable and free of machine-specific absolute paths;
  - add a YAML parser dependency only when this phase is implemented;
  - include `schema_version` in every persisted profile.
- [ ] Define a stable UI command registry for local-only commands:
  - toggle known overlay for selected model or unit;
  - show selected model details;
  - show selected unit details;
  - open selected-unit action menu;
  - start or stop measure mode;
  - confirm, cancel, and cycle local UI selections.
- [ ] Define a stable overlay registry for known advisory overlays:
  - movement budget;
  - movement path draft;
  - objective/control context, once present in projections;
  - engagement range, coherency, line-of-sight, and cover overlays as later phases expose data.
- [ ] Add selection-triggered overlay preferences:
  - overlays enabled when a model is selected with the default mouse button;
  - overlays enabled when a unit is selected;
  - overlays enabled while a movement draft is active.
- [ ] Add configurable hotkeys:
  - toggle individual overlays for the currently selected model or unit;
  - show selected model information;
  - show selected unit information;
  - cycle available overlays or selectable units;
  - open context menu and confirm/cancel local UI state.
- [ ] Add config diagnostics for:
  - unsupported schema versions;
  - unknown command IDs;
  - unknown overlay IDs;
  - duplicate hotkey bindings;
  - invalid key or modifier syntax;
  - settings that reference features not available in the current build.
- [ ] Add example profiles under documentation or fixtures:
  - default profile;
  - dense/debug profile;
  - keyboard-heavy profile.
- [ ] Wire preferences through render, input, HUD, and local UI state via typed registries rather
  than ad hoc string checks.

## Acceptance criteria

- [ ] JSON and YAML preference files can be loaded through the same typed schema.
- [ ] Built-in defaults can be exported or documented as a complete hand-editable profile.
- [ ] Unknown commands, unknown overlays, duplicate hotkeys, and invalid syntax produce visible typed
  config diagnostics instead of silent fallback behavior.
- [ ] Default selection overlays can be configured for model selection, unit selection, and movement
  drafting.
- [ ] Hotkeys can toggle known overlays and selected model/unit information panels.
- [ ] Config files cannot create finite options, proposal kinds, engine decisions, or validation
  behavior.
- [ ] Config-driven overlays remain viewer-scoped and cannot expose hidden opponent information.
- [ ] Tests cover schema loading, JSON/YAML parsing, default-profile generation, hotkey conflict
  detection, command/overlay ID validation, and selection-triggered overlay activation.

## Closeout milestone

**Milestone 8: “Shareable Preferences Layer”**

Users can hand-edit and pass around a portable UI preferences file that controls known overlays,
selected-model/unit information affordances, HUD defaults, and hotkeys while preserving the
engine-authoritative decision boundary.
