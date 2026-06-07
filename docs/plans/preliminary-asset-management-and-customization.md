# Preliminary - Asset management and customization

## Status

Preliminary. This roadmap records future work for installable runtime defaults, user-editable
configuration, HUD composition assets, simple icon overrides, and later broader art customization.

This revision is guided primarily by
`docs/guidance/ASSET_MGMT_AND_ADDRESSING.md`. The dominant guidance is:

- package resources are immutable built-in defaults;
- user configuration and durable user assets are normal filesystem files;
- cache is only for disposable, extracted, generated, or compiled artifacts;
- state/log/crash evidence belongs under platform state/log paths, not config or cache;
- user-facing commands should use named built-ins and ordinary paths, not Python package-path
  notation;
- paths referenced by shareable YAML profiles should resolve relative to the YAML file that
  contains the reference;
- runtime defaults should live inside the import package so installed-from-git and installed wheel
  workflows do not depend on top-level `docs/`.

## Goal

Create a stable customization model so players and power users can edit UI preferences, HUD
composition, simple icons, and later art assets without editing Python code or changing game rules.

The immediate outcome should be a clean source hierarchy:

```text
built-in package defaults
  src/warhammer40k_arcade_ui/resources/preferences/*.yaml
  src/warhammer40k_arcade_ui/resources/hud/*.yaml
  src/warhammer40k_arcade_ui/resources/art/...

platform user config
  platformdirs.user_config_path("warhammer40k-arcade-ui") / "ui-preferences.yaml"
  platformdirs.user_config_path("warhammer40k-arcade-ui") / "hud/*.yaml"
  platformdirs.user_config_path("warhammer40k-arcade-ui") / "profiles/*.yaml"

platform user data
  platformdirs.user_data_path("warhammer40k-arcade-ui") / "assets"
  platformdirs.user_data_path("warhammer40k-arcade-ui") / "themes"
  platformdirs.user_data_path("warhammer40k-arcade-ui") / "imported-art"

platform user cache
  platformdirs.user_cache_path("warhammer40k-arcade-ui") / "generated-atlases"
  platformdirs.user_cache_path("warhammer40k-arcade-ui") / "thumbnails"
  platformdirs.user_cache_path("warhammer40k-arcade-ui") / "extracted-package-assets"

platform user state
  platformdirs.user_state_path("warhammer40k-arcade-ui") / "event-traces"
  platformdirs.user_state_path("warhammer40k-arcade-ui") / "crash-bundles"
  platformdirs.user_state_path("warhammer40k-arcade-ui") / "recent-files.json"
```

Longer term, the same framework can support richer user assets such as unit portraits, faction
badges, terrain thumbnails, mission-card art, status effects, battlefield themes, and HUD skins.

## Design Principles

- Customization is presentation-only. It must not define legal actions, decision IDs, request IDs,
  proposal kinds, rules text authority, hidden-information visibility, or core-engine behavior.
- Built-in runtime defaults should be loaded through `importlib.resources`, not by assuming a source
  checkout path.
- `docs/` may contain examples and documentation copies, but runtime code should not depend on
  top-level `docs/` existing after installation.
- The default install remains pristine. Users customize by exporting or initializing starter files
  into writable config/data locations or by passing explicit paths.
- User-facing interfaces should prefer `--profile default`, `--hud-profile command-bench`, and
  ordinary paths such as `--ui-prefs /path/to/profile.yaml`.
- Do not expose `:pkg_name:path` or other Python packaging internals as the normal player-facing
  syntax.
- Shareable profiles should work as ordinary folders. Relative references inside a YAML file should
  resolve relative to that YAML file's directory.
- Use whole-profile replacement first. Defer deep-merge or inheritance until schemas are stable.
- Missing or invalid assets should produce typed diagnostics and fall back to built-ins where safe.
- Simple icon overrides are first-class, because they are a low-risk way for users to personalize
  the HUD without gaining any rule authority.

## Proposed Phase 23 - Packaged Runtime Defaults And Source Model

### Goal

Move runtime defaults into package resources and introduce explicit source metadata for built-in,
user-default, and explicit-path configuration.

### Requirements

