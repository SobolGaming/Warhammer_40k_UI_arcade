Below is a phased plan assuming this becomes a **separate Arcade-based UI repository** that consumes `Warhammer_40k_AI` as an engine/core dependency, rather than merging UI code directly into the core repo. That matches the core repo’s invariant that UI/headless/network/replay/test drivers share the same decision path and that the engine alone mutates authoritative state. ([GitHub][1])

## Recommended project shape

```text
warhammer40k-arcade-ui/
  README.md
  architecture.md
  pyproject.toml
  uv.lock
  src/
    warhammer40k_arcade_ui/
      __init__.py
      app.py
      config.py
      logging_config.py
      main.py

      core_client/
        __init__.py
        local_session_client.py
        protocol.py
        ids.py

      render/
        __init__.py
        camera.py
        table_renderer.py
        unit_renderer.py
        overlay_renderer.py
        primitives.py

      input/
        __init__.py
        selection.py
        movement_path_tool.py
        commands.py

      preferences/
        __init__.py
        defaults.py
        diagnostics.py
        export_profile.py
        io.py
        registries.py
        schema.py

      hud/
        __init__.py
        decision_panel.py
        unit_panel.py
        radial_menu.py
        diagnostics_panel.py

      state/
        __init__.py
        ui_state.py
        selection_state.py
        movement_draft.py

  tests/
    unit/
    integration/
    snapshots/
    fixtures/

  docs/
    protocol-notes.md
    movement-ui-flow.md
    ui-configuration.md
```

Use `uv` as the project and lockfile manager. It is a good fit here because it handles project dependencies, lockfiles, Python versions, scripts, and package-tool execution in one workflow. ([Astral Docs][2]) Arcade is a reasonable UI base because it is a Python 2D game library with GUI/event primitives and camera support, which maps well to a tactical table view with pan, zoom, selectable units, overlays, and HUD widgets. ([Python Arcade][3])

---

# Phase 0 — Repository bootstrap and quality baseline

**Goal:** Create a runnable, locked, tested Python UI package before any game-specific behavior is added.

### Tasks

* [ ] Create new repository, for example `Warhammer_40k_Arcade_UI`.
* [ ] Add `pyproject.toml` using `uv`.
* [ ] Add runtime dependencies:

  * `arcade`
  * `pydantic` or `msgspec`
  * `orjson`
  * `typing-extensions`
  * `platformdirs`
* [ ] Add dev dependencies:

  * `pytest`
  * `pytest-cov`
  * `ruff`
  * `pyright`
  * `mypy`, optional but recommended if you want parity with the core repo’s gates
  * `pre-commit`
* [ ] Add basic package entry point:

```toml
[project.scripts]
warhammer40k-arcade-ui = "warhammer40k_arcade_ui.main:main"
```

* [ ] Add first CI-equivalent local command group through `uv` documentation in README:

```bash
uv lock
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

* [ ] Add pre-commit hooks for `ruff`, formatting, and basic file hygiene.
* [ ] Add strict typing policy:

  * `pyright` strict mode for `src/`.
  * Tests can be less strict initially, but no untyped public API in `src/`.

### Acceptance criteria

* [ ] `uv sync` creates a reproducible environment.
* [ ] `uv run warhammer40k-arcade-ui` opens a blank Arcade window.
* [ ] `uv run pytest` passes with at least one smoke test.
* [ ] `uv run ruff check .` passes.
* [ ] `uv run pyright` passes.
* [ ] README contains exact setup and run commands.
* [ ] No direct dependency from the engine/core back into this UI package.

### Phase closeout milestone

**Milestone 0: “Runnable Empty Client”**

The repository can be cloned, synced, tested, type-checked, and launched into a blank Arcade window.

---

# Phase 1 — Documentation foundation: README and architecture.md

**Goal:** Make the repo understandable before it grows.

## README.md plan

The README should include:

* [ ] Project purpose: “Arcade-based local/network-capable UI client for `Warhammer_40k_AI`.”
* [ ] Explicit repository references:

  * Current core repo: `https://github.com/SobolGaming/Warhammer_40k_AI`
  * Adapter contract: `https://github.com/SobolGaming/Warhammer_40k_AI/blob/main/docs/ADAPTER_DECISION_CONTRACT.md`
  * Legacy pygame-era reference repo: `https://github.com/SobolGaming/Warhammer40k_AI`
