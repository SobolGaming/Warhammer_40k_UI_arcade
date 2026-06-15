# Phase 26: Generic Finite Decision Workbench Polish

Status: Proposed

## Purpose

Make every finite `DecisionRequest` understandable and actionable through one generic workbench
instead of a collection of ad hoc labels. This phase should quickly improve many currently rough
finite decisions without adding new rules knowledge to the UI.

The workbench should clearly answer:

- who is being asked to act;
- what decision type is pending;
- which option is currently selected;
- what the selected option means, using only engine-provided option IDs and payload fields;
- whether the option is a submit, skip, pass, completion, or decline style option;
- what key or button will submit the current choice.

## Scope

In scope:

- finite request display for all visible `UiFiniteDecisionRequest` instances;
- option cursor and current-option emphasis in the HUD;
- option detail summaries built from JSON-safe engine option payloads;
- visible submit, decline, skip, pass, and completion affordances when those meanings are present
  in the engine option ID or payload;
- actor/current-player clarity;
- stale/no-visible-request diagnostics;
- runtime HUD data and composition binding for finite decisions;
- input tests proving option selection does not change unrelated selected battlefield entities.

Out of scope:

- new core decision types;
- local legality filtering;
- local option synthesis;
- parameterized proposal editing;
- custom per-rule presentation beyond generic field summaries.

## Current Core Support

The core catalog already exposes many finite surfaces through the same selected-option lifecycle:

- setup decisions such as secondary selection, reserve declaration, deployment unit selection,
  redeploy unit selection, and pre-battle action selection;
- movement decisions such as movement unit, movement action, disembark, reinforcement, embark, and
  Desperate Escape model selection;
- shooting and fight selections such as shooting unit, shooting type, charging unit, fight
  activation, fight ability, target resolution, attack group, allocation, Precision, Feel No Pain,
  and destruction reaction;
- Stratagem use windows, including optional decline choices.

Finite submissions must keep using the current request ID and one engine-provided option ID. The UI
must not infer hidden legality or invent user-facing options.

## UX Model

The finite workbench is the HUD area that explains "the next question the engine is asking." It is
not a rules assistant. It is a structured view over the pending request:

- title: concise decision label derived from `decision_type`;
- actor band: actor/player currently responsible for answering;
- selected option row: emphasized option ID and friendly summary;
- option detail area: compact payload key/value summary;
- controls: next option, previous option, submit, and visible decline/pass/complete hints when
  applicable.

Option labels should remain honest when the UI does not know a domain-specific name. Prefer
`Normal Move`, `Decline Stratagem Window`, and `Complete Shooting Phase` when the option ID clearly
contains that meaning; otherwise show the raw option ID with a compact payload summary.

## Implementation Slices

1. **Finite option presentation model**
   - Add a small view model that converts a finite request and selected option index into HUD-ready
     rows.
   - Include request ID, actor ID, decision type, option count, selected option ID, and selected
     payload summary.
   - Classify obvious option styles from engine-provided IDs or payloads:
     `decline`, `complete`, `pass`, `skip`, `submit`, and `choose`.

2. **HUD runtime data integration**
   - Bind the finite view model into the existing ergonomic HUD runtime data.
   - Ensure the current HUD composition has a dedicated finite workbench slot or card.
   - Emphasize the selected option in a way visible without reading debug trace output.

3. **Input and selection separation**
   - Keep option cycling and submission scoped to the pending finite request.
   - Ensure `TAB`, arrow keys, or configured option cycling cannot replace the locked battlefield
     unit/model selection for the current decision unless the user explicitly selects an entity.
   - Preserve request-scoped selected-option state when the mouse moves.

4. **Submission visibility**
   - Show the configured confirm command.
   - Show when the selected option is a decline/pass/complete option.
   - Show a clear "no finite request" state instead of surfacing a client error when there is no
     finite decision to answer.

5. **Generic payload details**
   - Render shallow key/value details from the selected option payload.
   - Limit row count and truncate long values without overlap.
   - Prefer deterministic formatting so screenshots and tests are stable.

## Acceptance Criteria

- The Decision/Workbench HUD area visibly shows actor, decision type, selected option ID, selected
  option index/count, and a summary of the selected option payload.
- Decline/pass/complete options are visibly distinguishable when their engine-provided data makes
  that meaning clear.
- The selected option is emphasized in the HUD.
- Option cycling does not mutate selected unit/model state.
- Mouse movement does not reset finite option selection or movement-draft review state.
- Finite submission still uses the exact current request ID and selected engine option ID.
- No UI code invents option IDs or filters options as a local legality engine.

## Automated Verification

Add or update tests for:

- finite option view-model summaries for representative option families;
- current-option emphasis and command text in composition primitives;
- option cycling preserving selected entity state;
- decline/pass/complete style classification from engine-provided option IDs/payloads;
- finite submission still preserving request ID and selected option ID.

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

- Launch `uv run warhammer40k-arcade-ui --live-core-smoke`.
- At each visible finite request, confirm the workbench shows the actor, decision type, selected
  option, and submit command.
- Cycle options and verify the emphasized row changes.
- Select a battlefield unit, cycle a finite action option, and verify the battlefield selection does
  not jump to another unit.
- Submit a complete/pass/decline style option and verify the next core request or result appears.

## Reviewer Notes

Review should focus on boundary discipline. This phase is UI polish, not a rule interpretation
layer. Any label improvement must be derived from data the engine already exposed to the viewer.
