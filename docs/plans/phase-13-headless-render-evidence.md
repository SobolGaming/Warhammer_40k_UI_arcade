# Phase 13 - Headless render evidence

## Goal

Add headless rendering and framebuffer evidence tests that can prove UI elements render, move, and
remain nonblank without requiring a visible desktop session.

In plain language: Phase 12 proves event handlers and UI state transitions. This phase proves the
drawn result is actually visible. It should let tests render a frame, read pixels or screenshots
from the framebuffer, and attach useful artifacts when a visual bug or crash occurs.

This phase directly follows the attached testing discussion's approach 3: use Arcade headless mode
and framebuffer readback for screenshot/pixel evidence, while avoiding brittle exact golden-image
tests unless a surface is stable enough to justify them.

## Scope

- Add a headless render test mode that sets required environment flags before importing Arcade.
- Build a render test harness that can:
  - construct the window or render surface;
  - draw one or more frames;
  - synchronize GPU commands before pixel readback;
  - capture framebuffer pixels or an image;
  - save failure artifacts under a deterministic artifacts directory.
- Prefer semantic visual checks:
  - nonblank frame;
  - expected color clusters/layers present;
  - HUD region contains non-background pixels;
  - terrain/model/objective regions draw where expected;
  - camera framing keeps the table visible.
- Support a limited, explicit loose-diff snapshot mode only for stable views.
- Integrate with the Phase 12 driver so scripts can drive an interaction and then capture render
  evidence.

## Non-Goals

- No exact full-window golden screenshot suite by default.
- No OS-level screenshot automation.
- No rule validation or engine mutation.
- No dependence on manual display access for CI-critical tests.

## Tasks

- [x] Identify the correct Arcade headless initialization sequence for this repo and document the
  import-order constraints.
- [x] Add a render harness module, for example `tests/support/render_capture.py`.
- [x] Add framebuffer readback helpers that:
  - bind the intended framebuffer/render target;
  - call draw;
  - flush/finish before reading pixels;
  - read the correct color attachment;
  - report clear diagnostics for all-black or empty frames.
- [x] Add image artifact helpers:
  - deterministic output path;
  - per-test artifact naming;
  - optional JSON metadata next to the screenshot.
- [x] Add visual smoke tests for:
  - fake fixture table, terrain, objectives, and models;
  - HUD text/panel region presence;
  - live-core-smoke battlefield projection, if stable in headless mode;
  - one movement-draft overlay after the Phase 12 driver creates it.
- [x] Add documentation for when to use semantic pixel checks, loose image diffs, or manual
  validation.

## Acceptance Criteria

- [x] Headless render tests can run in CI or a Codex shell without a visible GUI when Arcade supports
  the environment.
- [x] Render captures fail with actionable diagnostics instead of silently returning all-black
  buffers.
- [x] Visual artifacts are saved on failure and can be attached to PR reviews or bug reports.
- [x] At least one GUI workflow test combines Phase 12 event driving with Phase 13 render evidence.
- [x] The README or testing docs explain local requirements for headless rendering.
- [x] Full repository gates pass.

## Testing Strategy

- Keep visual assertions broad and robust.
- Prefer layer/region checks over full-image exact matching.
- Add exact golden screenshots only for tiny, intentionally stable surfaces.
- Mark environment-dependent tests clearly if a platform cannot support Arcade headless mode.

## Manual Validation Checklist

After implementation:

- [x] Run the headless render tests locally.
- [x] Inspect at least one generated screenshot artifact.
- [x] Confirm an intentionally bad render readback fails with a useful diagnostic.
- [ ] Confirm normal GUI launch still works outside headless mode.

## Implementation Notes

- Added `tests/support/render_capture.py`, which captures the real `ArcadeWarhammerWindow` draw
  path through the explicit `window.ctx.screen` framebuffer, calls `window.on_draw()`, synchronizes
  with `window.ctx.finish()`, and reads RGBA bytes from color attachment `0`.
- Added `GuiTestDriver.capture_frame(...)` so Phase 12 event scripts can render the current window
  state and assert visual evidence without leaving the driver API.
- Added semantic pixel checks for nonblank frames, expected broad color clusters, HUD text regions,
  projected battlefield regions, movement overlays after event-driver actions, and live-core-smoke
  projections.
- Added PNG plus JSON artifact bundle helpers. Failure diagnostics include artifact paths and
  metadata with framebuffer size, byte length, unique color count, and common colors.
- README documents Linux EGL/OpenGL runtime requirements and the
  `WARHAMMER40K_ARCADE_UI_RENDER_ARTIFACT_DIR` override.
- The normal GUI launch remains a manual validation item because pytest intentionally runs Arcade in
  headless mode.

## Phase Closeout Milestone

**Milestone 13: "Headless Visual Evidence"**

The UI can produce automated visual evidence for rendered frames and interaction outcomes without
depending on a human-operated display.
