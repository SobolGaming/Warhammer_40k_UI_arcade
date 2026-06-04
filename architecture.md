# Arcade UI Architecture Build Order

Last updated: 2026-06-03

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

Phases 0-6 are complete. Later phases are planned and linked to independently reviewable documents
under `docs/plans/`.

| Phase | Status | Purpose | Plan |
| --- | --- | --- | --- |
| 0 | Complete | Repository bootstrap and quality baseline | [phase-00](docs/plans/phase-00-repository-bootstrap.md) |
| 1 | Complete | Documentation foundation | [phase-01](docs/plans/phase-01-documentation-foundation.md) |
| 2 | Complete | Core client adapter layer | [phase-02](docs/plans/phase-02-core-client-adapter.md) |
| 3 | Complete | Arcade rendering foundation | [phase-03](docs/plans/phase-03-arcade-rendering-foundation.md) |
| 4 | Complete | Shareable UI preferences framework | [phase-04](docs/plans/phase-04-shareable-ui-preferences.md) |
| 5 | Complete | Selection and unit information HUD | [phase-05](docs/plans/phase-05-selection-unit-hud.md) |
| 6 | Complete | Finite decision submission | [phase-06](docs/plans/phase-06-finite-decision-submission.md) |
| 7 | Planned | Movement path drafting UI | [phase-07](docs/plans/phase-07-movement-path-drafting.md) |
| 8 | Planned | Movement proposal diagnostics | [phase-08](docs/plans/phase-08-movement-proposal-diagnostics.md) |
| 9 | Planned | HUD ergonomics pass | [phase-09](docs/plans/phase-09-hud-ergonomics.md) |
| 10 | Planned | Packaging, CI, and regression hardening | [phase-10](docs/plans/phase-10-packaging-ci-regression.md) |

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

Phases 0-6 provide the runnable shell, core client boundary, inspectable render foundation,
shareable UI preference framework, local selection/HUD state, and finite decision submission:

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
- `warhammer40k_arcade_ui.core_client.fake_client` — deterministic fake client for UI tests.
- `warhammer40k_arcade_ui.render.view_models` — read-only battlefield render view models parsed from
  deterministic fixture/projection payloads.
- `warhammer40k_arcade_ui.render.camera` — world-space camera, pan/zoom, and screen/world
  coordinate conversion.
- `warhammer40k_arcade_ui.render.primitives` — pure table, deployment-zone, objective, terrain,
  unit, model-base, and HUD primitive generation.
- `warhammer40k_arcade_ui.render.arcade_window` — `ArcadeWarhammerWindow` consuming render
  primitives for drawing, right/middle-drag panning, mouse-wheel zoom, and mouse coordinate display.
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
- `warhammer40k_arcade_ui.input.commands` — preference-backed local hotkey matching.
- `warhammer40k_arcade_ui.hud.view_models` — selected-unit panel, context menu, finite-decision
  panel, and debug inspector view models derived from projection data and current pending requests.

Planned modules from later phases:

- `input` — movement path tooling and later command flows.
- `hud` — movement workflow controls and later phase-specific ergonomics.
- `state` — movement drafts and other local-only workflow state.

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
and submission remain deferred to Phases 7 and 8.

Tab now cycles finite-option focus when finite options are pending. Without finite options, Tab only
cycles an already selected overlapping model hit set; it no longer creates a selection from a merely
hovered model.

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

## Movement flow target

The first rules-facing vertical slice will be movement:

```text
finite movement action selection
  -> movement proposal request
  -> path drafting
  -> PathWitness payload
  -> proposal submission
  -> accepted movement or authoritative invalid diagnostics
```

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
- Future pure state tests for movement draft transitions.
- Future static checks to keep direct engine imports isolated to `core_client`.

## Known deferred work

- Live projection-to-render-state integration for the local game session.
- Network transport.
- Replay inspector.
- Shooting HUD, charge HUD, fight HUD, and damage-allocation UI.
- Line-of-sight and cover visualization.
- 3D renderer or full asset loading.
- Import-boundary audit that enforces direct engine imports only from `core_client`.

## Decision log

- 2026-05-31: Phase 0 targets Python 3.14.5 to match the current core-engine workflow.
- 2026-05-31: Phase 0 starts with a blank Arcade window and no core-engine dependency. The
  engine-facing boundary will be introduced in Phase 2 through `core_client`.
- 2026-05-31: Phase 0 completed with a locked `uv` project, blank Arcade entry point, strict
  typing/linting configuration, pre-commit hooks, and bootstrap tests.
- 2026-05-31: Phase 1 completed with README and architecture documentation covering repository
  relationships, first-run commands, UI/core boundaries, runtime modes, roadmap links, and deferred
  work.
- 2026-06-03: Added an initial later-phase plan for shareable JSON/YAML UI preferences covering
  overlay defaults, hotkeys, selected-model/unit information affordances, and config diagnostics
  while preserving the engine-authoritative decision boundary.
- 2026-06-03: Phase 2 completed with a `core_client` protocol, local in-process session wrapper,
  fake UI client, explicit request-ID submission boundary, core dependency declaration, and tests
  covering pending decisions, movement proposal requests, invalid diagnostics, terminal status, and
  stale request rejection.
- 2026-06-03: Phase 3 completed with fixture-backed battlefield view models, pure render primitive
  generation, camera pan/zoom coordinate transforms, `ArcadeWarhammerWindow`, HUD/debug coordinate
  rendering, and tests for camera math plus fixture-to-primitive generation.
- 2026-06-03: Pulled the shareable preferences framework forward to Phase 4 so upcoming overlay,
  HUD, hotkey, and local behavior settings can be encoded, exported, swapped, and round-tripped
  before selection and movement workflows consume them.
- 2026-06-03: Phase 4 completed with a typed preferences package, JSON/YAML loaders and exporters,
  command/overlay/planned-setting registries, built-in default/dense-debug/keyboard-heavy profiles,
  documented example files, CLI export support, and tests covering schema diagnostics and
  round-trips.
- 2026-06-03: Phase 5 completed with local selection state, model-base hit detection, overlap
  cycling, selected-unit/model overlays, selected-unit panel view models, context menu display from
  engine-provided finite options, debug inspector view models, preference-backed hotkeys, and tests
  covering state, HUD derivation, and render primitives.
- 2026-06-03: Phase 6 completed with generic finite-decision focus/submission state, deterministic
  UI result IDs, explicit request/option ID submission through `UiCoreClient`, parameterized
  proposal display without finite submission, viewer-scoped event cursor refresh, visible
  diagnostics, and a Tab regression fix that prevents hover-only selection.