* [ ] Current scope:

  * Local Arcade UI.
  * Initial movement-only interaction.
  * Engine-authoritative validation.
  * No UI-owned mutation of authoritative game state.
* [ ] Non-goals for first milestones:

  * No full 3D asset loading.
  * No authoritative shooting/fight/charge UI yet.
  * No private rules path in the UI.
* [ ] Setup commands:

```bash
uv sync
uv run warhammer40k-arcade-ui
uv run pytest
uv run ruff check .
uv run pyright
```

* [ ] Development principles:

  * UI consumes `GameViewPayload`.
  * UI submits `FiniteOptionSubmission` / `ParameterizedSubmission`.
  * UI displays invalid diagnostics from the engine.
  * UI previews are advisory only.
  * Engine remains authoritative.

These principles directly follow the adapter contract: adapters render, choose, transmit, or generate submissions, but do not own validation, mutation, events, or replay records. ([GitHub][4])

## architecture.md plan

The initial `architecture.md` should be intentionally short and updated over time. Suggested sections:

```markdown
# Architecture

## 1. Design Intent
Arcade UI client for Warhammer_40k_AI.

## 2. Boundary with Core Engine
The UI does not mutate GameState. It consumes projections and submits decisions.

## 3. Runtime Modes
- Local in-process session
- Future network session
- Future replay inspection mode

## 4. Main Modules
- core_client
- render
- input
- hud
- state

## 5. Decision Flow
GameViewPayload -> render controls -> user input -> submission -> engine validation -> refreshed view/events.

## 6. Movement UI Flow
Finite movement action selection -> movement proposal request -> path drafting -> PathWitness payload -> submit -> accepted/invalid diagnostics.

## 7. Testing Strategy
Pure unit tests, UI-state tests, protocol shape tests, smoke launch tests, and integration tests against a minimal core fixture.

## 8. Known Deferred Work
Network transport, shooting HUD, charge HUD, line of sight, 3D renderer, replay inspector.
```

### Acceptance criteria

* [ ] README explains how this repo relates to both the new and legacy repositories.
* [ ] README includes a “first run” path that works from a clean clone.
* [ ] `architecture.md` explains the UI/core boundary clearly.
* [ ] `architecture.md` has a “last updated” or “decision log” section so it can evolve.
* [ ] Docs explicitly say client-side previews are not authoritative.

### Phase closeout milestone

**Milestone 1: “Documented Scaffold”**

A new contributor can understand what the UI is, what it is not, how to run it, and how it talks to the core engine.

---

# Phase 2 — Core client adapter layer

**Goal:** Isolate Arcade from the engine’s adapter/session contract.

The core repo’s adapter contract is centered on `DecisionRequest`, finite submissions, parameterized submissions, movement/placement proposal payloads, `GameViewPayload`, and viewer-scoped event deltas. ([GitHub][4]) Build your UI around a small internal client facade rather than letting render/input code call the engine directly.

### Tasks

* [ ] Create `core_client/protocol.py` with UI-facing typed structures:

  * `UiGameView`
  * `UiDecision`
  * `UiFiniteOption`
  * `UiMovementProposalRequest`
  * `UiInvalidDiagnostic`
* [ ] Create `core_client/local_session_client.py`.
* [ ] Implement a local/in-process client wrapper:

  * `start_game(...)`
  * `advance_until_decision_or_terminal()`
  * `get_view(viewer_player_id)`
  * `get_events_since(cursor, viewer_player_id)`
  * `submit_finite(request_id, selected_option_id)`
  * `submit_movement_payload(request_id, payload)`