- Move runtime preference and HUD defaults into the package tree:

  ```text
  src/warhammer40k_arcade_ui/resources/
    __init__.py
    preferences/
      default.yaml
      keyboard-heavy.yaml
      command-bench.yaml
    hud/
      default-hud.yaml
      command-bench-hud.yaml
    art/
      icons/
      hud/
  ```

- Keep `docs/preferences` and `docs/hud` as documentation/examples only, or generate/copy examples
  from packaged resources in a deliberate documentation step.
- Add internal source objects such as `ConfigSource` and `ResourceSource` with source kinds:
  - `builtin`;
  - `user_default`;
  - `explicit_path`.
- Load built-in YAML/text resources with `importlib.resources.files()`.
- Use `importlib.resources.as_file()` only when an API truly requires a filesystem path, and make
  lifetime rules explicit when Arcade or another library stores paths for later use.
- Preserve current explicit path support, especially `--ui-prefs PATH`.
- Update packaging tests so wheels and source distributions can resolve built-in runtime defaults
  without the source-tree `docs/` directory.

### Acceptance Criteria

- [ ] Launching without `--ui-prefs` can load a packaged built-in preference profile.
- [ ] HUD preview can load a packaged built-in HUD profile.
- [ ] Runtime code no longer depends on top-level `docs/preferences` or `docs/hud`.
- [ ] Package artifact tests prove built-in YAML resources are present after installation.
- [ ] Source metadata is visible in debug/diagnostic surfaces where preference or HUD source names
  are already displayed.

### Testing

- Unit-test safe built-in resource path validation.
- Unit-test `ConfigSource` and `ResourceSource` construction.
- Unit-test fallback from absent user default to packaged built-in default.
- Build wheel/sdist and verify packaged defaults can be loaded from the artifact.

## Proposed Phase 24 - Platform Config Paths And Init Commands

### Goal

Make user-editable configuration discoverable and writable through platform-standard locations,
without silently copying defaults into cache on first launch.

### Requirements

- Use `platformdirs.user_config_path("warhammer40k-arcade-ui", appauthor=False)` for editable YAML:
  - `ui-preferences.yaml`;
  - `hud/*.yaml`;
  - `profiles/*.yaml`.
- Add a config command entrypoint, tentatively `warhammer40k-config`, with:
  - `warhammer40k-config paths`;
  - `warhammer40k-config init`;
  - `warhammer40k-config init --overwrite`.
- Keep `warhammer40k-export-preferences` as a focused export tool or fold its behavior into the new
  config command only after an explicit compatibility decision.
- Add named built-in profile selection separate from explicit paths:
  - `warhammer40k-arcade-ui --profile default`;
  - `warhammer40k-arcade-ui --profile keyboard-heavy`;
  - `warhammer40k-arcade-ui --profile command-bench`;
  - `warhammer40k-arcade-ui --hud-profile default-hud`;
  - `warhammer40k-arcade-ui --hud-profile command-bench-hud`.
- Preserve exact-file overrides:
  - `warhammer40k-arcade-ui --ui-prefs /path/to/profile.yaml`;
  - `warhammer40k-arcade-ui --hud-profile /path/to/hud.yaml`.
- Resolve precedence deterministically:
  1. explicit CLI path;
  2. named built-in profile requested by CLI;
  3. platform user default config if it exists;
  4. packaged built-in default.
- Avoid arbitrary silent deep merges. Use whole-profile replacement until a future phase defines
  explicit inheritance semantics.

### Acceptance Criteria

- [ ] `warhammer40k-config paths` prints config, data, cache, state, and log locations.
- [ ] `warhammer40k-config init` writes starter preferences/HUD files to the platform config
  directory without overwriting existing files.
- [ ] `warhammer40k-config init --overwrite` replaces starter files intentionally.
- [ ] README documents package defaults, user config paths, explicit path overrides, and named
  profile usage.
- [ ] Existing `--ui-prefs PATH` behavior remains supported.

### Testing

- Unit-test platform path helpers with test-controlled app names or monkeypatched path providers.
- Unit-test init write/skip/overwrite behavior.
- Unit-test source precedence.
- Unit-test that no cache directory is created for editable user configuration.

## Proposed Phase 25 - File-Relative Profile References And Durable Asset Roots

### Goal

Allow shareable profile folders to reference HUD YAML and asset folders naturally, while keeping
durable user art separate from editable config and disposable cache.

