# Phase 21A - Core Phase 15D-15F adapter adaptation

## Status

Implemented. This phase was planned after reviewing `Warhammer_40k_AI` `main` at
`643a99385e95` on 2026-06-07 and implemented as the first part of Phase 21 packaging and
regression hardening.

## Goal

Keep the existing UI safe against the newly exposed engine decision families while avoiding premature
implementation of fight, melee, Stratagem, charge, shooting, or placement tools.

The current UI movement draft tool is intentionally scoped to Movement phase `normal_move`,
`advance`, and `fall_back` proposals. The updated engine now exposes additional adapter-visible
request surfaces:

- Fight phase `submit_movement_proposal` requests for `pile_in` and `consolidate`.
- Fight phase `submit_melee_declaration` requests with model/weapon/target-allocation payloads.
- Charge/Fight `submit_stratagem_target_proposal` requests for Heroic Intervention,
  Counteroffensive, Crushing Impact, and Epic Challenge.
- Completion gate finite options such as `complete_charge_phase`, `complete_shooting_phase`,
  `complete_reinforcements`, `complete_disembarks`, `eligible_to_fight_pass`, and
  `decline_fight_interrupt`.
- Repaired normalized `pending_proposal` metadata: every visible parameterized request should carry
  `request_id`, `decision_type`, and `actor_id` from the pending `DecisionRequest`.

## Contract Impact

No UI-authored rules are required. The engine remains the source of truth for legal options,
proposal kinds, timing windows, target eligibility, attack counts, movement legality, CP costs,
Stratagem effects, and phase completion.

The immediate UI adaptation is defensive and representational:

- Parse and display the new requests without weakening strict protocol validation.
- Preserve exact request IDs, option IDs, proposal kinds, and engine-emitted metadata.
- Make unsupported parameterized tools obvious to the player/reviewer.
- Prevent unsupported engine request families from flowing through the existing Movement phase
  Normal Move/Fall Back submission path.

## Tasks

- [x] Add or refresh golden fixtures from the current engine for:
  - `pile_in` pending proposal;
  - `consolidate` pending proposal;
  - `submit_melee_declaration` pending proposal;
  - `submit_stratagem_target_proposal` requests for at least one Phase 15E Fight window and one
    Heroic Intervention Charge Move follow-up context;
  - completion-gate finite decisions for Movement, Shooting, Charge, and Fight phase examples.
- [x] Add protocol regression tests that prove missing `request_id`, `decision_type`, or `actor_id`
  in `pending_proposal` remains a hard UI protocol error rather than a fallback path.
- [x] Add state/HUD regression tests that prove `pile_in`, `consolidate`, `charge_move`,
  `submit_melee_declaration`, `submit_placement_proposal`, and
  `submit_stratagem_target_proposal` render through generic unsupported/proposal surfaces until a
  dedicated tool exists.
- [x] Add movement submission regression tests proving the existing movement draft can submit only
  the supported Movement phase proposal kinds: `normal_move`, `advance`, and `fall_back`.
- [x] Confirm finite completion options submit exact engine option IDs and do not invent local
  "next phase" shortcuts.
- [x] Update preview/manual validation docs with expected generic rendering for the new unsupported
  proposal families.
- [x] Track any need for a future generic `submit_payload` UI-client method separately from the
  current movement-only `submit_movement_payload` method.

## Acceptance Criteria

- [x] Current Normal Move/Advance/Fall Back behavior remains unchanged.
- [x] New Fight movement proposal kinds cannot be submitted by the existing Movement phase draft
  flow.
- [x] Unsupported parameterized proposals are visible and inspectable, but not locally validated or
  submitted through the wrong tool.
- [x] Finite completion/pass/decline options are displayed and submitted as exact engine-emitted
  option IDs.
- [x] `pending_proposal` metadata remains strict and fail-fast.
- [x] No UI code imports mutable engine internals outside `core_client`.

## Non-Goals

