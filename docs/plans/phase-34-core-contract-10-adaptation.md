# Phase 34: Core Contract 10.2 Adapter And Projection Adaptation

Status: Proposed

## Purpose

Move the UI from its currently documented core baseline to the current versioned adapter contract
without preserving private-session access, payload inference, or live-smoke state mutation.

This is a compatibility and architecture phase. It must restore the existing thin gameplay path on
the current core before later UI phases add more specialized interaction editors.

## Review Baseline

This plan was produced from a deep review on 2026-08-22 of:

- UI revision `03297efbfc0fe73b0dfecc7897f60c0340731803`;
- the UI's currently documented and locked core revision
  `f01293fb4d83249482ecee1c304e21f18e57055e`;
- current `Warhammer_40k_AI` revision
  `dbfcc3a99e9d560d1354506352a09d48ca555a94`;
- all core contract migrations from major 2 through major 10;
- `contracts/README.md`, `contracts/openapi.yaml`, canonical schemas and examples,
  `contracts/coordinate-system.md`, `docs/ADAPTER_DECISION_CONTRACT.md`, and the current shared
  adapter/session facade.

The current core is 230 commits ahead of the UI's locked revision. Its external contract bundle is
`10.2.0`, with the following UI-relevant public families:

- `game-view-v11-phase17n-step4`;
- `battlefield-view-v4-phase17n-step3`;
- `decision-request-view-v5-phase17n-step4`;
- `interaction-descriptor-v2-variants`;
- `lifecycle-status-v4-phase17n-step4`;
- `session-projection-v7-phase17n-step4`;
- `capability-manifest-v2-directed-primary` inside
  `support-profile-v4-directed-primary`.

The generated manifest currently covers 78 registered decision types, 13 interaction kinds, 90
interaction-conformance cases, 24 parameterized payload kinds, and 21 proposal kinds. The UI must
therefore adapt by contract family and interaction descriptor rather than maintain an independent
list of decision-type guesses.

## Confirmed Compatibility Failures

The review reproduced these failures against the current core source:

1. The UI lock does not contain the current core runtime dependencies `jsonschema` and
   `referencing`, so importing the current core fails before the application starts.
2. The live-smoke harness imports the removed
   `warhammer_event_companion_2026_06_mission_pack`; current core exposes the July 2026 package.
3. Parsing the current committed `post_deployment_view.json` contract example fails because
   `UiGameView` still requires the removed `event_count` member.
4. Focused UI tests continue to pass because they use pre-contract synthetic payloads and private
   queue state, so they do not currently prove compatibility with the installed core.
5. With the updated sibling core on the configured type-check path, `mypy` and `pyright` fail on
   the removed June mission-pack helper, newly required `MissionSetup.from_mission_pack(...)`
   arguments, and absent current dependency/type packages. The normal static gates therefore also
   expose the drift before runtime.

These are release-blocking compatibility failures, not optional feature gaps.

## Architectural Drift Requiring Adaptation

### Session boundary

`LocalSessionClient` currently inspects
`session.lifecycle.decision_controller.queue.pending_requests`, reads lifecycle state directly, and
submits through `session.lifecycle.submit_decision(...)`. Current core provides the shared
`AdapterGameSession` facade for local UI, CLI, headless, replay, and network producers, including:

- `start(...)` and `advance_until_decision_or_terminal()`;
- `view(...)` and `view_for_context(...)`;
- `rules_catalog_view()` and `support_profile()` (with viewer-safe redaction required before player
  display);
- `events_since(...)` and context-scoped event methods;
- `submit_option(...)` and `submit_parameterized_payload(...)`.

The UI must use those public methods and stop reconstructing queue-head validation or core
`DecisionResult` objects locally.

### Interaction dispatch

Every visible pending decision now carries an engine-authored interaction descriptor. The renderer
must be selected from `interaction_kind`; a submission must use an explicit
`submission_variant`, wrapper schema reference, and proposal schema reference. The UI must not
route from `decision_type`, display labels, arbitrary proposal keys, or a locally maintained rules
mapping.

