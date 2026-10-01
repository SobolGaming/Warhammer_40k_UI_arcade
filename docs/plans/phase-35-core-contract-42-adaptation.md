# Phase 35: Core Contract 42 Adaptation and Live Smoke Simplification

Status: Proposed (reviewed 2026-09-30)

Implementation note: this is the reviewed baseline plan. The Phase 35 branch now pins the exact
Contract 42 revision; [M2 evidence and limits](phase-35-contract-42-m2-evidence.md) records the
observed runtime behavior and remaining acceptance gaps. The baseline descriptions below are
historical and do not describe the current branch state.

## Purpose and baseline

Adapt the Arcade UI to the reviewed core revision without adding a second rules path. The UI
currently pins `Warhammer_40k_AI` at `dbfcc3a99e9d560d1354506352a09d48ca555a94` and external
contract `10.2.0`. The reference core checkout was fast-forwarded to
`6e86f44b87c4559a9297596d5d18dc4247b8cbc3`, 125 commits later, with external contract
`42.0.0`. This plan targets that exact revision. Recheck the intervening commits and contract
manifest if the implementation chooses a later core commit.

The public `AdapterGameSession` method set remains available. The primary work is adapting
viewer-scoped payloads, submissions, fixtures, and UI editors. The current UI guard and game-view
parser stop against the new core: it emits `game-view-v13-random-profiles`, while the UI requires
`game-view-v11-phase17n-step4`. A focused conformance test also fails because it reads the sibling
checkout's Contract 42 manifest while expecting the installed Contract 10 package. Do not treat
that mixed-version test run as a new-core regression.

## Confirmed changes that affect the UI

| Area | Reviewed core change | UI consequence |
| --- | --- | --- |
| Versioning | External contract `10.2.0` to `42.0.0`; game view v11 to v13. Battlefield, decision-request, interaction-descriptor, event-delta, support-profile, and capability discriminators checked here remain unchanged. | Update the pin, lock, declared versions, and strict parsers together. Do not relax version checks. |
| Decision coverage | Contract family coverage grows from 80 to 87 entries: nine new finite types and two retired types. Interaction conformance cases grow from 90 to 97. | Verify generic option-ID routing for new types; remove stale assumptions about `select_disembark_unit` and `select_reinforcement_unit`. Specialized UX can remain in later phases. |
| Parameterized requests | Four placement/revival families publish flat request layouts as well as the nested layout used elsewhere. | `UiParameterizedProposalRequest.from_decision_payload()` currently requires `payload.proposal_request`; parse both layouts and compare with the projected `pending_proposal` while validating request/actor identity. |
| Shooting | Contract 11 requires opaque `weapon_instance_id` for each physical ranged copy. Contract 42 permits empty declarations and nullable ranged targets. | Preserve weapon-copy identity, allow explicit no-target or empty choices, and stop treating zero assigned targets as inherently invalid. |
| Charge movement | Contract 18 commits a target set through finite `select_charge_targets` before `charge_move`; the proposal must use that exact set. | Read `context.target_selection.target_ids`, not every reachable target, and preserve the engine's movement budget and path witness. |
| Placement | Split successor placements require engine-projected `split_origin`. | Carry the projected origin and successor ownership into placement drafts; never derive it from names or IDs. |
| Display | Model keywords are projected, and random characteristics can have expressions with nullable numeric values. | Parse and render the source expression or unknown value; do not roll or invent numbers in the UI. |
| Retained models | Fight/Shoot On Death can retain a zero-wound model at its original physical pose. | Render engine-projected physical presence even when the model state says `destroyed`; hide it when the engine removes its pose. |
| History | Persistence and replay remain bound to the exact core build across these contract majors. | Do not reinterpret Contract 10 saves or cached requests as Contract 42 data. |

The migration review must cover `Warhammer_40k_AI/contracts/migrations/10-to-11.md` through
`41-to-42.md`, the current `contracts/manifest.json`, interaction conformance cases, and
`docs/ADAPTER_DECISION_CONTRACT.md`. The table highlights verified UI risks; it is not a substitute
for that complete contract inventory. The [migration inventory](phase-35-contract-42-migration-inventory.md)
records every reviewed migration at the exact target revision and maps it to UI consumers and
Contract 42 checks. It is preparatory evidence; the supported runtime pin remains Contract 10.2.

