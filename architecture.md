# Arcade UI Architecture Build Order

This document is the build-order roadmap for the Arcade UI client that drives the
[`Warhammer_40k_AI`](https://github.com/SobolGaming/Warhammer_40k_AI) core engine.

The roadmap is intentionally client-boundary first:

- engine lifecycle and state remain authoritative;
- every player-facing choice goes through `DecisionRequest`, `DecisionResult`, and engine-owned
  validation;
- Arcade objects are render/input objects, not game objects;
- local previews are advisory and never committed as authoritative state;
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

Phase 0 is complete. Later phases are planned and linked to independently reviewable documents under
`docs/plans/`.

| Phase | Status | Purpose | Plan |
| --- | --- | --- | --- |
| 0 | Complete | Repository bootstrap and quality baseline | [phase-00](docs/plans/phase-00-repository-bootstrap.md) |
| 1 | Planned | Documentation foundation | [phase-01](docs/plans/phase-01-documentation-foundation.md) |
| 2 | Planned | Core client adapter layer | [phase-02](docs/plans/phase-02-core-client-adapter.md) |
| 3 | Planned | Arcade rendering foundation | [phase-03](docs/plans/phase-03-arcade-rendering-foundation.md) |
| 4 | Planned | Selection and unit information HUD | [phase-04](docs/plans/phase-04-selection-unit-hud.md) |
| 5 | Planned | Finite decision submission | [phase-05](docs/plans/phase-05-finite-decision-submission.md) |
| 6 | Planned | Movement path drafting UI | [phase-06](docs/plans/phase-06-movement-path-drafting.md) |
| 7 | Planned | Movement proposal diagnostics | [phase-07](docs/plans/phase-07-movement-proposal-diagnostics.md) |
| 8 | Planned | HUD ergonomics pass | [phase-08](docs/plans/phase-08-hud-ergonomics.md) |
| 9 | Planned | Packaging, CI, and regression hardening | [phase-09](docs/plans/phase-09-packaging-ci-regression.md) |

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

## Current module map

Phase 0 provides only the runnable shell:

- `warhammer40k_arcade_ui.config` — immutable app/window configuration.
- `warhammer40k_arcade_ui.logging_config` — baseline console logging.
- `warhammer40k_arcade_ui.app` — blank Arcade window and event-loop launcher.
- `warhammer40k_arcade_ui.main` — console-script entry point.

Planned modules from later phases:

- `core_client` — UI-facing facade over approved core adapter/session APIs.
- `render` — camera, table, terrain, unit, and overlay rendering primitives.
- `input` — selection, movement path tooling, and command mapping.
- `hud` — decision panels, unit panels, diagnostics, and context menus.
- `state` — local-only UI state such as selection and movement drafts.

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
- Future protocol shape tests for request IDs, option IDs, and diagnostic view models.
- Future render-adjacent tests for camera coordinate transforms and render primitive generation.
- Future static checks to keep direct engine imports isolated to `core_client`.

## Decision log

- 2026-05-31: Phase 0 targets Python 3.14.5 to match the current core-engine workflow.
- 2026-05-31: Phase 0 starts with a blank Arcade window and no core-engine dependency. The
  engine-facing boundary will be introduced in Phase 2 through `core_client`.
- 2026-05-31: Phase 0 completed with a locked `uv` project, blank Arcade entry point, strict
  typing/linting configuration, pre-commit hooks, and bootstrap tests.
