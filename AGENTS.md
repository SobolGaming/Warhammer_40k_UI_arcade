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
- Core PR review template: `Warhammer_40k_AI/.github/pull_request_template.md`
- UI planning documents: `docs/plans/`
- Workspace PR credentials: `../github_token` for GitHub CLI authentication when Codex performs
  required pull request actions for repository-updating work.

If this file conflicts with the core adapter contract, stop and ask before coding.

## Session rule

Before coding or reviewing, read this file, `README.md` if present, `pyproject.toml` if
present, the relevant plan in `docs/plans/`, and relevant tests.

If a request would weaken the UI/core boundary or create a second validation path, stop
and ask.

This UI repository may use Warhammer_40k_AI core engine code, objects, and datatypes to represent
things and may have dependencies on it to simplify and deduplicate code instead of re-writing different
but functionally identical elements.


## Pull-request mediated development

All repository-updating work must be pull-request mediated by default. If Codex changes any tracked
or new repository file, Codex must create or reuse a task branch, commit the change, push the branch,
and open or update a GitHub pull request for review before handoff, unless the user explicitly says
not to open a PR for that task or GitHub access is unavailable.

Before starting a feature implementation:

1. identify the owning phase plan and acceptance criteria;
2. state whether the work changes UI/core boundaries, decision submission, preferences, rendering,
   input, HUD, local UI state, or documentation only;
3. keep the change scoped to one reviewable behavior slice;
4. avoid mixing unrelated refactors, dependency churn, and feature work;
5. call out any required core adapter-contract update before coding.

During implementation:

- preserve the current worktree and never revert unrelated user changes;
- keep commits/branches PR-ready throughout the task;
- use `gh` as the GitHub pull request tool to create, inspect, update, push for, or otherwise
  manage pull requests;
- authenticate `gh` with the access token stored in the workspace-level `../github_token` file when
  PR actions require GitHub access. Do not print, log, commit, or paste the token; pass it through
  `GH_TOKEN` or `gh auth login --with-token` as appropriate for the requested operation;
- after any repository file changes, push the task branch and open or update the PR automatically as
  part of the same task closeout;
- after opening or updating a PR, monitor the PR checks until they complete; inspect any failing
  checks, fix actionable failures, push the fixes, and re-check before treating a code or
  documentation update as complete. If checks are blocked, unavailable, or external to GitHub
  Actions, report that explicitly with the remaining risk;
- if the user explicitly requests local-only work, do not push or open a PR, and state that the
  task intentionally violates the default PR-mediated workflow at the user's request;
- update the relevant phase plan, README, architecture docs, or ADR notes in the same work item when
  behavior, sequencing, boundaries, or acceptance criteria change;
- add focused tests for the behavior slice instead of relying only on manual launch checks;
- for GUI/rendering changes, prefer deterministic camera/primitive tests and, when display access is
  available, native offscreen framebuffer validation before claiming visual rendering was checked.

Before a PR or PR-ready handoff, provide:

- purpose: invariant, module, or behavior changed;
- scope: docs only, preferences, render, input/state, HUD, core-client boundary, decision flow, or
  packaging/CI;
- invariants checked:
  - no UI-owned authoritative mutation;
  - no private rules path;
  - no invented decision IDs, proposal kinds, or option IDs;
  - no hidden-information leak;
  - no silent fallback or broad exception handling;
  - no direct mutable engine imports outside `core_client`;
  - preference files cannot define rules, legal actions, validation behavior, or visibility
    exceptions;
- commands run, including any command that could not be run and why;
- reviewer notes naming what should be scrutinized most carefully.

When a change adds or changes a player-facing decision, finite option family, proposal kind,
adapter-visible payload shape, or viewer-visibility behavior, the same PR must update
`Warhammer_40k_AI/docs/ADAPTER_DECISION_CONTRACT.md`, or explicitly justify why the existing
contract already covers the change.

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
11. live local core smoke path for thin manual end-to-end testing
12. GUI event test harness for deterministic in-process interaction tests
13. headless render evidence and framebuffer validation
14. forensic UI/core event tracing
15. crash diagnostic bundles
16. generic assignment HUD
17. configurable HUD zone layout framework
18. action visual summary overlays
19. HUD widget toolkit
20. HUD ergonomics
21A. core Phase 15D-15F adapter adaptation
21. packaging, CI, regression fixtures, and import-boundary audits
22. packaged runtime defaults and source model
23. HUD toolkit customizability and overflow tuning
24. dice tray and roll workbench
25. legacy UI cleanup
26. generic finite decision workbench polish
27. current action view and clickable HUD buttons
28. generic placement proposal editor
29. movement proposal family generalization
30. generic assignment proposal editors for shooting, melee, and stratagem targets
31. scrollable player-units roster and reciprocal selection

When adding shooting, fight, charge, AI, training, or other later-gameplay surfaces, keep them on
the same trusted decision/proposal path as movement. Do not add private rule logic or local
authoritative shortcuts.

## Non-negotiable invariants

- The engine alone mutates authoritative game state.
- The UI must not own rule validation, event logs, replay records, or authoritative model poses.
  - It may represent and check those things, but is not the authoritative arbiter of such.
  - Opt-in diagnostic UI traces are allowed when they are explicitly non-authoritative,
    viewer-scoped, redacted, and used only for debugging crashes or UI/client behavior.
- UI, headless, network, replay, and tests must use the same engine decision path.
- No game effecting player choice outside `DecisionRequest` / `DecisionResult`.
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

## Bugfixes

- For every bugix made, a regression test should be created if there is not already
  a test to cover that case where possible.
  - If a regression test is not possible, the agent should announce it to the developer and ask for
    guidance.

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
uv run mypy src tests
uv run pyright
uv run pytest tests/
uv run pre-commit run --all-files
```

If import-boundary checks, GUI smoke checks, or CI-specific gates are configured for the current
slice, run them too. If a command cannot be run because the project is not bootstrapped, display
access is unavailable, dependencies are unavailable, or the user has not approved an escalated
operation, say so. Do not claim it passed.

## Documentation policy

- Keep `docs/plans/` aligned with implementation progress.
- Update the relevant phase plan when scope, acceptance criteria, or sequencing changes.
- At phase closeout, include both automated verification commands and a manual validation checklist
  for user-facing features. If GUI interaction or live-engine state makes comprehensive manual
  validation difficult, say which behaviors are covered by automated tests and which need a future
  manual/debug harness.
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

Agents should prefer reviewable PR-sized slices, small typed modules, visible diagnostics,
deterministic fixtures, tests, and plan updates over large speculative UI rewrites.
