# Phase 27: Current Action View And Clickable HUD Buttons

Status: Proposed

## Purpose

Replace the crowded finite-decision workbench rows with one reusable, compact `CurrentActionView`
that can show the current player-facing action/request and render selectable options as first-class
clickable HUD buttons.

This phase should make the bottom workbench easier to read while creating a reusable clickable
button widget that later HUD work can use for Stratagems, dice choices, assignment rows, command
menus, setup flows, and other player-facing controls.

## Design Principle

The current action surface belongs to the GUI user's immediate workflow, not only to core finite
decisions. Many actions will be engine-driven `FiniteDecisionRequest` surfaces, but some may be
player-initiated GUI actions such as opening a Stratagem browser, toggling summaries, changing local
settings, or starting a supported advisory workflow.

Use `CurrentActionView` as the presentation model name. It may consume `FiniteDecisionUiState` when
the engine is asking a finite question, but it must not be strictly bound to finite decisions.

## Scope

In scope:

- a reusable clickable HUD button model and renderer;
- deterministic hit detection for HUD-rendered buttons;
- selected, active, inactive, disabled, hover, and focus visual states;
- button contents that can be text-only, icon-only, icon plus text, or text-as-icon;
- keyboard selection parity so `TAB` still updates the selected/highlighted button;
- a compact `CurrentActionView` that combines current action/request title, actor, summary, option
  buttons, and submit/decline affordance text;
- finite-option button rows for single-choice finite requests;
- preliminary data modeling for multi-select finite-like option groups where future engine surfaces
  allow selecting up to X options;
- removal of the separate Phase 26 `Current Action`, `Actor`, and `Option Details` widget trio from
  the default HUD composition once the combined panel replaces them.

Out of scope:

- local legality filtering;
- inventing option IDs or option groups not emitted by the engine;
- changing the core decision contract;
- generic placement, movement-family, shooting, melee, or Stratagem proposal editors;
- fully solving every future multi-select decision family before the core exposes those semantics.

## UX Model

The combined current-action panel should be one card or framed workbench section:

```text
Current Action: Movement
Actor: player-a    Request: select_movement_action
Movement action pending
[ Normal Move ] [ Advance ] [ Remain Stationary ]
ENTER submits selected option
```

Behavior:

- selected option button uses the selected/highlight color;
- unselected available buttons use a dull neutral/translucent visual;
- disabled buttons use the disabled visual and expose disabled reason where available;
- decline/pass/complete buttons use a warning/secondary treatment so their meaning is visible;
- `TAB` and any configured option-cycling command update the selected button;
- clicking a button selects that option without changing battlefield entity selection;
- confirm still submits the selected engine-provided option ID for the current request ID;
- optional future behavior may allow double-click or explicit submit button, but this phase should
  keep confirm submission behavior conservative unless a dedicated acceptance criterion is added.

## Reusable Clickable Button Requirements

The HUD button widget should be reusable across the board, not hard-coded to finite decisions.

Required model fields:

- stable widget/component ID;
- button ID;
- command ID or semantic action ID;
- optional engine option ID;
- label text;
- optional icon ID;
- optional text-as-icon content;
- tooltip/help text;
- state: `normal`, `hover`, `focus`, `selected`, `active`, `disabled`, `warning`, `invalid`;
- enabled/disabled flag and disabled reason;
- visual role/color role;
- selected/focused flag;
- payload metadata that is JSON-safe and diagnostic-only.

Required rendering features:

- rectangular/pill/square shape variants;
- configurable fill, border, text, opacity, padding, gap, and corner radius;
- stable minimum height/width;
- clipping or ellipsis for long text;
- text-as-icon rendering for compact tokens when no icon asset exists;
- optional icon placement left, right, both, or centered.

Required interaction features:

- collect rendered button bounds each frame;
- route HUD hit tests before battlefield hit tests;
- map a click to a typed HUD button action;
- prevent HUD clicks from selecting/moving battlefield entities;
- expose active/focus/hover state without mutating authoritative game state;
- trace HUD button events in forensic event traces.

## CurrentActionView Requirements

`CurrentActionView` should be a presentation adapter that may be built from:

- `FiniteDecisionUiState` and finite option view models;
- movement or assignment draft status;
- player-initiated GUI workflows such as opening a Stratagem tool or settings panel;
- future engine-driven setup/placement/shooting/melee workbench states.

