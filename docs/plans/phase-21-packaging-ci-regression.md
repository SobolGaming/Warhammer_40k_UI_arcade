# Phase 21 - Packaging, CI, and regression hardening

## Goal

Make the UI reliable enough to use during engine development.

## Tasks

- [ ] Add GitHub Actions or equivalent CI:
  - `uv sync --locked`
  - `ruff check`
  - `ruff format --check`
  - `pyright`
  - `pytest`
- [ ] Add coverage threshold for non-rendering logic.
- [ ] Add headless-safe smoke test mode where possible.
- [ ] Add golden fixtures:
  - finite movement option request
  - movement proposal request
  - Fall Back movement proposal request with `fall_back_mode`
  - Charge Move proposal request with `proposal_kind: "charge_move"` and target/no-move context
  - Fight movement proposal requests with `proposal_kind: "pile_in"` and
    `proposal_kind: "consolidate"` that remain outside the current Movement phase draft tool
  - melee declaration request with `decision_type: "submit_melee_declaration"` and
    `proposal_kind: "melee_declaration"`
  - Stratagem target-binding request with `decision_type: "submit_stratagem_target_proposal"` and
    `proposal_kind: "stratagem_target_binding"`
  - accepted movement response
  - invalid movement response
  - normalized `pending_proposal` metadata containing `request_id`, `decision_type`, `actor_id`,
    and `proposal_kind`
  - finite fight activation request
  - finite fight interrupt request
  - finite phase completion requests/options including `complete_reinforcements`,
    `complete_disembarks`, `complete_shooting_phase`, and `complete_charge_phase`
  - unsupported non-movement parameterized request, such as shooting declaration or Stratagem target
    proposal, to prove generic proposal display does not force movement parsing
  - default UI preferences profile
  - invalid UI preferences profile
- [ ] Add "no direct engine mutation" static check:
  - prohibit imports or calls into known mutable engine state APIs outside `core_client`
  - enforce via custom script if needed
- [ ] Add changelog.
- [ ] Add architecture decision records under `docs/adr/`.

## Acceptance criteria

- [ ] CI passes on clean checkout.
- [ ] All fixtures are deterministic and JSON-safe.
- [ ] Preference fixtures are deterministic, portable, and schema-versioned.
- [ ] Pull requests fail if pyright, ruff, or tests fail.
- [ ] A new developer can run the UI from README without hidden steps.
- [ ] `architecture.md` reflects actual module structure.

## Closeout milestone

**Milestone 16: "Development-Ready UI Repo"**

The UI repo is stable enough to use as a companion project while the core engine continues evolving.

## Testing strategy by layer

| Layer | What to test | Example acceptance test |
| --- | --- | --- |
| `core_client` | Contract translation, request IDs, invalid diagnostics | Given a pending movement request, generated submission includes exact request id. |
| `state` | Selection, draft path, cancel/submit transitions | Escape clears local draft but does not call submit. |
| `input` | Hit testing, waypoint editing, command mapping | Clicking overlapping bases cycles candidates deterministically. |
| `preferences` | Schema loading, hotkey conflicts, overlay/command IDs | Unknown overlay IDs produce typed config diagnostics, not silent fallback. |
| `render` | Coordinate transforms, primitive generation | World-to-screen-to-world round trip stays within tolerance. |
| `hud` | View-model generation | Finite options shown are exactly pending engine options. |
| integration | End-to-end finite + movement flow | Select Normal Move, submit path, refresh view, clear draft. |
| static QA | No private mutation path | Only `core_client` may import engine adapter/session modules. |

## Core Update Regression Targets

Reviewed `Warhammer_40k_AI` `main` at `643a99385e95` on 2026-06-07. CI fixtures should cover the
new adapter-visible request families without requiring their full UI tools to exist yet:

- `pending_proposal` metadata must be complete for every parameterized family the UI parses.
- `charge_move`, `pile_in`, and `consolidate` must remain unsupported or dedicated-tool-specific;
  they must not be submitted through Normal Move/Advance/Fall Back code paths.
- `submit_melee_declaration` and `submit_stratagem_target_proposal` must render through generic
  proposal/unsupported surfaces until dedicated assignment tools exist.
- `select_fight_activation` and `resolve_fight_interrupt` finite requests must render and submit
  exact engine option IDs, including pass/decline options.
- Phase completion finite options, including `complete_shooting_phase` and `complete_charge_phase`,
  must submit exact engine option IDs and must not be replaced by UI-local next-phase shortcuts.
- Completion gates should be treated as engine-owned sequencing: the UI can display the skipped-unit
  summaries, but it must not infer when a phase is complete from local table state.