The descriptor distinguishes:

- `finite_option_list`;
- `entity_selection`;
- `weapon_allocation_matrix`;
- `dice_selection`;
- `ordered_sequencing`;
- `battlefield_point_placement`;
- `model_pose_placement`;
- `multi_model_placement`;
- `path_editor`;
- `roster_construction`;
- `confirmation`;
- `quantity_selection`;
- `opportunity_window`.

Nested choices are now published in top-level `nested_interaction_requests`. Hidden decisions expose
`interaction: null` and no nested requests. The UI must preserve that visibility boundary.

### Projection and battlefield data

The current game view adds or formalizes:

- projection schema and projection-state hash;
- viewer role and viewer identity;
- a source-hashed rules-catalog reference;
- first-class `battlefield_view` authoritative, interaction, and render sections;
- grouped Primary Mission turn-start snapshots and public Primary progress state;
- nested interaction requests;
- expanded public unit/model display payloads.

The UI currently discards most of this data and rebuilds battlefield rendering primarily from
`mission_setup` plus `battlefield_state`. Phase 33's typed terrain-area bridge was correct for its
old baseline, but `battlefield_view` is now the canonical render-facing geometry contract. Its
`authoritative_geometry_hash` is informational; it must never replace the opaque
`spatial_context_hash` required by movement and placement proposals.

### Proposal coverage

Current core publishes 13 parameterized decision families:

- `submit_catalog_model_materialization_placement`;
- `submit_cult_ambush_marker_placement`;
- `submit_deployment_placement`;
- `submit_healing_revival_placement`;
- `submit_melee_declaration`;
- `submit_movement_proposal`;
- `submit_placement_proposal`;
- `submit_redeploy_placement`;
- `submit_return_on_death_placement`;
- `submit_scout_move`;
- `submit_scout_reserve_setup`;
- `submit_shooting_declaration`;
- `submit_stratagem_target_proposal`.

The current movement, placement, and assignment tools cover only a subset and select tools from
proposal/decision names. Contract 10 requires descriptor-driven selection and strict preservation
of the engine-owned spatial context.

### Mission and capability projection

The core now projects directed Primary Mission assignments, public Secondary card state, grouped
turn-start history, persistent Primary Mission progress, mission-action opportunities, public CP/VP
ledgers, and engine-enumerated Primary Mission finite choices. It also exposes a viewer-scoped
capability manifest with independent load, display, muster, physical, semantic, full-game, network,
and replay support dimensions.

The UI should display or retain these public facts and use capability results to explain unsupported
surfaces. Capability data is advisory support evidence, not rules authority.

## Goals

- Make the packaged UI start and run against core
  `dbfcc3a99e9d560d1354506352a09d48ca555a94` and contract bundle `10.2.0`.
- Replace private `GameLifecycle` and decision-queue access with the public adapter/session facade.
- Parse current projection, interaction, battlefield, rules-catalog, support-profile, status, and
  event payload families strictly.
- Drive generic and specialized UI tools from engine-authored interaction descriptors.
- Preserve engine-owned request IDs, option IDs, submission variants, schema references,
  `spatial_context_hash` values, viewer scoping, and projection identities.
- Restore deterministic live-core smoke coverage without mutating authoritative state from the UI.
- Add a CI gate that fails when the locked core and UI protocol fixtures drift apart.
- Update the lock and documented supported core SHA only after all acceptance tests pass.

## Non-Goals

- Implementing the formal HTTP server or a production network client.
- Implementing persistence administration, replay certification, authentication policy management,
  or optimistic-concurrency storage in the Arcade UI.
- Reimplementing core JSON Schema validation, legality, geometry tolerances, scoring, or capability
  certification in UI modules.
- Polishing every one of the 13 interaction kinds. Phase 34 must provide strict parsing, routing,
  generic finite handling where valid, and explicit unsupported diagnostics; specialized UX may
  remain in later numbered phases.
- Migrating old replay artifacts across contract majors.
- Editing `Warhammer_40k_AI` from this repository.

