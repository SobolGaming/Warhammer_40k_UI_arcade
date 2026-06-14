# Preliminary - Asset roots and shareable profile folders

## Status

Preliminary. This plan records the asset-root work left out of Phase 22.

## Goal

Introduce durable asset roots so user preferences, HUD composition YAML, and future art references
can find local assets in a predictable way.

The first useful capability is a shareable folder:

```text
my-warhammer-ui-profile/
  ui-preferences.yaml
  hud/
    my-custom-hud.yaml
  assets/
    icons/
    textures/
    themes/
```

Relative references inside YAML should resolve against the source that loaded the YAML. Asset roots
extend that same source-aware model to art and icon files.

## Motivation

Phase 22 supports source-relative HUD composition references. Future HUD and icon customization
needs the same model for assets so a user can hand-edit a profile, zip a folder, send it to someone
else, and have references continue to work without machine-specific absolute paths.

## Requirements

- Add an asset-root model that can represent:
  - built-in package resources;
  - platform user data roots;
  - explicit runtime roots from CLI flags;
  - profile-relative roots from the loaded preferences source.
- Add an optional CLI flag such as:

  ```bash
  warhammer40k-arcade-ui --asset-dir path/to/assets
  ```

- Add a preferences/HUD-safe way to name asset roots without creating a rules language. Candidate
  shape:

  ```yaml
  assets:
    roots:
      - assets
      - /abs/path/to/shared-assets
  ```

- Resolve relative root entries against the YAML file or package resource source that names them.
- Preserve the Phase 22 invariant that package-resource-relative references work even when the
  installed package is a wheel or zip-style Python package.
- Keep platform user assets under `user_data_path("warhammer40k-arcade-ui")`, not config or cache.
- Add path validation that rejects traversal, hidden unsafe package escapes, and unsupported URI
  schemes.
- Add diagnostics that report the source and resolved display name for each configured root.
- Add tests for filesystem-relative roots, absolute roots, platform data roots, and built-in
  package-resource roots.

## Non-Goals

- No asset pack manifests yet.
- No icon override mapping yet.
- No texture atlas generation yet.
- No automatic download/import behavior.
- No engine-side data or game-rule behavior.

## Acceptance Criteria

- [ ] Runtime can build an ordered `AssetRoot` list from built-ins, platform data, explicit CLI
  roots, and profile-relative entries.
- [ ] Relative roots resolve against normal filesystem config sources and package-resource sources.
- [ ] Missing roots produce typed diagnostics rather than silent fallback.
- [ ] Tests cover source-relative path resolution and unsafe references.
- [ ] README documents how to structure and share a profile folder with an `assets/` subdirectory.

## Manual Validation Checklist

- Create a temporary profile folder with `ui-preferences.yaml`, `hud/`, and `assets/`.
- Launch with:

  ```bash
  uv run warhammer40k-arcade-ui --ui-prefs /tmp/my-profile/ui-preferences.yaml
  ```

- Confirm debug diagnostics show the profile-relative asset root.
- Launch with an explicit asset root:

  ```bash
  uv run warhammer40k-arcade-ui --asset-dir /tmp/my-profile/assets
  ```

- Confirm missing or unsafe roots are reported clearly.
