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

- [x] Add a typed `EntityRef` model:
  - entity kind;
  - stable ID;
  - optional owner player ID;
  - optional parent refs;
  - optional display label;
  - optional visual anchor point when the current projection/request exposes one;
  - typed diagnostic when no safe visual anchor exists.
- [x] Add an `EntityLayer` registry:
  - model;
  - model group;
  - unit;
  - attached unit;
  - army;
  - objective;
  - request-specific custom layers.
- [x] Add `EntitySelectionProfile`:
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
- [x] Add `EntitySelectionState`:
  - selected refs;
  - focused ref;
  - active layer;
  - deterministic selection order;
  - diagnostics.
- [x] Add profile builders for current UI-supported request families:
  - no pending request / inspection fallback;
  - finite unit-selection style requests, when candidate IDs can be read from payload/options;
  - `submit_movement_proposal`;
  - unsupported parameterized requests.
- [x] Add selection operations:
  - replace;
  - add;
  - subtract;
  - toggle;
  - clear;
  - cycle within active layer;
  - cycle active layer;
  - apply allowed alias rules.
- [x] Add preference-backed command IDs and default bindings for additive/subtractive/layer actions:
  - add selection;
  - subtract selection;
  - toggle selection;
  - cycle entity layer;
  - select current group / expand selection.
- [x] Keep existing ordinary selection state intact for inspection and selected-unit panels.
- [x] Add visible diagnostics for:
  - unsupported request profiles;
  - unavailable entity layers;
  - candidate IDs that no longer exist in the refreshed projection;
  - selection cardinality violations.
- [x] Preserve summary-friendly selection metadata for later phases:
  - stable display labels;
  - selected entity visual anchors;
  - parent/child relationships safe for the viewer;
  - no guessed anchors for hidden or unavailable entities.

## Acceptance Criteria

- [x] A model click can select the model itself when the active profile allows model selection.
- [x] A model click can alias to its owning unit when the active profile asks for units and allows
  that alias.
- [x] Additive, subtractive, and toggle selection are deterministic and preserve stable ordering.
- [x] Layer cycling only visits layers allowed by the current profile.
- [x] Request-scoped selections clear or reconcile when the pending request ID changes.
- [x] Unsupported parameterized requests produce typed UI diagnostics rather than pretending to be
  movement or shooting tools.
- [x] Existing inspect selection and selected-unit HUD behavior keep working.
- [x] Preferences can bind the new selection commands without defining legal actions or rules.
- [x] Entity refs provide enough safe metadata for later visual summary overlays to draw selected
  entities without reinterpreting game rules.

Note: Phase 8 implements these behaviors in the request-scoped local state layer using
projection-derived entity refs. Live Arcade mouse/modifier wiring and separate visual
request-selection highlights are intentionally deferred to Phase 9 so movement assignment can
consume this foundation in one reviewable interaction slice.

## Tests

- [x] Unit tests for `EntityRef` validation.
- [x] Unit tests for profile construction from movement proposal fixtures.
- [x] Unit tests for unsupported parameterized request profiles.
- [x] Unit tests for replace/add/subtract/toggle selection transitions.
- [x] Unit tests for model-to-unit aliasing when allowed.
- [x] Unit tests for rejecting aliasing when not allowed.
- [x] Unit tests for layer cycling with unavailable layers filtered out.
- [x] Regression tests that Tab still prioritizes finite-option focus when finite options are
  pending.
- [x] Preference tests for the new command IDs and hotkey conflict diagnostics.
- [x] Tests for visual-anchor presence and unavailable-anchor diagnostics.

## Manual Validation Checklist

- [ ] Export the default profile with `uv run warhammer40k-export-preferences --format yaml` and
  confirm the entity-selection command IDs are present:
  - `add_entity_selection`
  - `subtract_entity_selection`
  - `toggle_entity_selection`
  - `cycle_entity_layer`
  - `select_current_entity_group`
- [ ] Start the Phase 7/8 debug fixture with
  `WARHAMMER40K_ARCADE_UI_DEBUG_PHASE7=1 uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/default.yaml`.
- [ ] Select a model for ordinary inspection and confirm the selected-unit panel still behaves.
- [ ] Press `space` with a selected unit and confirm the selected-unit action context menu still
  opens when finite actions are available.
- [ ] Begin the existing movement draft flow and confirm movement path drafting still opens for the
  selected unit.
- [ ] Note that separate request-scoped selection highlights, Shift-click subset selection, and
  visible model/unit layer cycling are not expected to appear until Phase 9 wires this foundation
  into live movement assignment input.

## Closeout Milestone

**Milestone 8: "Entity Selection Foundation"**

The UI has a reusable, request-scoped way to select and group engine-projected entities without
answering requests or implementing rules locally.

## Implementation Closeout

Completed on 2026-06-04.

Implemented:

- `state.entity_selection` with `EntityRef`, `EntitySelectionProfile`, `EntitySelectionState`,
  `EntityAliasRule`, `SelectionCardinality`, the entity layer registry, and visual-anchor
  diagnostics.
- Profile builders for inspection fallback, movement proposals, finite unit-candidate requests, and
  unsupported parameterized requests.
- Deterministic replace/add/subtract/toggle selection transitions, focus cycling, active-layer
  cycling, current-group expansion, request drift reconciliation, and cardinality diagnostics.
- Active preference command IDs and default/example profile bindings for request-scoped entity
  selection commands.
- Architecture, README, and UI configuration documentation updates.

Verification during implementation:

- `UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest tests/test_entity_selection_state.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest tests/test_preferences.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/warhammer40k_arcade_ui/state/entity_selection.py tests/test_entity_selection_state.py tests/test_preferences.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check src/warhammer40k_arcade_ui/state/entity_selection.py tests/test_entity_selection_state.py tests/test_preferences.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run mypy src/warhammer40k_arcade_ui/state/entity_selection.py tests/test_entity_selection_state.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pyright src/warhammer40k_arcade_ui/state/entity_selection.py tests/test_entity_selection_state.py`

Reviewer notes:

- This phase intentionally does not submit proposals, validate game rules, mutate authoritative
  state, or create new engine option/proposal IDs.
- Live GUI modifier input for additive/subtractive selection is deferred to Phase 9; this PR
  provides the tested local state and preference command vocabulary that Phase 9 will consume.
