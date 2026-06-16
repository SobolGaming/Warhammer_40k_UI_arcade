# Phase 28: Generic Placement Proposal Editor

Status: Implemented

## Purpose

Build one generic editor for engine placement proposals. A single placement workflow should unlock
deployment, redeploy, Scout reserve setup, reinforcements, Deep Strike, Strategic Reserves,
disembark, and Rapid Ingress without creating separate UI mini-engines for each case.

## Scope

In scope:

- visible handling for parameterized placement requests;
- advisory model placement drafting on the battlefield;
- integration with the Player Units panel for placement subject selection and placement progress
  status;
- integration with the Current Action panel for placement summary, current draft state, and submit
  readiness;
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
- if the player must choose among multiple units or entities before placing, the Player Units panel
  should be the primary selection surface for player-owned unit subjects;
- required models are shown as draft tokens or ghost bases;
- dragging or clicking places each model pose;
- optional rotate controls adjust facing when facing is part of the pose;
- the Current Action panel shows the placement family, current subject, draft completeness,
  selected/current placement option if one exists, and "preview only until submitted";
- submitting sends the exact current proposal request ID and generated placement payload.

The editor should feel like the existing movement draft flow, but it is setup/arrival placement, not
movement. It should not draw path witnesses for placement proposals.

## Existing HUD Integration

The implementation should build on the modern HUD surfaces instead of introducing another one-off
debug panel.

### Player Units Panel

The Player Units panel should become the main roster-level selector for placement flows when the
pending request allows the viewer to choose among player-owned units. This avoids duplicating unit
selection controls inside the placement editor and keeps the roster as the shared, reciprocal
selection surface.

During a placement proposal, each relevant roster row may receive advisory placement status:

- `unplaced`: the unit is required or eligible but has no complete draft placement yet;
- `current`: the unit is the current placement subject or owns the currently selected draft model;
- `placed`: all required models for that unit have draft poses;
- `submitted` or `resolved`: optional future status when the engine projection confirms the unit is
  no longer pending placement;
- `unavailable`: optional future status for visible units that are not legal subjects for the
  current request, when the core exposes that safely.

These colors and labels are presentation only. They must be derived from the current pending request,
local draft completeness, and authoritative projection. They must not infer placement legality or
hidden information.

Clicking a Player Units row during placement should:

- select/focus that unit locally;
- focus the matching placement subject if the pending request includes that unit;
- optionally select the first unplaced model for that unit;
- update matching Current Action focus through the existing reciprocal selection mechanism when
  there is a corresponding finite option or action button;
- never submit a decision by itself.

### Current Action Panel

The Current Action panel should remain the compact workbench for the active request. For placement
flows it should show:

- placement family or request title, such as `Deployment Placement`, `Deep Strike`, or
  `Disembark`;
- actor/player;
- current subject unit, if one is selected or required;
- draft completeness, such as `3/5 models placed`;
- submit readiness and advisory text such as `preview only until submitted`;
- action buttons for available local commands, such as `Submit`, `Clear`, `Next model`, or
  request-provided finite choices when applicable.

The Current Action panel may summarize placement state similar to movement, but it should not become
the primary roster browser when the Player Units panel can do that job.

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

4. **Player Units integration**
   - Add placement-aware roster status derived from pending placement request and local draft state.
   - Color-code roster rows for unplaced, current, and placed subjects.
   - Route roster-row clicks to local placement subject focus when the row maps to a pending
     placement subject.
   - Keep roster reciprocal selection aligned with battlefield selection and Current Action focus.
   - Ensure roster status is advisory and viewer-scoped; do not infer legality for units the engine
     did not expose as eligible or required.

5. **Current Action integration**
   - Reuse `CurrentActionView` for placement summary instead of creating a new placement-only HUD
     panel.
   - Show placement family, actor, current subject, placed/required model counts, and submit
     readiness.
   - Expose local action buttons for submit, clear/cancel draft, next unplaced model, and any
     request-driven finite options available in the current state.
   - Keep button highlighting synchronized with roster and battlefield focus where a corresponding
     entity exists.

6. **Payload generation**
   - Generate JSON-safe placement proposal payloads with the pending request ID and proposal kind.
   - Include `attempted_placement.model_placements` for every required model.
   - Thread request-family fields such as transport, setup step, source rule, ruleset hash, and
     placement kind only from the pending request.

7. **Submission and diagnostics**
   - Submit through the shared `DecisionRequest -> DecisionResult -> engine validation` path.
   - Display typed invalid diagnostics in the HUD and Review zone.
   - Keep a failed well-formed draft visible when the engine returns a fresh retry request, while
     clearly showing that the authoritative request ID changed.

8. **Placement HUD feedback**
   - Show placement family, required model count, placed count, selected draft model, and submit
     readiness.
   - Surface placement-kind hints such as `deployment`, `redeploy`, `strategic_reserves`,
     `reinforcement`, `deep_strike`, and `disembark` as labels only.

## Acceptance Criteria

- A visible placement proposal request opens the generic placement editor.
- When player-owned unit selection is needed, the Player Units panel can focus an eligible or
  required placement subject without submitting a decision.
- The Player Units panel shows at least unplaced, current, and placed advisory states during a
  multi-unit or multi-subject placement draft.
