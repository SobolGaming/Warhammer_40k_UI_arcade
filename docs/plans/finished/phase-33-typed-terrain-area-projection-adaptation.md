# Phase 33: Typed Terrain Area Projection Adaptation

Status: Implemented

## Purpose

Adapt the UI projection layer to the current core mission setup terrain contract introduced in
`Warhammer_40k_AI` commit `f01293fb4d83249482ecee1c304e21f18e57055e`.

The core now exposes validated Chapter Approved 2026-27 Event Companion layout geometry through
`GameViewPayload.mission_setup.terrain_areas[*]` and optional
`mission_setup.objective_terrain_areas[*]`. The UI must render those typed payloads directly and
must stop depending on `terrain_features[*].display_geometry` being populated for layout terrain.

## Core Update Context

The reviewed core commit:

- removes unvalidated terrain feature projections from layouts that do not yet have feature-level
  terrain semantics;
- adds first-class `terrain_areas` layout footprints with:
  - `terrain_area_id`;
  - `classification`;
  - `footprint_template_id`;
  - `center_x_inches`;
  - `center_y_inches`;
  - `rotation_degrees`;
  - `local_transform`;
  - `footprint_polygon`;
  - `source_layout_id`;
  - `source_id`;
- adds `objective_terrain_areas` records linking objective marker IDs and roles to one or more
  terrain area IDs;
- clarifies that Chapter Approved 2026-27 layout source geometry is canonical in `44x60` portrait
  orientation even when a UI renders the battlefield in a landscape-friendly view.

The existing UI `core_projection` path currently renders typed terrain feature display geometry from
`mission_setup.terrain_features[*].display_geometry`. Under the new core contract, current
validated layout terrain may appear only in `terrain_areas`, so terrain can visually disappear even
though the core payload is correct.

## Scope

In scope:

- parse and render `mission_setup.terrain_areas[*].footprint_polygon` as layout terrain footprints;
- preserve strict typed-geometry behavior and fail loudly on malformed area polygons;
- carry through area labels from `classification` or `footprint_template_id`;
- expose enough view-model metadata to distinguish ordinary terrain feature footprints from layout
  terrain areas when helpful for review/debug text;
- render `objective_terrain_areas` as objective footprint links when present, while preserving the
  objective marker identity/label as the stable objective entity;
- keep existing `terrain_features[*].display_geometry` support for future feature-level terrain;
- add fixture and live-smoke projection tests for both `terrain_areas` and empty
  `terrain_features`;
- update render evidence checks so missing terrain areas are detected.

Out of scope:

- terrain rules, cover, visibility, movement penalties, or other terrain-feature semantics;
- local inference of objective terrain, light/dense terrain traits, or terrain legality from area
  colors, template IDs, source IDs, or classification labels;
- local terrain layout selection;
- conversion of portrait source coordinates into new authoritative coordinates. If the UI rotates
  presentation for a wide display, the transform must remain an explicit render concern and must not
  reinterpret core payload coordinates.

## Implementation Slices

1. **Projection parser**
   - Add a strict `_terrain_areas_from_mission_setup(...)` path in `core_projection`.
   - Accept unclosed `footprint_polygon` vertices shaped as `{x_inches, y_inches}`.
   - Reject missing, closed, degenerate, or non-finite polygons with `CoreProjectionRenderError`.
   - Preserve existing typed `terrain_features[*].display_geometry` parsing for future feature
     payloads.

2. **View-model metadata**
   - Extend `TerrainFootprintView` only as needed to identify `terrain_area` versus
     `terrain_feature`.
   - Use `terrain_area_id` as the terrain ID for area footprints.
   - Use a readable label derived from `classification` first, falling back to
     `footprint_template_id`.

3. **Objective footprint links**
   - Parse `objective_terrain_areas` into an advisory render structure or cross-reference map.
   - Highlight linked terrain areas when rendering objective footprint overlays if that does not
     obscure model placement.
   - Keep the objective marker as the canonical objective ID and label. Do not turn terrain area IDs
     into objective IDs.

4. **Orientation handling**
   - Document the current presentation choice for portrait source coordinates.
   - If a display transform is needed for landscape presentation, implement it as an explicit render
     transform with tests for table bounds, deployment zones, objectives, terrain areas, and unit
     poses.
   - Do not silently rotate only terrain or only deployment zones.

5. **Regression fixtures**
   - Add a core-projection fixture with:
     - non-empty `terrain_areas`;
     - empty `terrain_features`;
     - at least one `objective_terrain_areas` entry;
     - a `local_transform` value.
   - Add a failure fixture for malformed terrain area polygons.
   - Add headless render evidence assertions that terrain area polygons produce non-background
     pixels in the expected battlefield region.

## Acceptance Criteria

- Live core mission setups using `terrain_areas` render visible terrain footprints even when
  `terrain_features` is empty.
- Malformed or missing typed terrain area geometry fails with a copyable projection diagnostic
  instead of silently rendering no terrain.
- Existing `terrain_features[*].display_geometry` fixtures still render and remain strict.
- Objective terrain links can be surfaced in runtime/render metadata without implying rules
  semantics.
- Tests prove the UI no longer parses `source_id` for terrain geometry.
- Tests prove `local_transform` is accepted as core-provided metadata but geometry is rendered from
  the already-projected `footprint_polygon`.

## Automated Verification

Add or update tests for:

- `terrain_areas` render projection with empty `terrain_features`;
- mixed `terrain_areas` and `terrain_features`;
- malformed terrain area polygon rejection;
- objective terrain area cross-reference parsing;
- render primitive generation from terrain area footprints;
- headless render evidence for terrain area visibility.

Run:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pyright
uv run pytest tests/test_core_projection.py tests/test_render_primitives.py tests/test_headless_render_capture.py
uv run pytest
```

## Manual Validation Checklist

- Launch a live core smoke scenario using the supported core commit:
  `uv run warhammer40k-arcade-ui --live-core-smoke --ui-prefs docs/preferences/default.yaml`.
- Confirm terrain footprints are visible when the core payload has non-empty `terrain_areas`.
- Confirm terrain layout and deployment map labels still render outside the battlefield.
- Confirm objective labels/markers remain stable when objective terrain links are present.
- Trigger or simulate a malformed terrain area payload and confirm startup fails with a clear
  projection diagnostic.

## Reviewer Notes

Review should focus on projection fidelity. This phase should make the UI render the core's typed
terrain geometry, not create a local terrain catalog, parse provenance strings, or infer terrain
rules.

## Implementation Notes

Implemented in the UI projection layer:

- `mission_setup.terrain_areas[*].footprint_polygon` now builds `TerrainFootprintView` entries
  when current live core layouts expose typed layout area geometry and leave `terrain_features`
  empty.
- `TerrainFootprintView` carries advisory `source_kind` and `objective_marker_ids` metadata so
  review/debug surfaces can distinguish typed layout terrain areas from future feature-level
  terrain footprints.
- `objective_terrain_areas` links are parsed as non-authoritative cross-reference metadata and
  render as a thin advisory outline over the linked area footprint.
- Existing `terrain_features[*].display_geometry` parsing remains strict and supported for future
  feature-level terrain.
- The UI renders from typed `footprint_polygon` data and does not parse `source_id` for geometry.
