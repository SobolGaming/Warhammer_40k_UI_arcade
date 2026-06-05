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

- [x] Define crash bundle schema and output directory policy.
- [x] Add version metadata helpers:
  - package version from installed metadata or `pyproject.toml`;
  - git commit SHA and dirty flag when running from a checkout;
  - placeholder core engine version fields.
- [x] Add crash capture utility, for example `diagnostics/crash_report.py`.
- [x] Integrate startup and fatal runtime paths:
  - app startup failures;
  - live-core smoke startup failures;
  - projection/parser fatal errors;
  - unhandled exceptions reaching the main entry point.
- [x] Add trace tail attachment when Phase 14 trace files exist.
- [x] Add optional screenshot/render artifact references when Phase 13 has produced them.
- [x] Add user-facing fatal message that gives the crash report path.
- [x] Add tests for:
  - crash report schema;
  - stack trace capture;
  - version metadata fallback behavior;
  - redaction of token-like values;
  - trace tail inclusion;
  - no crash report produced for ordinary authoritative invalid diagnostics.
- [x] Document how to attach crash reports to issues/PR review comments.

## Acceptance Criteria

- [x] An unhandled UI exception writes a crash report before exit.
- [x] Fatal engine/client errors write a report and close gracefully.
- [x] Crash reports include enough context to reproduce the mode and recent UI/core exchange.
- [x] Sensitive token-like data is redacted.
- [x] The user-facing fatal message includes the path to the diagnostic bundle.
- [x] Full repository gates pass.

## Manual Validation Checklist

After implementation:

- [ ] Trigger a controlled test crash and confirm a report is written.
- [ ] Confirm the report includes stack trace, UI commit SHA or fallback, runtime mode, preferences
  label, and recent trace tail when tracing is enabled.
- [ ] Confirm a normal authoritative invalid movement diagnostic does not create a crash bundle.
- [ ] Confirm the GUI exits gracefully and shows/prints the crash report path.

## Implementation Notes

- Added `warhammer40k_arcade_ui.diagnostics.crash_report` with JSON bundle output under
  `~/.local/state/warhammer40k-arcade-ui/crash-bundles/` by default.
- Added `WARHAMMER40K_ARCADE_UI_CRASH_REPORT_DIR` and `--crash-report-dir` overrides for test and
  manual triage sessions.
- `main.py` installs a process-level crash-report excepthook for uncaught exceptions.
- Live-core smoke startup failures and runtime fatal engine/client errors now write
  `crash-report.json` and include the report path in the user-facing fatal message.
- Reports include UI version/git metadata, runtime mode, preferences path/label, active
  viewer/request/status context, recent forensic trace tail, and recent render artifact references.
- Reports intentionally leave core engine version/commit as `null` until the adapter contract exposes
  that metadata.

## Automated Coverage

- `tests/test_crash_report.py` covers report schema, stack trace capture, trace tail inclusion,
  token-like launch argument redaction, fatal window report creation, and the no-report invariant for
  ordinary local invalid diagnostics.
- `tests/test_entrypoint.py` covers CLI parsing and runtime propagation of crash-report settings.

## Manual Validation Details

Run with an explicit output directory while reproducing a fatal issue:

```bash
EVENT_TRACE=payload EVENT_TRACE_FILE=/tmp/ui-trace.jsonl \
  uv run warhammer40k-arcade-ui \
  --live-core-smoke \
  --ui-prefs docs/preferences/default.yaml \
  --crash-report-dir /tmp/ui-crashes
```

When the UI reports a fatal game engine error, inspect the path shown in the HUD/status text. The
bundle should contain `/tmp/ui-crashes/crash-*/crash-report.json`. Attach that JSON file, the trace
file when enabled, the launch command, and any relevant render artifacts to the issue or PR review.

## Phase Closeout Milestone

**Milestone 15: "Actionable Crash Bundles"**

Crashes produce compact, reviewable diagnostic bundles that connect stack traces to recent UI/core
events and runtime context.
