# Phase 14 - Forensic event trace

## Goal

Add an opt-in UI forensic event log that records UI/core interactions and high-value UI events when
an `EVENT_TRACE` flag is enabled.

In plain language: when a bug or crash occurs, the reviewer should be able to see the sequence of
inputs, decisions, payloads, responses, projections, and event deltas that led to it. This trace
should be off by default, structured, deterministic where possible, and safe for viewer-scoped
debugging.

## Scope

- Add an `EVENT_TRACE` runtime flag through environment variable and/or CLI plumbing.
- Add trace levels:
  - `off`: no trace file;
  - `summary`: request/result IDs, event kinds, status transitions, selected refs, draft states;
  - `payload`: full JSON-safe payloads exchanged through the UI/core client facade;
  - `render`: optional high-level render/camera/frame markers, not raw pixels.
- Trace every JSON representation exchanged between the UI and core engine at `payload` level:
  - game view payloads;
  - finite submissions;
  - parameterized submissions;
  - status payloads;
  - event deltas;
  - projection refresh payloads;
  - invalid diagnostics.
- Trace high-value UI events:
  - key press/release;
  - mouse press/release/motion;
  - command dispatch;
  - context menu open/close;
  - movement draft mutations;
  - payload preview generation;
  - submission attempts and outcomes.
- Keep traces viewer-scoped and avoid logging secrets or access tokens.

## Non-Goals

- No engine replay replacement.
- No authoritative event log owned by the UI.
- No hidden-information expansion beyond what the current viewer can already see.
- No always-on logging of large payloads.

## Tasks

- [x] Define a `ForensicTraceWriter` interface and JSON Lines event schema.
- [x] Add trace configuration parsing from `EVENT_TRACE` and optional CLI flags.
- [x] Wrap the UI-facing core client facade with trace hooks rather than scattering trace calls
  through unrelated modules.
- [x] Add UI event trace hooks at the window boundary.
- [x] Add trace event categories and stable event names.
- [x] Include context fields:
  - wall-clock timestamp;
  - monotonic timestamp;
  - UI commit SHA when available;
  - UI release version when available;
  - viewer player ID;
  - game ID;
  - current request ID/status when available;
  - event cursor when available.
- [x] Add deterministic redaction rules for environment variables, paths if needed, and any future
  token-like fields.
- [x] Add tests for:
  - disabled trace produces no file;
  - summary trace records status transitions without full payload bodies;
  - payload trace records JSON-safe UI/core payloads;
  - trace writer rejects non-JSON-safe data;
  - no GitHub token or configured secret-like env var is emitted.
- [x] Document trace usage and attach-to-bug-report workflow.

## Acceptance Criteria

- [x] `EVENT_TRACE=summary` emits a structured trace suitable for ordinary bug reports.
- [x] `EVENT_TRACE=payload` includes every JSON representation exchanged between UI and core.
- [x] Trace files are JSON Lines, bounded or rotateable, and stored in a predictable diagnostics
  directory.
- [x] Tracing can be enabled without changing code.
- [x] Tracing does not weaken UI/core boundaries or create an authoritative UI event log.
- [x] Full repository gates pass.

## Manual Validation Checklist

After implementation:

- [ ] Launch with `EVENT_TRACE=summary` and confirm a trace file is created.
- [ ] Perform model selection and a movement draft; confirm the trace includes UI event and draft
  state transitions.
- [ ] Launch with `EVENT_TRACE=payload`; submit or simulate a core request; confirm full JSON-safe
  request/status/event payloads are present.
- [ ] Confirm no access token or unrelated environment secret appears in the trace.

Suggested manual commands:

```bash
EVENT_TRACE=summary EVENT_TRACE_FILE=/tmp/warhammer40k-ui-summary.jsonl uv run warhammer40k-arcade-ui --ui-prefs docs/preferences/default.yaml
EVENT_TRACE=payload EVENT_TRACE_FILE=/tmp/warhammer40k-ui-payload.jsonl uv run warhammer40k-arcade-ui --live-core-smoke --ui-prefs docs/preferences/default.yaml
uv run warhammer40k-arcade-ui --event-trace render --event-trace-file /tmp/warhammer40k-ui-render.jsonl
```

Review the JSONL file line-by-line in an editor, or parse individual lines with `json.loads` when a
specific test or bug report needs machine-readable evidence.

## Phase Closeout Milestone

**Milestone 14: "Forensic Event Trace"**

Human reviewers can attach a structured trace showing how a UI/core interaction unfolded before a
bug or crash.

## Implementation Notes

- Added `warhammer40k_arcade_ui.diagnostics.forensic_trace` with:
  - `ForensicTraceConfig` for `EVENT_TRACE`, `EVENT_TRACE_FILE`, `EVENT_TRACE_DIR`,
    `EVENT_TRACE_MAX_BYTES`, `--event-trace`, and `--event-trace-file`;
  - `JsonLinesTraceWriter` / `NoOpTraceWriter`;
  - token-like key redaction;
  - JSON-safe dataclass/container serialization;
  - simple one-file rotation;
  - `TracedCoreClient` for facade-level core request/response tracing.
- Wired UI window hooks for key press/release, mouse press/release/motion/scroll/drag, command
  dispatch, context menu open/close, movement draft mutations, payload preview readiness,
  movement/finite submission attempts and outcomes, projection refresh, fatal engine errors, and
  optional render frame markers.
- Added tests in `tests/test_forensic_trace.py` for disabled, summary, payload, redaction,
  JSON-safety rejection, rotation, and GUI-driver event/core trace coverage.
- Updated `README.md` with usage and bug-report attachment guidance.