* [ ] Preserve explicit `request_id` in all submission calls.
* [ ] Convert engine-facing payloads into simple UI view models.
* [ ] Add a fake/mock client for UI testing without launching a real game.

### Acceptance criteria

* [ ] UI modules do not import engine internals directly.
* [ ] All user choices flow through the client facade.
* [ ] All submissions include `request_id`.
* [ ] Stale or invalid responses can be represented in the UI state.
* [ ] Unit tests prove the client facade can represent:

  * no pending decision
  * finite decision
  * movement proposal request
  * invalid movement diagnostic
  * terminal state

### Phase closeout milestone

**Milestone 2: “Engine Boundary Stable”**

The UI has a narrow, testable boundary to the core engine and can later swap local in-process mode for WebSocket/network mode.

---

# Phase 3 — Arcade rendering foundation

**Goal:** Render a battlefield that can be panned, zoomed, and inspected without interaction complexity.

### Tasks

* [ ] Implement `ArcadeWarhammerWindow`.
* [ ] Add world-space camera:

  * pan
  * zoom
  * screen-to-world coordinate conversion
  * world-to-screen coordinate conversion
* [ ] Render table bounds.
* [ ] Render deployment zones as optional translucent overlays.
* [ ] Render objectives.
* [ ] Render terrain footprints as simple polygons/rectangles.
* [ ] Render units as placeholder tokens.
* [ ] Render model bases as circles or ellipses.
* [ ] Add basic HUD layer independent of world camera:

  * phase label
  * active player
  * pending decision summary
  * event log stub

### Acceptance criteria

* [ ] The app launches to a visible battlefield.
* [ ] Pan and zoom do not distort table coordinates.
* [ ] World coordinates are displayed under the mouse for debugging.
* [ ] Placeholder unit/model rendering works from fixture data.
* [ ] HUD remains fixed while the battlefield camera moves.
* [ ] Rendering code is testable where practical:

  * coordinate conversion tests
  * camera clamp/zoom tests
  * view-model-to-render-primitive tests

### Phase closeout milestone

**Milestone 3: “Inspectable Battlefield”**

A user can launch the UI, pan/zoom around the table, and visually inspect placeholder units, objectives, and terrain.

---

# Phase 4 — Shareable UI preferences framework

**Goal:** Add a hand-editable, shareable UI preferences framework before selection/HUD work so upcoming UI behavior can be encoded, exported, swapped, and experimented with through portable JSON or YAML profiles.

User configuration is allowed to control how the UI presents known information and maps local input to known UI commands. It must not create legal actions, finite option IDs, proposal kinds, rule validation, hidden-information visibility, or authoritative state changes.

Future-facing preferences may name known planned properties, but validation must distinguish between supported settings that are active in the current build, planned settings that are accepted and preserved but not yet applied, and unknown settings that produce typed diagnostics.

### Tasks

* [x] Add a `preferences` or `settings` module with versioned typed schemas:

  * `UiPreferences`
  * `OverlayPreferences`
  * `HotkeyBinding`
  * `SelectionBehaviorPreferences`
  * `HudPreferences`
  * `ExperimentalPreferenceFlags`
* [x] Define schema behavior for future-facing properties:

  * preserve recognized-but-unimplemented settings through load/export round trips;
  * mark them as inactive through diagnostics rather than dropping them;
  * reject unknown top-level keys unless they are under a clearly named experimental/extension section.
* [x] Support loading preferences from:

  * an explicit config path, planned for a future CLI flag;
  * a platform default path via `platformdirs`;
  * built-in defaults when no user file exists.
* [x] Support hand-editable JSON and YAML files:

  * keep generated examples portable and free of machine-specific absolute paths;
  * add a YAML parser dependency only when this phase is implemented;
  * include `schema_version` in every persisted profile.
* [x] Support exporting profiles as deterministic JSON and YAML with stable field order.
* [x] Define stable UI command and overlay registries for local-only presentation commands.
* [x] Add selection-triggered overlay preferences:

  * overlays enabled when a model is selected with the default mouse button;
  * overlays enabled when a unit is selected;
  * overlays enabled while a movement draft is active.
