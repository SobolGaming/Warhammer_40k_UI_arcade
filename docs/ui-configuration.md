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
uv run warhammer40k-export-preferences \
  --profile keyboard-heavy \
  --format yaml \
  --output ui-preferences.yaml
```

Available built-in profiles:

- `default`
- `dense-debug`
- `keyboard-heavy`
- `command-bench`

## Use A Profile

Launch with a specific JSON or YAML profile:

```bash
uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/default.yaml
uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/keyboard-heavy.yaml
uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/command-bench.yaml
```

If `--ui-prefs` is omitted, the app looks for the platform default preferences file:

```text
~/.config/warhammer40k-arcade-ui/ui-preferences.yaml
```

If that file is not present, the app uses the packaged built-in `default` profile. If the platform
default file is present but predates the current HUD composition system, startup stops with a
terminal error that names the incompatible file and tells you to move it out of the way or update it
manually. Render a fresh known-good default with:

```bash
warhammer40k-export-preferences --profile default --format yaml --output ~/.config/warhammer40k-arcade-ui/ui-preferences.yaml
```

When the debug inspector is visible, it displays the active UI preferences file name, such as
`default.yaml`, `keyboard-heavy.yaml`, or `built-in default` when no file was loaded.

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

## HUD Settings

The `hud` section controls local display defaults only. It cannot define legal actions, engine
requests, proposal kinds, validation behavior, or visibility rules.

Assignment review settings:

- `layout_preset`: `compass_ring` or `command_bench`.
- `composition_profile`: optional reference to a separate HUD composition YAML file. This file
  describes presentation-only widget trees for HUD zones and is kept separate from hotkeys,
  overlays, and other personal preferences. The reference may be:
  - a known built-in profile ID, such as `default-hud`;
  - a relative path resolved against the preferences file that names it, such as
    `hud/my-custom.yaml`;
  - a package-resource-relative path resolved against a packaged built-in preferences resource,
    such as `../hud/default-hud.yaml`;
  - an explicit absolute path.
- `zones`: known presentation-only HUD zone settings. Each zone supports:
  - `visible`: whether to show the zone socket;
  - `size_px`: preferred size in pixels;
  - `collapsed`: show the zone as a small socket for later expansion.
- `show_assignment_hud`: show or hide the request-scoped Assignment Review panel.
- `assignment_hud_mode`: `compact` or `detailed`.
- `show_assignment_warning_markers`: show color-independent warning markers for advisory hints and
  diagnostics.
- `action_summary_default`: `hidden`, `dim`, or `review` for the advisory battlefield summary
  overlay when the UI starts.
- `action_summary_max_labels`: maximum number of bright review labels drawn over the battlefield
  before visual labels are suppressed to reduce clutter.
- `show_chain_breadcrumbs`: show recent existing event-log lines as chain breadcrumbs in the
  Assignment Review panel.

Example:

```yaml
hud:
  layout_preset: compass_ring
  composition_profile: default-hud
  zones:
    top_ribbon:
      visible: true
      size_px: 84
      collapsed: false
    left_rail:
      visible: true
      size_px: 224
      collapsed: false
  show_phase: true
  show_active_player: true
  show_event_log: true
  show_config_diagnostics: true
  show_selected_model_panel: true
  show_selected_unit_panel: true
  show_assignment_hud: true
  assignment_hud_mode: detailed
  show_assignment_warning_markers: true
  action_summary_default: dim
  action_summary_max_labels: 6
  show_chain_breadcrumbs: true
  text_scale: 1.0
  high_contrast: false
```

## HUD Composition YAML

HUD composition files live separately from preference profiles. Production examples live in
[docs/hud](hud/); preview examples with placeholder data live in [docs/hud/examples](hud/examples/).

The composition dialect is schema-versioned and presentation-only. It supports known widget types,
known icon IDs, safe `data_ref` names, parent-relative layout hints, and component attributes. It
does not allow executable expressions, includes/templates, legal-action definitions, proposal
kinds, finite option IDs, request IDs, validation rules, or hidden-information visibility rules.

When a preferences file references a relative composition path, the path is resolved relative to the
source of the preferences file rather than the current working directory. This applies both to normal
filesystem preferences and to packaged built-in resources loaded from a wheel or zip-style Python
package.

Preview files may include `sample_data` so widgets can be reviewed without a game session:

```bash
uv run warhammer40k-hud-preview docs/hud/examples/unit-datasheet-preview.yaml
uv run warhammer40k-hud-preview docs/hud/examples/workbench-preview.yaml \
  --component movement_budget_ring \
  --headless \
  --artifact-dir /tmp/hud-preview
```

Headless preview writes a PNG and JSON metadata file for review automation.

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
- `add_entity_selection`
- `subtract_entity_selection`
- `toggle_entity_selection`
- `cycle_entity_layer`
- `select_current_entity_group`
- `toggle_debug_inspector`
- `toggle_action_summary`
- `review_action_summary`

`toggle_overlay` bindings must include an `overlay_id`.

The entity-selection commands are request-scoped selection commands. Phase 9 wires them into the
movement assignment UI while a movement draft is active. They still configure only local UI
behavior; they do not define legal movement, proposal kinds, or validation rules.

The action-summary commands are advisory presentation controls:

- `toggle_action_summary`: toggle the current action summary between hidden and the configured
  default visible mode.
- `review_action_summary`: toggle bright review mode for checking the current workspace before
  submission.

## Overlay IDs

Active overlay IDs:

- `debug_coordinates`
- `movement_budget`
- `movement_path_draft`
- `selected_model`
- `selected_unit`

Recognized planned overlay IDs are accepted and preserved, but emit inactive diagnostics until later
phases wire them to render, HUD, projection, or local-state data:

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
fields, unknown command IDs, unknown overlay IDs, unknown HUD layout presets, unknown HUD zone IDs,
invalid HUD zone sizes, duplicate hotkey bindings, invalid keys, invalid modifiers, and
recognized-but-inactive planned settings.

Unknown settings that a tool needs to preserve should live under `extensions` so the base UI can
round-trip them as JSON-safe values without treating them as first-party behavior.
