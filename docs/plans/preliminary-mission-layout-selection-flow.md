# Preliminary: Mission And Layout Selection Flow

Status: Preliminary - waiting on core DecisionRequest support

## Desired Outcome

If the core engine owner exposes mission, terrain layout, objective layout, or mission-pack
selection as user-facing decisions, the UI should present those choices as a setup workbench that
answers engine requests and then renders the resulting authoritative projection.

## Current State

Mission and table setup data can be configuration-driven. The UI renders the engine projection it
receives, but should not choose mission or terrain layout through a private path unless the core
emits a request requiring that user choice.

## Core Dependency

Concretize this plan only after the core exposes one or more setup `DecisionRequest` surfaces for:

- mission pack or mission selection;
- deployment map selection;
- terrain layout selection;
- objective layout selection;
- any roll-off or randomization result the engine owns.

Each request should include viewer visibility rules, legal option IDs, and the replay-safe context
needed to audit the selected setup path.

## Future UI Slices

1. Add setup workbench display for mission/layout request families.
2. Render engine-provided option cards with preview thumbnails when available.
3. Let users inspect but not locally mutate the table preview.
4. Submit selected option IDs through finite decisions or placement-like proposals if the core uses
   parameterized setup payloads.
5. Update HUD and event trace evidence for selected mission/layout state.

## Non-Goals

- No local random mission draw.
- No local terrain placement validator.
- No mission scoring rule implementation in the UI.
- No hidden setup leakage before the core marks information public.
