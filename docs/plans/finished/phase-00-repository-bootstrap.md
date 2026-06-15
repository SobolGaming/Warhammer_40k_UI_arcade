# Phase 0 — Repository bootstrap and quality baseline

## Goal

Create a runnable, locked, tested Python UI package before any game-specific behavior is added.

## Tasks

- [x] Create the new repository, for example `Warhammer_40k_Arcade_UI`.
- [x] Add `pyproject.toml` using `uv`.
- [x] Add runtime dependencies: `arcade`, `pydantic` or `msgspec`, `orjson`,
  `typing-extensions`, and `platformdirs`.
- [x] Add dev dependencies: `pytest`, `pytest-cov`, `ruff`, `pyright`, optional `mypy`,
  and `pre-commit`.
- [x] Add package entry point: `warhammer40k-arcade-ui = "warhammer40k_arcade_ui.main:main"`.
- [x] Document CI-equivalent local commands in README:
  - `uv lock`
  - `uv sync`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run pyright`
  - `uv run pytest`
- [x] Add pre-commit hooks for `ruff`, formatting, and basic file hygiene.
- [x] Add strict typing policy: `pyright` strict mode for `src/`; no untyped public API in `src/`.

## Acceptance criteria

- [x] `uv sync` creates a reproducible environment.
- [x] `uv run warhammer40k-arcade-ui` opens a blank Arcade window.
- [x] `uv run pytest` passes with at least one smoke test.
- [x] `uv run ruff check .` passes.
- [x] `uv run pyright` passes.
- [x] README contains exact setup and run commands.
- [x] There is no direct dependency from the engine/core back into this UI package.

## Closeout milestone

**Milestone 0: “Runnable Empty Client”**

The repository can be cloned, synced, tested, type-checked, and launched into a blank Arcade window.

## Notes

Choose the Python version based on Arcade/tooling compatibility. The core repo may target newer
Python versions, but the UI/core boundary should keep transport and protocol payloads JSON-safe and
deterministic across compatible runtimes.
