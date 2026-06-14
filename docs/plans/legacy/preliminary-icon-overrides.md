# Preliminary - Simple icon overrides

## Status

Preliminary. This plan records the icon-override work left out of Phase 22 and should come after
asset roots are stable. Full pack-driven overrides should come after the asset-pack plan.

## Goal

Allow users to override known presentation icons with their own simple icon assets while keeping
the icon registry explicit, typed, and presentation-only.

The UI should support a user editing a YAML file to replace icons such as confirm/cancel, movement,
selection, warning, or phase/status symbols without changing Python code.

## Motivation

The HUD widget toolkit and icon guidance both expect reusable, semantic icon IDs. Users will want
alternate icon aesthetics, faction-colored icon sets, high-contrast variants, or accessibility-driven
symbol substitutions. This should be possible through config and assets without letting config
create new engine decisions or rules.

## Requirements

- Add an explicit icon registry of known semantic icon IDs. Unknown icon IDs should produce typed
  diagnostics.
- Support overrides from:
  - a dedicated icon override YAML file;
  - HUD or preferences references to that YAML file;
  - later, asset-pack manifests.
- Candidate YAML shape:

  ```yaml
  schema_version: 1
  icons:
    command.confirm: assets/icons/check.svg
    command.cancel: assets/icons/x.svg
    movement.normal: /abs/path/icons/move.svg
  ```

- Resolve relative icon asset paths against the source containing the override YAML.
- Support simple raster icons first if that keeps implementation small, but preserve a path for SVG
  source icons as recommended by `docs/guidance/ICON_GRAPHICS_SYSTEM.md`.
- If SVG support is implemented:
  - treat SVG as source art, not an Arcade-native runtime format;
  - rasterize into textures at requested sizes;
  - cache by icon ID, source, size, and color/theme token;
  - support `currentColor` substitution for recolorable icons where practical.
- Add a safe fallback rule:
  - invalid overrides are diagnostics and do not replace the built-in icon;
  - missing optional icons fall back to built-in icons;
  - missing required built-in icons are test failures, not runtime guesses.
- Add an icon preview or extend `warhammer40k-hud-preview` so users can visually review icon
  overrides before launching a game.
- Keep preferences/HUD YAML presentation-only; icon mappings must not define legal actions,
  decision IDs, proposal kinds, or hidden-information behavior.

## Non-Goals

- No arbitrary user code.
- No remote URL loading.
- No engine contract changes.
- No model/terrain art pipeline.
- No guarantee that every future icon is overrideable until it is registered.

## Acceptance Criteria

- [ ] Known icon IDs are documented and test-covered.
- [ ] A user icon override YAML can replace a known icon with a filesystem-relative asset.
- [ ] Built-in package icons remain available when no override is configured.
- [ ] Invalid override entries produce typed diagnostics and preserve built-in fallback.
- [ ] Preview tooling can render overridden icons for manual review.
- [ ] Tests cover registry validation, relative path resolution, missing files, and fallback.

## Manual Validation Checklist

- Create a temporary profile folder with an icon override YAML and one custom icon.
- Launch the preview tool or HUD preview with the override loaded.
- Confirm the expected icon changes while unrelated icons continue using built-ins.
- Intentionally reference an unknown icon ID and confirm a visible diagnostic is emitted.