* [x] Add configurable hotkeys for toggling known overlays, selected model information, selected unit information, context menus, measure mode, confirm, cancel, and cycling.
* [x] Add typed config diagnostics for unsupported schema versions, unknown command IDs, unknown overlay IDs, duplicate hotkeys, invalid key syntax, inactive planned settings, and settings that reference unavailable features.
* [x] Add example profiles for defaults, dense/debug workflows, and keyboard-heavy workflows.
* [x] Add a small command-line or callable export path so users can generate a starter profile without copying internal defaults by hand.
* [x] Document the preference file format, supported IDs, planned-but-inactive IDs, and extension policy.
* [x] Establish typed registries for render, input, HUD, and local UI state boundaries so later phases consume the framework instead of ad hoc string checks.

### Acceptance criteria

* [x] JSON and YAML preference files can be loaded through the same typed schema.
* [x] Built-in defaults can be exported or documented as a complete hand-editable profile.
* [x] Exported profiles are portable, deterministic, schema-versioned, and easy to diff.
* [x] Recognized upcoming properties can be encoded, round-tripped, and diagnosed as inactive until the implementing phase enables them.
* [x] Unknown commands, unknown overlays, duplicate hotkeys, and invalid syntax produce visible typed config diagnostics instead of silent fallback behavior.
* [x] Default selection overlays can be configured for model selection, unit selection, and movement drafting.
* [x] Hotkeys can toggle known overlays and selected model/unit information panels.
* [x] Config files cannot create finite options, proposal kinds, engine decisions, or validation behavior.
* [x] Config-driven overlays remain viewer-scoped and cannot expose hidden opponent information.
* [x] Tests cover schema loading, JSON/YAML parsing, default-profile generation, hotkey conflict detection, export determinism, command/overlay ID validation, future-facing inactive properties, and selection-triggered overlay activation.

### Phase closeout milestone

**Milestone 4: “Shareable Preferences Framework”**

Users can hand-edit and pass around a portable UI preferences file that controls known overlays, selected-model/unit information affordances, HUD defaults, hotkeys, and planned UI behavior settings while preserving the engine-authoritative decision boundary.

Implemented by `warhammer40k_arcade_ui.preferences`, documented in `docs/ui-configuration.md`, and
covered by `tests/test_preferences.py`. Later phases should consume these typed registries rather
than introducing new local configuration shapes.

---

# Phase 5 — Selection and unit information HUD

**Goal:** Select a unit/model and show useful information without submitting decisions yet.

This phase should consume the Phase 4 preferences framework for default selection overlays, selected-model/unit information panel defaults, debug inspector defaults, and configured local selection hotkeys.

This phase does not change the core adapter decision contract. It displays current
engine-provided finite request/options only and does not submit options, invent options, invent
proposal kinds, or locally validate game rules.

### Tasks

* [x] Implement click selection:

  * click model base
  * select owning unit
  * highlight selected unit/model through Phase 4 overlay IDs activated by this phase
* [x] Add selection cycling for overlapping bases.
* [x] Add `SelectionState`.
* [x] Add selected-unit panel:

  * unit name/id
  * model count
  * current position summary
  * available finite options, if pending decision targets that unit
* [x] Add radial/context menu prototype:

  * appears near selected unit or cursor
  * shows available actions from current pending finite request
  * disabled actions display reason if provided
  * does not submit actions until the finite decision submission phase
* [x] Add debug inspector toggle:

  * raw request id
  * selected unit id
  * proposal kind
  * cursor position
  * event cursor
* [x] Apply relevant Phase 4 preferences:

  * default overlays when a model is selected;
  * default overlays when a unit is selected;
  * selected-model and selected-unit information panel defaults;
  * selection cycling and debug inspector hotkeys.
  * ignore recognized-but-inactive future-facing preference fields.

### Acceptance criteria

