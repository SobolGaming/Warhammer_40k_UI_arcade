# Proposal - Entity selection and assignment workspace

## Status

Accepted as roadmap direction and split into concrete phase plans.

Concrete phases:

- [Phase 8 - Entity selection profile foundation](phase-08-entity-selection-profile-foundation.md)
- [Phase 9 - Movement draft model assignments](phase-09-movement-draft-model-assignments.md)
- [Phase 10 - Movement proposal submission and diagnostics](phase-10-movement-proposal-submission-diagnostics.md)
- [Phase 11 - Generic assignment HUD](phase-11-generic-assignment-hud.md)

Preliminary future plans:

- [Preliminary - Shooting declaration assignment tool](preliminary-shooting-declaration-assignment-tool.md)
- [Preliminary - Stratagem target-binding assignment tool](preliminary-stratagem-target-binding-tool.md)

## Goal

Create a reusable UI mechanism for selecting, grouping, and assigning entities to request-scoped
operations without creating a private rules path.

This proposal addresses movement first, but the design should also support later shooting
declarations, Stratagem target binding, model allocation choices, and other mechanics where the
engine allows multiple entities to be chosen or assigned in one answer.

## Plain-Language Summary

The workspace is temporary scratch space for answering one engine request.

Imagine the engine asks, "Where does this unit move?" The workspace is the tray where the player
places the pieces of that answer before sending it:

- these models are selected right now;
- these models already have paths;
- these other models do not have paths yet;
- this is the payload preview that will be submitted when ready.

When the engine asks a different question, the old tray is cleared or rebuilt. The workspace never
changes the game by itself. It only helps the player assemble a clear answer for the engine.

The Generic Assignment HUD is the visible checklist for that workspace. It should answer ordinary
player questions:

- What request am I answering?
- What have I selected?
- What have I already assigned?
- What still needs a choice?
- Is this ready to submit?
- Are these warnings only local preview hints, or are they authoritative engine diagnostics?

The same checklist idea should work for movement first, then later for shooting and Stratagems.
Movement might show "model 1 has path A, model 2 has path B, model 3 is unassigned." Shooting might
show "these weapons target that unit, those weapons target another unit." A Stratagem might show
"friendly target slot has two units, enemy target slot is still empty."

## Problem Statement

The current Phase 7 movement draft uses a unit-simple mode: once a movement proposal is active,
clicking a path waypoint translates every model in the selected unit together. That is useful as a
temporary smoke-test interaction, but it is not the desired movement behavior.

Warhammer movement is model-specific. A movement proposal can include individual model paths as long
as the final submitted proposal satisfies engine-owned rules such as movement budgets, coherency,
engagement range, terrain, and any source-specific restrictions. The UI should therefore let the
player select one model, several models, or all models in the unit, draft paths for that subset, and
accumulate those paths into one movement proposal.

The same class of problem appears outside movement:

- assigning some models in a shooting unit to one enemy target and other models to another target;
- selecting multiple friendly or enemy units for a Stratagem target policy;
- choosing model groups, allocation groups, attached-unit components, or other entities when the
  current engine request exposes those as valid choices;
- progressing through chained follow-up requests after accepted movement, shooting, placement,
  Stratagem, destruction-reaction, or reactive-movement choices.

## Contract Assessment

Reviewed against `Warhammer_40k_AI` local checkout on 2026-06-04.

### Movement

The current core movement proposal contract supports independent model paths. The submitted payload
contains a `witness.model_paths` array keyed by model ID, and `MovementProposalPayload` accepts
optional `model_movements`.

That means the current all-model translation behavior is a UI limitation, not a core-contract
restriction. The UI can draft per-model paths and submit them as one aggregate movement proposal as
long as it preserves the pending request context:

- `proposal_request_id`
- `proposal_kind`
- `unit_instance_id`
- `movement_phase_action`
- optional `movement_mode`
- optional Fall Back `fall_back_mode`
- `PathWitness` model IDs and poses

The engine remains responsible for rejecting invalid movement, coherency, terrain, budget,
engagement, Fall Back, and mode-context violations.

### Shooting

The shooting declaration contract is compatible with the same assignment concept, but the UI must
use the shooting proposal request data rather than infer targets locally. Current request payloads
describe:

- the acting unit;
- `available_weapons`, including model ID, wargear ID, weapon profile ID, and optional Firing Deck
  source identity;
- `target_candidates`, including target unit IDs, legality/diagnostics, visibility and range
  evidence, allowed shooting types, and targeting rule IDs.

