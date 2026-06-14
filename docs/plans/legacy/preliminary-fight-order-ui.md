# Preliminary - Fight order UI

## Status

Preliminary plan. Do not treat this as a numbered implementation phase until the current
`Warhammer_40k_AI` fight order payloads are reviewed again immediately before work starts.

## Goal

Improve the finite-decision UI and visual summaries for Fight phase activation and interrupt
requests while keeping fight eligibility, ordering, and reaction consumption fully engine-owned.

In plain language: this is the future tool for helping the player understand "which unit can fight
now?", "is this Fights First or Remaining Combats?", "can I pass?", and "am I answering an
interrupt window?" before selecting one of the engine's finite options.

## Current Contract Assumptions

Based on the local core checkout reviewed on 2026-06-05:

- Fight activation is finite: `select_fight_activation`.
- Fight interrupts are finite reaction-window decisions: `resolve_fight_interrupt`.
- Fight activation options use `fight:<fight_type>:<unit_instance_id>`, where `fight_type` is
  `normal` or `overrun`.
- Non-fight options such as `eligible_to_fight_pass` and `decline_fight_interrupt` are
  engine-issued finite options.
- The request payload exposes fight-order state, ordering band, actor, eligibility contexts, pass
  availability, or interrupt context as engine-owned data.
- The UI must not infer fight eligibility, engagement context, pass distance, Fights First ordering,
  overrun eligibility, interrupt availability, or interrupt consumption.

## Proposed User Flow

1. The engine emits `select_fight_activation` or `resolve_fight_interrupt`.
2. The finite decision panel remains the submission surface.
3. The Generic Assignment HUD shows a richer request summary:
   - actor/player context;
   - ordering band;
   - fight activation options;
   - pass or decline options;
   - interrupt/reaction context when present.
4. Clicking an eligible model or unit can highlight the matching finite option only when the option
   exists in the engine request.
5. The action visual summary can highlight eligible units and brighten the currently highlighted
   fight option.
6. Submission still sends the selected finite option ID through the existing finite decision path.

## Preliminary Tasks

- [ ] Refresh the core fight order and interrupt contract before implementation.
- [ ] Add finite request summary view models for fight activation and fight interrupt payloads.
- [ ] Add option parsing helpers for display only:
  - `fight_type`;
  - `unit_instance_id`;
  - pass/decline option identity.
- [ ] Add model/unit click-to-option highlighting when the clicked entity maps to exactly one
  engine-issued fight option.
- [ ] Add HUD rows for ordering band, pass availability, interrupt context, and selected option.
- [ ] Add visual summary adapter:
  - highlight eligible units;
  - distinguish normal fight and overrun options;
  - distinguish interrupt requests from ordinary fight activation;
  - show pass/decline as explicit non-map choices.
- [ ] Add tests proving the UI submits exact finite option IDs and does not synthesize fight
  choices.

## Preliminary Acceptance Criteria

- [ ] Fight activation and fight interrupt requests remain finite submissions.
- [ ] The UI displays ordering and interrupt context from engine payloads without local inference.
- [ ] Clicking a unit can only highlight an existing engine-issued finite option.
- [ ] Pass and decline options are visible and distinct from unit activation options.
- [ ] Visual summaries highlight eligible units but do not draw pile-in, consolidation, or attack
  effects unless a later engine request exposes that data.

## Contract Questions To Revisit

- Which payload fields should be treated as stable display fields for ordering band and
  eligibility context?
- Does the request expose enough unit labels for useful HUD rows, or should labels come from the
  projection entity map?
- Should the UI display source-backed pass distance directly, or only whether the pass option
  exists?
- How should nested reaction breadcrumbs be displayed when an interrupt blocks and later resumes a
  parent Fight phase?
