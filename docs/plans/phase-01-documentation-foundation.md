# Phase 1 — Documentation foundation: README and architecture.md

## Goal

Make the repository understandable before it grows.

## README plan

The README should include:

- [ ] Project purpose: “Arcade-based local/network-capable UI client for `Warhammer_40k_AI`.”
- [ ] Explicit repository references:
  - current core repo: `https://github.com/SobolGaming/Warhammer_40k_AI`
  - adapter contract: `https://github.com/SobolGaming/Warhammer_40k_AI/blob/main/docs/ADAPTER_DECISION_CONTRACT.md`
  - legacy pygame-era reference repo: `https://github.com/SobolGaming/Warhammer40k_AI`
- [ ] Current scope:
  - local Arcade UI
  - initial movement-only interaction
  - engine-authoritative validation
  - no UI-owned mutation of authoritative game state
- [ ] Non-goals for first milestones:
  - no full 3D asset loading
  - no authoritative shooting/fight/charge UI yet
  - no private rules path in the UI
- [ ] Setup commands:
  - `uv sync`
  - `uv run warhammer40k-arcade-ui`
  - `uv run pytest`
  - `uv run ruff check .`
  - `uv run pyright`
- [ ] Development principles:
  - UI consumes `GameViewPayload`.
  - UI submits `FiniteOptionSubmission` / `ParameterizedSubmission`.
  - UI displays invalid diagnostics from the engine.
  - UI previews are advisory only.
  - Engine remains authoritative.

## architecture.md plan

The initial architecture document should be intentionally short and updated over time.

Suggested sections:

1. Design intent: Arcade UI client for `Warhammer_40k_AI`.
2. Boundary with core engine: UI does not mutate `GameState`; it consumes projections and submits decisions.
3. Runtime modes: local in-process session, future network session, future replay inspection mode.
4. Main modules: `core_client`, `render`, `input`, `hud`, and `state`.
5. Decision flow: `GameViewPayload -> controls -> user input -> submission -> engine validation -> refreshed view/events`.
6. Movement UI flow: finite movement action selection, movement proposal request, path drafting,
   `PathWitness` payload, submission, accepted result or invalid diagnostics.
7. Testing strategy: pure unit tests, UI-state tests, protocol shape tests, smoke launch tests,
   and integration tests against a minimal core fixture.
8. Known deferred work: network transport, shooting HUD, charge HUD, line of sight, 3D renderer,
   and replay inspector.

## Acceptance criteria

- [ ] README explains how this repo relates to both the new and legacy repositories.
- [ ] README includes a first-run path that works from a clean clone.
- [ ] `architecture.md` explains the UI/core boundary clearly.
- [ ] `architecture.md` has a “last updated” or “decision log” section so it can evolve.
- [ ] Docs explicitly say client-side previews are not authoritative.

## Closeout milestone

**Milestone 1: “Documented Scaffold”**

A new contributor can understand what the UI is, what it is not, how to run it, and how it talks to
the core engine.