### Requirements

- Resolve YAML file references using this user-facing model:
  - known built-in ID, such as `composition_profile: default-hud`;
  - relative path, such as `composition_profile: hud/my-custom.yaml`, resolved relative to the YAML
    file containing the reference;
  - absolute path, such as `composition_profile: /abs/path/hud.yaml`.
- Support shareable folders such as:

  ```text
  my-warhammer-ui-profile/
    ui-preferences.yaml
    hud/
      table-hud.yaml
    assets/
      icons/
      objective-marker.png
  ```

- Add durable asset roots under `platformdirs.user_data_path("warhammer40k-arcade-ui")`, not config
  or cache.
- Add explicit runtime roots only where useful:
  - `--asset-dir /path/to/assets`;
  - preview-only asset roots for `warhammer40k-hud-preview`.
- Treat `user_cache_path()` as disposable:
  - generated thumbnails;
  - compiled texture atlases;
  - extracted package resources for APIs requiring persistent files;
  - other rebuildable artifacts.
- Keep event traces, crash bundles, recent files, and similar diagnostics under user state/log paths.
- Reject unsafe relative references containing traversal outside declared roots unless the reference
  is an explicit absolute path accepted by the user.

### Acceptance Criteria

- [ ] A profile folder can be copied to another machine and loaded with `--ui-prefs`.
- [ ] Relative HUD and asset references resolve relative to the profile file.
- [ ] Explicit absolute paths still work for local power-user workflows.
- [ ] Durable imported assets are not stored under cache.
- [ ] Generated/extracted artifacts are not stored under config.

### Testing

- Unit-test relative path resolution from profile files.
- Unit-test absolute path handling.
- Unit-test traversal rejection.
- Unit-test asset root precedence.
- Add a sample shareable profile folder under docs or tests.

## Proposed Phase 26 - Logical Asset Registry And Simple Icon Overrides

### Goal

Introduce logical asset IDs after the path/source model is stable, then let users override simple
icons without changing UI semantics.

### Requirements

- Define logical asset IDs for presentation elements, for example:
  - `icon.action.normal_move`;
  - `icon.action.advance_move`;
  - `icon.status.invalid`;
  - `icon.overlay.movement_path`;
  - `badge.unit.battleline`;
  - `texture.hud.panel_frame`.
- Route existing icon-like references through the registry:
  - HUD status chips;
  - decision/action indicators;
  - movement and assignment HUD rows;
  - diagnostics and warning indicators;
  - overlay toggles and summary overlays where icons exist.
- Allow users to override simple icons by logical ID while preserving semantics. For example, a user
  may replace `icon.action.normal_move` with a custom arrow icon, but the UI still treats that
  visual as the normal-move icon.
- Support SVG as source input for recolorable simple icons and PNG for raster icons.
- Preserve the icon guidance:
  - SVG is a source format;
  - Arcade consumes raster/Pillow-backed textures;
  - SVGs using `currentColor` can be recolored;
  - rasterized variants should be cached by logical ID, resolved file, color role, and size.
- Store durable user-provided icons under user data or in explicit shareable profile folders.
- Store generated icon thumbnails, atlases, or extracted resources under cache.
- Return structured diagnostics for:
  - unknown logical IDs;
  - missing override files;
  - unsupported formats;
  - invalid manifests;
  - duplicate logical IDs;
  - overrides that are accepted but never referenced.
- Fall back to built-in icons when an override is invalid and fallback is safe.

### Example Override

```yaml
assets:
  icon_overrides:
    icon.action.normal_move: assets/icons/normal-move.svg
    icon.status.invalid: /home/player/warhammer-icons/warning.png
```

The first path resolves relative to the profile file. The second is an explicit local absolute path.
Neither can change which action is legal or what the engine request means.

### Acceptance Criteria

- [ ] Existing HUD/icon surfaces can render built-in logical icon IDs.
- [ ] A user profile can override at least one action icon and one status icon.
- [ ] Missing or invalid icon overrides produce diagnostics and fall back safely.
- [ ] Icon override diagnostics are visible in HUD preview and crash/trace evidence where relevant.
- [ ] No icon override can create or redefine a decision, proposal kind, legal action, or visibility
  exception.

### Testing

