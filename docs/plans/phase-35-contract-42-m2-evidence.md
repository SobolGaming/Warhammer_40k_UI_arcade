# Phase 35 M2 Contract 42 evidence and limits

Target Core: `6e86f44b87c4559a9297596d5d18dc4247b8cbc3`, external contract `42.0.0`.
The UI branch pins this exact build. The [migration inventory](phase-35-contract-42-migration-inventory.md)
maps every intervening contract to its UI consumer; this record states what the implementation
actually checks. The approved acceptance criteria remain unchanged.

## Public UI boundary evidence

| Surface | Evidence | Limit |
| --- | --- | --- |
| Version and parser gate | `test_contract42_compatibility.py`, `test_contract42_conformance.py`, and `test_contract42_protocol.py` cover the exact installed build, all current projection and interaction examples, strict flat/nested identity, and mismatch rejection. | Historical Phase 21 fixtures remain deliberately historical; their retired decision tokens are not current runtime claims. |
| Viewer and physical display | `test_contract42_projection.py`, `test_contract42_retained.py`, `test_contract42_split_placement.py`, and window tests cover alternating viewers, hidden rows/events, split ownership, and retained zero-wound models until pose removal. | Viewer checks assert public projections, not Core's private decision queue. |
| Finite decisions and source evidence | `test_contract42_finite_source.py` routes all nine new finite families using current engine-authored request/option IDs. Real sessions exercise duplicate Core ability privacy, mandatory Deadly Demise, Mission Action OC reenumeration, random values, source modifiers and dice evidence. | Canonical request examples prove UI routing; they do not claim nine independent gameplay scenarios. |
| Shooting, melee, Charge, placement | `test_contract42_shooting.py`, `test_contract42_shooting_hud.py`, `test_contract42_melee_sources.py`, `test_contract42_charge.py`, and `test_contract42_split_placement.py` cover real accepted/invalid submissions, physical weapon/profile and duplicated ability-instance choices, explicit empty and nullable shooting declarations, committed Charge subset, and current split successor origin/owner proof. Melee HUD choice selection is also exercised headlessly in `test_assignment_workspace.py`. | The attached Charge and general Firing Deck public-data gaps below remain open. |
| Setup and arrival | `test_contract42_setup_arrival.py` covers public nullable mission edges, oversized exception rejection and retry, loaded Transport ingress with Rapid Disembark restrictions and redaction, Shock's explicit empty engagement list, tactical setup history and subsequent Embark option suppression, Aircraft ingress/return options without Hover, and real revival with its source-linked phase-start witness. | This mission fixture offers reserve ingress in round one, so it does not prove a deadline that suppresses ingress. Its oversized arrival hands control to the opponent in round two, so that path does not establish a same-turn activity lock; the test checks current emitted options without local enforcement. |
| Source-specific continuations | `test_contract42_heroic_intervention.py`, `test_contract42_heroic_hud.py`, `test_contract42_overwatch.py`, `test_contract42_firing_deck.py`, and `test_contract42_public_contexts.py` exercise current actor/mode and phase-end shooter selection through the HUD, a first-shooter Firing Deck inventory, scoring attribution, nullable terrain capability, flight, Surge, and public contact redaction. | The Firing Deck fixture knows the initial shot history from its own setup. Contact redaction is seeded with typed Core event data and does not assert the engine generates that event in this fixture. |

The pinned Core interaction examples exercise the generic parameterized envelope for healing
revival but omit `revival_phase_start`. Actual emitted revival requests include that mandatory
source-linked witness. The specialized healing placement parser requires and preserves the real
witness; it does not fill one in to make the static example submit-ready. Generic conformance
passing therefore does not prove that the static healing example is a valid current placement
request. `test_contract42_setup_arrival.py` exercises the real emitted shape and submission.

All real-session tests use `LocalSessionClient` and public `LocalGameSession` decisions for the
submission or view under test. Test-only domain seeding prepares rare engine states; it does not
add production APIs or let the UI compute legality. Source expressions, source operation fields,
split proof, and nullable values are copied from public Core payloads. The UI does not compute
rules results from them.

