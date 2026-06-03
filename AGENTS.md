# AGENTS.md — Arcade UI Rules

## Purpose

This repository is an Arcade-based UI client for `Warhammer_40k_AI`.

The UI is a companion project, not a second rules engine. It renders engine projections,
collects user intent, submits decisions through the adapter/session contract, and displays
authoritative results or diagnostics returned by the core engine.

## Source of truth

- Core engine repository: `https://github.com/SobolGaming/Warhammer_40k_AI`
- Core agent rules: `Warhammer_40k_AI/AGENTS.md`
- Adapter contract: `Warhammer_40k_AI/docs/ADAPTER_DECISION_CONTRACT.md`
- UI planning documents: `docs/plans/`

If this file conflicts with the core adapter contract, stop and ask before coding.

## Session rule

Before coding or reviewing, read this file, `README.md` if present, `pyproject.toml` if
present, the relevant plan in `docs/plans/`, and relevant tests.

If a request would weaken the UI/core boundary or create a second validation path, stop
and ask.

## Build order

Build bottom-up:

1. repository governance and quality gates
2. blank Arcade app shell
3. UI/core client facade
4. fixture-backed view models
5. rendering primitives and camera
6. shareable UI preferences for known and planned overlays, HUD defaults, and input bindings
7. selection and local UI state
8. finite decision display and submission
9. movement draft state and path witness payloads
10. proposal submission diagnostics
11. HUD ergonomics
12. packaging, CI, regression fixtures, and import-boundary audits

Do not add shooting, fight, charge, AI, training, or private rule logic before the movement
decision path is trustworthy end to end.

## Non-negotiable invariants

- The engine alone mutates authoritative game state.
- The UI must not own rule validation, event logs, replay records, or authoritative model poses.
- UI, headless, network, replay, and tests must use the same engine decision path.
- No player choice outside `DecisionRequest` / `DecisionResult`.
- Finite decisions must submit one engine-provided option ID for the current request ID.
- Parameterized decisions must submit typed, JSON-safe payloads for the current proposal request.
- Movement/charge/pile-in/consolidate/disembark/reserves/reactive movement require a `PathWitness`
  or typed invalid result from the engine.
- Endpoint-only movement validation is invalid except for explicit teleport/setup placement.
- Client previews are advisory only and must be labeled as such.
- Hidden or secret pending decisions, projections, event deltas, and diagnostics must remain
  viewer-scoped.
- Entity IDs, request IDs, option IDs, UI result IDs, and payloads must be deterministic and
  serializable.
- User preferences may configure known UI commands, known overlays, local hotkeys, HUD defaults, and
  advisory presentation only; they must not create engine decisions, legal actions, proposal kinds,
  validation behavior, or hidden-information visibility.

## Exception and fallback policy

Forbidden by default:

- bare `except`
- `except Exception`
- `except BaseException`
- `except ...: pass`
- catching an error and returning `None`, `True`, `False`, or a default value to keep going
- using permissive defaults to tolerate incomplete engine payloads

Allowed exception handling must catch a specific exception, preserve context, and either re-raise
a typed UI/domain error or display a typed invalid/unsupported result returned by the engine.

If a fixture lacks a required field, fix the fixture. Do not weaken production UI code.

## Architecture boundaries

Dependency direction:

- `warhammer40k_arcade_ui.core_client` may import or wrap approved core adapter/session APIs.
- `warhammer40k_arcade_ui.preferences` may load and validate UI-local config profiles but must not
  import mutable engine internals or define rule behavior.
- `render`, `input`, `hud`, and `state` must depend on UI view models, not mutable engine internals.
- Arcade objects are visual/input objects only; they are not game objects.
- Future network clients must preserve the same UI-facing client facade.

Keep this split:

- engine/core state: authoritative, validated, replay-facing
- UI client view models: read-only projections of current game state
- Arcade render/input objects: visual and interactive only
- movement draft state: local proposed input, not committed game state

## Decision contract policy

All user-facing choices must follow:

`DecisionRequest -> UI selection/draft -> DecisionResult -> engine validation -> engine mutation`

The UI may render controls, collect input, serialize submissions, show previews, and display
diagnostics. It must not bypass `GameLifecycle.submit_decision(...)`, the decision controller,
decision records, event records, proposal validation, or engine-owned mutation.

Any new UI flow that requires a new finite option family, proposal kind, adapter-visible payload,
or viewer-visibility behavior must update or explicitly confirm the core adapter contract.

## Testing policy

Prefer pure, deterministic tests for non-rendering logic:

- client facade request/result translation
- request ID and option ID preservation
- selection and movement draft state transitions
- generated movement payload shapes
- diagnostic view models
- shareable preferences schema loading, default-profile export, hotkey conflict diagnostics, and
  command/overlay registry validation
- camera coordinate transforms and render primitive generation
- static checks that only `core_client` imports approved engine adapter/session modules

UI tests may use fakes for the UI-facing client facade. Engine integration tests must use real
domain objects or canonical core fixtures; do not use stubs to mask engine behavior.

Every bug fix must:

1. name the violated invariant;
2. search for the same bug class elsewhere;
3. replace duplicated local logic with shared code when possible;
4. add a regression test;
5. add a static/code-quality audit when feasible.

## Required commands before PR

Run the commands that exist for the current project stage:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest tests/
uv run pre-commit run --all-files
```

If optional gates such as `mypy` or import-boundary checks are configured, run them too. If a
command cannot be run because the project is not bootstrapped yet, say so. Do not claim it passed.

## Documentation policy

- Keep `docs/plans/` aligned with implementation progress.
- Update the relevant phase plan when scope, acceptance criteria, or sequencing changes.
- Record major architecture choices in `docs/adr/` once ADRs are introduced.
- Keep README and architecture documentation consistent with the actual module structure.

## Stop and ask

Stop before coding if the change would:

- add UI-owned authoritative rule validation or mutation;
- create a private movement, shooting, charge, fight, or damage path in the UI;
- make UI/headless/network paths diverge from the core decision contract;
- invent finite option IDs or proposal kinds not emitted by the engine;
- use endpoint-only movement validation;
- leak hidden opponent information through projections, events, diagnostics, logs, or UI state;
- introduce fallback behavior or broad exception handling;
- copy legacy code wholesale;
- weaken a core invariant from `Warhammer_40k_AI/AGENTS.md`.

Agents should prefer small typed modules, visible diagnostics, deterministic fixtures, and plan
updates over large speculative UI rewrites.
