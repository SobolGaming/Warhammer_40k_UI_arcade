# Arcade UI Architecture Build Order

Last updated: 2026-06-07

This document is the build-order roadmap for the Arcade UI client that drives the
[`Warhammer_40k_AI`](https://github.com/SobolGaming/Warhammer_40k_AI) core engine.

The roadmap is intentionally client-boundary first:

- engine lifecycle and state remain authoritative;
- every player-facing choice goes through `DecisionRequest`, `DecisionResult`, and engine-owned
  validation;
- Arcade objects are render/input objects, not game objects;
- local previews are advisory and never committed as authoritative state;
- shareable UI preferences affect presentation and input mapping only;
- UI payloads remain deterministic, JSON-safe, and viewer-scoped.

## Primary references

- Core engine repository: <https://github.com/SobolGaming/Warhammer_40k_AI>
- Core adapter decision contract:
  <https://github.com/SobolGaming/Warhammer_40k_AI/blob/main/docs/ADAPTER_DECISION_CONTRACT.md>
- Core architecture roadmap:
  <https://github.com/SobolGaming/Warhammer_40k_AI/blob/main/ARCHITECTURE_V2.md>
- Core agent rules: <https://github.com/SobolGaming/Warhammer_40k_AI/blob/main/AGENTS.md>
- Legacy reference repository: <https://github.com/SobolGaming/Warhammer40k_AI>
- Python Arcade documentation: <https://api.arcade.academy/en/latest/>
- uv documentation: <https://docs.astral.sh/uv/>

## Roadmap status

Phases 0-21 are complete. Later phases are planned and linked to independently reviewable documents
under `docs/plans/`.

| Phase | Status | Purpose | Plan |
| --- | --- | --- | --- |


## Cross-cutting architectural rules

1. **No UI-owned state mutation.** The UI renders projections and submits decisions; the engine
   validates and mutates authoritative state.
2. **No private rules path.** The UI must not implement hidden movement, shooting, charge, fight,
   scoring, or damage logic.
3. **No invented decisions.** Finite option IDs and parameterized proposal kinds must come from the
   current engine request.
4. **No endpoint-only movement validation.** Movement previews must capture path witness intent and
   defer authority to the engine.
5. **No hidden information leaks.** Projections, event deltas, diagnostics, logs, and derived UI
   state must remain viewer-scoped.
6. **No silent fallback behavior.** Unsupported or malformed payloads should surface typed
   diagnostics rather than guessing.
7. **No config-owned rules.** User preferences may bind known UI commands, known overlays, visual
   defaults, and local input behavior; they must not create legal actions, engine decisions,
   proposal kinds, visibility exceptions, or validation behavior.

## Current module map

Phases 0-21 provide the runnable shell, core client boundary, inspectable render foundation,
shareable UI preference framework, local selection/HUD state, finite decision submission, local
movement path drafting, request-scoped entity-selection foundation, per-model movement draft
assignments with authoritative movement proposal submission, opt-in live-core smoke startup,
scriptable GUI/render diagnostics, crash bundles, configurable HUD zones, the Generic Assignment
HUD, advisory action visual summaries, HUD widget composition/preview tooling, ergonomic HUD
summaries, CI quality gates, golden regression fixtures, ADRs, and packaging smoke coverage:

- `warhammer40k_arcade_ui.config` — immutable app/window configuration.
- `warhammer40k_arcade_ui.logging_config` — baseline console logging.
- `warhammer40k_arcade_ui.debug_fixtures` — opt-in deterministic fixtures for manual validation of
  current UI phases without changing normal launch behavior.
- `warhammer40k_arcade_ui.app` — Arcade window and event-loop launcher, with fake-runtime support
  for entry-point tests.
- `warhammer40k_arcade_ui.main` — console-script entry point.
- `warhammer40k_arcade_ui.core_client.protocol` — UI-facing dataclasses and client protocol.
- `warhammer40k_arcade_ui.core_client.local_session_client` — local in-process wrapper over the
  core engine adapter/session APIs.
- `warhammer40k_arcade_ui.core_client.live_smoke` — opt-in real-core smoke startup harness that
  constructs a canonical two-player local session and advances to the first movement-unit decision.
- `warhammer40k_arcade_ui.core_client.fake_client` — deterministic fake client for UI tests.
- `warhammer40k_arcade_ui.render.view_models` — read-only battlefield render view models parsed from
  deterministic fixture/projection payloads, plus supported refresh from render-shaped payloads or
  core battlefield runtime model-placement projections.
- `warhammer40k_arcade_ui.render.core_projection` — viewer-scoped core `GameViewPayload` to
  render-view adapter for the live smoke launch path.
- `warhammer40k_arcade_ui.render.camera` — world-space camera, pan/zoom, and screen/world
  coordinate conversion.
- `warhammer40k_arcade_ui.render.primitives` — pure table, deployment-zone, objective, terrain,
  unit, model-base, movement assignment overlay, action visual summary overlay, and HUD primitive
  generation.
- `warhammer40k_arcade_ui.render.arcade_window` — `ArcadeWarhammerWindow` consuming render
  primitives for drawing, right/middle-drag panning, mouse-wheel zoom, mouse coordinate display,
  finite hotkeys, context-menu actions, local movement-assignment input, and ready movement draft
  submission.
- `warhammer40k_arcade_ui.render.default_fixture` — deterministic launch-time battlefield fixture
  used until live projections are connected.
- `warhammer40k_arcade_ui.preferences.schema` — typed preference dataclasses, versioned parsing,
  registry validation, and config diagnostics.
- `warhammer40k_arcade_ui.preferences.registries` — stable command, overlay, and planned-setting
  registries used to avoid ad hoc config strings.
- `warhammer40k_arcade_ui.preferences.defaults` — built-in default, dense-debug, and
  keyboard-heavy preference profiles.
- `warhammer40k_arcade_ui.preferences.io` — explicit-path, platform-default, built-in-default,
  JSON, and YAML load/export helpers.
- `warhammer40k_arcade_ui.preferences.export_profile` — CLI entry point for exporting starter
  profiles.
- `warhammer40k_arcade_ui.state.selection` — local-only selection state, model-base hit detection,
  overlap cycling, active overlay defaults, panel visibility, and debug/context-menu toggles.
- `warhammer40k_arcade_ui.state.finite_decision` — local finite-option focus, deterministic UI
  result-ID generation, UI-boundary no-submit diagnostics, status refresh, and viewer-scoped event
  cursor state.
- `warhammer40k_arcade_ui.state.movement_draft` — local-only per-model movement proposal draft
  state, request-scoped entity selection, model assignment groups, advisory measurement/hint
  generation, summary-friendly assignment rows, and JSON-safe payload preview construction that
  preserves engine-issued movement context and includes explicit no-op paths for unchanged models.
- `warhammer40k_arcade_ui.state.movement_submission` — local movement submission orchestration:
  deterministic result IDs, explicit request-ID preservation, UI-boundary stale/not-ready/unsupported
  diagnostics, parameterized movement payload submission, accepted-state auto-follow, viewer-scoped
  event refresh, and safe same-context retry handling.
- `warhammer40k_arcade_ui.state.entity_selection` — request-scoped entity refs, layer registry,
  profile builders, alias rules, local add/subtract/toggle state transitions, request drift
  reconciliation, and visual-anchor diagnostics for movement and finite unit-selection profiles.
- `warhammer40k_arcade_ui.input.commands` — preference-backed local hotkey matching.
- `warhammer40k_arcade_ui.hud.layouts` — configurable HUD zone/region geometry, Compass Ring and
  Command Bench presets, center-viewport preservation, and panel overflow line-capacity helpers.
- `warhammer40k_arcade_ui.hud.widgets` — lazy Arcade GUI placeholder widgets for drawing the active
  HUD zone shell in the live window without making non-window tests import `arcade.gui`.
- `warhammer40k_arcade_ui.hud.action_summary` — advisory action visual summary models and adapters
  derived from existing assignment workspaces and diagnostics, currently supporting movement paths
  and explicit unsupported diagnostics for future request families.
- `warhammer40k_arcade_ui.hud.composition` — YAML-backed HUD composition parser for reusable
  preview/runtime widget layouts.
- `warhammer40k_arcade_ui.hud.toolkit` — presentation-only HUD widget dataclasses and tunable
  attributes.
- `warhammer40k_arcade_ui.hud.toolkit_render` — render primitive conversion for HUD toolkit
  widgets.
- `warhammer40k_arcade_ui.hud.preview` — console-script preview runner for raw HUD composition YAML.
- `warhammer40k_arcade_ui.hud.view_models` — selected-unit panel, context menu, finite-decision
  panel, movement draft/diagnostic panel, generic assignment review HUD, and debug inspector view
  models derived from projection data and current pending requests.
- `scripts/check_import_boundaries.py` — repository quality script enforcing direct engine imports
  only from `core_client`.

Planned modules from later phases:

- `input` — later command flows beyond finite decisions and movement drafting.
- `hud` — real content widgets and later phase-specific ergonomics.
- `render` — future action visual summary primitives for source-to-target links, icons, and
  operation-specific summaries beyond movement.
- `state` — assignment workspaces and other local-only workflow state beyond movement drafts and
  entity selection.

## Shareable Preferences

Phase 4 pulled the preferences framework forward so portable hand-editable profiles are available
before selection, HUD, movement drafting, and ergonomics begin hard-coding workflow assumptions.
Profiles load and export as JSON and YAML. They are intended to be easy to pass between users and
control local presentation and input behavior:

- default overlays enabled when a model or unit is selected;
- default overlays enabled while movement drafting is active;
- hotkeys for toggling known overlays for the currently selected model or unit;
- hotkeys for showing selected model or selected unit information;
- HUD defaults, accessibility preferences, and debug/diagnostic panel defaults.

Preferences are versioned and validated against a typed schema. Unknown command IDs, unknown overlay
IDs, duplicate hotkeys, unsupported schema versions, and settings for unavailable features produce
typed config diagnostics instead of silently falling back. Config files must be portable by default;
machine-local paths or caches should live in a separate local override if those are ever needed.

Preferences can only select from registered UI commands and registered advisory overlays. A config
file cannot invent finite option IDs, proposal kinds, engine decisions, hidden visibility rules, or
authoritative validation behavior.

The schema includes an `experimental.planned_settings` section so users can encode and exchange
recognized upcoming behavior assumptions early. These settings round-trip through export, but remain
inactive until their implementing phase wires them to a registered UI command, overlay, HUD feature,
or local state behavior. Unknown settings outside an explicit experimental/extension section produce
typed diagnostics.

Built-in profiles are exported through:

```bash
uv run warhammer40k-export-preferences --format yaml
uv run warhammer40k-export-preferences --profile dense-debug --format json
```

## Selection and HUD State

Phase 5 adds local-only selection and inspection state. The UI can select a model base from a
viewer-scoped battlefield projection, derive the owning unit, cycle overlapping hits when configured
by preferences, render selected-unit/model overlays, and show a selected-unit panel. Context menu
actions are derived only from the current engine-provided finite options when the pending decision
payload targets the selected unit.

This phase remains display-only for decisions: no option is submitted until the finite decision
submission phase. Selection state, context menu anchors, and debug inspector visibility are local UI
state and do not mutate authoritative engine state.

## Finite Decision Submission

Phase 6 adds the first user-facing decision submission surface. The UI can highlight and submit one
engine-provided finite option for the current explicit `request_id`, generate deterministic
`ui-result-*` result IDs, refresh the pending request and viewer-scoped event cursor through the
`UiCoreClient`, and display invalid/stale diagnostics returned by the client boundary or engine.

The finite-decision HUD is generic. It does not assume movement-only decision types or option IDs.
Parameterized requests are displayed as requiring a proposal tool and the fixed
`submit_parameterized_payload` option is not exposed as a finite action. Movement payload drafting
and submission continue through the later movement drafting, assignment, and submission phases.

Tab now cycles finite-option focus when finite options are pending. Without finite options, Tab only
cycles an already selected overlapping model hit set; it no longer creates a selection from a merely
hovered model.

## Movement Path Drafting

Phase 7 adds the first movement-specific local workflow. When the current pending request is a
`submit_movement_proposal` parameterized request for the selected unit, the UI opens a local
movement draft. The draft records the proposal request ID, proposal kind, selected unit,
`movement_phase_action`, optional `movement_mode`, optional Fall Back `fall_back_mode`, source
decision IDs, anchor model poses, waypoints, cursor preview, and advisory hints.

The renderer displays active movement-path and movement-budget overlays in world space: path lines,
waypoints, endpoint preview, final ghost bases, and budget rings. The HUD displays proposal context,
segment and total measurements, remaining budget estimates, ready state, and preview-only warnings.

This phase prepared a JSON-safe movement payload preview, including `witness.model_paths` and
optional `model_movements`, but did not submit the parameterized request. Phase 8 and Phase 9
replace the unit-simple interaction with request-scoped entity selection and per-model movement
assignments before Phase 10 submits movement proposals to the engine.

## Entity Selection And Assignment Workspace

Phase 8 introduces the reusable entity-selection foundation for answering request-scoped engine
questions. In plain terms, the later workspace is temporary local scratch space for one pending
request: what entities are selected now, what has already been assigned, what remains incomplete,
and what payload preview is being assembled.

The workspace is separate from ordinary inspect selection. A player can inspect a model or unit
while the active request-selection state tracks the entities that will actually be used to answer
the current request. This prevents accidental behaviors such as moving every model merely because
one model was selected for inspection.

The first concrete use is movement. Phase 8 defines typed `EntityRef` values, active entity layers,
movement and finite unit-selection profiles, explicit alias rules such as model-to-unit, and
deterministic add/subtract/toggle transitions. Phase 9 wires that foundation into movement drafting
so selecting one model moves one model, selecting a subset moves that subset, and selecting the
whole unit must be an explicit action. Later shooting and Stratagem tools should reuse the same
selection and assignment foundation when the engine request exposes safe candidate metadata.

Phase 9's movement draft payload preview represents every model in the proposal unit. Models with
no drafted movement are encoded as explicit start/end no-op paths in both `witness.model_paths` and
`model_movements`; the UI does not omit unchanged models or submit the proposal in this phase.

Phase 10 submits that aggregate payload to the engine through the parameterized submission path. The
UI keeps `request_id` explicit, rejects stale/not-ready/unsupported movement submissions before
calling the client, displays authoritative `proposal_validation` diagnostics, and clears local draft
state only after a non-invalid engine response and refreshed projection. Rule-invalid movement can
reuse the last drafted paths only when the engine emits a fresh movement proposal request with the
same unit, proposal kind, source movement action IDs, movement action, `movement_mode`, and Fall
Back `fall_back_mode`.

Phase 11 adds the next bridge: an opt-in live-core smoke launch path that uses the real local
session for thin manual movement testing while keeping fake debug fixtures available for
deterministic UI tests.

Phases 12 through 15 pause feature growth to harden GUI testability and debug evidence. The UI
should gain an in-process Arcade event driver, headless render evidence, opt-in forensic UI/core
event tracing, and crash diagnostic bundles before the next broad interactive workflow is added.
These tools are diagnostic and testing infrastructure only; they do not create authoritative game
state or a private replay log.

The Generic Assignment HUD is the visible review surface for that workspace. It should show what
request is being answered, which entities are selected, which entities are assigned, which entities
are still unassigned, whether the payload preview is ready, and whether messages are local preview
hints or authoritative engine diagnostics.

Phase 18 adds a battlefield-level visual summary for the same workspace. If the assignment HUD is
the checklist, the visual summary is the map overlay: dim green/grey paths for movement, future red
source-to-target lines for shooting, and future Stratagem markers with lines to affected units. The
summary is togglable and preference-backed. A subdued summary may remain visible while working, and
a brighter review summary can appear when the player actively checks selections before submission.

## Runtime modes

- **Local in-process session** — initial wrapper implemented in `core_client`; later phases will
  bind live projections to render, selection, HUD, and decision workflows.
- **Future network session** — planned transport mode behind the same UI-facing client facade.
- **Future replay inspection mode** — planned read-only mode for inspecting engine replay/projection
  data without introducing a second mutation path.

## Decision flow

```text
GameViewPayload
  -> UI view models
  -> render and HUD controls
  -> user input
  -> FiniteOptionSubmission or ParameterizedSubmission
  -> engine validation
  -> refreshed projection, events, or diagnostics
```

The UI may preview proposed actions, but preview state is advisory only. Accepted state appears only
after the core engine returns an accepted result and a refreshed projection.

`LocalSessionClient` preserves explicit `request_id` values at the UI boundary. It rejects stale
request IDs before constructing engine `DecisionResult` objects, and accepted submissions still flow
through `FiniteOptionSubmission` or `ParameterizedSubmission` into
`GameLifecycle.submit_decision(...)`.

## Testing strategy

- Unit tests for immutable config and entry-point behavior.
- Protocol shape tests for request IDs, option IDs, proposal payloads, and diagnostic view models.
- Render-adjacent tests for camera coordinate transforms, zoom clamping, fixture view-model parsing,
  HUD primitive placement, and view-model-to-render-primitive generation.
- Preferences tests for JSON/YAML schema loading, deterministic default-profile export, hotkey
  conflict detection, future-facing inactive properties, command/overlay registry validation, config
  diagnostics, and documented example profiles.
- Pure state/HUD tests for selection hit detection, overlap cycling, preference-backed hotkeys,
  selected-unit panels, context menu derivation from pending finite decisions, finite decision
  submission state, debug inspector content, and selection overlay primitive generation.
- Pure movement draft tests for activation gates, waypoint transitions, payload preview shape,
  Fall Back mode preservation, and unsupported parameterized requests.
- Render/HUD tests for movement path primitives, ghost bases, movement budget overlays, and
  movement draft panel content.
- Request-scoped entity selection tests for model/unit aliasing, additive/subtractive selection,
  layer cycling, assignment workspaces, and request drift reconciliation.
- Assignment HUD tests for active/assigned/unassigned entity rows and preview-vs-engine diagnostic
  separation.
- Action visual summary tests for dim/review modes, summary view models, movement path overlays,
  request drift cleanup, and preference defaults.
- Manual validation checklists for user-facing graphical workflows because live GUI interaction is
  only partially automatable.
- Movement submission tests for exact request/payload/result-ID preservation, stale request
  rejection before client submission, unsupported parameterized request diagnostics, accepted draft
  clearing and auto-follow, invalid diagnostic display, same-context retry retargeting, and render
  projection model-position refresh.
- Static import-boundary checks to keep direct engine imports isolated to `core_client`.
- Coverage, packaging metadata, and golden regression fixture tests for CI hardening.

## Known deferred work

- Network transport.
- Replay inspector.
- Placement proposal tools for reserves, disembark, Rapid Ingress, and other
  `submit_placement_proposal` requests.
- Shooting declaration and ranged attack-resolution UI for `select_shooting_unit`,
  `select_shooting_type`, `submit_shooting_declaration`, `select_resolve_target_unit`,
  `select_attack_weapon_group`, defender allocation, save/damage, and reaction decisions.
- Charge HUD, fight HUD, and damage-allocation UI.
- Line-of-sight and cover visualization.
- 3D renderer or full asset loading.

## Decision log

- 2026-06-16: Decision Log Reset