Required fields:

- title, e.g. `Movement`, `Stratagem`, `Shooting`, `Deployment`, or `Current Action`;
- request summary, e.g. `select_movement_action` or a GUI workflow label;
- actor/current player summary when known;
- advisory status text;
- selected option/action ID when applicable;
- option/action button list;
- confirm/submit hint;
- cancel/back hint when applicable;
- source kind: `engine_finite`, `engine_parameterized`, `local_gui`, or `none`.

Finite decision adapter rules:

- preserve exact engine request ID and option IDs;
- do not invent or hide options;
- classify labels like decline/pass/complete only from engine-provided option IDs, labels, or
  payload fields;
- support future `max_selected`/multi-select semantics only when the engine payload exposes them;
- for current single-choice finite requests, selecting a new button replaces the highlighted option.

## Implementation Slices

1. **Clickable button model**
   - Add reusable HUD button view models and data bindings.
   - Define button states, shape controls, text/icon content modes, and diagnostic metadata.

2. **Button rendering and hit regions**
   - Render buttons through the HUD toolkit.
   - Store frame-local hit regions with component ID, button ID, state, and action metadata.
   - Add deterministic tests for generated primitives and hit-region geometry.

3. **HUD input routing**
   - Route mouse press through HUD hit testing before battlefield selection.
   - Dispatch typed local actions for finite-option selection.
   - Ensure clicks on HUD buttons do not alter selected battlefield unit/model state.

4. **CurrentActionView adapter**
   - Build a compact current-action presentation model from finite state, draft state, and local
     GUI workflow state.
   - Keep this model presentation-only and JSON-safe.

5. **Finite option button row**
   - Render finite options as clickable buttons.
   - Keep `TAB` highlight and clicked selection in sync.
   - Show selected, inactive, disabled, and warning/decline/pass/complete visuals.

6. **Retire Phase 26 split rows**
   - Remove the separate `Current Action`, `Actor`, and `Option Details` composition widgets from
     default HUD profiles.
   - Replace them with one `CurrentActionView`/current-action panel widget.
   - Keep runtime data compatibility only where needed for previews or transition tests.

7. **Trace and diagnostics**
   - Trace `ui.hud_button_hover`, `ui.hud_button_selected`, and `ui.hud_button_submitted` events.
   - Include component ID, button ID, command/action ID, request ID when applicable, and option ID
     when applicable.

## Acceptance Criteria

- The bottom workbench shows one combined current-action/request panel instead of three separate
  finite-decision rows.
- Finite options render as separate buttons that can be read without a clipped subtitle line.
- `TAB` updates the selected finite-option button highlight.
- Clicking a finite-option button updates the highlighted option without selecting/moving battlefield
  entities.
- Confirm submits the selected engine-provided option ID and current request ID.
- Disabled/decline/pass/complete options are visually distinct when the engine-provided data exposes
  that meaning.
- The reusable button widget is not coupled to finite decisions and can be used by other HUD
  surfaces.
- The UI does not invent option IDs, perform local legality filtering, or mutate authoritative game
  state.

## Automated Verification

Add or update tests for:

- button model validation and runtime data serialization;
- button primitive rendering for text-only, icon-only, icon+text, and text-as-icon modes;
- hit detection priority over battlefield selection;
- finite option click selection preserving request ID and battlefield selection;
- `TAB` highlight synchronization with button selected state;
- disabled/decline/pass/complete visual state mapping;
- current-action panel composition text and button primitives;
- forensic trace events for HUD button interaction.

Run the normal gates:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pyright
uv run pytest tests/
uv run pre-commit run --all-files
```

## Manual Validation Checklist

- Launch `uv run warhammer40k-arcade-ui --live-core-smoke --ui-prefs docs/preferences/default.yaml`.
- At a finite movement request, verify the bottom workbench shows one current-action panel.
- Verify available movement actions appear as individual buttons.
- Press `TAB` and confirm the highlighted button changes.
- Click a different option button and confirm battlefield selection does not change.
- Press `ENTER` and confirm the selected engine option submits.
- Verify decline/pass/complete options use a distinct visual treatment when present.

## Reviewer Notes

Review should focus on keeping interaction generic and presentation-only. The new clickable button
system should be reusable, but button clicks must still submit through the same engine decision path
and must not become a private gameplay command layer.
