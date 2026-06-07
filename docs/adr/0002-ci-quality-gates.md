# ADR 0002 - CI Quality Gates

## Status

Accepted.

## Context

The UI is now used to manually drive real engine development. Regressions can appear in Python
typing, preference parsing, deterministic fixtures, headless rendering, GUI event handling,
packaging metadata, or the UI/core boundary. Local tests alone are too easy to run inconsistently.

## Decision

Pull-request CI must run:

- locked dependency sync with `uv sync --locked --all-groups`;
- `ruff check`;
- `ruff format --check`;
- `mypy src tests`;
- `pyright`;
- the import-boundary audit;
- pre-commit hooks;
- package build;
- pytest under coverage with a configured threshold.

The coverage threshold starts conservatively at the current development-ready baseline so future
work is prevented from dropping broad non-rendering coverage while still allowing render-heavy
features to iterate.

## Consequences

- Pull requests fail before review when static quality, packaging, fixture parsing, or import
  boundary rules regress.
- Headless render tests remain part of the normal test suite, with CI installing EGL/OpenGL runtime
  libraries.
- Coverage can be raised later as HUD, preview, diagnostics, and workflow modules stabilize.
