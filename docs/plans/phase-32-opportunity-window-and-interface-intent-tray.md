# Phase 32: Opportunity Window And Interface Intent Tray

Status: Proposed

## Purpose

Support the core engine's Phase 18B `OpportunityWindow` contract for optional triggered actions,
Stratagems, rerolls, reactions, and side actions.

The UI should render "available now" opportunities without creating a second rules path. The engine
still emits a normal pending `DecisionRequest`; the UI displays the opportunity envelope, helps the
player choose an engine-provided option, and submits the ordinary `DecisionResult`.

## Core Update Context

Warhammer_40k_AI revision `0531ebe` adds:

- `OpportunityWindow`, `OpportunityLegalAction`, `TriggerBatchingMode`, `WindowPass`, and
  `InterfaceIntent` types in `warhammer40k_core.engine.opportunity_windows`;
- `submission_family: "opportunity_window"` request payloads for trigger hosts that need stale-state
  hashes, sequence numbers, legal-action fingerprints, priority order, and replay-safe pass
  suppression;
- attack-sequence Command Re-roll hooks in Shooting and Fight after eligible Hit, Wound, real Save,
  and random Damage rolls;
- finite `use_stratagem` options where each use/decline option carries a nested
  `opportunity_submission`;
- optional nested `select_dice_reroll` requests after Command Re-roll selection for multi-die rolls.

This phase is the UI counterpart to `Warhammer_40k_AI/docs/TRIGGER_OPPORTUNITY_WINDOWS.md` and the
Phase 18B additions in `ADAPTER_DECISION_CONTRACT.md`.

Reviewed forward through `Warhammer_40k_AI`
`f01293fb4d83249482ecee1c304e21f18e57055e` on 2026-06-16. The later core update
adds typed terrain-area and objective-terrain projection fields but does not change the
opportunity-window request model. Phase 32 should continue to target finite
`submission_family: "opportunity_window"` requests; terrain projection drift is tracked separately
in Phase 33.

## Scope

In scope:

- detect finite `DecisionRequest` payloads whose `submission_family` is `opportunity_window`;
- parse and preserve `opportunity_window`, `opportunity_window_id`, boundary state hash, sequence
  number, anchor event IDs, priority order, legal-action fingerprint, and option-level
  `opportunity_submission` payloads;
- render a generic Opportunity Tray or Current Action extension for currently available actions;
- show action label, source, kind, target summary, cost summary, batching mode, priority/acting
  player, and pass/decline availability;
- submit only engine-provided option IDs for the current request ID;
- hand off nested `select_dice_reroll` requests to the dice tray / finite option UI;
- display stale/wrong-window/wrong-player/fingerprint-drift diagnostics exactly as returned by the
  engine;
- add local, non-authoritative `InterfaceIntent` data structures and UI affordance hooks only where
  they can be validated against the current pending request before materialization.

Out of scope:

- applying rerolls, spending CP, suppressing prompts, or mutating game state locally;
- inventing legal actions, action IDs, targets, option IDs, state hashes, or fingerprints;
- fully automated policy agents for auto-pass or auto-use;
- parameterized `stratagem_target_binding` editing, which remains Phase 30;
- attack-resolution UI beyond rendering the current opportunity and any nested dice-reroll choice.

## UX Model

Opportunity windows should feel like contextual "available now" controls, not repeated modal
interruptions. The first implementation should use a compact tray in the bottom workbench or Current
Action region:

- one row/card per `OpportunityLegalAction`;
- clear selected/default/pass state;
- cost and source label visible enough to audit a CP-spending action;
- timing/window summary visible in the review/debug text;
- nested dice-reroll requests displayed by the dice tray after the engine accepts the parent action.

For Command Re-roll, the player should see the just-rolled dice context, the eligible source action,
and a decline/pass affordance. The UI must not decide reroll eligibility from dice text; it must use
only the engine-emitted opportunity options.

Future proactive intents should be visible as queued advisory intent chips. They may be captured
while no matching opportunity is open, but they must materialize only when the pending request
matches the intended window, state hash, source/action, targets, and expiration.

