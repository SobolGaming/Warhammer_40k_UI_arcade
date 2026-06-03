# Arcade UI Architecture Build Order

Last updated: 2026-06-03

This document is the build-order roadmap for the Arcade UI client that drives the
[`Warhammer_40k_AI`](https://github.com/SobolGaming/Warhammer_40k_AI) core engine.

The roadmap is intentionally client-boundary first:

- engine lifecycle and state remain authoritative;
- every player-facing choice goes through `DecisionRequest`, `DecisionResult`, and engine-owned
  validation;
- Arcade objects are render/input objects, not game objects;
- local previews are advisory and never committed as authoritative state;
- shareable UI preferences affect presentation and input mapping only;
- UI payloads remain deterministic, JSON-safe, and viewer-scoped.

## Primary references

- Core engine repository: <https://github.com/SobolGaming/Warhammer_40k_AI>
- Core adapter decision contract:
  <https://github.com/SobolGaming/Warhammer_40k_AI/blob/main/docs/ADAPTER_DECISION_CONTRACT.md>
- Core architecture roadmap:
  <https://github.com/SobolGaming/Warhammer_40k_AI/blob/main/ARCHITECTURE_V2.md>
- Core agent rules: <https://github.com/SobolGaming/Warhammer_40k_AI/blob/main/AGENTS.md>
- Legacy reference repository: <https://github.com/SobolGaming/Warhammer40k_AI>
- Python Arcade documentation: <https://api.arcade.academy/en/latest/>
- uv documentation: <https://docs.astral.sh/uv/>

## Roadmap status

Phases 0-1 are complete. Later phases are planned and linked to independently reviewable documents
under `docs/plans/`.

| Phase | Status | Purpose | Plan |
| --- | --- | --- | --- |
| 0 | Complete | Repository bootstrap and quality baseline | [phase-00](docs/plans/phase-00-repository-bootstrap.md) |
| 1 | Complete | Documentation foundation | [phase-01](docs/plans/phase-01-documentation-foundation.md) |
| 2 | Planned | Core client adapter layer | [phase-02](docs/plans/phase-02-core-client-adapter.md) |
| 3 | Planned | Arcade rendering foundation | [phase-03](docs/plans/phase-03-arcade-rendering-foundation.md) |
| 4 | Planned | Selection and unit information HUD | [phase-04](docs/plans/phase-04-selection-unit-hud.md) |
| 5 | Planned | Finite decision submission | [phase-05](docs/plans/phase-05-finite-decision-submission.md) |
| 6 | Planned | Movement path drafting UI | [phase-06](docs/plans/phase-06-movement-path-drafting.md) |
| 7 | Planned | Movement proposal diagnostics | [phase-07](docs/plans/phase-07-movement-proposal-diagnostics.md) |
| 8 | Planned | Shareable UI configuration and bindings | [phase-08](docs/plans/phase-08-shareable-ui-configuration.md) |
| 9 | Planned | HUD ergonomics pass | [phase-09](docs/plans/phase-09-hud-ergonomics.md) |
| 10 | Planned | Packaging, CI, and regression hardening | [phase-10](docs/plans/phase-10-packaging-ci-regression.md) |

## Cross-cutting architectural rules

1. **No UI-owned state mutation.** The UI renders projections and submits decisions; the engine
   validates and mutates authoritative state.
2. **No private rules path.** The UI must not implement hidden movement, shooting, charge, fight,
   scoring, or damage logic.
3. **No invented decisions.** Finite option IDs and parameterized proposal kinds must come from the
   current engine request.
4. **No endpoint-only movement validation.** Movement previews must capture path witness intent and
   defer authority to the engine.
5. **No hidden information leaks.** Projections, event deltas, diagnostics, logs, and derived UI
   state must remain viewer-scoped.
6. **No silent fallback behavior.** Unsupported or malformed payloads should surface typed
   diagnostics rather than guessing.
7. **No config-owned rules.** User preferences may bind known UI commands, known overlays, visual
   defaults, and local input behavior; they must not create legal actions, engine decisions,
   proposal kinds, visibility exceptions, or validation behavior.

## Current module map

Phase 0 provides only the runnable shell:

- `warhammer40k_arcade_ui.config` — immutable app/window configuration.
- `warhammer40k_arcade_ui.logging_config` — baseline console logging.
- `warhammer40k_arcade_ui.app` — blank Arcade window and event-loop launcher.
- `warhammer40k_arcade_ui.main` — console-script entry point.

Planned modules from later phases:

- `core_client` — UI-facing facade over approved core adapter/session APIs.
- `preferences` — typed loading, validation, diagnostics, and export for shareable UI
  JSON/YAML profiles.
- `render` — camera, table, terrain, unit, and overlay rendering primitives.
- `input` — selection, movement path tooling, and command mapping.
- `hud` — decision panels, unit panels, diagnostics, and context menus.
- `state` — local-only UI state such as selection and movement drafts.

## Shareable Preferences

The UI should support portable hand-editable preference profiles in JSON and YAML. These profiles are
intended to be easy to pass between users and should control local presentation and input behavior:

- default overlays enabled when a model or unit is selected;
- default overlays enabled while movement drafting is active;
- hotkeys for toggling known overlays for the currently selected model or unit;
- hotkeys for showing selected model or selected unit information;
- HUD defaults, accessibility preferences, and debug/diagnostic panel defaults.

Preferences must be versioned and validated against a typed schema. Unknown command IDs, unknown
overlay IDs, duplicate hotkeys, unsupported schema versions, and settings for unavailable features
should produce typed config diagnostics instead of silently falling back. Config files must be
portable by default; machine-local paths or caches should live in a separate local override if those
are ever needed.

Preferences can only select from registered UI commands and registered advisory overlays. A config
file cannot invent finite option IDs, proposal kinds, engine decisions, hidden visibility rules, or
authoritative validation behavior.

## Runtime modes

- **Local in-process session** — planned first integration mode. `core_client` will wrap approved
  engine lifecycle/session APIs and expose UI view models.
- **Future network session** — planned transport mode behind the same UI-facing client facade.
- **Future replay inspection mode** — planned read-only mode for inspecting engine replay/projection
  data without introducing a second mutation path.

## Decision flow

```text
GameViewPayload
  -> UI view models
  -> render and HUD controls
  -> user input
  -> FiniteOptionSubmission or ParameterizedSubmission
  -> engine validation
  -> refreshed projection, events, or diagnostics
```

The UI may preview proposed actions, but preview state is advisory only. Accepted state appears only
after the core engine returns an accepted result and a refreshed projection.

## Movement flow target

The first rules-facing vertical slice will be movement:

```text
finite movement action selection
  -> movement proposal request
  -> path drafting
  -> PathWitness payload
  -> proposal submission
  -> accepted movement or authoritative invalid diagnostics
```

## Testing strategy

- Unit tests for immutable config and entry-point behavior.
- Future pure state tests for selection and movement draft transitions.
- Future preferences tests for JSON/YAML schema loading, default-profile export, hotkey conflict
  detection, command/overlay registry validation, and config diagnostics.
- Future protocol shape tests for request IDs, option IDs, and diagnostic view models.
- Future render-adjacent tests for camera coordinate transforms and render primitive generation.
- Future static checks to keep direct engine imports isolated to `core_client`.

## Known deferred work

- Core client adapter implementation and real local game-session integration.
- Network transport.
- Replay inspector.
- Shooting HUD, charge HUD, fight HUD, and damage-allocation UI.
- Line-of-sight and cover visualization.
- 3D renderer or full asset loading.
- Import-boundary audit that enforces direct engine imports only from `core_client`.

## Decision log

- 2026-05-31: Phase 0 targets Python 3.14.5 to match the current core-engine workflow.
- 2026-05-31: Phase 0 starts with a blank Arcade window and no core-engine dependency. The
  engine-facing boundary will be introduced in Phase 2 through `core_client`.
- 2026-05-31: Phase 0 completed with a locked `uv` project, blank Arcade entry point, strict
  typing/linting configuration, pre-commit hooks, and bootstrap tests.
- 2026-05-31: Phase 1 completed with README and architecture documentation covering repository
  relationships, first-run commands, UI/core boundaries, runtime modes, roadmap links, and deferred
  work.
- 2026-06-03: Added Phase 8 for shareable JSON/YAML UI preferences covering overlay defaults,
  hotkeys, selected-model/unit information affordances, and config diagnostics while preserving the
  engine-authoritative decision boundary.