The UI can support per-model or per-weapon target assignment once it has a shooting declaration tool
that builds the engine's `ShootingDeclarationProposal` shape. It must not invent targets, shooting
types, visibility evidence, or weapon/profile IDs.

### Stratagems And Other Target Binding

Finite `use_stratagem` options are already fully engine-bound choices. If a Stratagem target set is
fully enumerated as finite options, the UI can display those options but cannot decompose or edit
their target bindings unless the engine exposes a parameterized target proposal.

Parameterized `submit_stratagem_target_proposal` requests can use this workspace only when the
request payload exposes enough target-binding metadata for the UI to know:

- target roles or slots;
- valid entity kinds per slot;
- min/max counts;
- candidate IDs or candidate filters safe for the viewer;
- whether additive selection is allowed;
- whether multiple roles can be selected in parallel.

If that metadata is absent, the UI should display an unsupported target-binding tool state and the
core adapter contract should be extended before implementation.

### Chained Effects And Follow-Up Requests

The current engine contract supports chained resolution through lifecycle-owned pending decisions,
reaction windows, proposal requests, event deltas, and parent-resume behavior. The GUI can
automatically follow the chain by refreshing events and advancing to the next pending request after a
submission.

The GUI must not automatically choose player-facing options unless the engine itself has already
auto-resolved a forced outcome. "Automatic cycling" should mean:

- submit the user's accepted answer;
- refresh viewer-scoped events/projection;
- call the client lifecycle until the next pending decision or terminal status;
- focus the next request and load the appropriate finite, movement, shooting, placement, or
  target-binding tool;
- show waiting/interrupt context when the next actor is not the current viewer.

## Design Principles

1. **Request-scoped selection.** Entity selections and assignments belong to the current pending
   request or proposal request. They are cleared or reconciled when request ID, actor, proposal kind,
   unit, movement mode, Fall Back mode, visibility cache, or relevant source context changes.
2. **Engine-described candidates.** The workspace selects from projected entities and
   request-provided candidates. It must not create legal target sets or rule exceptions locally.
3. **Aliasing is explicit.** Clicking a model may select that model's unit when the current request
   asks for units, but only because the active selection profile allows that alias.
4. **Layers are UI lenses, not rules.** Model, model-group, unit, attached-unit, bodyguard,
   character, and army layers are ways to navigate and visualize candidates. They do not change what
   the engine request accepts.
5. **Batch operations produce aggregate payloads.** Movement can draft multiple model paths before
   one movement proposal submission. Shooting can build multiple weapon declarations before one
   shooting declaration submission. Stratagem targeting can fill multiple target slots before one
   target-binding submission when the engine request supports it.
6. **Local diagnostics are advisory.** Measurement, completeness, duplicate assignment, and
   "not yet assigned" warnings are UI hints. Engine diagnostics are authoritative.
7. **Viewer-scoped only.** Candidate extraction, entity relationships, event following, and
   diagnostics must not leak hidden information.

## Proposed Architecture

### EntityRef

Introduce a stable UI-local reference type that can identify projected/selectable objects without
turning Arcade render objects into game objects:

```text
EntityRef
  kind: model | model_group | unit | attached_unit | army | objective | terrain | card | dice | custom
  id: stable engine/projection ID
  owner_player_id: optional viewer-safe owner
  parent_refs: optional tuple[EntityRef]
```

`EntityRef` is not authoritative state. It is a typed pointer into the current viewer projection or
the current request payload.

### EntityLayer

Define selection layers as ordered UI lenses:

- `model`
- `model_group`
- `unit`
- `attached_unit`
- `army`
- future request-specific layers such as allocation group, weapon group, objective, card, dice, or
  Stratagem target role

Each layer has deterministic ordering and cycling behavior. Layer availability comes from the
current selection profile, not from global UI state.

### EntitySelectionProfile

Build a request-scoped profile from the current `UiDecision` or parameterized proposal request:

```text
EntitySelectionProfile
  request_id
  decision_type
  actor_id
  source_context_hash
  selectable_layers
  active_layer
  candidate_refs
  alias_rules
  cardinality
  additive_allowed
  subtractive_allowed
  assignment_slots
  unsupported_reason
```

Examples:

- `select_movement_unit`: unit layer only; model click may alias to owning unit.
- `submit_movement_proposal`: model and unit layers within the proposal unit; unit selection aliases
  to all current models in that unit for draft assignment.
- `submit_shooting_declaration`: attacker model/weapon assignment slots and target-unit candidates
  from the proposal request.
