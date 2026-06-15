# Phase 28: Generic Placement Proposal Editor

Status: Proposed

## Purpose

Build one generic editor for engine placement proposals. A single placement workflow should unlock
deployment, redeploy, Scout reserve setup, reinforcements, Deep Strike, Strategic Reserves,
disembark, and Rapid Ingress without creating separate UI mini-engines for each case.

## Scope

In scope:

- visible handling for parameterized placement requests;
- advisory model placement drafting on the battlefield;
- per-model pose editing for all required models in the pending request;
- proposal payload generation for supported placement proposal kinds;
- invalid diagnostics and retry behavior from the engine;
- HUD feedback for placement kind, required models, draft completeness, and submit state.

Out of scope:

- local placement legality validation beyond basic payload completeness;
- local deployment-zone, reserve, transport, objective, engagement, or coherency authority;
- hidden setup mechanics not exposed by the core projection;
- army list or mission setup selection.

## Current Core Support

The core contract and decision catalog expose placement requests through the same parameterized
submission path. Relevant proposal families include:

- `submit_placement_proposal`:
  - `reinforcement_placement`;
  - `deep_strike_placement`;
  - `strategic_reserves_placement`;
  - `disembark_placement`.
- setup placement request types:
  - `submit_deployment_placement` with `deployment_placement`;
  - `submit_redeploy_placement` with `redeploy_placement`;
  - `submit_scout_reserve_setup` with `scout_reserve_setup`.

The engine owns validation and mutation. Malformed or stale payloads reject before queue pop.
Rule-invalid but well-formed placements return typed diagnostics and leave state unchanged.

## UX Model

When the engine asks for a placement proposal, the UI enters a placement draft mode:

- the selected/requested unit is shown as the placement subject;
- required models are shown as draft tokens or ghost bases;
- dragging or clicking places each model pose;
- optional rotate controls adjust facing when facing is part of the pose;
- the HUD shows draft completeness, placement kind, and "preview only until submitted";
- submitting sends the exact current proposal request ID and generated placement payload.

The editor should feel like the existing movement draft flow, but it is setup/arrival placement, not
movement. It should not draw path witnesses for placement proposals.

## Implementation Slices

1. **Placement request model**
   - Extend the UI protocol/client facade so all placement proposal request families expose a
     common `UiPlacementProposalRequest` shape.
   - Preserve family-specific fields needed for submission without weakening strict parser
     requirements.
   - Keep request ID, decision type, actor ID, proposal kind, unit ID, placement kind(s), and
     required model IDs explicit.

2. **Draft state**
   - Add local placement draft state keyed by proposal request ID.
   - Track per-model draft pose, completion, selected draft model, and advisory notes.
   - Reset only when the request ID changes or the user explicitly cancels/clears the draft.

3. **Battlefield interaction**
   - Let the user place or move ghost bases for required models.
   - Support selecting a model token and adjusting position/facing.
   - Do not allow unrelated hover changes to destroy the draft.
   - Support all required models explicitly; incomplete drafts remain not ready instead of omitting
     required models from the submitted payload.

4. **Payload generation**
   - Generate JSON-safe placement proposal payloads with the pending request ID and proposal kind.
   - Include `attempted_placement.model_placements` for every required model.
   - Thread request-family fields such as transport, setup step, source rule, ruleset hash, and
     placement kind only from the pending request.

5. **Submission and diagnostics**
   - Submit through the shared `DecisionRequest -> DecisionResult -> engine validation` path.
   - Display typed invalid diagnostics in the HUD and Review zone.
   - Keep a failed well-formed draft visible when the engine returns a fresh retry request, while
     clearly showing that the authoritative request ID changed.

6. **Placement HUD feedback**
   - Show placement family, required model count, placed count, selected draft model, and submit
     readiness.
   - Surface placement-kind hints such as `deployment`, `redeploy`, `strategic_reserves`,
     `reinforcement`, `deep_strike`, and `disembark` as labels only.

## Acceptance Criteria

- A visible placement proposal request opens the generic placement editor.
- The editor can produce a complete payload for at least one fixture-backed placement kind.
- The payload includes the current request ID, proposal kind, unit ID, placement kind, and one model
  placement per required model.
- The editor is family-aware but not rule-authoritative.
- Invalid engine diagnostics are shown without mutating local authoritative state.
- Existing movement draft behavior is unchanged.

## Automated Verification

Add or update tests for:

- strict parsing of placement proposal requests;
- placement draft lifecycle keyed by request ID;
- payload generation for deployment, redeploy, reserve/ingress, and disembark representative
  request shapes;
- draft survival across mouse hover and unrelated HUD interaction;
- invalid result display and retry-request handling.

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

- Launch a core setup or smoke scenario that emits a placement proposal.
- Select a placement subject if the core first emits a finite unit-selection request.
- Place each required model token.
- Confirm the HUD shows placement draft completeness.
- Submit a valid-looking draft and verify the core either accepts it or returns an authoritative
  invalid diagnostic.
- Intentionally place a model illegally and verify the UI displays the core diagnostic, not a local
  invented one.

## Reviewer Notes

Review should focus on whether the editor is genuinely generic. Any proposal-kind branch should be
limited to serialization of fields the engine already exposed, not a separate rules path.
