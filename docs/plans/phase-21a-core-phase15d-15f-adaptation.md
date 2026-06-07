# Phase 21A - Core Phase 15D-15F adapter adaptation

## Status

Immediate planning slice after reviewing `Warhammer_40k_AI` `main` at `643a99385e95` on
2026-06-07. This should run before, or as the first part of, Phase 21 packaging and regression
hardening.

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

- [ ] Add or refresh golden fixtures from the current engine for:
  - `pile_in` pending proposal;
  - `consolidate` pending proposal;
  - `submit_melee_declaration` pending proposal;
  - `submit_stratagem_target_proposal` requests for at least one Phase 15E Fight window and one
    Heroic Intervention Charge Move follow-up context;
  - completion-gate finite decisions for Movement, Shooting, Charge, and Fight phase examples.
- [ ] Add protocol regression tests that prove missing `request_id`, `decision_type`, or `actor_id`
  in `pending_proposal` remains a hard UI protocol error rather than a fallback path.
- [ ] Add state/HUD regression tests that prove `pile_in`, `consolidate`, `charge_move`,
  `submit_melee_declaration`, `submit_placement_proposal`, and
  `submit_stratagem_target_proposal` render through generic unsupported/proposal surfaces until a
  dedicated tool exists.
- [ ] Add movement submission regression tests proving the existing movement draft can submit only
  the supported Movement phase proposal kinds: `normal_move`, `advance`, and `fall_back`.
- [ ] Confirm finite completion options submit exact engine option IDs and do not invent local
  "next phase" shortcuts.
- [ ] Update preview/manual validation docs with expected generic rendering for the new unsupported
  proposal families.
- [ ] Track any need for a future generic `submit_payload` UI-client method separately from the
  current movement-only `submit_movement_payload` method.

## Acceptance Criteria

- [ ] Current Normal Move/Advance/Fall Back behavior remains unchanged.
- [ ] New Fight movement proposal kinds cannot be submitted by the existing Movement phase draft
  flow.
- [ ] Unsupported parameterized proposals are visible and inspectable, but not locally validated or
  submitted through the wrong tool.
- [ ] Finite completion/pass/decline options are displayed and submitted as exact engine-emitted
  option IDs.
- [ ] `pending_proposal` metadata remains strict and fail-fast.
- [ ] No UI code imports mutable engine internals outside `core_client`.

## Manual Validation Checklist

- Launch the fake UI and confirm ordinary Movement phase drafting still behaves as before.
- Launch the live core smoke flow and confirm finite completion options remain selectable when the
  engine emits them.
- If the live core reaches Fight Pile In, Consolidate, melee declaration, or Phase 15E Stratagem
  target-binding windows before dedicated tools exist, confirm the UI shows an unsupported proposal
  panel instead of a Movement draft workflow.

## Non-Goals

- No implementation of Charge Move path drafting.
- No implementation of Pile In or Consolidate path drafting.
- No implementation of melee weapon/target allocation.
- No implementation of Stratagem target binding.
- No attempt to infer Fight eligibility, legal targets, CP costs, or phase completion from local UI
  state.
