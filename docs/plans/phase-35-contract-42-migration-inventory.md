# Phase 35 migration inventory: core Contract 10.2 to 42.0

Reviewed against `Warhammer_40k_AI` commit
`6e86f44b87c4559a9297596d5d18dc4247b8cbc3`. This is evidence for the Phase 35 plan,
not a claim that every UI workflow supports Contract 42. The original planning baseline pinned
`dbfcc3a99e9d560d1354506352a09d48ca555a94` / Contract `10.2.0`; the Phase 35 implementation
branch now pins the reviewed Contract 42 commit. The pin must not merge until the atomic
compatibility milestone passes its acceptance gates. The separate
[M2 evidence record](phase-35-contract-42-m2-evidence.md) tracks implemented behavior, measured
performance, and unresolved public-contract gaps.

Sources at the reviewed commit: every file from `contracts/migrations/10-to-11.md` through
`41-to-42.md`, `contracts/manifest.json`,
`contracts/examples/decisions/family-coverage.json`,
`contracts/examples/decisions/interaction-conformance.json`, and
`docs/ADAPTER_DECISION_CONTRACT.md`. The commit fixes the meaning of all paths in the table.
The engine's public `AdapterGameSession` method set remains available; it owns legality,
mutation, redaction, persistence, and replay.

## Contract inventory and version boundary

| Evidence | Contract 10.2 | Contract 42 | UI consequence |
| --- | ---: | ---: | --- |
| External contract | `10.2.0` | `42.0.0` | Update the strict compatibility guard with the pin. |
| Game-view discriminator | `game-view-v11-phase17n-step4` | `game-view-v13-random-profiles` | Adapt projection parsing and rendering before merging the pin. |
| Known external decision tokens | 80 | 87 | Nine finite types added; two retired. Route current engine option IDs. |
| Registered decision types | 78 | 85 | Check the same finite coverage against registered requests. |
| Interaction conformance cases | 90 | 97 | Parse and dispatch all target cases under the new pin. |
| Parameterized payload kinds / proposal kinds / interaction kinds | 24 / 21 / 13 | 24 / 21 / 13 | No invented proposal or interaction family is needed. |

The nine added finite types are `select_charge_targets`, `select_core_ability_instance`,
`select_dice_extremum`, `select_lethal_hit_wound`, `select_melee_weapon`,
`select_modifier_ignores`, `select_mortal_wound_model`, `select_target_replacement`, and
`select_unit_split_membership`. `select_disembark_unit` and `select_reinforcement_unit` retire.
The family inventory is the source for this difference. The target interaction inventory
contains 97 cases, including five conformance cases for four flat request families: Cult
Ambush marker has place and no-marker variants. The flat families are Cult Ambush marker,
model materialization, healing revival, and return-on-death placement. Other parameterized
families retain nested `payload.proposal_request` examples.

Model materialization is a flat placement family whose newly created model IDs are absent
from `battlefield_view.authoritative.models_by_id` until Core accepts placement. Its current
request supplies the exact `models`, ordered `model_instance_ids`, `army_id`, source physical
unit, and player. The editor uses those fields for the new model base and submission identity;
it continues to require projected ownership and `split_origin` for existing placement models.
The source unit may also lack a rendered `UnitView` after its last old model is destroyed.
The materialization regression covers the headless editor, Core payload shape, stale/invalid
retry, viewer switch, and accepted placement through a public session built from a pinned
Core-generated checkpoint. Core-valid rectangular bases use a circumscribed radius only for
the current circular draft/render preview; Core validates the exact footprint on submission.
No local model profile or placement legality is inferred.

