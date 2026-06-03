# Phase 4 — Shareable UI preferences framework

## Goal

Add a hand-editable, shareable UI preferences framework before selection/HUD work so upcoming UI
behavior can be encoded, exported, swapped, and experimented with through portable JSON or YAML
profiles.

User configuration is allowed to control how the UI presents known information and maps local input
to known UI commands. It must not create legal actions, finite option IDs, proposal kinds, rule
validation, hidden-information visibility, or authoritative state changes.

This phase intentionally creates the preferences schema early, before every referenced overlay or
HUD behavior exists. Future-facing preferences may name known planned properties, but validation must
distinguish between:

- supported settings that are active in the current build;
- planned settings that are accepted and preserved but not yet applied;
- unknown settings, unknown commands, or unknown overlays that should produce typed diagnostics.

## Tasks

- [x] Add a `preferences` or `settings` module with versioned typed schemas:
  - `UiPreferences`
  - `OverlayPreferences`
  - `HotkeyBinding`
  - `SelectionBehaviorPreferences`
  - `HudPreferences`
  - `ExperimentalPreferenceFlags`
- [x] Define schema behavior for future-facing properties:
  - preserve recognized-but-unimplemented settings through load/export round trips;
  - mark them as inactive through diagnostics rather than dropping them;
  - reject unknown top-level keys unless they are under a clearly named experimental/extension
    section.
- [x] Support loading preferences from:
  - an explicit config path, planned for a future CLI flag;
  - a platform default path via `platformdirs`;
  - built-in defaults when no user file exists.
- [x] Support hand-editable JSON and YAML files:
  - keep generated examples portable and free of machine-specific absolute paths;
  - add a YAML parser dependency only when this phase is implemented;
  - include `schema_version` in every persisted profile.
- [x] Support exporting profiles:
  - write the active/default profile as JSON;
  - write the active/default profile as YAML;
  - preserve stable field order for easy diffs;
  - include comments or adjacent docs for YAML examples where practical.
- [x] Define a stable UI command registry for local-only commands:
  - toggle known overlay for selected model or unit;
  - show selected model details;
  - show selected unit details;
  - open selected-unit action menu;
  - start or stop measure mode;
  - confirm, cancel, and cycle local UI selections.
- [x] Define a stable overlay registry for known advisory overlays:
  - movement budget;
  - movement path draft;
  - objective/control context, once present in projections;
  - engagement range, coherency, line-of-sight, and cover overlays as later phases expose data.
- [x] Add selection-triggered overlay preferences:
  - overlays enabled when a model is selected with the default mouse button;
  - overlays enabled when a unit is selected;
  - overlays enabled while a movement draft is active.
- [x] Add configurable hotkeys:
  - toggle individual overlays for the currently selected model or unit;
  - show selected model information;
  - show selected unit information;
  - cycle available overlays or selectable units;
  - open context menu and confirm/cancel local UI state.
- [x] Add config diagnostics for:
  - unsupported schema versions;
  - unknown command IDs;
  - unknown overlay IDs;
  - duplicate hotkey bindings;
  - invalid key or modifier syntax;
  - settings that reference features not available in the current build.
- [x] Add example profiles under documentation or fixtures:
  - default profile;
  - dense/debug profile;
  - keyboard-heavy profile.
- [x] Add a small command-line or callable export path so users can generate a starter profile
  without copying internal defaults by hand.
- [x] Document the preference file format, supported IDs, planned-but-inactive IDs, and extension
  policy.
- [x] Establish typed registries for render, input, HUD, and local UI state boundaries so later
  phases consume the framework instead of inventing ad hoc local configuration shapes.

## Acceptance criteria

- [x] JSON and YAML preference files can be loaded through the same typed schema.
- [x] Built-in defaults can be exported or documented as a complete hand-editable profile.
- [x] Exported profiles are portable, deterministic, schema-versioned, and easy to diff.
- [x] Recognized upcoming properties can be encoded, round-tripped, and diagnosed as inactive until
  the implementing phase enables them.
- [x] Unknown commands, unknown overlays, duplicate hotkeys, and invalid syntax produce visible typed
  config diagnostics instead of silent fallback behavior.
- [x] Default selection overlays can be configured for model selection, unit selection, and movement
  drafting.
- [x] Hotkeys can toggle known overlays and selected model/unit information panels.
- [x] Config files cannot create finite options, proposal kinds, engine decisions, or validation
  behavior.
- [x] Config-driven overlays remain viewer-scoped and cannot expose hidden opponent information.
- [x] Tests cover schema loading, JSON/YAML parsing, default-profile generation, hotkey conflict
  detection, export determinism, command/overlay ID validation, future-facing inactive properties,
  and selection-triggered overlay activation.

## Closeout milestone

**Milestone 4: “Shareable Preferences Framework”**

Users can hand-edit and pass around a portable UI preferences file that controls known overlays,
selected-model/unit information affordances, HUD defaults, hotkeys, and planned UI behavior settings
while preserving the engine-authoritative decision boundary.

## Implementation notes

Implemented in `warhammer40k_arcade_ui.preferences`:

- `schema.py` owns versioned typed dataclasses, schema parsing, JSON-safe extension preservation,
  registry validation, duplicate hotkey detection, invalid key/modifier checks, and typed
  diagnostics.
- `registries.py` defines the stable UI command registry, advisory overlay registry, and recognized
  planned-setting registry.
- `defaults.py` provides built-in `default`, `dense-debug`, and `keyboard-heavy` profiles.
- `io.py` supports explicit-path loading, platform-default lookup via `platformdirs`, built-in
  defaults when no user file exists, deterministic JSON export, and deterministic YAML export.
- `export_profile.py` exposes `warhammer40k-export-preferences` for generating starter profiles.

Documented example profiles live under `docs/preferences/`, and the file format/ID policy is
documented in `docs/ui-configuration.md`.

Later phases still need to consume these registries through selection, input, HUD, movement-draft,
and render state wiring. Phase 4 intentionally does not activate planned overlays or planned
settings that lack supporting projection/local-state data.

## Verification

Ran the following checks after implementation:

- `uv lock`
- `uv run ruff format .`
- `uv run ruff check .`
- `uv run pyright`
- `uv run mypy src tests`
- `uv run pytest`
- `uv run pre-commit run --all-files`
