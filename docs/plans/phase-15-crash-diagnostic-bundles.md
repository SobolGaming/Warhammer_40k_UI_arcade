# Phase 15 - Crash diagnostic bundles

## Goal

Add a catch-all crash diagnostic tool that captures stack traces and useful runtime context when the
UI crashes or encounters a fatal engine/client error.

In plain language: when the UI fails, it should leave behind a compact report that makes the next
debugging step obvious. The report should include what version was running, what mode it was in,
what request/status was active, recent forensic trace entries if tracing was enabled, and the full
stack trace.

## Scope

- Add a centralized crash capture function for app/window startup and fatal runtime paths.
- Capture:
  - exception type and message;
  - full Python stack trace;
  - UI git commit SHA when available;
  - UI release/package version when available;
  - branch/dirty-state indicator when available;
  - Python version and platform;
  - Arcade and pyglet versions when available;
  - launch arguments with redaction;
  - selected runtime mode, such as fake fixture or live-core smoke;
  - UI preferences source path/label;
  - viewer player ID, game ID, event cursor, active request ID/status when available;
  - recent forensic trace tail when Phase 14 tracing is enabled;
  - latest crash-adjacent screenshot/render artifact when Phase 13 evidence is available.
- Leave space for future core engine version/commit fields once the core contract exposes them.
- Store crash bundles in a predictable diagnostics directory.

## Non-Goals

- No automatic network upload.
- No inclusion of secrets or access tokens.
- No broad exception swallowing that lets the UI continue after corrupted state.
- No changes to core engine contracts.

## Tasks

- [ ] Define crash bundle schema and output directory policy.
- [ ] Add version metadata helpers:
  - package version from installed metadata or `pyproject.toml`;
  - git commit SHA and dirty flag when running from a checkout;
  - placeholder core engine version fields.
- [ ] Add crash capture utility, for example `diagnostics/crash_report.py`.
- [ ] Integrate startup and fatal runtime paths:
  - app startup failures;
  - live-core smoke startup failures;
  - projection/parser fatal errors;
  - unhandled exceptions reaching the main entry point.
- [ ] Add trace tail attachment when Phase 14 trace files exist.
- [ ] Add optional screenshot/render artifact references when Phase 13 has produced them.
- [ ] Add user-facing fatal message that gives the crash report path.
- [ ] Add tests for:
  - crash report schema;
  - stack trace capture;
  - version metadata fallback behavior;
  - redaction of token-like values;
  - trace tail inclusion;
  - no crash report produced for ordinary authoritative invalid diagnostics.
- [ ] Document how to attach crash reports to issues/PR review comments.

## Acceptance Criteria

- [ ] An unhandled UI exception writes a crash report before exit.
- [ ] Fatal engine/client errors write a report and close gracefully.
- [ ] Crash reports include enough context to reproduce the mode and recent UI/core exchange.
- [ ] Sensitive token-like data is redacted.
- [ ] The user-facing fatal message includes the path to the diagnostic bundle.
- [ ] Full repository gates pass.

## Manual Validation Checklist

After implementation:

- [ ] Trigger a controlled test crash and confirm a report is written.
- [ ] Confirm the report includes stack trace, UI commit SHA or fallback, runtime mode, preferences
  label, and recent trace tail when tracing is enabled.
- [ ] Confirm a normal authoritative invalid movement diagnostic does not create a crash bundle.
- [ ] Confirm the GUI exits gracefully and shows/prints the crash report path.

## Phase Closeout Milestone

**Milestone 15: "Actionable Crash Bundles"**

Crashes produce compact, reviewable diagnostic bundles that connect stack traces to recent UI/core
events and runtime context.
