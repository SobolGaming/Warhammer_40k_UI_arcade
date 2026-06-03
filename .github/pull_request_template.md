## Purpose

What UI invariant, module, behavior, or phase plan does this PR introduce/change?

## Scope

- [ ] Docs/plans only
- [ ] Preferences/configuration
- [ ] Render/camera/primitives
- [ ] Input/local UI state
- [ ] HUD/diagnostics
- [ ] Core-client boundary
- [ ] Decision submission flow
- [ ] Tests/fixtures only
- [ ] Packaging/CI

## Invariants checked

- [ ] No UI-owned authoritative mutation
- [ ] No private rules path or client-side rule validation
- [ ] No invented finite option IDs, request IDs, proposal kinds, or engine decisions
- [ ] No hidden-information leak through projections, diagnostics, logs, or UI state
- [ ] No broad `except` or silent fallback path
- [ ] No mutable engine imports outside `warhammer40k_arcade_ui.core_client`
- [ ] Preferences cannot define rules, legal actions, validation behavior, or visibility exceptions
- [ ] GUI objects remain visual/input objects, not game objects

## Adapter contract

Does this PR add or change a player-facing decision, finite option family, proposal kind,
adapter-visible payload shape, or viewer-visibility behavior?

- [ ] No
- [ ] Yes, and `Warhammer_40k_AI/docs/ADAPTER_DECISION_CONTRACT.md` is updated in the same PR
- [ ] Yes, and the existing contract already covers it

Explanation:

## Testing

Commands run:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pyright
uv run pytest
uv run pre-commit run --all-files
```

Additional GUI/render validation, if applicable:

## Fixture/fake usage

- [ ] No fakes/stubs used
- [ ] UI-facing fakes used only at the `core_client` protocol boundary
- [ ] Deterministic fixtures used for render/preferences/state tests
- [ ] Real core domain objects or canonical core fixtures used for integration behavior

Explain any fakes/fixtures:

## Legacy/reference code

Was any code copied or adapted from the legacy `Warhammer40k_AI` repo?

- [ ] No
- [ ] Yes, with review

If yes, what changed to satisfy UI/core boundary and fail-fast invariants?

## Reviewer notes

What should be scrutinized most carefully?
