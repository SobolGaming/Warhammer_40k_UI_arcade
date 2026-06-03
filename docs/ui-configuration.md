# UI Preferences

Phase 4 introduces portable UI preference profiles for local presentation and input behavior.
Profiles are hand-editable, schema-versioned, and exportable as JSON or YAML.

Preferences may configure only registered UI commands, registered advisory overlays, HUD defaults,
and local behavior settings. They cannot define engine decisions, legal actions, proposal kinds,
validation behavior, or hidden-information visibility.

## Export

Generate a starter profile:

```bash
uv run warhammer40k-export-preferences --format yaml
uv run warhammer40k-export-preferences --format json --output ui-preferences.json
```

Available built-in profiles:

- `default`
- `dense-debug`
- `keyboard-heavy`

## File Shape

Every profile includes:

- `schema_version`
- `profile_name`
- `overlays`
- `hotkeys`
- `selection`
- `hud`
- `experimental`
- `extensions`

Recognized planned settings under `experimental.planned_settings` are preserved through load/export
round trips and reported as inactive until their implementing phase wires them to the UI. Unknown
top-level fields produce diagnostics. Tool- or user-specific extension payloads belong under
`extensions`.

Example profiles live in [docs/preferences](preferences/).

## Command IDs

Active command IDs:

- `toggle_overlay`
- `show_selected_model`
- `show_selected_unit`
- `open_selected_unit_actions`
- `toggle_measure_mode`
- `confirm`
- `cancel`
- `cycle_selection`
- `toggle_debug_inspector`

`toggle_overlay` bindings must include an `overlay_id`.

## Overlay IDs

Active overlay IDs:

- `debug_coordinates`

Recognized planned overlay IDs are accepted and preserved, but emit inactive diagnostics until later
phases wire them to render, HUD, projection, or local-state data:

- `selected_model`
- `selected_unit`
- `movement_budget`
- `movement_path_draft`
- `objective_control_context`
- `engagement_range`
- `coherency`
- `line_of_sight`
- `cover`

## Planned Settings

Recognized planned settings under `experimental.planned_settings`:

- `hud.minimap_enabled`
- `input.keyboard_first_mode`
- `movement.auto_path_preview`
- `render.cached_text_objects`
- `selection.history_limit`

These values round-trip through load/export and produce `inactive_planned_setting` diagnostics in
the current build.

## Diagnostics

The loader reports typed diagnostics for unsupported schema versions, unknown top-level or nested
fields, unknown command IDs, unknown overlay IDs, duplicate hotkey bindings, invalid keys, invalid
modifiers, and recognized-but-inactive planned settings.

Unknown settings that a tool needs to preserve should live under `extensions` so the base UI can
round-trip them as JSON-safe values without treating them as first-party behavior.