## Required Invariants

- The engine remains the only authority for state mutation, legality, scoring, visibility, event
  history, and replay.
- A visible interaction is rendered from `interaction_kind` and its descriptor. Missing or unknown
  metadata is a hard compatibility error, not a fallback to `decision_type`.
- Finite commands submit only the current engine-provided request and option IDs.
- Parameterized commands submit the current request ID and a body matching the selected
  engine-provided submission variant.
- Physical drafts preserve the exact current `spatial_context_hash`; drafts are discarded after a
  request change, projection-generation change, reconnect, or resynchronization.
- `authoritative_geometry_hash` is never used as submission authority.
- Hidden decisions, nested requests, support evidence, events, and diagnostics stay viewer-scoped.
- Render, HUD, input, and state modules consume UI DTOs. Only `core_client` may import approved core
  adapter/session APIs.
- Unsupported contract versions, schema discriminators, interaction kinds, and proposal variants
  produce copyable typed diagnostics before submission.

## Implementation Slices

### 1. Lock, dependency, and compatibility gate

- Point `uv.lock` at the reviewed core SHA and resolve the current core dependency graph, including
  `jsonschema` and `referencing`.
- Advance the CI `SUPPORTED_CORE_REVISION` with the lock and README so static analysis, tests, and
  packaging always inspect one declared baseline rather than mixing locked dependencies with core
  `main`.
- Add one central UI compatibility declaration containing the supported external-contract major and
  exact projection-family discriminators.
- Validate those discriminators before constructing runtime state.
- For a future network client, validate `server_contract_version`; for the local client, validate
  public projection/support-profile discriminators and the pinned package baseline.
- Emit a terminal, copyable startup diagnostic for an incompatible core instead of trying old
  payload fallbacks.
- Update README supported-core text only at phase closeout.

### 2. Contract-shaped UI protocol models

- Add strict UI DTOs for:
  - interaction descriptors, constraints, display hints, and submission variants;
  - annotated nested interaction requests;
  - projection identity and viewer context;
  - battlefield authoritative/interaction/render sections;
  - rules-catalog references and catalog display projections;
  - capability manifest/support profile;
  - Primary Mission history and progress projection fields needed by runtime/HUD consumers.
- Remove obsolete `UiGameView.event_count` parsing. Event position belongs to the event-stream
  cursor, not the game projection.
- Require current fields and exact known schema versions. Do not use permissive defaults to accept
  an older fixture.
- Keep unconsumed JSON only at an explicitly typed extension boundary; do not route behavior from
  it.

### 3. Public local-session client

- Type `LocalSessionClient.session` against `AdapterGameSession` where practical.
- Submit finite choices through `session.submit_option(...)`.
- Submit all parameterized bodies through `session.submit_parameterized_payload(...)`.
- Remove access to `session.lifecycle`, `decision_controller`, and `pending_requests` from production
  UI code.
- Stop reconstructing pending-request and queue-head validation in the UI. Render the engine's
  invalid status and refresh the viewer projection.
- Convert lifecycle results into minimal UI status data, then source the current decision and
  interaction from the viewer-scoped game projection.
- Extend `UiCoreClient`, `FakeClient`, trace wrappers, and test doubles with rules-catalog and
  support-profile reads.

### 4. Interaction-driven dispatch

- Introduce an interaction renderer/editor registry keyed only by `interaction_kind`.
- Route existing reusable surfaces as follows:
  - generic Current Action buttons for finite lists, confirmations, sequencing, entity choices,
    quantity choices, and minimally viable opportunity choices;
  - Dice Tray for `dice_selection`;
  - movement-family editor for `path_editor`;
  - placement editor for point, model-pose, and multi-model placement;
  - assignment editors for weapon-allocation matrices and supported declaration workflows.
- Use `display_hints.confirm_label` and `decline_label` rather than hard-coded action labels.
- Select an explicit engine-published submission variant and satisfy its `required_inputs`.
- Parse and retain all nested interaction requests, and display only those visible in the current
  viewer projection.
