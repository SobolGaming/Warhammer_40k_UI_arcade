# Preliminary - `warhammer40k-config` and platform init commands

## Status

Preliminary. This plan records the follow-on work left out of Phase 22 for a dedicated
configuration-management command surface.

## Goal

Add a small `warhammer40k-config` command that helps users discover, initialize, and inspect the UI
configuration directories without silently extracting package resources at app launch.

The user-facing model should stay simple:

- packaged resources are immutable defaults;
- editable YAML lives in the platform config directory;
- durable imported art/assets live in the platform data directory;
- generated or extracted artifacts live in the platform cache directory;
- traces and crash bundles live in the platform state directory.

## Motivation

Phase 22 made installed Git/wheel launches independent from top-level `docs/` files. The next step
is to give users a deliberate command for copying starter profiles into writable locations so they
can edit and share UI configuration without mutating installed package resources.

This also gives bug reports and support instructions a stable way to ask "show me your UI paths" or
"initialize a starter config folder" without guessing platform-specific directories.

## Proposed Commands

Initial command surface:

```bash
warhammer40k-config paths
warhammer40k-config init
warhammer40k-config init --overwrite
warhammer40k-config init --dry-run
warhammer40k-config init --profile default
warhammer40k-config init --profile command-bench
```

Later commands may be added by the asset-root and asset-pack phases, but this first slice should
stay focused on paths and starter YAML.

## Requirements

- Add a `warhammer40k-config` project script entrypoint.
- Add platform path helpers that consistently expose:
  - `user_config_path("warhammer40k-arcade-ui")`;
  - `user_data_path("warhammer40k-arcade-ui")`;
  - `user_cache_path("warhammer40k-arcade-ui")`;
  - `user_state_path("warhammer40k-arcade-ui")`.
- `paths` should print JSON-safe, deterministic path information suitable for copying into issue
  reports.
- `init` should copy starter config files from packaged resources to the platform config directory:
  - `ui-preferences.yaml`;
  - `hud/default-hud.yaml`;
  - `hud/command-bench-hud.yaml`.
- `init` should not overwrite existing files unless `--overwrite` is passed.
- `init --dry-run` should report intended writes without modifying files.
- The copy process must read package resources through `importlib.resources`, not assume files exist
  on disk inside the installed package.
- The command should emit typed, user-readable diagnostics for skipped existing files, invalid
  profile names, write errors, and unsafe resource paths.
- README and `docs/ui-configuration.md` should document the command.

## Non-Goals

- No asset-pack install/import behavior yet.
- No icon override behavior yet.
- No profile inheritance or deep merge behavior.
- No game-rule, decision, visibility, or validation configuration.
- No automatic expansion of defaults during normal `warhammer40k-arcade-ui` launch.

## Acceptance Criteria

- [ ] `warhammer40k-config paths` reports config, data, cache, and state directories.
- [ ] `warhammer40k-config init --dry-run` reports starter files without writing.
- [ ] `warhammer40k-config init` writes starter preferences and HUD profiles into the platform
  config directory.
- [ ] Existing files are skipped unless `--overwrite` is passed.
- [ ] Tests prove package-resource reads work without requiring resources to be normal filesystem
  files.
- [ ] README documents the workflow for initializing and editing a platform config profile.

## Manual Validation Checklist

- Run:

  ```bash
  uv run warhammer40k-config paths
  uv run warhammer40k-config init --dry-run
  ```

- Run `init` into a temporary platform-dir override if supported by the implementation, or manually
  inspect the real platform config directory.
- Confirm `warhammer40k-arcade-ui` still launches without running `init`.
- Confirm editable files created by `init` can be passed through `--ui-prefs`.
