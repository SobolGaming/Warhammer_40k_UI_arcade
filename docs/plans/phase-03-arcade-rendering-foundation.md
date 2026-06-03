# Phase 3 — Arcade rendering foundation

## Goal

Render a battlefield that can be panned, zoomed, and inspected without interaction complexity.

## Initial review notes

Phase 3 stays fixture-backed on purpose. Rendering now consumes typed UI render view models and pure
render primitives; live core projections will be connected in a later phase after selection and HUD
state have stable boundaries. The renderer does not import mutable engine internals or perform rules
validation.

## Tasks

- [x] Implement `ArcadeWarhammerWindow`.
- [x] Add world-space camera:
  - pan
  - zoom
  - screen-to-world coordinate conversion
  - world-to-screen coordinate conversion
- [x] Render table bounds.
- [x] Render deployment zones as optional translucent overlays.
- [x] Render objectives.
- [x] Render terrain footprints as simple polygons/rectangles.
- [x] Render units as placeholder tokens.
- [x] Render model bases as circles or ellipses.
- [x] Add a basic HUD layer independent of the world camera:
  - phase label
  - active player
  - pending decision summary
  - event log stub

## Acceptance criteria

- [x] The app launches to a visible battlefield.
- [x] Pan and zoom do not distort table coordinates.
- [x] World coordinates are displayed under the mouse for debugging.
- [x] Placeholder unit/model rendering works from fixture data.
- [x] HUD remains fixed while the battlefield camera moves.
- [x] Rendering code is testable where practical:
  - coordinate conversion tests
  - camera clamp/zoom tests
  - view-model-to-render-primitive tests

## Closeout milestone

**Milestone 3: “Inspectable Battlefield”**

A user can launch the UI, pan/zoom around the table, and visually inspect placeholder units,
objectives, and terrain.

## Implementation progress

Completed on 2026-06-03.

- Added `warhammer40k_arcade_ui.render.view_models` for strict fixture/projection parsing into
  read-only render view models.
- Added `warhammer40k_arcade_ui.render.camera` for deterministic table-inch to screen-pixel
  transforms, right/middle-drag panning, cursor-centered zoom, resize preservation, and zoom clamps.
- Added `warhammer40k_arcade_ui.render.primitives` for pure table, deployment-zone, objective,
  terrain, unit-token, model-base, label, and fixed HUD primitive generation.
- Added `warhammer40k_arcade_ui.render.arcade_window.ArcadeWarhammerWindow` and wired the normal
  app launch path to it while preserving injected fake Arcade runtime tests.
- Added `warhammer40k_arcade_ui.render.default_fixture` and
  `tests/fixtures/phase03_battlefield_view.json` so placeholder rendering works from deterministic
  fixture data before live core projections are connected.

## Verification notes

Passed:

- `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .`
- `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check .`
- `env UV_CACHE_DIR=/tmp/uv-cache uv run pyright`
- `env UV_CACHE_DIR=/tmp/uv-cache uv run mypy src tests`
- `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest`

Additional GUI validation attempts:

- `PYGLET_HEADLESS=true` real-window construction failed before app code could create the window
  because Arcade/pyglet import attempted Linux XInput setup and raised
  `AttributeError: module 'pyglet.window' has no attribute 'xlib'`.
- Before Codex had display access, creating an invisible Arcade window without headless mode failed
  with
  `NoSuchDisplayException: Cannot connect to "None"` in this display-less container.
- After Codex was granted desktop display access, real `ArcadeWarhammerWindow` construction, draw,
  flip, and close succeeded on `DISPLAY=:0` / `WAYLAND_DISPLAY=wayland-0`.
- Reading pixels directly from `ctx.screen` still returned an all-black buffer. A minimal Arcade
  render had the same issue, so this is a default-framebuffer readback limitation rather than a
  Phase 3 rendering failure.
- Native offscreen framebuffer validation succeeded by rendering into a texture-backed
  `arcade.gl.Framebuffer`, calling `framebuffer.use()`, drawing the Phase 3 battlefield, synchronizing
  with `ctx.finish()`, and reading `attachment=0` / `GL_COLOR_ATTACHMENT0` with
  `framebuffer.read(...)`. The captured PNG at `/tmp/warhammer40k_arcade_phase3_fbo_capture.png`
  was nonblank and showed the expected HUD, table bounds, deployment zones, terrain, objectives,
  unit tokens, and model bases.

Manual visual launch should still be performed in a desktop environment when checking interaction
feel, but native offscreen framebuffer readback is now available for Codex-side render validation.

## Follow-up notes

- Connect `LocalSessionClient.get_view(...)` projections to `BattlefieldView` once the core exposes
  stable renderable battlefield projection fields.
- Phase 4 should layer selection state over the primitive IDs rather than making Arcade objects into
  game objects.
