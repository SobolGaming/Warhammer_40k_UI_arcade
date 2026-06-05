# Phase 8 - Entity selection profile foundation

## Goal

Build the reusable request-scoped entity selection foundation that future movement, shooting,
placement, Stratagem, allocation, and damage workflows can share.

In plain language: this phase teaches the UI what the current engine request is asking the player
to pick. Sometimes clicking a model should mean "this exact model." Sometimes it should mean "the
unit this model belongs to." Sometimes it should mean "one item in a larger group." This phase does
not answer the engine request by itself. It creates the local selection vocabulary and state so the
right later tool can answer the engine request without guessing.

## Why This Comes Before Movement Submission

The current movement draft can accidentally imply that all models in the selected unit move
together. That is not a safe interaction to submit to the engine. Movement submission should wait
until the UI can distinguish:

- ordinary inspection selection;
- request-answer selection;
- one selected model;
- multiple selected models;
- an intentionally selected whole unit;
- the group of entities that will receive the next assignment.

## Contract Review Notes

Reviewed against the local `Warhammer_40k_AI` checkout on 2026-06-04.

- Movement proposals already support independent per-model `PathWitness` entries. This phase does
  not require a core movement contract change.
- Existing finite requests already provide engine-owned option IDs. The entity-selection layer must
  never invent finite option IDs.
- `submit_shooting_declaration` and `submit_stratagem_target_proposal` can use this foundation
  later, but this phase should only build generic request-profile mechanics and movement-relevant
  profiles.
- Attached-unit, bodyguard, and character layer support may require richer projection metadata
  later. This phase may define those layers but should surface unavailable-layer diagnostics rather
  than fabricating relationships.
- All entity refs must be viewer-scoped and derived from the current projection or current pending
  request payload.

## Concepts

### EntityRef

An `EntityRef` is a small local pointer to something the user can select or assign:

- a model;
- a unit;
- a group of models;
- an attached unit;
- an objective;
- a future request-specific thing such as a weapon row, allocation group, card, or dice result.

It is not a game object and it is not authoritative state. It only says, "the current viewer
projection or request payload contains this selectable thing."

### Selection Profile

An `EntitySelectionProfile` describes what kind of selection is valid for the current request. For
example:

- a unit-selection request allows units;
- a movement proposal allows models in the moving unit and optionally a unit alias for all models;
- a damage-allocation request may allow only models in the current allocation group;
- an unsupported proposal exposes no usable selection profile and gives a clear diagnostic.

### Request-Scoped Selection

Request-scoped selection is separate from ordinary inspect selection. The player can still inspect a
model or unit, while the active request-selection state tracks what will be used to build the
current answer.

## Tasks

- [ ] Add a typed `EntityRef` model:
  - entity kind;
  - stable ID;
  - optional owner player ID;
  - optional parent refs;
  - optional display label.
- [ ] Add an `EntityLayer` registry:
  - model;
  - model group;
  - unit;
  - attached unit;
  - army;
  - objective;
  - request-specific custom layers.
- [ ] Add `EntitySelectionProfile`:
  - request ID;
  - decision type;
  - actor ID;
  - selectable layers;
  - active layer;
  - candidate refs;
  - alias rules;
  - cardinality;
  - additive/subtractive support;
  - unsupported reason.
- [ ] Add `EntitySelectionState`:
  - selected refs;
  - focused ref;
  - active layer;
  - deterministic selection order;
  - diagnostics.
- [ ] Add profile builders for current UI-supported request families:
  - no pending request / inspection fallback;
  - finite unit-selection style requests, when candidate IDs can be read from payload/options;
  - `submit_movement_proposal`;
  - unsupported parameterized requests.
- [ ] Add selection operations:
  - replace;
  - add;
  - subtract;
  - toggle;
  - clear;
  - cycle within active layer;
  - cycle active layer;
  - apply allowed alias rules.
- [ ] Add preference-backed command IDs and default bindings for additive/subtractive/layer actions:
  - add selection;
  - subtract selection;
  - toggle selection;
  - cycle entity layer;
  - select current group / expand selection.
- [ ] Keep existing ordinary selection state intact for inspection and selected-unit panels.
- [ ] Add visible diagnostics for:
  - unsupported request profiles;
  - unavailable entity layers;
  - candidate IDs that no longer exist in the refreshed projection;
  - selection cardinality violations.

## Acceptance Criteria

- [ ] A model click can select the model itself when the active profile allows model selection.
- [ ] A model click can alias to its owning unit when the active profile asks for units and allows
  that alias.
- [ ] Additive, subtractive, and toggle selection are deterministic and preserve stable ordering.
- [ ] Layer cycling only visits layers allowed by the current profile.
- [ ] Request-scoped selections clear or reconcile when the pending request ID changes.
- [ ] Unsupported parameterized requests produce typed UI diagnostics rather than pretending to be
  movement or shooting tools.
- [ ] Existing inspect selection and selected-unit HUD behavior keep working.
- [ ] Preferences can bind the new selection commands without defining legal actions or rules.

## Tests

- [ ] Unit tests for `EntityRef` validation.
- [ ] Unit tests for profile construction from movement proposal fixtures.
- [ ] Unit tests for unsupported parameterized request profiles.
- [ ] Unit tests for replace/add/subtract/toggle selection transitions.
- [ ] Unit tests for model-to-unit aliasing when allowed.
- [ ] Unit tests for rejecting aliasing when not allowed.
- [ ] Unit tests for layer cycling with unavailable layers filtered out.
- [ ] Regression tests that Tab still prioritizes finite-option focus when finite options are
  pending.
- [ ] Preference tests for the new command IDs and hotkey conflict diagnostics.

## Manual Validation Checklist

- [ ] Start the Phase 7/8 debug fixture.
- [ ] Select a model for ordinary inspection and confirm the selected-unit panel still behaves.
- [ ] Enter a movement proposal and confirm the request-scoped selection highlights the active
  model separately from the ordinary inspection highlight.
- [ ] Shift-click another model in the same unit and confirm both are selected for the active
  request.
- [ ] Remove one model from request selection and confirm ordinary inspection does not reset.
- [ ] Cycle model -> unit layer and confirm the visible request-selection state changes.
- [ ] Open an unsupported parameterized request fixture and confirm it displays as unsupported.

## Closeout Milestone

**Milestone 8: "Entity Selection Foundation"**

The UI has a reusable, request-scoped way to select and group engine-projected entities without
answering requests or implementing rules locally.
