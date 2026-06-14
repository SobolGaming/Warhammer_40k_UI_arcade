# Preliminary - Forensic event replay

## Goal

Explore a future `--play-events` workflow that ingests a forensic event trace and uses it to drive
the same UI-side interactions during a game session.

In plain language: when a tester finds a bug, they should be able to attach a trace file. Another
developer or agent should be able to launch the UI with that trace and have the UI replay the same
clicks, key presses, movement drafts, and submissions far enough to reproduce or narrow the bug.

This is intentionally preliminary and has no assigned phase. It should be revisited after crash
diagnostic bundles, generic assignment HUD work, and engine-side deterministic replay support are
better understood.

## Motivation

The Phase 14 forensic trace can already explain what happened, but it does not yet reproduce what
happened. Reproduction is especially valuable for:

- GUI-only bugs such as bad selection, bad hotkey dispatch, missing HUD state, or unexpected draft
  transitions;
- core/UI boundary bugs that happen only after a specific sequence of player actions;
- crash reports where the human-readable description is incomplete but the trace contains enough UI
  inputs to drive the same path;
- agent-driven debugging where a render or event harness can detect the failure after replay.

## Proposed Command Shape

Possible launch forms:

```bash
uv run warhammer40k-arcade-ui --play-events /tmp/ui-trace.jsonl
uv run warhammer40k-arcade-ui --live-core-smoke --play-events /tmp/ui-trace.jsonl
uv run warhammer40k-arcade-ui --play-events /tmp/ui-trace.jsonl --play-events-mode ui-only
uv run warhammer40k-arcade-ui --play-events /tmp/ui-trace.jsonl --play-events-stop-on-divergence
```

Possible supporting options:

- `--play-events-mode ui-only|core-assisted|captured-core`;
- `--play-events-speed instant|realtime|step`;
- `--play-events-until <event_name-or-index>`;
- `--play-events-stop-on-divergence`;
- `--play-events-write-trace /tmp/replayed-trace.jsonl` for comparing original and replayed runs.

Names and exact modes should stay provisional until the engine replay contract is clearer.

## Replay Modes

### UI-Only Replay

UI-only replay would read a forensic JSONL file, filter for UI boundary events, and dispatch the same
window-level calls through the existing GUI event driver:

- `ui.mouse_motion`;
- `ui.mouse_press`;
- `ui.mouse_release`;
- `ui.mouse_scroll`;
- `ui.mouse_drag`;
- `ui.key_press`;
- `ui.key_release`;
- later explicit UI command or tool events once those exist.

This mode is useful for pure UI bugs. It does not guarantee a live core session reaches the same
state because the engine may return different decisions, dice rolls, event cursors, card draws,
reaction windows, or projection payloads.

### Core-Assisted Replay

Core-assisted replay would run a real core session but use trace checkpoints to detect divergence.
The replayer would compare the current session against trace fields such as:

- viewer player ID;
- game ID;
- current request ID;
- decision type;
- proposal kind;
- event cursor;
- status kind;
- selected unit/model IDs;
- movement draft assignment counts;
- core response event names and payload summaries.

If a checkpoint does not match, replay should stop with a typed diagnostic that identifies the first
divergent event. This avoids silently driving a different game state.

### Captured-Core Replay

Captured-core replay would require more engine cooperation. The UI would replay inputs while a
captured core-response stream feeds back the same `GameViewPayload`, `LifecycleStatus`, and
event-delta payloads that were recorded during the original run.

This mode would be closest to deterministic reproduction of UI behavior, but it is not a substitute
for engine replay. It should be treated as a diagnostic harness, not an authoritative game replay.

## Engine Cooperation Needed

Reliable reproduction of live-core bugs requires engine-side support beyond UI input replay.
Likely needs include:

- engine commit SHA or release version in adapter-visible diagnostics;
- ruleset/source package version identifiers;
- deterministic game setup seed and any generated deployment/mission/card order data;
- deterministic dice manager seed or explicit dice outcome replay;
- event log cursor and event IDs stable enough for divergence checks;
- current pending request IDs and result IDs captured in replayable form;
- a way to initialize a live session from a replay manifest or captured crash diagnostic bundle;
- optional support for returning captured `LifecycleStatus`, `GameViewPayload`, and event-delta
  payloads for UI-only reproduction without mutating a live engine session.

Open question: whether the engine should expose a first-class replay/session snapshot API, or
whether this should be built on top of existing event logs, deterministic seeds, and adapter
payloads.

## Trace Schema Needs

The Phase 14 trace already contains many useful fields, but replay will likely need schema additions:

- stable monotonically increasing trace event index;
- original trace file/session ID;
- window size and camera state before input events;
- whether the UI event came from user input, GUI-driver input, or replay input;
- normalized input primitives that avoid Arcade/pyglet version-specific symbol ambiguity;
- explicit before/after checkpoints for command dispatch, selection state, movement draft state,
  pending decision, and event cursor;
- optional hash or digest of large payloads to support summary-level divergence checks.

Payload-level traces should remain viewer-scoped and redacted. Replay must not use hidden
information or secret opponent payloads.

## Non-Goals

- No authoritative UI-owned replay system.
- No UI-owned rules validation.
- No attempt to make stochastic live-core behavior deterministic without engine support.
- No hidden-information expansion through captured traces.
- No fallback that ignores divergence and keeps replaying as if the game states still match.
- No guarantee that traces from old UI/core versions replay cleanly after contracts change.

## Preliminary Tasks

- [ ] Define a `TraceReplayDriver` that can parse Phase 14 JSONL rows and dispatch supported UI
  input events through the existing GUI event driver.
- [ ] Add a typed replay diagnostic model for unsupported event names, malformed trace rows,
  missing UI fields, version mismatch, and divergence checkpoints.
- [ ] Add `--play-events` CLI plumbing behind an explicit opt-in flag.
- [ ] Add UI-only replay tests that confirm a trace containing selection and movement draft inputs
  reproduces the same local UI state against deterministic fake data.
- [ ] Add replay event markers to distinguish original human input from replay-driven input.
- [ ] Add optional side-by-side trace comparison: original trace row vs replayed row.
- [ ] Define engine-facing requirements for deterministic live-core replay and connect them to
  future Warhammer_40k_AI work.
- [ ] Decide whether crash diagnostic bundles should embed forensic traces directly or reference
  external trace files.

## Draft Acceptance Criteria

Future concrete implementation should satisfy:

- `--play-events <trace.jsonl>` can replay supported UI input rows against a deterministic fixture or
  fake-core session.
- Unsupported rows produce typed diagnostics, not silent skips.
- Replay stops on divergence when the trace says the current request/status/event cursor should be
  different from the running session.
- Replayed inputs go through the same window/event-driver path as ordinary GUI tests.
- The workflow remains viewer-scoped and does not treat UI traces as authoritative engine state.
- Live-core replay requirements are documented before claiming live-core bug reproduction is
  reliable.

## Relationship To Existing Plans

- Phase 12 GUI event test harness provides the natural dispatch mechanism.
- Phase 13 headless render evidence can verify visual state after replay.
- Phase 14 forensic event trace provides the source JSONL rows.
- Phase 15 crash diagnostic bundles can package traces, screenshots, commit metadata, and future
  replay manifests together.

This preliminary plan should become one or more numbered phases only after the team decides how much
engine-side deterministic replay support will exist.