- Add a typed unsupported-interaction state for a valid but not-yet-implemented specialized editor.
  It must identify the interaction kind and required inputs and must not submit guessed data.

### 5. Canonical battlefield projection

- Make `battlefield_view` the primary source for table bounds, model geometry and state, terrain,
  objectives, deployment zones/regions, interaction overlays, and hit/render hints.
- Preserve world coordinates exactly as
  `battlefield_inches_right_handed_z_up`; keep screen/camera transforms presentation-only.
- Render physical terrain polygons independently while retaining `logical_terrain_area_id` for
  grouping and inspection.
- Render model measurement geometry and support bases distinctly; never derive rules geometry from
  sprites or hit regions.
- Keep `mission_setup` for mission identity and supporting display metadata, not duplicate physical
  geometry ownership.
- Retire the Phase 33 mission-setup terrain bridge after parity tests prove the canonical
  battlefield path. Do not silently retain two competing geometry sources.

### 6. Physical proposal context and family coverage

- Add `spatial_context_hash` to strict movement and placement request DTOs and carry it unchanged
  into the submitted proposal body required by the active schema variant.
- Bind every local draft to request ID, interaction variant, spatial-context hash, and projection
  generation/hash; invalidate it when any binding changes.
- Route all current parameterized families through descriptor metadata.
- Extend placement support for catalog model materialization, Cult Ambush point/marker placement,
  healing revival model-pose placement, and return-on-death placement.
- Preserve the existing movement, scout, deployment/redeploy, shooting, melee, and stratagem
  editors where their generated bodies match the current proposal schema.
- Surface engine invalid diagnostics without clearing or mutating authoritative state locally.

### 7. Rules catalog, support profile, and mission state

- Fetch and cache the rules catalog by its engine-provided identity/hash so HUD details use public
  source-backed display data rather than labels inferred from IDs.
- Obtain a viewer-safe support profile through an approved core redaction/context API and expose
  unsupported capability reasons in diagnostics and review tooling. The raw local
  `session.support_profile()` result is administrative data and must not be sent directly to a
  player HUD.
- Retain and project public Secondary choices/card states, directed Primary assignments, grouped
  turn-start snapshots, Primary progress markers/designations/choices, CP/VP ledgers, and Stratagem
  use records.
- Route `select_primary_mission_choice` and current mission-action choices through descriptor-driven
  generic finite UI.
- Do not calculate mission eligibility, Objective Control, or VP in the UI.

### 8. Live-core smoke rebuild

- Replace the removed June mission-pack import with the current public canonical setup/pre-battle
  smoke fixture.
- Remove `_nudge_live_smoke_monster_for_movement_bridge` and every direct
  `replace_battlefield_state(...)` or equivalent authoritative mutation.
- Remove UI-side geometry grafting when the current core fixture already publishes canonical
  mission and battlefield geometry.
- Reach setup, deployment, Scout, movement, shooting, charge, and fight checkpoints only by public
  adapter decisions or a core-owned fixture configuration.
- Keep `--stop-at-phase` deterministic and fail with a typed harness diagnostic when a requested
  checkpoint cannot be reached through valid core decisions.
- Verify both player perspectives and actor transitions without leaking the prior player's hidden
  projection.

### 9. Event cursor, tracing, and future transport seam

- Keep event position in a dedicated UI cursor abstraction sourced from `UiEventDelta.next_cursor`.
- Preserve integer in-process cursors now while allowing a future network implementation to hold an
  opaque protected cursor without changing render/HUD code.
- Reset projection-bound drafts and replace projection state after a future resync response; do not
  merge stale physical state.
- Include contract schema versions, projection hash, interaction kind/variant, request ID, and
  spatial-context hash in forensic traces where viewer-safe.
- Never record hidden nested requests or redacted catalog/support data.

### 10. Conformance tests and documentation closeout

- Replace permissive synthetic game-view fixtures with current contract-shaped fixtures.
- Add a compatibility test that parses representative committed core projection, decision,
  interaction, battlefield, status, event, support-profile, and proposal examples.
