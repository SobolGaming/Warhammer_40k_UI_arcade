# Arcade UI repository instructions

## Scope

This repository is an Arcade client for the `Warhammer_40k_AI` engine. It renders viewer-scoped
projections, collects intent, submits current engine decisions, and displays engine results. The
sibling `../Warhammer_40k_AI/` checkout is reference-only; do not edit it.

## Invariants

- The engine alone validates rules and mutates authoritative state. UI selection, drafts, previews,
  traces, and Arcade objects are local or advisory; they must not become a second rules path. Label
  client previews as advisory.
- Every game-effecting choice follows the current `DecisionRequest` / `DecisionResult` through the
  public adapter/session facade. Preserve engine-provided request and option IDs. Parameterized
  choices use typed, JSON-safe payloads; never invent proposal kinds or legal options in the UI.
  UI, headless, network, replay, and tests use the same engine decision path.
- Keep entity, request, option, and UI result IDs, plus payloads, deterministic and serializable.
- Keep projections, pending choices, events, diagnostics, and traces scoped to the current viewer.
  A local debug surface must not reveal hidden opponent information.
- Only `warhammer40k_arcade_ui.core_client` may directly import approved core APIs. Other UI modules
  consume UI-facing protocols and view models. `scripts/check_import_boundaries.py` enforces this
  boundary and rejects private lifecycle/queue access.
- For movement-like proposals, follow the active core contract's `PathWitness` shape. Do not
  validate movement legality in the UI or synthesize intermediate poses to satisfy client assumptions.
- Preferences may change presentation, known commands, bindings, and HUD layout. They must not
  define legality, engine decisions, validation, or visibility exceptions.
- When an active workflow exposes the same selection in the battlefield, Current Action view, or
  roster, keep their underlying focus, selection, and highlight synchronized even when a surface is
  hidden. Resolve model/unit aliases to the entity layer required by the current engine request;
  highlighting remains advisory.
- Fail visibly on missing or incompatible engine data. Catch specific exceptions, preserve context,
  and show typed diagnostics; do not use broad catches or permissive defaults to continue. Fix
  incomplete fixtures instead of weakening production parsing.

## Read when relevant

- Before changing decision submission, adapter payloads, projections, or viewer visibility, read
  `docs/adr/0001-ui-core-boundary.md` and the version-matched
  `../Warhammer_40k_AI/docs/ADAPTER_DECISION_CONTRACT.md`. If the pinned core contract lacks the
  needed behavior, identify the compatibility gap and arrange separate authorized core work; do
  not implement a private UI path or edit the sibling checkout.
- Before implementing a planned feature, use `docs/plans/README.md` to find its active plan and
  acceptance criteria. Update the relevant plan when scope or acceptance criteria change.
- Before changing preferences or HUD composition, read `docs/ui-configuration.md` or
  `docs/hud-customization.md`, respectively, and inspect the matching examples and tests.
- Before changing installation, packaging, or quality gates, read `README.md`, `pyproject.toml`,
  and `.github/workflows/ci.yml`. Use the current pinned core revision rather than the sibling
  checkout's branch tip.
- Before opening a PR, use `.github/pull_request_template.md` for the review evidence and scope.

## Verification

Run commands from this repository root. The project targets Python 3.14.5; a fresh checkout uses
`uv sync --locked --all-groups`. The sibling core checkout supplies type information for mypy and
pyright. For documentation-only edits, run `git diff --check` and verify referenced paths and
commands. For behavior changes, add a focused regression test where practical; core integration
tests use real domain objects or canonical fixtures, while UI tests may fake the client facade.

Run relevant focused tests while iterating. Before a code PR, run the maintained quality gates:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pyright
uv run python scripts/check_import_boundaries.py
uv run coverage run -m pytest
uv run coverage report
uv run pre-commit run --all-files
uv build
```

For rendering or interaction changes, use the relevant headless GUI tests; report whether a manual
display check was possible. In the handoff, distinguish checks that passed, failed, or were not run
and why. A bug fix should name the violated invariant, check for the same failure elsewhere, and
include a regression test when feasible.

## Branches and pull requests

- Preserve unrelated worktree changes. Keep repository edits on a scoped task branch; commit, push,
  and open or update a PR through `gh` unless the user explicitly requests local-only work or
  GitHub access is unavailable.
- For `gh` PR actions, pass the token from `../github_token` through `GH_TOKEN`. Never display or
  commit the token.
- After opening or updating a PR, wait for its checks, investigate failures, and fix actionable issues before
  reporting completion. If remote access or checks are unavailable, state the exact blocker and
  the remaining unverified work.