- Unit-test logical ID parsing and normalization.
- Unit-test icon override precedence.
- Unit-test SVG and PNG resolution.
- Unit-test missing override fallback behavior.
- Add preview/headless render evidence showing a built-in icon and an overridden icon.

## Proposed Phase 27 - Asset Preview, Packaging, And Regression Workbench

### Goal

Make configuration and asset customization easy to inspect before launching a full game, and make CI
prove installed-package behavior.

### Requirements

- Extend `warhammer40k-hud-preview` or add a dedicated asset preview mode that can load:
  - a named built-in HUD profile;
  - an explicit HUD YAML file;
  - a UI preference profile;
  - one or more asset roots or icon override sets;
  - optional placeholder runtime data.
- Render a gallery of resolved icon IDs with labels, source information, and diagnostics.
- Render sample HUD panels using selected built-in or user assets.
- Add command examples such as:

  ```bash
  warhammer40k-config paths
  warhammer40k-config init
  warhammer40k-arcade-ui --profile default
  warhammer40k-arcade-ui --ui-prefs ./my-warhammer-ui-profile/ui-preferences.yaml
  warhammer40k-hud-preview --hud-profile command-bench-hud --asset-dir ./my-icons
  ```

- Ensure wheel/sdist packaging includes built-in resource manifests and assets.
- Add CI checks that package artifacts can load built-in preferences, HUD files, and icons from the
  installed package rather than from the source tree.

### Acceptance Criteria

- [ ] Preview can render a sample HUD using packaged built-in resources.
- [ ] Preview can render a sample HUD using a shareable profile folder.
- [ ] Preview can show icon override diagnostics without launching the game.
- [ ] Build artifact smoke tests prove packaged resources load after wheel/sdist install.
- [ ] README documents the source model and the difference between config, data, cache, and state.

### Testing

- Build artifact smoke test resolves at least one built-in preference file, one HUD file, and one
  icon asset.
- Preview smoke test loads a sample override folder.
- Headless evidence test proves the preview path can display overridden icons.
- Regression-test that top-level `docs/` can be absent from an installed package without breaking
  runtime defaults.

## Future Extensions

These are intentionally out of scope for the first asset customization pass but should shape the
addressing model:

- explicit profile inheritance such as `extends: default` after schema stability improves;
- faction badge packs;
- unit portrait packs;
- mission-card art packs;
- terrain thumbnails and terrain-pack preview assets;
- battlefield texture/theme packs;
- audio cue packs;
- remote marketplace/distribution workflows;
- versioned compatibility against future UI schema versions;
- engine-authored asset hints once the core exposes first-class display data.

## Non-Goals

- No changes to `Warhammer_40k_AI`.
- No client-side rule validation.
- No user asset pack may redefine game mechanics, legal targets, proposal kinds, decision IDs, or
  hidden state.
- No remote asset download or marketplace support in the first implementation.
- No user-facing `:pkg_name:path` syntax.
- No silent deep-merge behavior for arbitrary profile files in the first implementation.
- No guarantee that arbitrary SVG features will render; first-pass SVG support should target simple
  recolorable icons.

## Open Questions

- Should `warhammer40k-export-preferences` remain separate, or should it become a subcommand of
  `warhammer40k-config`?
- Should docs examples be generated from packaged defaults or maintained as intentionally separate
  examples?
- Which named built-in profiles should be canonical once runtime defaults move into package
  resources?
- Should HUD YAML reference only logical asset IDs, or also permit direct file references in
  preview-only examples?
- Which built-in icon IDs are required before player-facing HUD screens can stop using raw text for
  common actions?
- Should icon override diagnostics be visible in the player HUD, debug HUD, forensic trace, or all
  three?

## Manual Review Checklist

- Confirm the package-resource-first ordering matches
  `docs/guidance/ASSET_MGMT_AND_ADDRESSING.md`.
- Confirm config, data, cache, and state paths are separated correctly.
- Confirm named built-ins and ordinary paths are preferable to user-facing Python package path
  notation.
- Confirm relative references inside shareable profile folders are understandable for power users.
- Confirm simple icon overrides are explicitly supported without giving asset packs rule authority.
- Confirm future art assets can use the same source/path model without forcing icon-specific
  assumptions into terrain, card, or portrait assets.