## Live smoke and catalog decision

Keep one real-core manual startup route for setup, deployment, Scout Move, and movement. The core
still exposes `canonical_setup_prebattle_smoke_config()`, but no core-owned lightweight fixture for
a later phase. Exact-build persistence restore exists; it is not a cross-version fixture. The UI's
`--live-core-smoke` path therefore remains useful for exercising the public decision facade. Its
scripted choice policy is fixture automation, not gameplay logic.

Simplify the stopgap after Contract 42 parsing works:

- Verify reachability on the reviewed core. If the canonical fixture still ends before shooting,
  remove `shooting`, `charge`, and `fight` from accepted CLI stop phases and replace the long
  terminal-traversal test with a fast unsupported-phase check. Reintroduce them only with a
  core-owned reachable fixture.
- `setup` and `secondary-missions` currently stop at the same request. Test that checkpoint once;
  retain an alias only if it serves a documented user workflow.
- Replace eight fresh-session checkpoint assertions with one public-decision traversal or a small
  number of representative sessions. Prefer one traversal for read-only assertions. If independent
  mutable sessions need checkpoint reuse, benchmark public `fork()` inside `core_client` and rebuild
  the UI status/view; do not share a mutable session or use cross-version persistence files.
- Replace first-option/completion-token fallbacks with explicit choices for the canonical fixture.
  Fail with a typed smoke diagnostic when a new decision family cannot be automated. Keep generated
  result IDs and parameterized payloads deterministic and engine-valid.
- Profile duplicate viewer projections: `LocalSessionClient._status_from_lifecycle()` projects a
  view, then `_drive_to_checkpoint()` requests another view at many boundaries. Cache or reuse a
  view only if measurements justify it and request, actor, visibility, and invalidation behavior
  remain correct. Invalidate on start, advance, accepted or invalid submission, and viewer switch.

At the old Contract 10 pin, PR #90's CI run spent about 295 seconds in the nine live-smoke tests.
A separate local run measured about 189 seconds in the unreachable late-checkpoint test and 117
seconds in the eight-checkpoint test. Those figures locate likely waste; they are not a Contract 42
baseline or directly comparable across runners.

The canonical smoke uses a seven-datasheet in-code `ArmyCatalog`; it does not parse every faction
catalog for each startup. Latest core selects faction runtime modules by roster activation, and
the lifecycle caches the runtime bundle by activation hash. Cold build-identity verification reads
packaged JSON, including faction files, and is cached per process. In local probes, the latest
cold import took about 2.5 seconds and made 227 JSON reads; the first smoke config took about
7.7 seconds, while repeated config calls in that process took about 0.1 seconds and read no JSON.
About 5.6 seconds of the first config call built the cached Event Companion mission pack; the
remainder was not separately profiled. These are exploratory local figures, not CI budgets.
Do not add a UI cache for all faction JSON. If measured cold build-identity I/O remains a product
problem, raise a separate core-owned performance change without bypassing identity verification.

## Implementation slices

1. **Versioned evidence and dependency gate.** Record the 10-to-42 migration matrix by payload
   family and UI consumer. Make conformance fixtures match the declared core revision: either
   check the sibling checkout SHA explicitly or commit a small versioned fixture set. Eliminate
   silent mixing of an installed old package with newer sibling examples. Stage the reviewed SHA
   in `pyproject.toml`, `uv.lock`, `README.md`, CI, and `core_client/compatibility.py` together on
   the implementation branch so it can be tested. Keep fail-fast diagnostics for unsupported
   versions.
