# warhammer40k-arcade-ui

Arcade-based local and future network-capable UI client for the
[`Warhammer_40k_AI`](https://github.com/SobolGaming/Warhammer_40k_AI) core engine.

This repository is a companion client, not a second rules engine. It renders engine-owned
projections, collects user intent, submits choices through the shared adapter decision contract, and
displays authoritative results or diagnostics returned by the core engine.

## Start here

Target Python version: **3.14.5**.

From a clean clone of this repository:

```bash
uv python install 3.14.5
uv lock
uv sync
uv run warhammer40k-arcade-ui
uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/keyboard-heavy.yaml
uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/command-bench.yaml
uv run warhammer40k-arcade-ui --live-core-smoke --ui-prefs docs/preferences/default.yaml
uv run warhammer40k-arcade-ui --event-trace summary --event-trace-file /tmp/ui-trace.jsonl
uv run warhammer40k-arcade-ui --crash-report-dir /tmp/ui-crashes
uv run warhammer40k-hud-preview default-hud
uv run warhammer40k-hud-preview docs/hud/examples/workbench-preview.yaml
uv run pytest
```

While movement drafting, press `v` to show/hide the advisory action summary overlay and `shift+v`
to switch into the brighter review summary. These overlays visualize local workspace intent only;
the core engine still owns validation and state mutation.

## Installation modes

The UI is still a companion package for the core engine. Until the core package is published through
a normal package index, package-style installs should install the core engine from Git first in the
same environment.

### Development checkout

Use this when changing code in this repository. The package dependency resolves from the core Git
repository, not a local editable path. The sibling core checkout is still used by mypy and pyright
until the core package publishes a `py.typed` marker.

```bash
git clone https://github.com/SobolGaming/Warhammer_40k_AI.git
git clone https://github.com/SobolGaming/Warhammer_40k_UI_arcade.git
cd Warhammer_40k_UI_arcade
uv python install 3.14.5
uv sync --locked --all-groups
uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/default.yaml
```

### Git install

Use this as an in-between path for trying a branch without a local source checkout:

```bash
uv venv --python 3.14.5 .venv-warhammer-ui
source .venv-warhammer-ui/bin/activate
uv pip install git+https://github.com/SobolGaming/Warhammer_40k_AI
uv pip install git+https://github.com/SobolGaming/Warhammer_40k_UI_arcade@main
warhammer40k-arcade-ui
```

To test an open UI branch, replace `@main` with the branch name, for example:

```bash
uv pip install git+https://github.com/SobolGaming/Warhammer_40k_UI_arcade@codex/phase21-packaging-ci-regression
```

### Built package artifact

Use this to install a wheel or source distribution produced by `uv build`:

```bash
uv build
uv venv --python 3.14.5 .venv-warhammer-ui-package
source .venv-warhammer-ui-package/bin/activate
uv pip install git+https://github.com/SobolGaming/Warhammer_40k_AI
uv pip install dist/warhammer40k_arcade_ui-0.1.0-py3-none-any.whl
warhammer40k-arcade-ui
```

The source distribution can be installed the same way:

```bash
uv pip install dist/warhammer40k_arcade_ui-0.1.0.tar.gz
```

## Local quality gates

Run these before opening a pull request:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run mypy src tests
uv run python scripts/check_import_boundaries.py
uv run pytest
uv run coverage run -m pytest
uv run coverage report
uv run pre-commit run --all-files
uv build
```

## Headless render tests

The GUI event and render-evidence tests run Arcade in headless mode through pytest. On Linux, the
headless framebuffer path requires EGL/OpenGL runtime libraries. The GitHub Actions test job installs
`libegl1` and `libgl1-mesa-dri`; local Linux machines need equivalent packages available.

Render evidence helpers save PNG and JSON artifact bundles only when a semantic visual check fails,
unless a test explicitly requests a success artifact. Set `WARHAMMER40K_ARCADE_UI_RENDER_ARTIFACT_DIR`
to override the default local artifact directory `.test-artifacts/render`.

## HUD widget preview

HUD composition YAML files can be previewed without starting a game session:

```bash
uv run warhammer40k-hud-preview docs/hud/examples/unit-datasheet-preview.yaml
uv run warhammer40k-hud-preview docs/hud/examples/workbench-preview.yaml --component movement_budget_ring
uv run warhammer40k-hud-preview docs/hud/examples/overflow-stress-preview.yaml --headless --artifact-dir /tmp/hud-stress
uv run warhammer40k-hud-preview docs/hud/examples/workbench-preview.yaml --headless --artifact-dir /tmp/hud-preview
```

Runtime defaults are packaged under `warhammer40k_arcade_ui.resources`, so installed Git/wheel
launches can run without depending on top-level `docs/`. The documented `docs/preferences` and
`docs/hud` files remain editable examples. HUD composition can be loaded by built-in profile name
such as `default-hud`, by a path relative to the preferences YAML file that references it, or by an
explicit YAML path. Preview examples under `docs/hud/examples/` use the same YAML dialect plus
placeholder `sample_data`.

## Forensic event traces

Enable a structured JSON Lines trace when a UI/core interaction needs bug-report evidence:

```bash
EVENT_TRACE=summary uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/default.yaml
EVENT_TRACE=payload EVENT_TRACE_FILE=/tmp/ui-trace.jsonl uv run warhammer40k-arcade-ui --live-core-smoke --ui-prefs docs/preferences/default.yaml
uv run warhammer40k-arcade-ui --event-trace payload --event-trace-file /tmp/ui-trace.jsonl
```

Trace levels:

- `off`: no file is created.
- `summary`: UI inputs, command dispatch, status transitions, request/result IDs, and movement
  draft state summaries.
- `payload`: summary trace plus JSON-safe UI/core payloads exchanged through the `core_client`
  facade.
- `render`: payload trace plus high-level frame/camera markers; it does not store raw pixels.

If no file is specified, trace files are written under
`~/.local/state/warhammer40k-arcade-ui/event-traces/`. Set `EVENT_TRACE_DIR` to choose another
directory, or `EVENT_TRACE_FILE` / `--event-trace-file` for an exact file. Files rotate when they
reach `EVENT_TRACE_MAX_BYTES` bytes, defaulting to 5 MB.

Trace rows are viewer-scoped and redact token-like fields such as `github_token`, `access_token`,
`authorization`, `password`, and `api_key`. Attach the JSONL file to bug reports alongside the exact
launch command and any render evidence artifacts.

## Crash diagnostic bundles

Fatal UI, parser, projection, or game-engine client errors write a compact crash bundle before the
window exits. By default, bundles are written under
`~/.local/state/warhammer40k-arcade-ui/crash-bundles/`. Use either runtime option to choose another
directory:

```bash
WARHAMMER40K_ARCADE_UI_CRASH_REPORT_DIR=/tmp/ui-crashes uv run warhammer40k-arcade-ui
uv run warhammer40k-arcade-ui --crash-report-dir /tmp/ui-crashes
```

Each bundle contains `crash-report.json` with the stack trace, UI version/commit metadata when
available, runtime mode, preferences source, active request/status context, recent forensic trace
tail when tracing is enabled, and references to recent render evidence artifacts. When event tracing
is enabled, the current trace file is copied into the same bundle as `event-trace.jsonl`, so the
crash report and trace evidence are colocated. Token-like launch arguments are redacted. Attach the
bundle and the launch command to issue reports.

## Purpose

The core engine is a strict bottom-up reconstruction of the Warhammer 40,000 rules engine. This UI
exists to drive that engine with an Arcade tactical table, while preserving the core invariant that
UI, headless, network, replay, and test drivers all use the same decision and command path.

Repository relationships:

- This repository owns the Arcade UI, local UI state, rendering, HUD, and user-input workflows.
- [`Warhammer_40k_AI`](https://github.com/SobolGaming/Warhammer_40k_AI) owns authoritative rules,
  validation, mutation, projections, events, replay-facing records, and adapter/session contracts.
- [`Warhammer40k_AI`](https://github.com/SobolGaming/Warhammer40k_AI) is the legacy pygame-era
  reference repository. Treat it as a reference for concepts and known bug classes, not as code to
  copy wholesale.

The UI is initially scoped to:

- local Arcade rendering;
- blank runnable client scaffolding;
- initial movement-only interaction as the first rules-facing vertical slice;
- engine-authoritative validation for all accepted state changes;
- Phase 4 hand-editable JSON/YAML UI preferences for shareable overlay, HUD, hotkey, and planned
  local behavior settings;
- a future network client mode behind the same UI-facing client facade.

Early milestone non-goals:

- no full 3D asset loading;
- no authoritative shooting, charge, fight, or damage UI yet;
- no private rules path in the UI;
- no UI-owned mutation of authoritative game state;
- no hidden validation fallback when the engine returns an invalid or unsupported result.

## References

- Core engine repository: <https://github.com/SobolGaming/Warhammer_40k_AI>
- Core adapter decision contract:
  <https://github.com/SobolGaming/Warhammer_40k_AI/blob/main/docs/ADAPTER_DECISION_CONTRACT.md>
- Core architecture roadmap:
  <https://github.com/SobolGaming/Warhammer_40k_AI/blob/main/ARCHITECTURE_V2.md>
- Legacy pygame-era reference repository: <https://github.com/SobolGaming/Warhammer40k_AI>
- UI architecture: [architecture.md](architecture.md)
- UI phase plans: [docs/plans/README.md](docs/plans/README.md)

## Non-negotiable UI invariants

These rules are copied forward from the core project's architecture where they apply to the UI:

1. Engine alone mutates authoritative game state.
2. No player choice occurs outside `DecisionRequest` / `DecisionResult`.
3. UI, headless, network, replay, and tests use the same engine decision path.
4. Movement, charge, pile-in, consolidate, disembark, reserves, and reactive movement require
   `PathWitness` or an explicit typed invalid result.
5. Endpoint-only movement validation is invalid unless a rule explicitly models teleport/setup
   placement.
6. All request IDs, option IDs, entity IDs, event IDs, and replay-facing payloads must be
   deterministic and serializable.
7. Client-side previews are advisory only and must be labeled as such.

## Current repository layout

```text
warhammer40k-arcade-ui/
  AGENTS.md
  README.md
  architecture.md
  pyproject.toml
  uv.lock
  src/
    warhammer40k_arcade_ui/
      __init__.py
      app.py
      config.py
      debug_fixtures.py
      core_client/
        __init__.py
        fake_client.py
        local_session_client.py
        protocol.py
      diagnostics/
        __init__.py
        crash_report.py
        forensic_trace.py
      hud/
        __init__.py
        layouts.py
        view_models.py
        widgets.py
      input/
        __init__.py
        commands.py
      logging_config.py
      main.py
      render/
        __init__.py
        arcade_window.py
        camera.py
        default_fixture.py
        primitives.py
        view_models.py
      preferences/
        __init__.py
        defaults.py
        diagnostics.py
        export_profile.py
        io.py
        registries.py
        schema.py
      state/
        __init__.py
        entity_selection.py
        finite_decision.py
        movement_draft.py
        movement_submission.py
        selection.py
  tests/
    fixtures/
      phase03_battlefield_view.json
    test_core_client_local_session.py
    test_core_client_protocol.py
    test_entity_selection_state.py
    test_config.py
    test_entrypoint.py
    test_finite_decision_state.py
    test_hud_selection.py
    test_movement_draft.py
    test_preferences.py
    test_render_camera.py
    test_render_primitives.py
    test_selection_state.py
  docs/
    README.md
    ui-configuration.md
    preferences/
      default.yaml
      dense-debug.yaml
      keyboard-heavy.yaml
    plans/
      README.md
      phase-00-repository-bootstrap.md
      ...
```

## Dependency direction

The UI must remain a leaf client of the core engine:

```text
Warhammer_40k_AI engine/session APIs -> exposed through core_client facade
warhammer40k_arcade_ui.core_client -> may wrap approved adapter/session APIs
render/input/hud/state -> depend on UI view models, not mutable engine internals
Arcade objects -> visual and input only, never authoritative game objects
```

Phase 2 introduces the core-engine dependency as an editable local path dependency on the sibling
`../Warhammer_40k_AI` repository. The `core_client` package owns the only approved engine import
surface.

## Development notes

- Use `uv` for Python version management, dependency locking, and command execution.
- Keep `pyright` strict for `src/`.
- Prefer deterministic tests for non-rendering logic.
- UI consumes engine `GameViewPayload`-style projections rather than mutable engine objects.
- The current launch path renders a fixture-backed inspectable battlefield until live engine
  projections are connected to the render view models.
- The opt-in live core smoke path launches a real local core session with
  `uv run warhammer40k-arcade-ui --live-core-smoke --ui-prefs docs/preferences/default.yaml`.
  It advances through fixed-secondary setup to the first Movement phase unit selection and then
  reuses the normal finite-decision, movement draft, movement submission, diagnostics, event, and
  projection-refresh paths.
- Render code uses typed read-only view models, pure camera transforms, and render primitives before
  handing anything to Arcade.
- UI submits `FiniteOptionSubmission` / `ParameterizedSubmission`-style choices through the
  adapter/session contract.
- UI-facing submission methods keep `request_id` explicit and reject stale request drift before
  constructing engine-facing results.
- UI displays authoritative invalid diagnostics from the engine instead of silently correcting them.
- Phase 6 finite-decision UI state generates deterministic `ui-result-*` IDs, submits only the
  current request's engine-provided finite option IDs, refreshes viewer-scoped event cursors, and
  displays parameterized requests as proposal-required pending state.
- Manually validate the current fixture-backed Phase 6 finite flow with
  `WARHAMMER40K_ARCADE_UI_DEBUG_PHASE6=1 uv run warhammer40k-arcade-ui`.
- Phase 7 movement drafting activates only for selected-unit `submit_movement_proposal` requests,
  renders advisory path/measurement overlays, and builds JSON-safe payload previews while leaving
  actual engine submission to a later movement proposal submission phase.
- Manually validate the current fixture-backed Phase 7 movement draft flow with
  `WARHAMMER40K_ARCADE_UI_DEBUG_PHASE7=1 uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/default.yaml`.
- Phase 8 entity-selection state is request-scoped and local-only: it builds typed selectable
  entity profiles from viewer projections and pending requests, supports explicit alias rules such
  as model-to-owning-unit, preserves deterministic selection order, and emits typed diagnostics for
  unsupported request profiles, missing candidates, cardinality violations, and unavailable visual
  anchors.
- Phase 9 movement drafts use request-scoped per-model assignment: click a model during an active
  movement draft to replace the active subset, Shift-click to add, Ctrl-click to remove, click empty
  table space to add a waypoint for that subset, and press `g` to select the current model group.
  Payload previews include every proposal-unit model in both `witness.model_paths` and
  `model_movements`; unchanged models are explicit start/end no-op paths.
- Phase 10 movement submission uses Enter as a two-step flow: the first Enter marks a movement
  draft ready, and the second Enter submits the ready payload through the explicit
  `submit_movement_payload(request_id=..., payload=..., result_id=...)` UI/core boundary. Accepted
  movement clears local draft state after a refreshed projection; invalid movement displays
  authoritative diagnostics and keeps same-context retry paths local-only.
- UI previews are advisory only; only accepted engine results can update authoritative state.
- Phase 4 UI preference files may configure known overlays, hotkeys, HUD defaults, selected
  model/unit information affordances, and recognized upcoming behavior settings. They must not
  define rules, legal actions, engine decisions, proposal kinds, validation behavior, or
  hidden-information visibility.
- Generate starter preference profiles with `uv run warhammer40k-export-preferences --format yaml`
  or load the documented examples under `docs/preferences/`.
- Select a profile at launch with `uv run warhammer40k-arcade-ui --ui-prefs path/to/profile.yaml`.
- Phase 5 selection state is local-only: model-base clicks select projected units, selection
  highlights and panels are advisory, and context menus display engine-provided finite options
  without submitting them.
- Phase 6 keyboard focus is local-only: Tab cycles finite-option focus when options are pending and
  otherwise only cycles an existing overlap selection, not a merely hovered model.
- Do not add hidden fallback behavior when an engine payload is incomplete; fix the fixture or show
  a typed diagnostic.
- Keep `docs/plans/` updated as implementation scope changes.
