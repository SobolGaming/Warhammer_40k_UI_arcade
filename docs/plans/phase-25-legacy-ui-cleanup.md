# Phase 25: Legacy UI Cleanup

Status: Proposed

## Purpose

Remove divergent and legacy UI paths that predate the current ergonomic HUD composition model. The
active interface should have one intentional player-facing written-feedback path:

1. engine/core projection data enters UI view models;
2. UI view models become ergonomic HUD runtime data;
3. HUD composition YAML places toolkit widgets into zones;
4. the composition renderer draws those widgets.

Direct screen writing should remain only for narrow overlays that are not HUD panels, such as the
world-space table, movement path previews, advisory action summaries, and context menus. Debug
evidence should come from the Review HUD zone, forensic event traces, crash bundles, and tests, not
from old standalone debug panels.

## Current Cleanup Candidates

These items should be audited and removed or narrowed during implementation.

- `render/hud_ergonomics.py`
  - Old direct primitive renderer for the ergonomic HUD.
  - Current production rendering uses `hud.toolkit_render.render_composition_profile(...)` with
    `hud.runtime_data.runtime_data_for_ergonomic_hud(...)`.
  - Tests that still import `build_ergonomic_hud_primitives` should be migrated to composition
    rendering or toolkit/runtime-data assertions.

- `hud/widgets.py`
  - Arcade GUI placeholder zone widgets from the early zone-layout phase.
  - It appears unreferenced by production code and should be removed unless a current preview or
    test path still needs it.

- Legacy debug inspector view models
  - `hud.view_models.DebugInspectorView`
  - `hud.view_models.build_debug_inspector(...)`
  - `hud.__init__` exports for those names
  - The Review HUD zone and forensic trace/crash tooling should replace this standalone panel.

- Legacy panel visibility state
  - `SelectionState.debug_inspector_visible`
  - `SelectionState.selected_unit_panel_visible`
  - `SelectionState.selected_model_panel_visible`
  - `SelectionState.show_selected_unit_panel()`
  - `SelectionState.show_selected_model_panel()`
  - These flags couple selection state to old panel display behavior. The modern composition should
    decide where selected-unit, selected-model, diagnostics, and assignment data appear.

- Legacy preference flags and commands
  - `selection.show_debug_inspector`
  - `hud.show_selected_unit_panel`
  - `hud.show_selected_model_panel`
  - `toggle_debug_inspector`, `show_selected_unit_panel`, and `show_selected_model_panel` command
    handlers if they no longer control active composition widgets.
  - Packaged and documented preference profiles should remove or replace those fields in a
    migration-safe way.

- Direct HUD primitive helper scope
  - `render.primitives.build_hud_primitives(...)` currently still owns context menu primitives,
    layout skeleton labels, and a direct mouse-coordinate debug text.
  - It should be renamed or narrowed to a screen-overlay helper whose allowed output is explicit:
    context menus and non-panel annotations only.
  - Mouse coordinates should move to the Review HUD zone or event trace when needed.

- Phase debug launch path
  - `WARHAMMER40K_ARCADE_UI_DEBUG_PHASE6`
  - `WARHAMMER40K_ARCADE_UI_DEBUG_PHASE7`
  - runtime imports from `debug_fixtures.py` in `app.py`
  - Keep deterministic fixtures available to tests only if still valuable, but remove old runtime
    launch modes that compete with `--live-core-smoke`, `--event-trace`, GUI driver tests, and HUD
    preview.

- Legacy tests that assert old panels
  - Tests should stop asserting direct legacy panel text.
  - Replacement coverage should assert runtime data, composition primitives, trace output, or
    explicit context-menu behavior.

## Explicitly Not Legacy

Do not remove these as part of this phase:

- `state.movement_draft` and `state.movement_submission`
  - Local movement drafts remain the current advisory input model for movement proposals.

- `hud.view_models.AssignmentHudPanelView` and related assignment group models
  - These feed the modern Assignments zone and future assignment/visual-summary systems.

- `hud.ergonomics.HudErgonomicsView`
  - This is the adapter between game/UI state and composition runtime data.

- `hud.runtime_data`
  - This is the intended bridge into configurable HUD composition YAML.

- `render.primitives.build_world_primitives(...)`
  - World-space battlefield, model, terrain, movement preview, and action-summary overlays are not
    HUD panels and remain valid render output.