- `submit_stratagem_target_proposal`: only supported when target-binding metadata exposes slots,
  candidate entity kinds, and cardinality.
- `select_damage_allocation_model`: model layer only within the current allocation group.

### EntitySelectionState

Add a cross-cutting local state module for request-scoped selection:

```text
EntitySelectionState
  profile
  selected_refs
  active_layer
  active_group_key
  focus_ref
  selection_order
  diagnostics
```

Core operations:

- replace selection;
- add selection;
- subtract selection;
- toggle selection;
- clear selection;
- cycle entity within current layer;
- cycle active layer;
- expand alias if the profile permits it;
- reconcile selected refs with a refreshed projection/request.

This state should remain separate from the existing general inspect selection until the model is
proven. The existing selected-unit/model panel can continue to show inspection state, while the new
workspace owns request-answer selections.

### EntityAssignmentWorkspace

Add a reusable aggregate workspace for operations where selected entities are assigned to outcomes:

```text
EntityAssignmentWorkspace
  request_id
  operation_kind: movement | shooting_declaration | stratagem_target_binding | placement | custom
  assignments
  active_assignment_group
  completeness_hints
  payload_preview
```

Assignments are operation-specific but use the same selection mechanics:

- movement: model refs -> model path drafts;
- shooting: attacker model/weapon refs -> target unit ref and shooting type;
- Stratagem target binding: target role -> selected unit/model/objective refs;
- placement: model refs -> final poses;
- allocation/damage: current group ref -> selected model ref, when the engine exposes a choice.

Payload builders live in operation-specific modules so the generic workspace does not learn
movement, shooting, or Stratagem rules.

## Input Model

Use preference-backed bindings, with defaults to be reviewed:

- primary click: replace selection at the active layer;
- Shift + primary click: add entity or alias expansion to current selection;
- Ctrl + primary click: remove entity from current selection;
- Shift + Ctrl + primary click: toggle membership;
- Tab / Shift+Tab: cycle focus within the current layer when finite-option focus is not active;
- layer-cycle hotkey: move model -> group -> unit -> attached-unit, filtered to layers allowed by
  the active profile;
- "select group" command: expand the current entity to its allowed group at the active or next layer;
- Escape: clear active request-selection or cancel the current draft, depending on workspace state.

The exact default hotkeys should be finalized with the preferences schema so users can swap input
styles without changing rules behavior.

## Movement-Specific Revision

Replace Phase 7's `unit_simple` movement draft behavior with a model-assignment workflow:

1. A movement proposal for a selected unit creates a movement workspace.
2. The default active layer is `model`, seeded with the currently selected model.
3. Adding waypoints affects only the active selected model subset.
4. Shift-click can add additional models from the same proposal unit to the active subset.
5. A unit-layer selection or "select all models in unit" command can intentionally assign the same
   path transform to all models in the proposal unit.
6. Each model path is stored independently.
7. The aggregate payload preview includes all drafted model paths in `witness.model_paths`.
8. The UI displays completeness hints for models in the proposal unit that have no path or only an
   unchanged start pose.
9. The UI may show advisory budget/coherency/table-bound hints, but only the engine validates.
10. Phase 10 movement submission should not proceed until this aggregate path model replaces the
    current all-model synchronized movement behavior.

Open implementation detail: decide whether unchanged models must be explicitly represented with a
start/end no-op path or omitted from `model_movements`. The `PathWitness` itself must remain
compatible with the engine's current required witness shape.

## Shooting-Specific Future Use

When the shooting declaration tool is implemented, the workspace should support:

- selecting attacker models or model weapon rows from `available_weapons`;
- additively assigning multiple selected weapons/models to the same target unit;
- assigning different subsets to different target units;
- preserving engine-issued weapon IDs, profile IDs, shooting type tokens, Firing Deck source
  identity, visibility cache keys, and target candidate IDs;
- building the exact `ShootingDeclarationProposal` payload;
- showing unsupported states when the request lacks enough candidate metadata.

## Stratagem-Specific Future Use

When the engine emits parameterized target-binding metadata, the workspace should support:

- role-based target slots such as friendly unit, enemy unit, objective, model, card, or dice;
- min/max cardinality per role;
- additive and subtractive selection within a role;
- multi-role review before payload submission;
- target aliasing, such as model click -> owning unit, only when the role allows unit targets;
- visible diagnostics for incomplete or unsupported roles.

If the engine emits fully bound finite Stratagem options instead, the UI should keep using finite
option selection and should not decompose those bindings into editable local target sets.

## Chained Resolution Navigation

Add an "auto-follow lifecycle chain" behavior after successful submissions:

