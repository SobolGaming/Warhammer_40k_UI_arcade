# Phase 29: Movement Proposal Family Generalization

Status: Proposed

## Purpose

Generalize the current movement draft tool so it can answer all current movement-shaped proposal
families, not only Movement phase normal/advance/fall-back proposals. This should reuse the strong
path-witness and assignment-draft foundation while respecting each core proposal family's payload
shape.

## Scope

In scope:

- movement-family request profiles for:
  - `normal_move`;
  - `advance`;
  - `fall_back`;
  - `surge_move`;
  - `charge_move`;
  - `pile_in`;
  - `consolidate`;
  - `scout_move`;
- shared path drafting, ghost bases, no-op model handling, and witness generation;
- family-specific required fields copied from the pending request;
- no-move choices where the core contract allows no witness;
- HUD labels and diagnostics for each movement family.

Out of scope:

- placement proposals, including disembark and reserve arrival;
- generic `OpportunityWindow` rendering, proactive `InterfaceIntent` capture, and reaction/stratagem
  trays; those belong to Phase 32;
- local target legality checks for charge, pile-in, or consolidate;
- rolling dice locally;
- resolving attacks or melee declarations.

## Current Core Support

The core catalog already exposes these movement-shaped parameterized proposal rows:

- Movement phase proposals: `normal_move`, `advance`, `fall_back`, and `surge_move`.
- Charge phase proposal: `charge_move`.
- Fight phase proposals: `pile_in` and `consolidate`.
- Setup pre-battle proposal: `scout_move`.

The engine is authoritative for maximum distance, target snapshots, required movement modes,
coherency, terrain, engagement range, and no-move validity. Some families allow explicit no-move
payloads with empty target/objective context and no witness; others require a complete witness.

Core revision `0531ebe` adds Phase 18B trigger opportunity windows around attack-sequence rerolls
and optional actions, but it does not add a new movement proposal family. The movement draft tool
must therefore remain request-driven: it should start drafting only when the current pending request
is a movement-shaped parameterized proposal. If the engine emits a finite opportunity window,
reroll request, grant-selection request, or other interrupt before a movement proposal, this phase
should defer to the finite/current-action, dice, or future opportunity-window UI until the engine
emits the movement proposal request.

Path shape is also family-profile driven. The UI must not keep a blanket rule that every displaced
path needs a synthetic midpoint. Endpoint-only paths are valid for families where the active core
contract accepts them, and invalid diagnostics must be rendered exactly when the core rejects them.
The UI should synthesize intermediate poses only when the active request profile or adapter
contract explicitly requires sampled evidence.

## UX Model

The UI should present all movement-shaped requests through one "movement draft" experience:

- movement subject and family label;
- model path assignment state;
- distance budget and target/objective hints when the core exposes them;
- family-specific submit/no-move affordances;
- preview paths and ghost bases;
- clear "preview only until submitted" status.

The user should not have to learn separate controls for normal movement, charging, pile-in,
consolidate, or Scout moves. The differences should appear as engine-provided constraints and labels.

## Implementation Slices

1. **Movement proposal request profiles**
   - Introduce a request-profile layer that maps a strict `UiParameterizedProposalRequest` to a
     movement-family profile.
   - Capture family fields such as `movement_phase_action`, `movement_mode`, maximum distance,
     charge target IDs, pile-in/consolidate target IDs, consolidation objective/mode, Scout action
     kind, source rule ID, setup step, and ruleset hash.

2. **Generalized draft state**
   - Rename or wrap Movement phase-specific draft code into a proposal-family-neutral draft model.
   - Key draft state by request ID and proposal kind.
   - Preserve explicit no-op model paths when a witness is required.
   - Support no-witness no-move submissions only for families where the request profile says the
     core allows it.

3. **Payload builders**
   - Split payload construction into family-specific builders that consume shared path assignments.
   - Use only pending-request fields for family-specific context.
   - Preserve explicit start/end no-op paths for unchanged models when witness rows are required.
   - Let each request profile decide whether displaced paths may be endpoint-only or require
     sampled/intermediate evidence. Do not add synthetic midpoint poses merely to satisfy stale UI
     assumptions.

4. **HUD and visual summary**
   - Show the movement family name and any engine-provided budget/target context.
   - Show whether the current family requires a witness, permits no-move without witness, or needs
     selected target/objective IDs.
   - Reuse action visual summary overlays for all movement families.

5. **Submission and retry**
   - Submit through the same parameterized decision path with the current request ID.
   - Keep rejected attempts visible as advisory drafts when the engine emits a retry request.
   - Display core invalid diagnostics exactly as returned.

## Acceptance Criteria

- Existing normal/advance/fall-back Movement phase behavior remains covered by regression tests.
- The same draft tool can create a syntactically valid payload for charge, pile-in, consolidate,
  and Scout Move request fixtures.
- Family-specific payload fields come from the pending request, not local inference.
- Allowed no-move choices are represented correctly per family.
- Endpoint-only versus sampled-path requirements are covered by family-profile tests and follow the
  current core contract.
- Mouse hover and HUD interaction do not reset a ready movement draft.
- The UI never rolls charge, advance, or Scout distances locally.

## Automated Verification

Add or update tests for:

- movement-family request profile parsing;
- family-specific payload builders;
- no-move/no-witness versus required-witness behavior;
- explicit no-op paths for unchanged models when witness rows are required;
- endpoint-only accepted and endpoint-only rejected behavior where the core exposes those distinct
  family contracts;
- retry and diagnostic display after invalid movement-family results;
- existing movement draft regressions.

Run the normal gates:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pyright
uv run pytest tests/
uv run pre-commit run --all-files
```

## Manual Validation Checklist

- In Movement phase, complete a normal movement proposal.
- Select an Advance action and verify the UI waits for engine dice/reroll resolution before drafting
  the movement proposal.
- In Charge phase, select a charging unit and verify the movement draft shows charge context after
  the core roll creates a reachable target proposal. Do not expect a Command Re-roll opportunity for
  Charge rolls when the core request marks that reroll forbidden.
- In Fight phase, draft pile-in and consolidate movement when the core emits those requests.
- During setup, draft a Scout Move when a pre-battle action request emits it.

## Reviewer Notes

Review should focus on whether "movement" has become a generic path-witness editor rather than a
Movement phase-only implementation. Each family still needs a strict serializer because the engine
payload shapes are intentionally different.

## Implementation Progress

- Implemented on branch `codex/phase29-movement-proposal-family-generalization`.
- Added movement proposal family profiles for `normal_move`, `advance`, `fall_back`,
  `surge_move`, `charge_move`, `pile_in`, `consolidate`, and `scout_move`.
- Normal Movement phase proposals now preserve endpoint-only moved paths; synthetic midpoint
  evidence is profile-gated to families that currently need sampled/intermediate path evidence.
- Charge, Pile In, and Consolidate support no-witness no-move payload previews when no model
  assignment has been drafted.
- Charge, Pile In, Consolidate, and Scout Move payload builders preserve engine-issued family
  context instead of rolling, deriving, or inventing local rule data.
- `submit_scout_move` requests are parsed as movement-shaped drafts and submitted through the
  generic parameterized client method; normal movement-family requests continue through the
  existing movement submission path.
- Updated HUD/action-summary/regression tests so previously unsupported Phase 15 movement-family
  requests are treated as draftable.

## Implementation Verification

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .
env UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check .
env UV_CACHE_DIR=/tmp/uv-cache uv run mypy src tests
env UV_CACHE_DIR=/tmp/uv-cache uv run pyright
env UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest
```
