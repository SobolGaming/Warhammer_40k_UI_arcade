# Phase 12 - GUI event test harness

## Goal

Add an in-process Arcade/pyglet test harness that can drive UI event handlers deterministically
without relying on OS-level mouse and keyboard automation.

In plain language: future UI work needs automated tests that can act like a careful player without
requiring a real desktop session. The test harness should let tests press keys, move the mouse,
click table positions, advance frames, and inspect resulting UI state through stable APIs. It should
exercise the same event handlers the real window uses, but it should not depend on display focus,
Wayland/X11 input permissions, screen scaling, or timing guesses.

This phase directly follows the attached testing discussion's approach 2: simulate real handlers
inside the process through direct handler calls or pyglet-style `dispatch_event(...)`.

## Scope

- Add a test-only driver API for `ArcadeWarhammerWindow` or its narrow test facade.
- Support deterministic scripted actions:
  - `press_key`
  - `release_key`
  - `click_world`
  - `click_screen`
  - `move_mouse_world`
  - `move_mouse_screen`
  - `step_frames`
- Preserve the production event path:
  - test driver actions should call the same window event handlers used by Arcade;
  - no separate selection, hotkey, or movement logic should exist only in tests.
- Add stable state inspection helpers:
  - selected entity refs;
  - context menu visibility and items;
  - finite decision status;
  - movement draft status and payload readiness;
  - active overlays and debug HUD state.
- Use fake and live-client-shaped fixtures through the existing UI-facing client facade.
- Keep OS-level automation out of this phase except as a documented future smoke layer.

## Non-Goals

- No PyAutoGUI/PyDirectInput dependency.
- No real desktop focus/input automation.
- No broad screenshot comparison.
- No rules validation in the UI.
- No new engine decision contracts.

## Tasks

- [x] Define `tests/support/gui_driver.py` or equivalent with a small `GuiTestDriver`.
- [x] Add a test window factory that can construct the current Arcade window in a deterministic
  fixture mode without launching `arcade.run()`.
- [x] Add event-driver methods that route through window handlers or `dispatch_event(...)`:
  - key press/release;
  - mouse press/release;
  - mouse motion;
  - frame stepping with `on_update`.
- [x] Add world/screen coordinate helpers using the existing camera transforms.
- [x] Add state-inspection helpers that read existing UI state without mutating it.
- [x] Add regression tests for current player-facing flows:
  - select a model by click;
  - open selected-unit actions by hotkey;
  - select a finite option by keyboard;
  - draft movement waypoints by table clicks;
  - mark movement ready;
  - verify mouse hover does not clear ready movement;
  - cancel/close menus where existing behavior supports it.
- [x] Document how future phases should add driver-level regression tests for GUI-visible
  behavior.

## Acceptance Criteria

- [x] Tests can drive existing UI event handlers without opening a visible OS-controlled window.
- [x] A new GUI bug can usually be reproduced as a short driver script in pytest.
- [x] Existing selection, context-menu, finite-decision, and movement-draft workflows have at least
  one event-harness test.
- [x] Driver helpers expose stable user-level assertions instead of requiring tests to inspect
  unrelated private fields.
- [x] The harness does not bypass the UI-facing core client facade or submit invented engine
  decisions.
- [x] Full repository gates pass.

## Testing Strategy

- Prefer ordinary pure state tests for non-rendering logic.
- Use this harness for event wiring and player workflow tests.
- Add appropriate regression tests when GUI bugs are discovered.
- Keep tests deterministic by using fixed fixtures, explicit coordinates, and explicit frame counts.
- Do not assert exact pixel output in this phase.

## Manual Validation Checklist

After implementation:

- [x] Run the new event-harness tests with `uv run pytest tests/test_gui_event_driver.py`.
- [ ] Manually exercise one covered workflow in the GUI and confirm the automated test steps match
  the real interaction.
- [ ] When a GUI bug is found, confirm the harness can reproduce it or document why it requires the
  Phase 13 headless render layer or a later OS smoke layer.

## Implementation Notes

- Added `GuiTestDriver.phase6_debug()` as a deterministic headless Arcade window factory for the
  current finite-decision and movement-draft debug workflow.
- Driver actions call the production `ArcadeWarhammerWindow` event handlers directly, except key
  release, which routes through pyglet `dispatch_event(...)` because the window currently has no
  custom release handler.
- Added narrow read-only window properties for test inspection of battlefield view, pending
  decision, finite state, movement draft, event cursor, and current context menu.
- Added event-harness regression coverage for model click selection, selected-unit action hotkey
  opening/canceling, keyboard finite submission, movement waypoint drafting, movement-ready
  preview creation, the mouse-hover ready-state regression, and fake-client movement submission.
- Future GUI-visible bugs should usually get a short pytest script that starts from
  `GuiTestDriver.phase6_debug()` or a purpose-built driver factory for the relevant fixture.

## Phase Closeout Milestone

**Milestone 12: "Scriptable GUI Events"**

Codex and human reviewers can reproduce GUI event bugs with deterministic in-process tests instead
of relying on manual-only evidence.