- The Current Action panel summarizes placement state and submit readiness without duplicating a
  separate roster browser.
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
- Player Units roster status mapping for unplaced/current/placed placement subjects;
- reciprocal focus between Player Units rows, battlefield selection, placement draft selection, and
  Current Action buttons;
- Current Action placement summary state for incomplete, ready, submitted, and invalid drafts;
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

- Launch the live core smoke scenario at deployment unit selection:
  `uv run warhammer40k-arcade-ui --live-core-smoke --stop-at-phase deployment --ui-prefs docs/preferences/default.yaml`.
- Confirm the UI pauses at `select_deployment_unit` before any deployment unit is auto-selected.
- Select a placement subject from the Player Units panel and confirm it highlights the same unit
  option in Current Action.
- Confirm the Player Units panel lists all units for the current viewer/player army, including
  unplaced units.
- Confirm the selected/current Player Units row, placed rows, and unplaced rows use distinct visual
  states.
- Confirm the selected Player Units row and battlefield unit highlight stay synchronized where a
  battlefield unit already exists.
- Place each required model token.
- Confirm Player Units row colors distinguish unplaced, current, and fully placed subjects.
- Submit a placement, continue to the next placement request, and confirm the previous placement
  remains visible as advisory ghost bases or authoritative projected units.
- Confirm the board has placeholder `player-a side` / `player-b side` labels below the lower board
  corners.
- Confirm Current Action shows placement draft completeness and submit readiness.
- Submit a valid-looking draft and verify the core either accepts it or returns an authoritative
  invalid diagnostic.
- Intentionally place a model illegally and verify the UI displays the core diagnostic, not a local
  invented one.

## Reviewer Notes

Review should focus on whether the editor is genuinely generic. Any proposal-kind branch should be
limited to serialization of fields the engine already exposed, not a separate rules path.

## Implementation Notes

Implemented in the Phase 28 PR:

- Added strict `UiPlacementProposalRequest` parsing for the current placement proposal families.
- Added a generic `submit_parameterized_payload` UI core-client method and local-session bridge.
- Added local `PlacementDraft` state keyed by proposal request ID.
- Added reserve/arrival placement payload generation using `attempted_placement.model_placements`.
- Added deployment/pre-battle placement payload generation using top-level `model_placements`.
- Wired placement drafts into the Arcade window:
  - placement proposal requests auto-open a local placement draft;
  - left click places the current model ghost base and advances focus;
  - `TAB` or the Current Action `Next model` button cycles placement-model focus;
  - first `ENTER` marks a complete draft ready for review;
  - second `ENTER` submits the payload through the generic parameterized client path;
  - `ESC`/cancel clears the local draft without submitting.
- Added placement ghost-base primitives on the battlefield without text labels.
- Added Current Action placement summary and local placement buttons.
- Added Player Units placement metadata/status for projected units, core unit-display-map units when
  available, and the pending placement subject before it is projected onto the battlefield.
- Added live-smoke display-map seeding so the Player Units panel shows the current actor's full
  two-unit army during deployment even when the installed core package predates unit display maps.
- Added persistent advisory placement ghost history for accepted local placement drafts.
- Added placeholder side labels under the lower left and lower right board corners.
- Added Assignment HUD placement rows for current, placed, and unplaced model poses.
- Added `--stop-at-phase deployment` for `--live-core-smoke` so the real core smoke harness can
  pause at the first deployment unit-selection request. Roster-row clicks can then focus the
  matching engine-provided finite option before entering the placement editor.
- Updated deployment smoke launch to use the pending deployment actor as the viewer so the manual
  tester sees the side that is currently being asked to deploy.
- Updated Player Units roster selection so unprojected deployment units can focus matching finite
  options without requiring a battlefield projection first.
- Updated finite-option transitions so when the engine advances from one deployment placement to
  the next unit-selection request, the Player Units roster starts highlighted on the same unit as
  the Current Action option without requiring a mouse or keyboard refresh first.

Important limitations:

- The editor does not perform local placement legality validation.
- The editor does not yet support rotation/facing controls beyond preserving the default facing
  value in generated poses.
- The Player Units panel can show core-provided undeployed unit display records when the installed
  engine exposes them. Older engine installs still show the current placement request's subject as a
  focused row, but cannot safely show a complete undeployed roster without additional core exposure.
- Failed authoritative submissions keep the local draft only when the core returns an invalid
  status. If the core advances to a different request, the request ID remains the boundary for
  clearing local state.

## Verification

Automated checks run:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests
env UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check .
env UV_CACHE_DIR=/tmp/uv-cache uv run mypy src tests
env UV_CACHE_DIR=/tmp/uv-cache uv run pyright
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/
env UV_CACHE_DIR=/tmp/uv-cache PRE_COMMIT_HOME=/tmp/pre-commit-cache uv run pre-commit run --all-files
```

Manual reviewer focus:

- Reach a core or fixture scenario that exposes `submit_placement_proposal` with
  `reinforcement_placement`.
- Confirm the Current Action panel shows placement progress and local placement buttons.
- Confirm the Player Units row for the requested unit is selected/focused when the draft starts.
- Click battlefield locations for each model and confirm ghost bases appear without text labels.
- Press `ENTER` once after all models are placed and confirm the Current Action/Assignment state
  moves to ready/review.
- Press `ENTER` again and confirm the UI submits via the core parameterized path or displays the
  authoritative invalid diagnostic.