* [x] Clicking a model selects its unit.
* [x] Selected unit is visually distinguishable.
* [x] Unit panel updates when selection changes.
* [x] Radial/context menu never invents options; it only displays engine-provided options.
* [x] Tests verify hit detection and selection priority.
* [x] Tests verify menu options are derived from pending decision data, not hard-coded rule assumptions.
* [x] Tests verify selection behavior consumes typed preferences and ignores inactive future-facing preference fields.

### Phase closeout milestone

**Milestone 5: “Selectable Tactical View”**

A user can select a unit, inspect it, and see context-sensitive options provided by the engine.

Implemented by `warhammer40k_arcade_ui.state.selection`,
`warhammer40k_arcade_ui.input.commands`, and `warhammer40k_arcade_ui.hud.view_models`, with render
primitive/window wiring for selected overlays, unit panel, context menu, and debug inspector.
Context menu actions remain display-only until the finite decision submission phase.

---

# Phase 6 — Finite decision submission

**Goal:** Let the user choose a movement action such as Normal Move through the authoritative decision contract.

The adapter contract’s finite-decision example explicitly models selecting a finite option such as `normal_move`, and says adapters must select one of the pending request’s option IDs rather than inventing option IDs. ([GitHub][4])

### Tasks

* [ ] Implement finite option buttons in the HUD.
* [ ] Implement radial/context menu finite option selection.
* [ ] On selection:

  * create a UI result id
  * submit selected option id with current request id
  * refresh status/view/events
* [ ] Display success, invalid, stale, or terminal status.
* [ ] Add event log panel from viewer-scoped event deltas.
* [ ] Add keyboard shortcuts:

  * Escape cancels local UI selection/menu state
  * Enter confirms highlighted finite option
  * Tab cycles selectable units/options

### Acceptance criteria

* [ ] User can select a finite option from the UI.
* [ ] Submission includes the current request id.
* [ ] UI refreshes after accepted submission.
* [ ] Stale/invalid submission response is visible and does not silently disappear.
* [ ] Tests verify exact submitted option id and request id.
* [ ] Tests verify UI cannot submit when no pending request exists.
* [ ] Tests verify UI cannot submit a non-existent option id.

### Phase closeout milestone

**Milestone 6: “Authoritative Finite Decision UI”**

The UI can answer engine-provided finite decisions correctly and visibly handles invalid/stale outcomes.

---

# Phase 7 — Movement path drafting UI

**Goal:** Let the user create a visible movement path before submitting it.

This is the first major Warhammer-specific interaction. The core repo’s README treats `PathWitness` as mandatory for movement/charge/pile-in/consolidate/disembark/reserves/reactive movement unless a rule explicitly models teleport/setup placement. ([GitHub][1]) The adapter contract also describes normal movement as a parameterized proposal containing model paths and poses. ([GitHub][4])

Contract refresh, 2026-06-04: movement drafting activates only for
`decision_type: "submit_movement_proposal"`. The draft and payload builder must preserve the
engine-issued `movement_phase_action`, `movement_mode`, and Fall Back `fall_back_mode` context
exactly. Placement, shooting declaration, Stratagem target-binding, and other parameterized
requests remain visible as proposal-required states until their own tools exist.

### Tasks

* [ ] Add `MovementDraft` state:

  * selected unit id
  * proposal request id
  * proposal kind
  * movement phase action
  * engine-issued movement mode, if present
  * engine-issued Fall Back mode, if present
  * source decision request/result ids
  * per-model path points
  * current cursor preview point
  * local-only validity hints
* [ ] Activate drafting only when the current pending proposal is a movement proposal for the
  selected unit.
* [ ] Implement movement tool modes:

  * unit-level simple path mode
  * model-level edit mode, deferred if too large
* [ ] Add path interactions:

  * click to add waypoint
  * drag endpoint
  * right-click/remove last waypoint
  * Escape cancel draft
  * Enter marks the draft ready and builds the payload preview; engine submission remains Phase 8
