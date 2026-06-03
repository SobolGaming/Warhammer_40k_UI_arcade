# Arcade UI Plan Index

These plans split `../../OverallPlan.md` into independently reviewable and actionable phase files.
Each phase owns its goal, tasks, acceptance criteria, and closeout milestone.

## Phase sequence

| Phase | Plan | Milestone |
| --- | --- | --- |
| 0 | [Repository bootstrap and quality baseline](phase-00-repository-bootstrap.md) | Runnable Empty Client |
| 1 | [Documentation foundation](phase-01-documentation-foundation.md) | Documented Scaffold |
| 2 | [Core client adapter layer](phase-02-core-client-adapter.md) | Engine Boundary Stable |
| 3 | [Arcade rendering foundation](phase-03-arcade-rendering-foundation.md) | Inspectable Battlefield |
| 4 | [Selection and unit information HUD](phase-04-selection-unit-hud.md) | Selectable Tactical View |
| 5 | [Finite decision submission](phase-05-finite-decision-submission.md) | Authoritative Finite Decision UI |
| 6 | [Movement path drafting UI](phase-06-movement-path-drafting.md) | Movement Path Planner |
| 7 | [Movement proposal submission and diagnostics](phase-07-movement-proposal-diagnostics.md) | End-to-End Movement UI |
| 8 | [Shareable UI configuration and bindings](phase-08-shareable-ui-configuration.md) | Shareable Preferences Layer |
| 9 | [HUD ergonomics pass](phase-09-hud-ergonomics.md) | Usable Movement Client |
| 10 | [Packaging, CI, and regression hardening](phase-10-packaging-ci-regression.md) | Development-Ready UI Repo |

## First sprint recommendation

Keep the first sprint intentionally narrow:

1. Bootstrap the repo with `uv`, `ruff`, `pyright`, and `pytest`.
2. Launch a blank Arcade window.
3. Render a fake 60" x 44" table with placeholder objectives.
4. Render two fake units from fixture JSON.
5. Add pan/zoom and click selection.
6. Add a unit info panel.
7. Add a fake pending decision panel with “Normal Move”.
8. Add movement path drafting against fake data.
9. Add a small default preferences profile for overlay and hotkey assumptions used by the prototype.
10. Connect the same UI flow to a real `LocalGameSession` wrapper only after the UI loop is stable.

## Most important architectural rule

Do **not** let Arcade objects become game objects.

Keep this split:

- Engine/core state: authoritative, validated, replay-facing.
- UI client view models: read-only projections of current game state.
- Arcade render/input objects: visual and interactive only.
- Movement draft: local proposed input, not committed game state.