## Implementation Slices

1. **Opportunity request parser**
   - Add strict UI-side parsing for `submission_family: "opportunity_window"` finite requests.
   - Preserve raw JSON payloads needed for option submission and diagnostics.
   - Fail fast on malformed envelopes in fixtures instead of silently falling back.

2. **Runtime view model**
   - Create a JSON-safe `OpportunityWindowUiState` for HUD/runtime data.
   - Include window ID, action count, timing label, actor/priority order, selected option ID,
     default action ID, source/action summaries, batching mode, and diagnostic breadcrumbs.
   - Keep this separate from assignment-workspace rows.

3. **HUD tray rendering**
   - Reuse the Phase 27 clickable HUD button infrastructure for opportunity actions.
   - Support selected, hovered, unavailable, pass/decline, and high-cost visual states.
   - Keep all opportunity controls synchronized with Current Action selection.

4. **Submission path**
   - Submit the selected engine option ID through the finite decision path with the current request
     ID.
   - Preserve option-level `opportunity_submission` payloads as metadata for trace/review, but do not
     alter them.
   - Surface engine invalid diagnostics for stale state hash, stale sequence, wrong window,
     fingerprint drift, wrong player, unavailable action, and malformed envelopes.

5. **Dice tray handoff**
   - When an accepted opportunity produces `select_dice_reroll`, render it as a normal finite dice
     selection.
   - Keep original/replacement roll display advisory and engine-sourced.
   - Do not re-roll locally or infer reroll targets from rendered dice.

6. **Interface intent foundation**
   - Add local data structures for captured proactive intent with player ID, source ID, action ID,
     target IDs, trigger kind, creation/expiration sequence, and optional state hash.
   - Store intents as advisory UI state only.
   - Add a materialization guard that can produce a finite selection only when the active pending
     request matches the intent exactly.

7. **Tracing and diagnostics**
   - Include opportunity window IDs, state hashes, fingerprints, selected option IDs, and intent IDs
     in forensic traces.
   - Redact or omit hidden target/source fields according to viewer-scoped payloads.

## Acceptance Criteria

- The UI detects and displays finite opportunity-window requests without treating them as
  parameterized assignment proposals.
- Command Re-roll opportunities after Shooting/Fight Hit, Wound, Save, and random Damage rolls can
  be selected or declined through engine-provided option IDs.
- Wrong-window/stale/fingerprint-drift invalid diagnostics render in the HUD and event trace without
  consuming local state incorrectly.
- Nested `select_dice_reroll` requests after accepted multi-die opportunities are displayed through
  existing finite/dice UI.
- Captured `InterfaceIntent` records remain advisory until an active pending request exactly matches
  them.
- The UI does not spend CP, reroll dice, apply actions, or suppress opportunities locally.

## Automated Verification

Add or update tests for:

- strict opportunity-window request parsing;
- Current Action/HUD runtime data from representative `use_stratagem` and `resolve_reaction_window`
  opportunity payloads;
- clickable opportunity action buttons selecting engine option IDs;
- pass/decline rendering and submission;
- stale/wrong-window/fingerprint-drift diagnostic display;
- nested `select_dice_reroll` handoff after an opportunity selection;
- interface-intent exact-match materialization and stale-intent rejection;
- guards that assignment editors ignore finite opportunity-window requests.

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

- Trigger a Shooting attack Hit-roll Command Re-roll opportunity and confirm the Opportunity Tray
  shows use and decline/pass options.
- Decline the opportunity and confirm the engine resumes the attack sequence.
- Use Command Re-roll on a single-die opportunity and confirm the engine records the reroll and
  resumes the host.
- Use Command Re-roll on a multi-die opportunity and confirm the UI transitions to the nested
  `select_dice_reroll` decision.
- Confirm stale or wrong-window submissions show the core diagnostic instead of clearing the tray
  silently.

## Reviewer Notes

Review should focus on the UI/core boundary. Opportunity windows are finite engine decisions with a
rich envelope, not local UI permissions. The tray can make opportunities ergonomic, but must never
become a client-side timing, CP, reroll, or rules engine.
