# Phase 13 - Packaging, CI, and regression hardening

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
  - accepted movement response
  - invalid movement response
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

**Milestone 13: "Development-Ready UI Repo"**

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