- Context menu rendering
  - The menu is a transient command overlay. It may remain direct-rendered until a widget-backed menu
    exists.

- Fake clients and fixtures used by deterministic tests
  - Remove only stale runtime debug entrypoints, not useful test fixtures.

## Implementation Slices

1. **Inventory and static references**
   - Produce a removal checklist from `rg` output.
   - Confirm each candidate has no production dependency or identify the modern replacement path.
   - Add or update a test that fails if legacy direct HUD modules are reintroduced into production
     render flow.

2. **Remove unused direct render alternatives**
   - Delete `render/hud_ergonomics.py` if only tests reference it.
   - Migrate tests to `render_composition_profile(...)`, `runtime_data_for_ergonomic_hud(...)`, or
     toolkit unit assertions.
   - Delete `hud/widgets.py` if unused.

3. **Retire standalone debug panels**
   - Remove `DebugInspectorView` and `build_debug_inspector(...)`.
   - Remove exports and tests for the old inspector.
   - Ensure the Review zone still shows diagnostics, events, hotkeys, and any user-needed debug
     summary.

4. **Remove selection-owned panel visibility**
   - Remove selected-unit/model/debug panel visibility from `SelectionState`.
   - Keep selection state focused on selected entities, context menu state, active overlay IDs, and
     local interaction state.
   - Ensure selected-unit and selected-model data still render via the configured composition.

5. **Clean preferences and commands**
   - Remove obsolete preference schema fields from built-in YAML resources and documented examples.
   - Remove obsolete commands and hotkeys or migrate them to modern composition-visible behavior.
   - If removing fields breaks platform default preferences, provide a terminal-facing diagnostic
     with copyable recovery commands rather than silently falling back.

6. **Narrow direct screen overlay helpers**
   - Rename or split `build_hud_primitives(...)` so it does not sound like a second HUD renderer.
   - Keep context-menu primitives and any explicitly allowed transient overlay.
   - Move mouse-coordinate debug text to Review HUD data or event trace.

7. **Retire old runtime debug launch modes**
   - Remove Phase 6/7 debug environment aliases from runtime startup.
   - Keep equivalent test fixtures under `tests/` or test-only helpers if still useful.
   - Update README and tests to point developers to GUI driver, HUD preview, live core smoke, event
     trace, and crash bundles.

## Acceptance Criteria

- Production `ArcadeWarhammerWindow.on_draw()` has only one HUD-panel path:
  `HudErgonomicsView -> runtime_data_for_ergonomic_hud -> render_composition_profile`.
- No production module imports `render.hud_ergonomics` or `hud.widgets`.
- No player-facing text panel is rendered through legacy direct HUD primitives.
- Selection state no longer stores old panel visibility toggles.
- Built-in preference YAML files no longer expose obsolete panel toggles or commands.
- The current HUD composition still displays:
  - status chips;
  - selected unit/model summary when available;
  - current decision/option feedback;
  - assignment draft state;
  - dice tray state;
  - diagnostics/events/hotkeys in the Review zone.
- Context menus and world-space movement/action overlays still render.
- No UI-owned authoritative rule validation or mutation is introduced.

## Automated Verification

Run the normal quality gates for the implementation PR:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pyright
uv run pytest tests/
uv run pre-commit run --all-files
```

Add or update focused tests for:

- composition runtime data replacing old direct panel output;
- absence of production imports of removed legacy modules;
- preference schema/profile loading after obsolete fields are removed;
- selected-unit and assignment feedback still appearing through composition primitives;
- context menu and world-space movement preview surviving the cleanup.

## Manual Validation Checklist

- Launch `uv run warhammer40k-arcade-ui`.
- Launch `uv run warhammer40k-arcade-ui --live-core-smoke`.
- Select a unit and verify selected-unit/model information appears only in the configured HUD zone.
- Open the action menu and verify the context menu still appears.
- Start a movement draft and verify movement paths, ghost bases, assignment state, and advisory
  action-summary overlays still render.
- Trigger or simulate an invalid local submission and verify the Review zone shows the diagnostic.
- Run HUD preview examples and confirm no legacy panel shell appears outside configured zones.

## Reviewer Notes

Review should focus on accidental behavior loss. This phase is deletion-heavy, so the safest review
question is not whether old code was removed, but whether every removed display path has an
intentional modern replacement in composition/runtime data, event trace, crash reporting, or tests.