## Confirmed public-data gaps

**Attached Charge.** A real `submit_movement_proposal` Charge request names the canonical Attached
Unit as `unit_instance_id`, but does not publish its component unit IDs or model IDs. The public
battlefield projection contains physical component rows only. The current movement editor correctly
reports a projection mismatch instead of guessing attachment membership from names or model-ID
prefixes. `test_contract42_charge_sources.py` retains the failing accepted-path regression and the
emitted request/view evidence. The exact public request and both viewer projections are saved in
the Phase 35 review packet at `m2/artifacts/attached-charge-public.json`, with its capture script,
source-fixture hash, and result index beside it. The request context lists the canonical actor and
committed target, while the viewer model rows name only `army-alpha:source` and
`army-alpha:leader` as physical owners. This remains an in-scope acceptance gap pending a public
Core contract change or reviewed resolution.

**General Firing Deck.** Core requires `already_shot_unit_instance_ids` in the exact
`firing_deck_selection` snapshot, but the ordinary shooting declaration request does not publish
that list. `test_contract42_firing_deck.py` proves accepted and invalid submissions when the
Transport shoots first and the test fixture knows the history is empty. The UI displays a missing
public-evidence diagnostic for a general declaration; it does not silently supply an empty list or
read private session state. The issued declaration and both viewer projections are captured in the
review packet at `m2/artifacts/firing-deck-public.json`, with fixture provenance in the result
index. This remains an in-scope public-data limitation.

## Smoke and performance method

The canonical smoke fixture reaches `setup`, `secondary-missions`, `reserve-declarations`,
`deployment`, `redeploy`, `prebattle`, `scout-move`, `movement`, and `shooting` through public
decisions. The simplified `test_live_core_smoke.py` observes the advertised checkpoints in one
traversal, with actor, current request, viewer projection, event count, and monotonically advancing
public decision records. Independent mutable tests start fresh sessions. `charge` and `fight` fail
argument validation because the canonical fixture reaches terminal without those requests after
79 accepted decisions; separate real-session tests cover those editors.

The same-runner corrected Contract 42 baseline at UI SHA
`7b1b0339f1c39e35d1846543b997c915b28004d4` ran nine smoke tests in 198.01 seconds
(198.96 seconds wall); the unchanged repeated-checkpoint test took 75.27 seconds. The first
pre-cleanup run had eight passes and one failure because its generic Stratagem policy chose an
unsupported parameterized target. The corrected baseline added an explicit public decline and a
verified Shooting checkpoint before timing the successful suite; both raw runs are retained.
The unchanged external probe measured 40 projections across 20 boundaries, including 20
duplicate calls, in 1.775 seconds, and full
headless window startup in 29.052 seconds. Half of the measured projection time, about 0.89
seconds, is a rough duplicate-call estimate for the probed Movement traversal; it was not
separately instrumented within window startup. A general view cache would add viewer and mutation
invalidation complexity for that estimated saving, so this change keeps Core views uncached and
removes the repeated traversal instead. The external probe and raw baseline logs are in the Phase 35
campaign performance packet. The final candidate comparison must use that same probe on an idle
runner, with exact UI SHA, command, test count, and Core build recorded there.

Exact-build public session `fork()` was also probed as a possible way to share setup among mutable
tests. Core restore failed with `Primary mission boundary contradicts preceding movement history`.
The simplified suite uses fresh mutable sessions and does not claim a passing replay test or
cross-version persistence migration. Existing saves remain bound to their original exact Core
runtime; switching the UI dependency does not reinterpret them.

## Gate status

Final clean install, quality, coverage, and optimized performance gates are scheduled on the
frozen M2 candidate. The pull request checks and Phase 35 review packet are the authoritative
record of their commands, counts, result index, and raw logs. No measured comparison above is a
CI budget or an unverified claim about JSON loading.