- No implementation of Charge Move path drafting.
- No implementation of Pile In or Consolidate path drafting.
- No implementation of melee weapon/target allocation.
- No implementation of Stratagem target binding.
- No attempt to infer Fight eligibility, legal targets, CP costs, or phase completion from local UI
  state.

## Implementation Notes

- Added `tests/fixtures/phase21a_core_requests.json` with current-contract examples for Fight
  movement, melee declaration, Stratagem target binding, placement, Charge Move follow-up, and
  completion/pass/decline finite decisions.
- Added `tests/test_core_phase15_adapter_regression.py` to prove:
  - fixture payloads parse as JSON-safe UI protocol objects;
  - `pending_proposal` metadata requires `request_id`, `decision_type`, and `actor_id`;
  - unsupported parameterized requests render through generic unsupported HUD surfaces;
  - `pile_in`, `consolidate`, and Heroic Intervention `charge_move` cannot be submitted by the
    current Movement phase draft flow;
  - completion/pass/decline finite options submit exact engine-emitted option IDs.
- Hardened `UiParameterizedProposalRequest` so `actor_id` is required for parameterized proposal
  parsing.
- Hardened `prepare_movement_submission` so the Movement phase draft submitter rejects unsupported
  movement proposal kinds before client submission.
- Fixed the live-core UI handoff so clicked units update finite-option focus, and proposal-required
  movement drafts anchor to the engine proposal unit even if local selection drifted before the
  proposal arrived.
- Fixed finite-option focus so a newly arrived engine request starts at its own first option instead
  of inheriting the previous request's option index. Unit clicks now retarget finite focus only when
  the option-to-unit match is unambiguous, preventing movement action focus from silently changing
  when every action option belongs to the same unit.
- The selected-unit inspector now marks the currently highlighted finite action in its action list
  so `advance`, `normal_move`, and `remain_stationary` focus can be reviewed before pressing Enter.
- The future generic `submit_payload` facade remains tracked as future work. It should be introduced
  when a dedicated non-Movement draft tool exists, not as part of this defensive regression slice.

## Automated Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_core_phase15_adapter_regression.py tests/test_core_client_protocol.py tests/test_movement_submission.py tests/test_hud_selection.py tests/test_finite_decision_state.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gui_event_driver.py::test_driver_live_core_smoke_click_unit_opens_actions_and_starts_movement_draft tests/test_movement_draft.py::test_start_for_pending_uses_proposal_unit_when_selection_drifted`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_finite_decision_state.py tests/test_gui_event_driver.py::test_driver_live_core_smoke_click_unit_opens_actions_and_starts_movement_draft tests/test_hud_selection.py::test_unit_panel_options_are_derived_from_pending_decision_data tests/test_hud_ergonomics.py::test_ergonomic_selected_unit_actions_mark_highlighted_option tests/test_render_primitives.py::test_hud_primitives_include_selection_panel_menu_and_debug_inspector`

## Manual Validation Checklist

- Launch
  `WARHAMMER40K_ARCADE_UI_DEBUG_PHASE6=1 uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/default.yaml`
  and verify Normal Move drafting still opens and submits as before against the fake/debug movement
  fixture.
- Launch `uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/default.yaml`, select a unit,
  and press Enter once. Confirm the plain read-only fake fixture does not show a `no_core_client`
  diagnostic when no engine decision is pending.
- Launch `uv run warhammer40k-arcade-ui --live-core-smoke --ui-prefs docs/preferences/default.yaml`
  and verify live Movement phase finite and movement proposal interactions still behave as before.
- In live-core smoke, select the second friendly Intercessor unit during `select_movement_unit`,
  press Enter, confirm the inspector marks `Advance` first, press Tab once, confirm the inspector
  marks `Normal Move`, click the same unit again, and press Enter. Confirm the resulting
  `submit_movement_proposal` request remains for that same selected unit and `normal_move`.
- If the live core reaches a Fight Pile In, Consolidate, melee declaration, placement, or Phase 15E
  Stratagem target-binding request before dedicated tools exist, verify the HUD says
  `Unsupported proposal tool: <proposal_kind>` and does not enter the movement draft workflow.