* [ ] Render:

  * movement path line
  * waypoints
  * final ghost base positions
  * movement budget ring/overlay
  * warning color/style for advisory local violations
* [ ] Add measurement overlay:

  * segment length
  * total path length
  * remaining budget estimate
* [ ] Keep local validation advisory:

  * endpoint distance estimate
  * table bounds estimate
  * obvious self-overlap indicator
  * but engine remains authority
* [ ] Add a payload builder that emits the core movement payload shape and copies
  `movement_phase_action`, `movement_mode`, and `fall_back_mode` from the pending proposal request.
* [ ] Display a clear unsupported-tool state for non-movement parameterized requests.

### Acceptance criteria

* [ ] Movement proposal request activates movement drafting mode.
* [ ] Non-movement parameterized requests do not activate movement drafting mode.
* [ ] User can create, edit, and cancel a path.
* [ ] Draft path renders in world space and survives camera pan/zoom.
* [ ] UI can build a JSON-safe movement payload shape.
* [ ] Payload includes proposal request id, proposal kind, unit id, movement phase action, witness,
  optional model movements, and required mode context.
* [ ] Client-side warnings are clearly labeled as preview/advisory.
* [ ] Tests verify movement draft state transitions.
* [ ] Tests verify generated payload shape from a simple two-point path.
* [ ] Tests verify Fall Back payload generation preserves the pending `fall_back_mode`.
* [ ] Tests verify canceling draft does not submit anything.

### Phase closeout milestone

**Milestone 7: “Movement Path Planner”**

A user can select a unit, choose Normal Move, draft a movement path, preview the result, and prepare an engine-compatible movement proposal payload.

---

# Phase 8 — Movement proposal submission and diagnostics

**Goal:** Submit the movement path to the engine and display authoritative result/diagnostics.

The adapter contract distinguishes malformed/stale/context-drift submissions from rule-invalid but well-formed proposals. Malformed or stale proposals leave the pending request unresolved; rule-invalid but well-formed proposals can be recorded and followed by a fresh proposal request with diagnostics. ([GitHub][4])

Contract refresh, 2026-06-04: Phase 8 remains movement-only. It must submit through the
parameterized path with the current explicit `request_id`, surface movement mode and Fall Back mode
drift diagnostics, and avoid applying movement retry behavior to placement, shooting, Stratagem, or
other parameterized proposal families.

### Tasks

* [ ] Implement `submit_movement_payload`.
* [ ] Keep `request_id` explicit in the UI submission method and reject stale request drift before
  constructing an engine-facing result.
* [ ] Submit through the parameterized path only; never answer `submit_parameterized_payload` as an
  ordinary finite option.
* [ ] Add result handling:

  * accepted
  * invalid shape
  * stale request
  * movement mode or Fall Back mode drift
  * rule-invalid movement
  * unsupported proposal kind
  * unsupported non-movement parameterized request
* [ ] Add diagnostics panel:

  * violation code
  * message
  * affected field/model/path segment, if present
* [ ] On accepted movement:

  * clear draft
  * refresh battlefield projection
  * append events
* [ ] On invalid movement:

  * retain or reconstruct draft if still relevant
  * show diagnostic
  * update to new request id and proposal context if engine emits a fresh movement proposal request
* [ ] Add “retry from last path” affordance if safe.
* [ ] Add snapshot tests for representative diagnostic payloads.

### Acceptance criteria

* [ ] Accepted movement visibly updates model positions after view refresh.
* [ ] Invalid movement displays authoritative diagnostics.
* [ ] Stale request errors are obvious to the user.
* [ ] Movement-mode and Fall Back mode drift diagnostics are obvious to the user.
* [ ] UI never mutates authoritative model positions before engine acceptance.
* [ ] UI rejects or displays unsupported non-movement parameterized requests without trying to
  submit them through the movement payload path.
* [ ] Tests verify invalid diagnostics are surfaced.
* [ ] Tests verify accepted movement clears draft state.
* [ ] Tests verify rejected movement does not locally commit final positions.
* [ ] Tests verify retry-from-last-path is offered only when the fresh proposal request still
  targets the same unit, proposal kind, movement action, movement mode, and Fall Back mode context.
