# Phase 35 migration inventory: core Contract 10.2 to 42.0

Reviewed against `Warhammer_40k_AI` commit
`6e86f44b87c4559a9297596d5d18dc4247b8cbc3`. This is evidence for the Phase 35 plan,
not a claim that the UI already supports Contract 42. The UI still pins
`dbfcc3a99e9d560d1354506352a09d48ca555a94` / Contract `10.2.0` until the atomic
compatibility milestone passes its acceptance gates.

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
| `10-to-11.md` | Every physical ranged copy has an opaque `weapon_instance_id`; declaration and history retain it. | `state/assignment_workspace.py`: copy each emitted ID, distinguish duplicate copies, test accepted and invalid real-core submissions. | Editor change; never derive the ID from model/profile or row order. |
| `11-to-12.md` | Fight/Shoot On Death may retain a destroyed model at its original pose until resolution. | `render/core_projection.py`: render physical pose while present, then remove when core removes it; headless render regression. | Renderer change; model `state` alone is insufficient. |
| `12-to-13.md` | Model keyword/source arrays, current rules-unit keywords, and private split/attachment membership enter projections. | `core_client/protocol.py`, `render/arcade_window.py`: strict model display parse and alternating viewer-cache/redaction tests. | Projection change; do not rebuild rules-unit keywords or retain hidden rows. |
| `13-to-14.md` | Continuous LOS witness replaces ray-index fields in shooting candidates; Cover remains engine-authored. | `state/assignment_workspace.py` treats candidates as engine evidence; parse target examples and check no old ray-field assumptions. | No UI LOS algorithm or witness synthesis. |
| `14-to-15.md` | Mandatory/optional sequencing is engine ordered; selected actor can differ from turn owner. | `state/finite_decision.py`, `core_client/local_session_client.py`: submit emitted option IDs and use request actor for viewer/status. | No UI rule-order table. |
| `15-to-16.md` | Nested hit rolls carry `critical_threshold` and `threshold_source_ids`; raw six alone does not define critical. | `hud/dice_tray.py` and viewer event surfaces: preserve/display engine evidence in conformance tests. | No UI critical-hit calculation. |
| `16-to-17.md` | Phase-end Overwatch window no longer names a moved enemy; it may be declined. | `state/assignment_workspace.py` Stratagem context and finite route: test source context/decline without moved-unit key. | No new editor family; no inferred trigger target. |
| `17-to-18.md` | Finite `select_charge_targets` commits a subset. The modified Charge roll is bounded to 1–12; subsequent distance effects produce a separate nonnegative `movement_budget.maximum_distance_inches` that may exceed 12 or be fractional. Target eligibility requires both that maximum and the distinct 12-inch Charge target limit. | `state/movement_draft.py`: use `context.target_selection.target_ids`, preserve the engine budget and witness, and test the bounded roll, different movement maximum, 12-inch target gate, and rejection of reachable-but-uncommitted targets. | Movement editor and finite-routing change; never use the roll as the full path budget or widen target eligibility with later distance effects. |
| `18-to-19.md` | Charge uses canonical Attached Unit actor and living models from every component; endpoint witness is engine-authored. | `state/movement_draft.py`: exercise attached paths through real session; preserve component membership and witness. | No component alias or endpoint inference. |
| `19-to-20.md` | Eligible whole-Charge reroll happens before target selection. | `state/finite_decision.py`: route current reroll option; test continuation to target selection. | No reroll calculation or new UI proposal. |
| `20-to-21.md` | Heroic Intervention shares Charge options, targets, and witnessed movement; source roll cap may be six. | `state/movement_draft.py`: consume published movement budget and Charge target commitment in that context. | Shared editor path; no Heroic-only rules. |
| `21-to-22.md` | Walking/Take to the Skies is an emitted finite choice; selected flight and penalty persist into proposals. | `state/finite_decision.py`, `state/movement_draft.py`: preserve option ID, request context, and path on retry. | No synthetic flight option or distance adjustment. |
| `22-to-23.md` | Surge finite option commits closest enemy; triggered movement uses plural `aircraft_movement_policies`. | `state/movement_draft.py`: preserve target/context and test no singular-policy assumption. | No Surge target picker or aircraft policy calculation. |
| `23-to-24.md` | Optional movement keyword choice is in finite option IDs/context; terrain capability adds nullable transit height. | `state/finite_decision.py`, `render/core_projection.py`: route emitted options and parse nullable capability where consumed. | No grant or terrain legality inference. |
| `24-to-25.md` | Public mission setup adds nullable attacker/defender battlefield edges for oversized setup. | `core_client/protocol.py` mission payload and `state/placement_draft.py`: preserve projected context; conformance and real placement. | No UI edge eligibility algorithm. |
| `25-to-26.md` | Duplicate weapon abilities use physical ability-instance IDs and nested `select_weapon_ability_instance`. | `state/assignment_workspace.py`, `state/finite_decision.py`: retain selected IDs, route nested option IDs, test duplicates. | Editor/finite coverage change; no descriptor-based substitution. |
| `26-to-27.md` | Same-turn setup history blocks Embark; completion records add `setup_kind`. | `state/finite_decision.py` and placement submission: test engine options/diagnostics after setup. | No editor change: core decides eligibility and owns history. |
| `27-to-28.md` | Shock Disembark starts with an explicitly empty engaged-enemy list; resulting engagement is engine evidence. | `state/placement_draft.py`: preserve empty published list and rejected-placement diagnostics. | No UI reconstruction from Transport engagement. |
| `28-to-29.md` | Loaded Transport ingress and Rapid Disembark inherit private placement restrictions. | `state/placement_draft.py`, viewer projection: test public placement/retry and redaction. | No policy decoding; private ingress history stays core-owned. |
| `29-to-30.md` | Reserve deadlines and post-ingress movement locks change legal options. | `state/finite_decision.py`, placement submission: test engine-issued options and invalid diagnostics. | No editor change: no UI deadline table. |
| `30-to-31.md` | Firing Deck declaration request lists all embarked cargo; accepted inventory includes noncontributors. | `state/assignment_workspace.py`: preserve candidate data and test cargo snapshot/selection paths. | No UI reconstruction of all cargo from chosen weapons. |
| `31-to-32.md` | Aircraft use mandatory ingress/return; Hover toggle and hover state are removed. | `state/finite_decision.py` and smoke traversal: accept only current options, test return visibility. | No UI Aircraft exit/toggle action. |
| `32-to-33.md` | Warlord/Enhancement construction requires explicit model profile and one-based index. | `core_client/live_smoke.py` uses a core-owned canonical config; verify startup against target. | No current UI roster constructor to migrate; future roster UI must collect these fields. |
| `33-to-34.md` | Detachments require canonical identity and source-backed construction constraints. | `core_client/live_smoke.py` again receives core-owned config/catalog; verify startup. | No UI catalog authoring; never invent empty constraints for old records. |
| `34-to-35.md` | Reactive Normal Move records distinguish turn owner from moving unit owner. | `core_client/local_session_client.py`, `state/movement_draft.py`: test opponent-turn actor/viewer and emitted movement mode. | No inference of actor or phase occurrence from unit owner. |
| `35-to-36.md` | Revival engagement changes from model IDs to canonical enemy unit evidence. | `state/placement_draft.py`: preserve public request/context and test accepted/rejected revival. | No UI engagement calculation or old-save migration. |
| `36-to-37.md` | Revival requests add source-linked `revival_phase_start` witness. | `core_client/protocol.py`, `state/placement_draft.py`: retain request identity/context in real placement tests. | No synthesized phase-start anchors. |
| `37-to-38.md` | Dice result overrides, source thresholds, and finite `select_dice_extremum` are explicit. | `hud/dice_tray.py`, `state/finite_decision.py`: display result evidence and submit emitted extremum ID. | No UI die reinterpretation or arithmetic. |
| `38-to-39.md` | Movement records may carry `base_contact_query`/`deemed_base_contacts`, redacted from public view. | `state/movement_draft.py`, viewer events: submit original path witness and check redaction. | No UI counterfactual path or contact validation. |
| `39-to-40.md` | Random characteristics expose source expressions and nullable numeric values; Range can resolve to no target. | `core_client/protocol.py`, `render/core_projection.py`, `state/assignment_workspace.py`: strict parse, expression/unknown display, targetless workflow. | Projection/editor change; never roll or substitute zero. |
| `40-to-41.md` | `select_modifier_ignores` is a per-occurrence finite subset choice; traces retain source operations. | `state/finite_decision.py`, HUD: route each emitted ID and preserve viewer scope on continuation. | No modifier-sign heuristic or reused choice. |
| `41-to-42.md` | Ranged `declarations` may be empty; selected physical weapons may have `target_unit_instance_id: null`; targetless candidates and optional `weapons_without_attacks` appear. | `state/assignment_workspace.py`: preserve empty versus omitted inventories, instance IDs, ability choices and null target; test real accepted/invalid submissions. | Editor change; zero attacks is a valid core result. |

## Cross-cutting checks for the atomic pin milestone

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

The target pin must remain on an implementation branch until strict examples, real public-session
submission and invalid-diagnostic tests, viewer-scope/render tests, the simplified smoke path,
and all repository gates pass. No core source file is edited for this inventory.