Attached reserve and Disembark placement requests publish the current physical component and
model inventories in their context. The placement editor keeps the canonical rules-unit actor
separate from those physical owners, checks every requested model against its projected owner
and emitted component set, and emits `attempted_rules_unit_placement` with one complete row per
current component. The real attached reserve regression covers headless opening, grouped
accepted/invalid/stale submissions, and same-owner nonmember rejection. Pinned Core's
`engine/phases/movement_transports.py` Disembark builder emits the same current component/model
inventories plus Transport context; a focused test checks the shared UI serializer and Core
payload decoder. That test does not claim a live attached Disembark acceptance. The grouped draft
obtains `army_id` from a unique public placed-army owner row or support-profile mustering row,
with conflicts rejected. If both are absent, the HUD reports a typed local placement diagnostic;
it does not derive an ID from the attached or component spelling. Deployment and prebattle
placement requests instead publish component and model inventories at the request top level.
The same physical-row editor now consumes them, and a real empty-battlefield attached deployment
is accepted using the canonical fixture's public mustering row. Pinned Core `GameConfig` requires
an `army_catalog` and exactly one `ArmyMusterRequest` per player; it has no direct
`army_definitions` config field. The owner-visible support profile emits that player's mustering
row. If supplied public authority is missing or conflicting, the editor reports a typed local
diagnostic for malformed or stale input. This does not establish a supported-session Core blocker.