* [ ] Tests verify stale request ID rejection happens at the UI boundary before engine mutation.

### Phase closeout milestone

**Milestone 8: “End-to-End Movement UI”**

A user can complete the full flow: select unit → select movement action → draw path → submit movement proposal → see accepted state or authoritative diagnostics.

---

# Phase 9 — HUD ergonomics pass

**Goal:** Improve decision-making speed and reduce cognitive load.

This phase should consume the Phase 4 preferences framework for overlay defaults, HUD defaults, and hotkeys instead of hard-coding user workflow assumptions into render, input, or HUD modules.

### Tasks

* [ ] Add selected-unit radial menu polish:

  * movement actions
  * inspect
  * measure
  * cancel
* [ ] Add range overlays using configured defaults where available:

  * movement budget
  * advance preview band, if data exists
  * weapon range rings as non-authoritative info overlays
* [ ] Add tooltip system:

  * action descriptions
  * invalid diagnostic explanation
  * model/unit id debug mode
* [ ] Add event log filtering:

  * current player
  * current phase
  * invalid diagnostics
* [ ] Add keyboard-first workflow:

  * select next unit
  * open action menu
  * confirm action
  * submit/cancel draft
  * honor configured hotkeys for known commands and overlays
* [ ] Add accessibility basics:

  * scalable HUD text
  * color-independent warning icons
  * high-contrast toggle
* [ ] Add preference-aware HUD affordances:

  * apply configured selected-model and selected-unit panels;
  * apply configured default overlay sets;
  * surface config diagnostics in a non-authoritative diagnostics view.

### Acceptance criteria

* [ ] A movement can be completed with mostly keyboard input.
* [ ] A movement can be completed with mostly mouse input.
* [ ] HUD labels distinguish authoritative facts from preview estimates.
* [ ] Radial menu is not required for functionality; there is also a panel/button path.
* [ ] Configured overlay defaults and hotkeys route through stable command/overlay registries.
* [ ] Tests cover HUD view-model generation for selected unit and pending request.

### Phase closeout milestone

**Milestone 9: “Usable Movement Client”**

The UI is no longer only a technical prototype; it is comfortable enough for repeated manual movement-phase testing.

---

# Phase 10 — Packaging, CI, and regression hardening

**Goal:** Make the UI reliable enough to use during engine development.

### Tasks

* [ ] Add GitHub Actions or equivalent CI:

  * `uv sync --locked`
  * `ruff check`
  * `ruff format --check`
  * `pyright`
  * `pytest`
* [ ] Add coverage threshold for non-rendering logic.
* [ ] Add headless-safe smoke test mode where possible.
* [ ] Add golden fixtures:

  * finite movement option request
  * movement proposal request
  * Fall Back movement proposal request with `fall_back_mode`
  * accepted movement response
  * invalid movement response
  * unsupported non-movement parameterized request
  * default UI preferences profile
  * invalid UI preferences profile
* [ ] Add “no direct engine mutation” static check:

  * prohibit imports or calls into known mutable engine state APIs outside `core_client`
  * enforce via custom script if needed
* [ ] Add changelog.
* [ ] Add architecture decision records under `docs/adr/`.

### Acceptance criteria

* [ ] CI passes on clean checkout.
* [ ] All fixtures are deterministic and JSON-safe.
* [ ] Preference fixtures are deterministic, portable, and schema-versioned.
* [ ] Pull requests fail if pyright, ruff, or tests fail.
* [ ] A new developer can run the UI from README without hidden steps.
* [ ] `architecture.md` reflects actual module structure.

### Phase closeout milestone

**Milestone 10: “Development-Ready UI Repo”**

The UI repo is stable enough to use as a companion project while the core engine continues evolving.

---

## Suggested first cut of `pyproject.toml`

This is intentionally a starting point, not a final lockfile.

