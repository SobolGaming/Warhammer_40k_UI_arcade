# Preliminary - Asset packs

## Status

Preliminary. This plan records the asset-pack work left out of Phase 22 and should come after the
asset-root model is implemented.

## Goal

Allow users to install, inspect, and reference bundles of presentation assets without making the UI
depend on mutable package resources or executable plugin code.

Asset packs should be data-only. They may provide HUD examples, themes, icons, textures, and future
terrain/model presentation assets, but they must not define rules, legal actions, validation
behavior, proposal kinds, option IDs, hidden-information visibility, or engine mutation.

## Motivation

The UI should eventually support user-created terrain packs, icon sets, HUD themes, and other art
customizations. A pack system gives those assets stable IDs and manifests while keeping package
defaults immutable and user imports durable under the platform data directory.

## Proposed Pack Shape

Candidate unpacked shape:

```text
my-pack/
  pack.yaml
  icons/
  textures/
  hud/
  themes/
```

Candidate manifest:

```yaml
schema_version: 1
pack_id: sobol.default-icons
display_name: Sobol Default Icons
version: 0.1.0
assets:
  icons:
    command.confirm: icons/check.svg
  hud:
    compact: hud/compact.yaml
```

The exact schema should be finalized after asset roots exist.

## Requirements

- Add a typed asset-pack manifest parser and diagnostics.
- Require stable `pack_id`, display name, version, and schema version.
- Support loading packs from:
  - built-in package resources;
  - platform user data directory;
  - explicit filesystem directories.
- Consider archive import only after directory packs are stable. If zip import is added, read
  package/archive contents through a generic source abstraction rather than assuming paths exist on
  disk.
- Add `warhammer40k-config` subcommands after the config command exists:

  ```bash
  warhammer40k-config packs list
  warhammer40k-config packs inspect path/to/pack
  warhammer40k-config packs install path/to/pack
  ```

- Installed user packs should live under `user_data_path("warhammer40k-arcade-ui") / "asset-packs"`.
- Validate that manifest asset paths remain inside the pack root.
- Reject executable hooks, Python imports, shell commands, or remote URLs in manifests.
- Add deterministic ordering and conflict diagnostics when multiple packs provide the same logical
  asset ID.
- Add tests for valid packs, invalid manifests, unsafe paths, duplicate IDs, and built-in vs user
  precedence.

## Non-Goals

- No live downloads or marketplace integration.
- No executable plugins.
- No automatic trust of third-party pack contents beyond data validation.
- No engine-side terrain/rules integration.
- No icon override behavior beyond exposing pack-provided logical assets for later phases.

## Acceptance Criteria

- [ ] Asset-pack manifests parse into typed view models with source metadata.
- [ ] Pack paths are validated against traversal and unsupported schemes.
- [ ] Pack listing shows built-in and installed user packs.
- [ ] Pack inspection reports logical asset IDs and diagnostics.
- [ ] Tests cover manifest validation, ordering, and conflict diagnostics.

## Manual Validation Checklist

- Create a minimal temporary pack directory with `pack.yaml` and one sample asset.
- Run:

  ```bash
  uv run warhammer40k-config packs inspect /tmp/my-pack
  ```

- Install it into the platform data directory once install support exists.
- Confirm `packs list` shows built-in and user-installed packs separately.