Attached Scout finite options and `submit_scout_move` requests also publish component and model
inventories. Current Action, physical roster rows, battlefield selection, and the movement draft
now share the canonical actor through that explicit membership. The draft keeps the emitted Scout
distance and model witness IDs. Pinned Core's Scout resolver still looks up the canonical Attached
Unit as a physical placement and raises `PlacementError`; the real accepted-path regression remains
failing ([Core #537](https://github.com/SobolGaming/Warhammer_40k_AI/issues/537)). Attached
Charge's movement request still lacks public component/model membership, so the
UI does not transfer the Scout mapping or infer Charge membership.

The additional first-failed-save Damage-to-zero regression in
`tests/test_contract42_damage_zero.py` follows the public `select_modifier_ignores` request
through both keep and ignore branches. It checks the emitted sourced `SET 0` operation,
forged and stale option rejection without a decision record or projection change, and
owner/opponent event and pending-request scope. The UI never computes replacement damage.
Its exact-build checkpoint comes from pinned Core's
`tests/order93_save_damage_helpers.py` via the explicit
`scripts/generate_contract42_damage_zero_fixture.py` generator. Runtime UI tests restore the
committed checkpoint and use public session choices; the generator's Core-owned helper starts
from an in-progress shooting scenario, not a roster-start traversal. Fixture provenance and
hashes are recorded in `tests/fixtures/contract42_damage_zero_checkpoint.md`.

The target manifest's JSON schema URI revisions are distinct from the runtime payload
discriminators. The target runtime still emits `decision-request-view-v5-phase17n-step4` and
`interaction-descriptor-v2-variants`; their manifest schema URIs are v6 and v3 respectively.
Battlefield view, lifecycle status, event deltas, support profile, and capability manifest
runtime discriminators checked by `core_client/compatibility.py` also remain unchanged. Only
the external contract and game-view runtime constants change there.

## Migration-by-migration UI disposition

Paths under `src/warhammer40k_arcade_ui/` are abbreviated below. “No editor change” means
the current public decision facade or a viewer-scoped opaque payload already carries that
engine-owned rule; it does not waive the listed conformance or integration check.

| Migration | Payload or semantic change | UI consumer and required Contract 42 check | Disposition |
| --- | --- | --- | --- |
| `10-to-11.md` | Every physical ranged copy has an opaque `weapon_instance_id`; declaration and history retain it. Different legal profiles can share one physical ID, while identical copies have different IDs; Firing Deck retains the embarked source. | `state/assignment_workspace.py`: key allocation by physical ID plus profile and optional Firing Deck source, show engine `shooting_weapon_selection_limits`, and test duplicate same-profile copies, legal multi-profile rows sharing an ID, Firing Deck identity, and accepted/invalid real-core submissions. | Editor change; never derive the ID from model/profile or row order, or collapse legal profiles by ID alone. |
| `11-to-12.md` | Fight/Shoot On Death may retain a destroyed model at its original pose until resolution; Fight target witnesses use `present_model_instance_ids`, and retained shooting follows the ordinary declaration path. | `render/core_projection.py`, `state/finite_decision.py`, `state/assignment_workspace.py`: render physical presence until removal; submit the emitted destruction reaction, then a witnessed retained shooting declaration; check public completion versus private parent-cause events. | Renderer and submission coverage; model `state` alone is insufficient, and the UI never reconstructs retention or target authority. |
| `12-to-13.md` | Model keyword/source arrays, current rules-unit keywords, and private split/attachment membership enter projections. | `core_client/protocol.py`, `render/arcade_window.py`: strict model display parse and alternating viewer-cache/redaction tests. | Projection change; do not rebuild rules-unit keywords or retain hidden rows. |
| `13-to-14.md` | Continuous LOS witness replaces ray-index fields in shooting candidates; Cover remains engine-authored. | `state/assignment_workspace.py` treats candidates as engine evidence; parse target examples and check no old ray-field assumptions. | No UI LOS algorithm or witness synthesis. |
| `14-to-15.md` | Mandatory/optional sequencing is engine ordered; selected actor can differ from turn owner. Public scoring evidence adds `scoring_player_id`; movement requests retain opaque source grants. | `state/finite_decision.py`, `core_client/local_session_client.py`, `core_client/protocol.py`: submit emitted option IDs and use request actor for viewer/status; check scoring attribution and preserve current movement context. | No UI rule-order table, scoring owner inference, or movement-grant arithmetic. |
| `15-to-16.md` | Nested hit rolls carry `critical_threshold` and `threshold_source_ids`; raw six alone does not define critical. | `hud/dice_tray.py` and viewer event surfaces: preserve/display engine evidence in conformance tests. | No UI critical-hit calculation. |
| `16-to-17.md` | Phase-end Overwatch window no longer names a moved enemy; it may be declined. Accepted shooting selects one engine-eligible enemy within the source limit using Snap. | `state/assignment_workspace.py` Stratagem and shooting contexts plus `state/finite_decision.py`: test decline, shooter, exact candidate target and source context without a moved-unit key. | No new editor family, inferred trigger target, or local range/visibility ruling. |
| `17-to-18.md` | Finite `select_charge_targets` commits a subset, with `select_target_replacement` on an invalidated commitment. The modified Charge roll is bounded to 1–12; later distance effects produce a separate nonnegative `movement_budget.maximum_distance_inches` that may exceed 12 or be fractional. Target eligibility requires both that maximum and the distinct 12-inch Charge target limit. | `state/finite_decision.py`, `state/movement_draft.py`: use emitted target and replacement option IDs plus `context.target_selection.target_ids`; preserve the engine budget and witness; test bounded roll, different movement maximum, 12-inch target gate, stale refresh and rejection of reachable-but-uncommitted targets. | Movement editor and finite-routing change; never use the roll as the full path budget or widen target eligibility with later distance effects. |
| `18-to-19.md` | Charge uses canonical Attached Unit actor and living models from every component; endpoint witness is engine-authored. | `state/movement_draft.py`: exercise attached paths through real session; preserve component membership and witness. | No component alias or endpoint inference. |
| `19-to-20.md` | Eligible whole-Charge reroll happens before target selection and binds the canonical rolling rules unit plus `charge_action_id` or source reroll context. | `state/finite_decision.py`, `hud/dice_tray.py`: route the current emitted reroll option; test the source-bound continuation to target selection. | No reroll calculation, component alias, or new UI proposal. |
| `20-to-21.md` | Heroic Intervention requires source-backed `effect_selection.mode` in its parameterized Stratagem proposal before CP/roll; its acting player may differ from turn owner. It then shares Charge options, targets and witnessed movement; source roll cap may be six. | `state/assignment_workspace.py`, `core_client/local_session_client.py`, `state/movement_draft.py`: carry a source-authorized mode, request actor, budget and target commitment; test Into the Fray or Leap to Defend accepted shared-Charge continuation and missing/invalid mode rejection before CP spend. | Stratagem editor and actor-scope check; no Heroic-only movement path or locally invented mode/roll rule. |
| `21-to-22.md` | Walking/Take to the Skies is an emitted finite choice; selected flight and penalty persist into proposals. | `state/finite_decision.py`, `state/movement_draft.py`: preserve option ID, request context, and path on retry. | No synthetic flight option or distance adjustment. |
| `22-to-23.md` | Surge finite option commits closest enemy; triggered movement uses plural `aircraft_movement_policies`. | `state/movement_draft.py`: preserve target/context and test no singular-policy assumption. | No Surge target picker or aircraft policy calculation. |
| `23-to-24.md` | Optional movement keyword choice is in finite option IDs/context; terrain capability adds nullable transit height. | `state/finite_decision.py`, `render/core_projection.py`: route emitted options and parse nullable capability where consumed. | No grant or terrain legality inference. |
| `24-to-25.md` | Public mission setup adds nullable attacker/defender battlefield edges, including source corners, for oversized setup; non-Aircraft exceptional arrivals carry a setup-turn activity lock. | `core_client/protocol.py` mission payload, `state/placement_draft.py`, movement/shooting routes: preserve projected edge/context; test real oversized acceptance/rejection and later engine-issued options under the lock. | No UI edge eligibility or activity-lock algorithm. |
| `25-to-26.md` | Duplicate weapon abilities use physical ability-instance IDs and nested `select_weapon_ability_instance`; persistent Core abilities add `select_core_ability_instance`, owner-secret setup choices with `visibility_source: "core_ability_instance"`, and source-backed unit selections. Duplicated mandatory Deadly Demise has one source per option and no decline. | `state/assignment_workspace.py` copies selected weapon instance IDs; `state/finite_decision.py` and `core_client/protocol.py` retain the current Core/Destruction request, source context and emitted option IDs; `core_client/local_session_client.py` consumes owner-scoped status/events and `render/arcade_window.py` partitions display state by viewer. M2 checks duplicated shooting/melee, two Core source occurrences during setup, owner/opponent alternating views, and mandatory Deadly Demise accepted/invalid option behavior in real sessions. | Editor identity and finite/viewer coverage; no descriptor fallback, synthesized decline, or UI-owned ability arithmetic. |
| `26-to-27.md` | Same-turn setup history blocks Embark; completion records add `setup_kind`. | `state/finite_decision.py` and placement submission: test engine options/diagnostics after setup. | No editor change: core decides eligibility and owns history. |
| `27-to-28.md` | Shock Disembark starts with an explicitly empty engaged-enemy list; resulting engagement is engine evidence. | `state/placement_draft.py`: preserve empty published list and rejected-placement diagnostics. | No UI reconstruction from Transport engagement. |
| `28-to-29.md` | Loaded Transport ingress and Rapid Disembark inherit private placement restrictions. | `state/placement_draft.py`, viewer projection: test public placement/retry and redaction. | No policy decoding; private ingress history stays core-owned. |
| `29-to-30.md` | Reserve deadlines and post-ingress movement locks change legal options. | `state/finite_decision.py`, placement submission: test engine-issued options and invalid diagnostics. | No editor change: no UI deadline table. |
| `30-to-31.md` | Firing Deck declaration request lists all embarked cargo; accepted inventory includes noncontributors. | `state/assignment_workspace.py`: preserve candidate data and test cargo snapshot/selection paths. | No UI reconstruction of all cargo from chosen weapons. |
| `31-to-32.md` | Aircraft use mandatory ingress/return; Hover toggle and hover state are removed. Movement availability distinguishes contacting `enemy_aircraft_engagement_model_ids`. | `state/finite_decision.py`, `state/movement_draft.py` and smoke traversal: accept only current options, preserve contact evidence and test public return visibility. | No UI Aircraft exit/toggle action or derived engagement inventory. |
| `32-to-33.md` | Warlord/Enhancement construction requires explicit model profile and one-based index. | `core_client/live_smoke.py` uses a core-owned canonical config; verify startup against target. | No current UI roster constructor to migrate; future roster UI must collect these fields. |
| `33-to-34.md` | Detachments require canonical identity and source-backed construction constraints. | `core_client/live_smoke.py` again receives core-owned config/catalog; verify startup. | No UI catalog authoring; never invent empty constraints for old records. |
| `34-to-35.md` | Reactive Normal Move records distinguish turn owner from moving unit owner. | `core_client/local_session_client.py`, `state/movement_draft.py`: test opponent-turn actor/viewer and emitted movement mode. | No inference of actor or phase occurrence from unit owner. |
| `35-to-36.md` | Revival engagement changes from model IDs to canonical enemy unit evidence. | `state/placement_draft.py`: preserve public request/context and test accepted/rejected revival. | No UI engagement calculation or old-save migration. |
| `36-to-37.md` | Revival requests add source-linked `revival_phase_start` witness. | `core_client/protocol.py`, `state/placement_draft.py`: retain request identity/context in real placement tests. | No synthesized phase-start anchors. |
| `37-to-38.md` | Dice result overrides, source thresholds, Hit/Wound `critical_is_threshold`, Snap `success_requires_exact`, and finite `select_dice_extremum` are explicit. | `hud/dice_tray.py`, `state/finite_decision.py`: display physical faces separately from an assigned component value above die size and an aggregate override with unchanged faces; preserve source flags, submit emitted extremum component/option ID, and test private dice/event scope in real sessions because canonical examples omit these overrides. | No UI die reinterpretation, tie breaking, or arithmetic. |
| `38-to-39.md` | Movement records may carry `base_contact_query`/`deemed_base_contacts`, redacted from public view. | `state/movement_draft.py`, viewer events: submit original path witness and check redaction. | No UI counterfactual path or contact validation. |
| `39-to-40.md` | Random characteristics expose source expressions and nullable numeric values; Range can resolve to no target, random Wounds initialize before live health, and suppressed OC remains unevaluated. | `core_client/protocol.py`, `render/core_projection.py`, `state/assignment_workspace.py`: strict parse, expression/unknown display, targetless workflow and health/presence regression. | Projection/editor change; never roll, substitute zero for unknowns, or infer health from a later evaluation. |
| `40-to-41.md` | `select_modifier_ignores` is a per-occurrence finite subset choice. Mission Action requests/options require nullable `objective_control_modifier_scope_id` and scoped reenumeration. Nested save options require `inherent_roll_modifiers`; evaluated random values pair `evaluation_raw` with evaluation/ID; source operations may carry `result_floor`, with modifier traces and ignore inventories remaining distinct from intrinsic dice. A first-failed-save Damage-to-zero `SET 0` is one sourced operation. | `core_client/protocol.py` preserves open nested decision/event/game-view payloads; `state/finite_decision.py` submits only current emitted option IDs after each Mission Action/modifier continuation; `hud/dice_tray.py` and `render/core_projection.py` consume viewer-visible result/projection evidence without recomputation. M2 runs real owner/opponent sessions for scoped Action reenumeration, save choice/inherent AP or cover, random raw versus evaluated display, floor-limited and Damage-to-zero source operations with stale/invalid option diagnostics. | No UI save-profile editing, modifier-sign heuristic, floor arithmetic, synthesized random raw, or reused choice across occurrences; engine/private restore evidence stays core-owned. |
| `41-to-42.md` | Ranged `declarations` may be empty; selected physical weapons may have `target_unit_instance_id: null`; targetless candidates and optional `weapons_without_attacks` appear. Explicit empty declarations, selected targetless weapons, and automatic no-candidate completion are distinct origins with different obligations. | `state/assignment_workspace.py`, viewer event/HUD consumers: preserve empty versus omitted inventories, instance IDs, nested ability choices and null target; M2 tests real accepted/invalid submissions for all three origins plus mixed attacking/targetless rows, selected-only Hazardous/One Shot, omitted versus explicit-empty `weapons_without_attacks`, and display that never labels a targetless selection as a fired attack. | Editor and event-display change; zero attacks is valid, but shot participation, Hidden loss and after-shot effects belong only to actual attacks. |

## Cross-cutting checks for the atomic pin milestone

Contract 26's duplicated Core ability path is separate from nested weapon selections.
`UiDecision` in `core_client/protocol.py` must retain each source-backed unit, opportunity,
physical occurrence and current option payload; `state/finite_decision.py` sends only that
request's emitted ID. The owner's setup view/status/event delta may show the selected
`core_ability_instance`; the opponent's projection and event delta must not reveal the
secret request, selected source, expiry or `visibility_source` metadata. M2 should use a
real source-backed duplicate Core ability setup (the target core's
`tests/unit/test_unit_abilities.py` provides a fixture pattern), alternate both viewers,
submit an emitted source, and reject a stale/forged source. A second real destruction
path must show `selection_kind: "duplicated_deadly_demise_instance"`, one required
source choice without decline, accepted continuation and a rejected invented decline.
Scouts and Feel No Pain continue through their emitted source choices; test Scouts'
shared/lowest-unshared distance options, including Transport cargo, without deriving
source or distance in the UI. These branches are not proved by weapon declaration tests.

Contract 41 adds nested modifier evidence to existing envelopes, rather than a new
proposal editor. `UiDecision.payload`, `UiFiniteOption.payload`, `UiGameView` and
`UiEventDelta` must preserve viewer-visible source operation fields; the UI must not
read private restore origins, change a `SaveOption`, infer `evaluation_raw` from a
display value, or evaluate `result_floor`. M2 needs a real automatic Action
opportunity where OC modifier choices reenumerate `start_mission_action` options
with the same non-null `objective_control_modifier_scope_id`, including a choice
that removes an Action by leaving OC 0. Check owner-only modifier requests,
opponent-safe refreshes, current option IDs, and a stale/invalid submission.
Separate real save and random-profile scenarios must preserve required
`inherent_roll_modifiers` distinct from `roll_modifiers`, paired
`evaluation_raw`/`evaluation`/`evaluation_id`, and optional source-operation
`result_floor` while the HUD shows only core-evaluated results. The target core's
`tests/unit/test_order93_mission_action_modifiers.py`,
`tests/unit/test_ws14_attack_sequence_runtime_hooks.py`, and
`tests/unit/test_order93_modifier_ignore.py` provide construction patterns;
the current canonical examples do not contain those four fields. Use the UI's
public session facade for the M2 consumer tests, not a direct call to the core's
internal Action request builder.

Order 24 in `docs/ADAPTER_DECISION_CONTRACT.md` adds source-authorized splitting under
Contract 11.3, between the numbered major migration files. The finite
`select_unit_split_membership` choices install two successors. Their visible model rows in
`battlefield_view.authoritative.models_by_id` carry the **current** `unit_instance_id` and an
optional closed `split_origin` proof (`source_unit_instance_id`, `split_id`,
`successor_index`). `core_client/protocol.py` must preserve that projection;
`render/core_projection.py` and its view models must make current ownership/proof available to
`state/placement_draft.py`, whose model-placement serializer must copy both exact values.
Immutable model-ID prefixes cannot establish successor ownership. M2 must split a real unit,
submit a successor placement through the public session facade, verify the accepted placement,
verify typed invalid diagnostics for missing or drifted origin/owner proof, and alternate player
views to ensure the private partition and successor rows remain viewer-scoped.

The adapter contract's Formal Session Transport section binds persistence, replay, and cached
requests to the exact engine build; no Contract 10 save or request is reinterpreted under 42.
Order 91 can automatically complete shooting when selection has no attack candidates. Order 92
adds `select_melee_weapon`, a committed melee weapon instance, and random Attacks context.
Order 95 distinguishes empty declarations, targetless selected weapons, and omitted inventories.
Twin-linked optional wound rerolls remain in the existing finite dice-reroll family. These
details prevent a shooting-only migration from masking melee or no-candidate failures.
For M2, use the target core's `tests/unit/test_order95_optional_shooting.py` patterns to
exercise each zero-attack origin through the UI's public facade and compare owner/opponent
event displays; `tests/unit/test_phase10j_dice_semantics.py` supplies physical-versus-assigned
die and aggregate-override patterns absent from the canonical conformance examples.

The target pin must remain on an implementation branch until strict examples, real public-session
submission and invalid-diagnostic tests, viewer-scope/render tests, the simplified smoke path,
and all repository gates pass. No core source file is edited for this inventory.

## Authorized continuation: Contract 42.0 to 44.1.0

The table above records the original 10.2-to-42 review. The current implementation target is
Core `fc12fa214642f1b1f2a31b56be7323b7d76dbebc`, external contract `44.1.0`.
The fourteen commits after the original `6e86f44b87c4559a9297596d5d18dc4247b8cbc3` target
were reviewed against `contracts/migrations/42-to-43.md`, `43-to-44.md`, the current manifest,
`docs/ADAPTER_DECISION_CONTRACT.md`, and the changed public producers and consumers.

| Change | Current public authority | UI consumer |
| --- | --- | --- |
| Order 101 setup retry | A well-formed rule-invalid Disembark or reserve attempt can return fresh movement selection; malformed or stale input retains the proposal. | Follow current request/option IDs; no cached selection retry. |
| Contract 42.1 Shock Disembark | Start/completion engagement lists are empty and no forced Fight selection is queued. | Keep the engine event and current decision ordering. |
| Contract 42.2 Fight completion | `fight_selection_completed` records consumed selection; `unit_has_fought` requires an actual melee attack. | Display emitted events without equating an empty selection to combat. |
| Contract 43 Precision grouping | Every `GatheredAttackGroup` requires Boolean `target_has_character`; deterministic group IDs change. | Preserve current Core group/option IDs and recorded context; discard older cached IDs. |
| Contract 44 membership | Every authoritative battlefield model requires nullable `rules_unit_instance_id`; battlefield schema is `battlefield-view-v5-rules-unit-membership`. | Join current `placed` models across physical owners to the canonical movement actor; preserve null redaction and physical owner separately. |
| Contract 44.1 Firing Deck | A non-null Firing Deck proposal publishes `firing_deck_already_shot_unit_instance_ids`; `[]` is authentic empty history, `null` is no ordinary Shooting authority. | Copy the request history and current weapon/cargo identities into the declaration; reject missing or null authority for borrowed weapons. |

Session metadata, command result and outcome tags are `v44-contract`. Persistence is
`session-persistence-v35-target-aware-attack-groups` with external persistence pin `44.0.0`;
the current runtime contract is `44.1.0`. Replay is
`replay-artifact-v36-target-aware-attack-groups`. Old saves, replay data, pending requests and
attack-group IDs stay on their original exact runtime. Neither migration file authorizes an
inferred missing membership or target context.

The intervening Core issue fixes also repair attached Scout physical ownership and accepted
history, reserve-deadline continuation, attached Charge membership projection, and public Firing
Deck history. They require real UI submission checks before an M2 acceptance claim. Catalog reuse
in the same range affects selected test construction and offline immutable geometry generation;
it does not establish a current UI startup speedup. The separate M2 evidence record reports
the exact current checks and limits.
