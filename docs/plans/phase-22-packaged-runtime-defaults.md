# Phase 22 - Packaged runtime defaults and source model

## Status

Implemented. This phase concretizes the first asset-management slice from the preliminary roadmap
into an implementation phase.

## Goal

Move runtime preference and HUD defaults into importable package resources and make configuration
sources explicit. Installed-from-git and installed wheel workflows should be able to launch with
built-in defaults without relying on top-level `docs/` files.

This phase is intentionally narrower than the full asset-customization roadmap. It establishes the
resource/source model needed by later platform config, asset-root, and icon-override phases.

## Guidance Applied

This phase is guided by `docs/guidance/ASSET_MGMT_AND_ADDRESSING.md`:

- package resources are immutable defaults;
- user configuration and durable user assets are normal filesystem files;
- cache is only for disposable/extracted/generated artifacts;
- runtime defaults should live inside the import package;
- user-facing commands should use named built-ins and ordinary paths, not Python package internals;
- top-level `docs/` may contain examples, but runtime code should not depend on it after install.

## Requirements

- Add packaged runtime resources under `src/warhammer40k_arcade_ui/resources/`:
  - `preferences/default.yaml`;
  - `preferences/dense-debug.yaml`;
  - `preferences/keyboard-heavy.yaml`;
  - `preferences/command-bench.yaml`;
  - `hud/default-hud.yaml`;
  - `hud/command-bench-hud.yaml`.
- Add safe package resource helpers:
  - built-in resource path validation;
  - text loading via `importlib.resources.files()`;
  - filesystem path materialization via `importlib.resources.as_file()` for future APIs that need
    real paths.
- Add explicit source metadata:
  - `ConfigSource(kind="builtin" | "user_default" | "explicit_path")`;
  - `ResourceSource(kind="builtin" | "user_default" | "explicit_path")`.
- Change no-file preference loading to parse packaged `preferences/default.yaml` only when no
  platform default preference file exists.
- Preserve existing explicit `--ui-prefs PATH` behavior.
- Continue checking the platform default preference file before using packaged defaults.
- Emit a loud HUD compatibility diagnostic when a platform default preference file is present but
  lacks `hud.composition_profile`, including guidance to move it aside or regenerate it with
  `warhammer40k-export-preferences --profile default --format yaml --output <platform path>`.
- Change built-in preference profiles to reference named HUD profiles:
  - `default-hud`;
  - `command-bench-hud`.
- Make HUD composition loading resolve named built-ins from packaged resources while preserving
  explicit file paths such as `docs/hud/default-hud.yaml`.
- Resolve HUD composition references relative to the source containing the preference profile:
  - known built-in ID, such as `composition_profile: default-hud`;
  - filesystem-relative path, such as `composition_profile: hud/my-custom.yaml` from a user
    preference file;
  - package-resource-relative path, such as `composition_profile: ../hud/default-hud.yaml` from a
    packaged preference resource;
  - explicit absolute path.
- Update HUD preview so a packaged built-in HUD profile can be previewed by name.
- Keep `docs/preferences` and `docs/hud` as examples/documentation copies, not runtime
  dependencies.
- Add tests proving built-in packaged resources load and explicit docs paths still work.

## Non-Goals

- No platform config init command yet.
- No `warhammer40k-config` entrypoint yet.
- No asset roots, asset packs, or icon override implementation yet.
- No profile inheritance/deep merge behavior.
- No core engine changes.

## Acceptance Criteria

- [x] `load_preferences()` with no user config file returns the packaged built-in default profile.
- [x] Launching the game without `--ui-prefs` still honors the platform default preference file when
  it exists.
- [x] A stale platform default preference file without `hud.composition_profile` displays a loud HUD
  compatibility diagnostic with regeneration guidance.
- [x] `load_preferences(explicit_path)` still loads the exact requested file.
- [x] Preference load results expose source metadata for built-in, platform default, and explicit
  path sources.
- [x] `load_hud_composition_for_preferences(default_preferences())` resolves `default-hud` from
  package resources.
- [x] `composition_profile: hud/my-custom.yaml` resolves relative to a filesystem preference file
  source.
- [x] Package-resource-relative HUD references resolve inside `warhammer40k_arcade_ui.resources`
  without requiring package resources to exist as normal filesystem files.
- [x] Absolute HUD paths resolve as explicit filesystem paths.
- [x] Explicit HUD YAML paths still load through `load_hud_composition(Path(...))`.
- [x] `warhammer40k-hud-preview default-hud --headless ...` can render packaged HUD resources.
- [x] Package metadata/build tests prove the resource files are inside the selected package tree.

## Follow-On Roadmap

Future phases should continue the asset-management roadmap in this order:

1. Platform config paths and init commands.
2. File-relative shareable profile references and durable asset roots.
3. Logical asset registry and simple icon overrides.
4. Asset preview, packaging, and regression workbench.
5. HUD toolkit customizability and overflow tuning.

## Manual Validation Checklist

- Launch without explicit preferences:

  ```bash
  uv run warhammer40k-arcade-ui
  ```

- Launch with the documented example profile and confirm explicit file paths still work:

  ```bash
  uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/default.yaml
  ```

- Preview the packaged default HUD:

  ```bash
  uv run warhammer40k-hud-preview default-hud --headless --artifact-dir /tmp/hud-preview
  ```

- Preview the documented example HUD by explicit path:

  ```bash
  uv run warhammer40k-hud-preview docs/hud/examples/workbench-preview.yaml --headless --artifact-dir /tmp/hud-preview-docs
  ```

## Implementation Notes

- Added `warhammer40k_arcade_ui.resources` with packaged preference and HUD YAML defaults.
- Added `ConfigSource` and `ResourceSource` metadata plus safe built-in resource readers.
- Changed no-file preference loading to parse packaged `preferences/default.yaml`.
- Preserved the platform default preference lookup before packaged fallback.
- Added a HUD compatibility diagnostic for platform default preference files that lack
  `hud.composition_profile`, so stale user config fails loudly instead of rendering no HUD.
- Preserved explicit path loading for `--ui-prefs PATH` and direct HUD YAML paths.
- Changed built-in preference profiles to reference named HUD profiles:
  - `default-hud`;
  - `command-bench-hud`.
- Changed HUD composition loading so named built-ins resolve from packaged resources.
- Added generic source-relative resource reference resolution for filesystem and package-resource
  sources.
- Updated HUD preview so `warhammer40k-hud-preview default-hud` renders the packaged profile.
- Left platform config init commands, asset roots, icon overrides, and profile inheritance for the
  follow-on phases listed above.

## Validation

- `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .`
- `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check .`
- `env UV_CACHE_DIR=/tmp/uv-cache uv run mypy src tests`
- `env UV_CACHE_DIR=/tmp/uv-cache uv run pyright`
- `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/`
- `env UV_CACHE_DIR=/tmp/uv-cache uv run warhammer40k-hud-preview default-hud --headless --artifact-dir /tmp/hud-preview-phase22`
- `env UV_CACHE_DIR=/tmp/uv-cache uv run warhammer40k-hud-preview docs/hud/examples/workbench-preview.yaml --headless --artifact-dir /tmp/hud-preview-phase22-docs`
