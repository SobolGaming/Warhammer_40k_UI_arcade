# Phase 20 - HUD ergonomics pass

## Goal

Improve decision-making speed and reduce cognitive load.

This phase should consume the Phase 4 preferences framework, the Phase 16 generic assignment HUD,
the Phase 17 HUD zone layout framework, the Phase 18 action visual summaries, and the Phase 19 HUD
widget toolkit for overlay defaults, HUD defaults, assignment review, summary overlays, reusable
components, and hotkeys instead of hard-coding user workflow assumptions into render, input, or HUD
modules.

## Tasks

- [ ] Add selected-unit radial menu polish (partial: action-menu hints are surfaced in HUD):
  - movement actions
  - inspect
  - measure
  - cancel
- [ ] Add range overlays using configured defaults where available (partial: existing movement budget
  overlay remains preference-driven):
  - movement budget
  - advance preview band, if data exists
  - weapon range rings as non-authoritative info overlays
- [ ] Add tooltip system (partial: compact diagnostic/event/hotkey rows use tooltip components):
  - action descriptions
  - invalid diagnostic explanation
  - model/unit id debug mode
- [x] Add event log filtering:
  - current player
  - current phase
  - invalid diagnostics
- [ ] Add keyboard-first workflow (partial: configured hotkey hints are surfaced in HUD):
  - select next unit
  - open action menu
  - confirm action
  - submit/cancel draft
  - honor configured hotkeys for known commands and overlays
- [x] Add accessibility basics:
  - scalable HUD text
  - color-independent warning icons
  - high-contrast toggle
- [ ] Add preference-aware HUD affordances (partial: HUD text/event/status preferences are honored):
  - apply configured selected-model and selected-unit panels;
  - apply configured default overlay sets;
  - surface config diagnostics in a non-authoritative diagnostics view.
- [x] Replace one-off HUD text placement with Phase 19 toolkit components where practical:
  - selected-unit headers and stat strips;
  - status chips for phase/action readiness;
  - icon text bars for action rows;
  - assignment rows inside the bottom workbench.

## Acceptance criteria

- [ ] A movement can be completed with mostly keyboard input.
- [ ] A movement can be completed with mostly mouse input.
- [x] HUD labels distinguish authoritative facts from preview estimates.
- [x] Radial menu is not required for functionality; there is also a panel/button path.
- [x] Configured overlay defaults and hotkeys route through stable command/overlay registries.
- [x] HUD polish uses reusable toolkit components rather than new one-off render primitives.
- [x] Tests cover HUD view-model generation for selected unit and pending request.

## Closeout milestone

**Milestone 15: "Usable Movement Client"**

The UI is no longer only a technical prototype; it is comfortable enough for repeated manual
movement-phase testing.

## Implementation notes

Implemented Phase 20 as the first ergonomic HUD slice rather than a full radial-menu rewrite.

- Added a `HudErgonomicsView` builder that summarizes:
  - phase/active/pending status chips;
  - selected-unit card and selected-model/unit rows;
  - current decision and movement draft rows;
  - request-scoped assignment rows;
  - invalid diagnostics, filtered event breadcrumbs, and configured hotkey hints.
- Added a primitive adapter that renders the ergonomic view through Phase 19 toolkit components:
  - top ribbon status chips;
  - right inspector selected-unit panel;
  - bottom workbench columns for decision, assignments, and review.
- Suppressed legacy status/finite/movement/assignment text in the player-facing Arcade window while
  keeping context-menu and debug-inspector primitives available.
- Extended the toolkit renderer to display tooltip bodies, hotkey hint text, and assignment summary
  lines as secondary text.
- Kept all content advisory or viewer-scoped; no core-client boundary, decision payload, or rules
  validation behavior changed.

Deferred items:

- Full radial menu art/interaction polish remains future work.
- Weapon range rings and advance preview bands still need core-projected data before they can be
  useful without inventing rules.
- Rich tooltip hover routing is still planned; this slice renders compact diagnostic/event/hotkey
  tooltip rows in the review column.

## Automated verification

- `tests/test_hud_ergonomics.py` covers ergonomic HUD view-model generation, preference visibility,
  hotkey summary routing, and screen-space toolkit primitive output.
- Existing render/toolkit tests continue to cover legacy primitive generation and widget toolkit
  preview rendering.

## Manual validation checklist

- Launch default UI:
  `uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/default.yaml`
- Select a friendly unit and confirm the right inspector shows a `Selected Unit` panel with the unit
  name/model count instead of overlapping legacy debug text.
- Select a movement action and confirm the bottom workbench shows:
  - `Decision` with the current engine request or local draft status;
  - `Assignments` marked as preview-only until submitted;
  - `Review` with hotkey hints and any invalid diagnostics.
- During a movement draft, confirm movement paths/range overlays remain advisory and the HUD says
  preview where appropriate.
- Toggle the action summary with the configured hotkey (`V` by default, `Shift+V` for review mode)
  and confirm the workbench remains readable.
- Try the keyboard-heavy preferences profile and confirm hotkey hint labels update from the loaded
  profile:
  `uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/keyboard-heavy.yaml`
