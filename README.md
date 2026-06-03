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
uv run pytest
```

## Local quality gates

Run these before opening a pull request:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run mypy src tests
uv run pytest
uv run pre-commit run --all-files
```

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
      core_client/
        __init__.py
        fake_client.py
        local_session_client.py
        protocol.py
      hud/
        __init__.py
        view_models.py
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
        selection.py
  tests/
    fixtures/
      phase03_battlefield_view.json
    test_core_client_local_session.py
    test_core_client_protocol.py
    test_config.py
    test_entrypoint.py
    test_hud_selection.py
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
- Render code uses typed read-only view models, pure camera transforms, and render primitives before
  handing anything to Arcade.
- UI submits `FiniteOptionSubmission` / `ParameterizedSubmission`-style choices through the
  adapter/session contract.
- UI-facing submission methods keep `request_id` explicit and reject stale request drift before
  constructing engine-facing results.
- UI displays authoritative invalid diagnostics from the engine instead of silently correcting them.
- UI previews are advisory only; only accepted engine results can update authoritative state.
- Phase 4 UI preference files may configure known overlays, hotkeys, HUD defaults, selected
  model/unit information affordances, and recognized upcoming behavior settings. They must not
  define rules, legal actions, engine decisions, proposal kinds, validation behavior, or
  hidden-information visibility.
- Generate starter preference profiles with `uv run warhammer40k-export-preferences --format yaml`
  or load the documented examples under `docs/preferences/`.
- Phase 5 selection state is local-only: model-base clicks select projected units, selection
  highlights and panels are advisory, and context menus display engine-provided finite options
  without submitting them.
- Do not add hidden fallback behavior when an engine payload is incomplete; fix the fixture or show
  a typed diagnostic.
- Keep `docs/plans/` updated as implementation scope changes.
