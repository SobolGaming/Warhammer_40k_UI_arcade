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
| 4 | [Shareable UI preferences framework](phase-04-shareable-ui-preferences.md) | Shareable Preferences Framework |
| 5 | [Selection and unit information HUD](phase-05-selection-unit-hud.md) | Selectable Tactical View |
| 6 | [Finite decision submission](phase-06-finite-decision-submission.md) | Authoritative Finite Decision UI |
| 7 | [Movement path drafting UI](phase-07-movement-path-drafting.md) | Movement Path Planner |
| 8 | [Entity selection profile foundation](phase-08-entity-selection-profile-foundation.md) | Entity Selection Foundation |
| 9 | [Movement draft model assignments](phase-09-movement-draft-model-assignments.md) | Per-Model Movement Planner |
| 10 | [Movement proposal submission and diagnostics](phase-10-movement-proposal-submission-diagnostics.md) | End-to-End Movement UI |
| 11 | [Live core manual smoke path](phase-11-live-core-manual-smoke.md) | Live Core Movement Smoke |
| 12 | [GUI event test harness](phase-12-gui-event-test-harness.md) | Scriptable GUI Events |
| 13 | [Headless render evidence](phase-13-headless-render-evidence.md) | Headless Visual Evidence |
| 14 | [Forensic event trace](phase-14-forensic-event-trace.md) | Forensic Event Trace |
| 15 | [Crash diagnostic bundles](phase-15-crash-diagnostic-bundles.md) | Actionable Crash Bundles |
| 16 | [Generic assignment HUD](phase-16-generic-assignment-hud.md) | Assignment Review HUD |
| 17 | [Action visual summary overlays](phase-17-action-visual-summary-overlays.md) | Action Summary Overlays |
| 18 | [HUD ergonomics pass](phase-18-hud-ergonomics.md) | Usable Movement Client |
| 19 | [Packaging, CI, and regression hardening](phase-19-packaging-ci-regression.md) | Development-Ready UI Repo |

## Umbrella And Preliminary Plans

These documents either explain cross-phase direction or outline future work that is not yet ready
for a numbered phase.

- [Entity selection and assignment workspace](proposal-entity-selection-assignment-workspace.md) -
  accepted roadmap direction that explains the cross-cutting workspace concept and links to the
  concrete phases above.
- [Forensic event replay](preliminary-forensic-event-replay.md) - preliminary future plan for
  replaying forensic trace UI events through a `--play-events` workflow, with explicit engine-side
  deterministic replay needs called out.
- [Shooting declaration assignment tool](preliminary-shooting-declaration-assignment-tool.md) -
  preliminary future plan for model/weapon-to-target assignment.
- [Stratagem target-binding assignment tool](preliminary-stratagem-target-binding-tool.md) -
  preliminary future plan for multi-slot Stratagem target selection.

## First sprint recommendation

Keep the first sprint intentionally narrow:

1. Bootstrap the repo with `uv`, `ruff`, `pyright`, and `pytest`.
2. Launch a blank Arcade window.
3. Render a fake 60" x 44" table with placeholder objectives.
4. Render two fake units from fixture JSON.
5. Add a small default preferences profile for overlay, HUD, and hotkey assumptions used by the
   prototype.
6. Add pan/zoom and click selection.
7. Add a unit info panel.
8. Add a fake pending decision panel with “Normal Move”.
9. Add movement path drafting against fake data.
10. Connect the same UI flow to a real `LocalGameSession` wrapper only after the UI loop is stable.

## Most important architectural rule

Do **not** let Arcade objects become game objects.

Keep this split:

- Engine/core state: authoritative, validated, replay-facing.
- UI client view models: read-only projections of current game state.
- Arcade render/input objects: visual and interactive only.
- Movement draft: local proposed input, not committed game state.