```toml
[project]
name = "warhammer40k-arcade-ui"
version = "0.1.0"
description = "Arcade-based UI client for SobolGaming Warhammer_40k_AI"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
  "arcade",
  "orjson",
  "pydantic>=2",
  "typing-extensions",
  "platformdirs",
]

[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "ruff",
  "pyright",
  "mypy",
  "pre-commit",
]

[project.scripts]
warhammer40k-arcade-ui = "warhammer40k_arcade_ui.main:main"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
  "E",
  "F",
  "I",
  "B",
  "UP",
  "SIM",
  "PL",
  "RUF",
]
ignore = []

[tool.pyright]
typeCheckingMode = "strict"
pythonVersion = "3.12"
include = ["src", "tests"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
  "--strict-markers",
  "--strict-config",
  "-ra",
]

[tool.coverage.run]
branch = true
source = ["warhammer40k_arcade_ui"]

[tool.coverage.report]
show_missing = true
skip_covered = true
```

I would choose your Python version based on dependency compatibility. The core repo currently documents a Python 3.14-oriented workflow, but a UI repo may be more practical on 3.12/3.13 until all UI dependencies and developer tooling are comfortable there. The UI/core boundary should make that version difference acceptable as long as the transport/protocol payloads remain JSON-safe and deterministic.

---

## Testing strategy by layer

| Layer         | What to test                                           | Example acceptance test                                                           |
| ------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------- |
| `core_client` | Contract translation, request IDs, invalid diagnostics | Given a pending movement request, generated submission includes exact request id. |
| `state`       | Selection, draft path, cancel/submit transitions       | Escape clears local draft but does not call submit.                               |
| `input`       | Hit testing, waypoint editing, command mapping         | Clicking overlapping bases cycles candidates deterministically.                   |
| `preferences` | Schema loading, hotkey conflicts, overlay/command IDs  | Unknown overlay IDs produce typed config diagnostics, not silent fallback.        |
| `render`      | Coordinate transforms, primitive generation            | World-to-screen-to-world round trip stays within tolerance.                       |
| `hud`         | View-model generation                                  | Finite options shown are exactly pending engine options.                          |
| integration   | End-to-end finite + movement flow                      | Select Normal Move, submit path, refresh view, clear draft.                       |
| static QA     | No private mutation path                               | Only `core_client` may import engine adapter/session modules.                     |

---

## Practical ordering for the very first sprint

For the first sprint, I would keep scope very tight:

1. Bootstrap repo with `uv`, `ruff`, `pyright`, `pytest`.
2. Launch blank Arcade window.
3. Render a fake 60" x 44" table with placeholder objectives.
4. Render two fake units from fixture JSON.
5. Add pan/zoom and click selection.
6. Add unit info panel.
7. Add fake pending decision panel with “Normal Move”.
8. Add movement path drafting against fake data.
9. Only then connect the same UI flow to a real `LocalGameSession` wrapper.

That gives you fast feedback and prevents early coupling to half-changing core details.

---

## Most important architectural rule

Do **not** let Arcade objects become game objects.

Keep this split:

```text
Engine/core state:
  authoritative, validated, replay-facing

UI client view models:
  read-only projection of current game state

Arcade render/input objects:
  visual and interactive only

MovementDraft:
  local proposed input, not committed game state
```

That mirrors the core contract: adapters may render, collect input, serialize submissions, show previews, and display diagnostics, but they must not mutate `GameState`, battlefield state, model poses, mission state, objective state, or event logs directly. ([GitHub][4])

[1]: https://raw.githubusercontent.com/SobolGaming/Warhammer_40k_AI/main/README.md "raw.githubusercontent.com"
[2]: https://docs.astral.sh/uv/ "uv"
[3]: https://api.arcade.academy/en/latest/ "The Python Arcade Library — Python Arcade 4.0.0.dev5"
[4]: https://raw.githubusercontent.com/SobolGaming/Warhammer_40k_AI/main/docs/ADAPTER_DECISION_CONTRACT.md "raw.githubusercontent.com"