1. Submit through the current explicit `request_id`.
2. Refresh viewer-scoped events and projection.
3. Advance the client until the next pending decision or terminal status.
4. Build a new selection profile/workspace for the new pending request.
5. Focus the relevant HUD/tool:
   - finite option panel;
   - movement draft workspace;
   - placement tool;
   - shooting declaration tool;
   - Stratagem target-binding tool;
   - waiting/opponent-action panel.
6. Keep a visible chain breadcrumb using engine event/request context when available.

This is compatible with reaction windows and chained side effects as long as the UI follows emitted
requests and does not choose answers locally.

## Implementation Map

### Phase 8 - Selection Profile And EntityRef Foundation

- Add typed `EntityRef`, `EntityLayer`, `EntitySelectionProfile`, and `EntitySelectionState`.
- Build profiles for current known request families:
  - selected-unit inspection fallback;
  - finite unit-selection requests;
  - movement proposal requests;
  - unsupported parameterized requests.
- Add deterministic selection/cycling tests.
- Add preference-backed hotkey IDs for additive/subtractive selection and layer cycling.

### Phase 9 - Movement Draft Refactor

- Replace synchronized all-model movement with independent model-path assignment.
- Support selected subset movement, additive model selection, unit-layer select-all, path removal,
  and aggregate payload preview.
- Preserve all existing Phase 7 movement context invariants.
- Add tests for one-model path, subset path, all-model path, removing a subset path, and payload
  generation with independent model paths.

### Phase 10 - Movement Submission

- Resume movement proposal submission after Phase 9.
- Submit the aggregate movement payload through the explicit request ID.
- Display authoritative invalid diagnostics.
- Retain/reconcile draft paths only when the fresh proposal context still matches.

### Phase 11 - Generic Assignment HUD

- Add a compact assignment review panel showing selected layer, selected refs, assigned refs,
  unassigned refs, and request context.
- Add render primitives for multi-selection highlights that distinguish inspect selection,
  request-selection, active assignment group, and assigned-but-not-active groups.

### Preliminary - Shooting Declaration Tool

- Consume `submit_shooting_declaration` requests.
- Build model/weapon-to-target assignments from `available_weapons` and `target_candidates`.
- Generate `ShootingDeclarationProposal` payload previews.
- Submit through the same parameterized path in the later shooting phase.

### Preliminary - Stratagem Target-Binding Tool

- Consume `submit_stratagem_target_proposal` only when the request exposes enough role/candidate
  metadata.
- If needed, prepare a core contract update that standardizes target-binding metadata for UI,
  network, headless, and replay adapters.

## Tests

Add deterministic tests before live GUI validation:

- selection profile construction for known request types;
- model-click aliasing to unit for unit-only requests;
- layer cycling with unavailable layers filtered out;
- additive/subtractive/toggle selection order;
- request ID drift clears or reconciles request-scoped selections;
- movement subset drafting and aggregate payload shape;
- shooting request fixture conversion into candidate refs;
- unsupported parameterized request diagnostics;
- chained-resolution state refresh after accepted fake-client submissions.

## Manual Validation Checklist

After implementation, provide manual checks for:

- selecting one model and moving only that model;
- Shift-selecting two models and moving only those models;
- selecting the whole unit intentionally and moving all models;
- drafting separate paths for different model subsets in one unit;
- confirming the movement payload preview includes independent model paths;
- canceling and clearing request-scoped selection without clearing ordinary inspect selection;
- cycling model -> unit -> attached-unit/bodyguard/character layers when fixture data supports it;
- following a fake chained decision after a submitted action.

## Open Questions For Review

- Should ordinary click during a movement proposal replace the active model subset, or should it
  select for inspection unless a movement-tool mode is explicitly active?
- What should the default layer-cycle hotkeys be, given Tab already has finite-option focus behavior?
- Should "select unit" during movement mean all current models in that proposal unit, or should
  there be a distinct "select all models in unit" command to avoid accidental all-model movement?
- Does the core projection currently expose enough attached-unit/bodyguard/leader relationship
  metadata for UI layer cycling, or do we need a projection enhancement?
- Do Stratagem target-binding proposal requests need a standardized `target_schema` /
  `target_slots` payload before the UI can support additive multi-target binding?
- For movement payloads, should unchanged models be represented as explicit no-op paths for witness
  completeness, or omitted from `model_movements` while still present in `witness.model_paths`?
- Should chain auto-follow be always enabled, or preference-controlled for users who want to inspect
  each accepted event before the next request takes focus?