- Exercise all 90 current interaction-conformance cases at the parser/dispatch level. An editor may
  report a typed unsupported state, but no known valid descriptor may be misclassified or parsed by
  fallback.
- Add import-boundary tests proving production UI code does not access `session.lifecycle`, core
  decision queues, or mutable engine state.
- Run deterministic fake-client and real-local-session flows through the same `UiCoreClient`
  surface.
- Update `README.md`, `architecture.md`, `ui_and_core_features_summary.md`, and this plan's progress
  notes after implementation.
- Move the plan to `docs/plans/finished/` only after the lock and README identify the exact tested
  core SHA and all CI/manual gates pass.

## Acceptance Criteria

- A clean `uv sync --locked --all-groups` installs the current pinned core and all required runtime
  dependencies.
- The UI starts against core `dbfcc3a99e9d560d1354506352a09d48ca555a94` without the June
  mission-pack import error or obsolete `event_count` parser error.
- `LocalSessionClient` production code contains no direct lifecycle, pending-queue, or mutable-state
  access.
- Current core game-view and interaction-conformance fixtures parse strictly with exact schema
  discriminators.
- Current finite decisions and supported parameterized workflows dispatch from
  `interaction_kind` and an explicit submission variant.
- Unknown/malformed descriptors and unsupported valid editor kinds fail visibly before submission;
  they never fall back to decision-name inference.
- Movement and placement submissions preserve the current opaque `spatial_context_hash`, and stale
  drafts are rejected locally before they can target a new request.
- Battlefield rendering uses the first-class battlefield projection and passes geometry parity and
  headless render-evidence checks.
- Rules-catalog, capability, public mission, CP/VP, and display data remain viewer-scoped and
  available to runtime/HUD view models.
- Live smoke reaches its supported checkpoints without UI-owned authoritative mutation.
- The README and lock agree on the exact supported core revision.
- CI checks out that same supported revision for both quality and test jobs.

## Automated Verification

Add focused gates for:

- current core import and locked dependency completeness;
- exact contract/schema-version rejection and acceptance;
- current game-view, battlefield, lifecycle-status, event-delta, rules-catalog, support-profile, and
  interaction fixture parsing;
- all interaction kinds and submission variants in the conformance inventory;
- public adapter submission and stale-request diagnostics;
- spatial-context preservation and draft invalidation;
- nested interaction visibility/redaction;
- canonical battlefield projection and framebuffer evidence;
- current live-smoke startup and stop-point progression;
- forbidden private core imports and attribute access.

Run the normal gates:

```bash
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pyright
uv run pytest tests/
uv run pre-commit run --all-files
```

## Manual Validation Checklist

Use payload tracing and the packaged default preferences for each run.

- Launch from earliest setup and verify both player perspectives can complete visible finite setup
  choices.
- Stop at deployment and complete one placement for each player.
- Continue through Scout setup/movement and confirm the path editor is selected from the descriptor.
- Stop at movement and submit normal, Advance, and no-op model paths.
- Enter shooting and verify assignment/weapon-allocation interactions either open the correct editor
  or show a precise unsupported-interaction diagnostic.
- Trigger a dice, sequencing, confirmation, and opportunity interaction and verify the generic
  surface uses engine labels and option IDs.
- Inspect terrain, deployment zones, objectives, model hull/base geometry, and interaction overlays
  for parity with the core battlefield projection.
- Switch viewer/actor context and verify hidden requests, nested interactions, and support evidence
  do not leak.
- Intentionally run against an incompatible core revision and confirm startup exits with a
  copyable contract-version diagnostic.

## Reviewer Notes

Review this phase primarily as a trust-boundary migration. The highest-risk mistakes would be
retaining private lifecycle access, accepting incomplete old payloads, routing from decision names,
using viewer geometry hashes as proposal authority, or letting the live-smoke harness mutate core
state. A visually working flow is not sufficient unless the contract examples and public facade are
also the paths exercised by tests.