2. **Projection and proposal normalization.** Parse Contract 42 examples strictly, including
   game-view v13 model keywords, random expressions, nullable numbers, and viewer redaction. Make
   standalone decision parsing accept the declared flat and nested request layouts, or pass the
   projected `pending_proposal` into that parser; then compare the result against `pending_proposal`
   and the current request/descriptor identity. Replace or partition the render window's
   accumulated unit/model display maps by viewer; do not merge rows from one player's projection
   into another player's HUD cache. Render retained Fight/Shoot On Death models while the engine
   still projects their physical pose. Cover all four flat families plus a nested family and
   alternating player views after hidden split/attachment choices.
3. **Submission editors.** Update shooting assignment rows and payloads to copy each
   engine-provided `weapon_instance_id`, distinguish physical copies and profiles, preserve
   selected ability-instance IDs, and support explicit empty inventories and `null` targets.
   Update Charge drafts to submit only the finite choice's committed target set and current
   movement budget/path witness. Update placement drafts to preserve `split_origin`. Exercise all
   three through real `LocalGameSession` decisions, including invalid diagnostics and viewer-scoped
   projections.
4. **Finite decision routing.** Test all nine added finite families through the current
   engine-provided option-ID path, including charge targets, target replacement, modifier ignores,
   dice extremum, melee weapon, lethal-hit wound, mortal-wound model, ability instance, and split
   membership. Keep unsupported specialized presentations explicit; coordinate later opportunity
   tray polish with Phase 32 rather than adding parallel rules logic here.
5. **Smoke cleanup and measurement.** Apply the live-smoke decisions above only after slices 1-4
   can start and project a real session. Measure cold import, first/warm config, session start,
   decision traversal, per-decision projection, and full UI startup separately. Compare the old
   repeated-checkpoint test count and elapsed time with the simplified suite on the same runner
   and exact Contract 42 core build.
6. **Closeout.** Update examples, README launch/stop-phase instructions, relevant phase notes,
   packaged defaults if their inputs changed, and reviewer evidence. Merge the reviewed core pin
   only when supported UI behaviors and quality gates pass. Keep older sessions on their exact
   original runtime rather than adding an inferred migration.

## Acceptance criteria

- A clean install launches against the pinned Contract 42 core and rejects a mismatched core with
  a copyable compatibility diagnostic.
- Current core projection and interaction examples parse without permissive defaults. Hidden
  decisions, model data, nested choices, events, and diagnostics remain viewer-scoped. Alternating
  player-a/player-b refreshes do not retain the previous viewer's hidden display rows. A retained
  zero-wound model remains rendered until its physical pose is removed by the engine.
- Finite submissions preserve current engine request/option IDs. Parameterized submissions accept
  engine-declared flat and nested layouts and preserve proposal identity and spatial context.
- Duplicate physical ranged weapons, empty declarations, nullable targets, committed Charge
  targets, and split successor placement submit through the public facade with core-owned
  validation. A Charge test covers multiple reachable targets with one committed subset and
  rejects a mismatched target set.
- One real-core manual smoke path reaches each advertised checkpoint with its expected actor and
  request, a viewer-safe projection, and public-decision history. The default movement launch still
  works. Unsupported phase names fail at argument validation. The automated suite does not replay
  the same long setup path for every checkpoint, and optimized view reuse preserves visibility and
  replay.
- Performance evidence separates cold package identity reads from warm catalog/config creation and
  repeated decision traversal. No performance claim is based on an unmeasured JSON-loading guess.
- Existing UI/core boundaries and all project quality gates pass. Full-game Core Rules support is
  outside this UI compatibility phase and must not be claimed from smoke coverage.

## Verification and PR slices

Use separate reviewable PRs for the version/fixture gate, protocol/projection changes, proposal
editors, and smoke cleanup if the implementation cannot remain a single focused slice. Run focused
tests while changing each surface, then the README quality gates before pin closeout. Include real
core local-session tests for accepted and invalid submissions, conformance examples for every
changed family, headless UI interaction/render tests for visible changes, and an import-boundary
audit. Report exact checks passed, failed, or not run. Record the before/after timing command,
environment, and test count; do not use timing assertions tied to one machine.

Do not edit the sibling `Warhammer_40k_AI` checkout from the UI task. If a necessary public core
fixture or performance fix is missing, identify it as separate authorized core work.
