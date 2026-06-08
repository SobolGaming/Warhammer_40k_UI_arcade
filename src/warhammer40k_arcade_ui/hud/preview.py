"""Command-line HUD composition preview renderer."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from PIL import Image

from warhammer40k_arcade_ui.hud.composition import (
    HudCompositionProfile,
    HudCompositionValidationResult,
    load_hud_composition_reference,
)
from warhammer40k_arcade_ui.hud.toolkit import HudDensity, default_hud_theme
from warhammer40k_arcade_ui.hud.toolkit_render import render_composition_profile
from warhammer40k_arcade_ui.render.primitives import (
    CirclePrimitive,
    PolygonPrimitive,
    PolylinePrimitive,
    RenderPrimitive,
    TextPrimitive,
)

DEFAULT_PREVIEW_WIDTH_PX = 1280
DEFAULT_PREVIEW_HEIGHT_PX = 800


class ReadableFramebuffer(Protocol):
    """Typed subset of Arcade's framebuffer used for preview readback."""

    def use(self) -> None:
        """Bind this framebuffer as the active render target."""

        ...

    def read(
        self,
        *,
        viewport: tuple[int, int, int, int],
        components: int,
        attachment: int,
        dtype: str,
    ) -> bytes:
        """Read raw framebuffer bytes."""

        ...


class PreviewContext(Protocol):
    """Typed subset of an Arcade context used by preview rendering."""

    screen: object

    def finish(self) -> None:
        """Synchronize pending GPU work."""

        ...


class PreviewWindow(Protocol):
    """Typed subset of an Arcade window used by preview rendering."""

    ctx: PreviewContext

    def clear(self) -> None:
        """Clear the active framebuffer for the next draw."""

        ...

    def close(self) -> None:
        """Close the preview window."""

        ...


@dataclass(frozen=True, slots=True)
class PreviewArtifactPaths:
    """Paths written by a headless HUD preview."""

    image_path: Path
    metadata_path: Path


def main(argv: Sequence[str] | None = None) -> None:
    """Run the HUD preview entrypoint."""

    args = parse_args(argv)
    if args.headless:
        os.environ.setdefault("PYGLET_HEADLESS", "true")
        os.environ.setdefault("ARCADE_HEADLESS", "true")
    result = load_hud_composition_reference(
        args.composition_profile,
        preview=_strict_preview_validation(args.composition_profile),
    )
    if result.has_errors or result.profile is None:
        _write_diagnostics(result)
        raise SystemExit(2)
    density = cast(HudDensity, args.density)
    theme = default_hud_theme(
        density=density,
        high_contrast=args.theme == "high-contrast",
    )
    primitives = render_composition_profile(
        result.profile,
        viewport_width_px=args.width,
        viewport_height_px=args.height,
        component_id=args.component,
        theme=theme,
    )
    if args.headless:
        paths = render_headless_artifacts(
            profile=result.profile,
            primitives=primitives,
            width=args.width,
            height=args.height,
            component_id=args.component,
            artifact_dir=args.artifact_dir,
        )
        print(f"Wrote HUD preview artifacts: {paths.image_path} {paths.metadata_path}")
        return
    run_interactive_preview(
        primitives=primitives,
        width=args.width,
        height=args.height,
        title=f"Warhammer 40k HUD Preview - {result.profile.profile_id}",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse HUD preview CLI arguments."""

    parser = argparse.ArgumentParser(description="Preview a Warhammer 40k Arcade HUD YAML file.")
    parser.add_argument(
        "composition_profile",
        type=str,
        help="Built-in HUD profile name or path to a HUD composition YAML file.",
    )
    parser.add_argument("--component", type=str, default=None)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--artifact-dir", type=Path, default=Path(".test-artifacts/hud-preview"))
    parser.add_argument("--width", type=int, default=DEFAULT_PREVIEW_WIDTH_PX)
    parser.add_argument("--height", type=int, default=DEFAULT_PREVIEW_HEIGHT_PX)
    parser.add_argument("--theme", choices=("default", "high-contrast"), default="default")
    parser.add_argument(
        "--density",
        choices=("compact", "standard", "detailed"),
        default="standard",
    )
    return parser.parse_args(argv)


def _strict_preview_validation(composition_profile: str) -> bool:
    """Return whether this profile should require explicit preview sample data."""

    if composition_profile in ("default-hud", "command-bench-hud"):
        return False
    return not composition_profile.startswith("builtin:")


def render_headless_artifacts(
    *,
    profile: HudCompositionProfile,
    primitives: tuple[RenderPrimitive, ...],
    width: int,
    height: int,
    component_id: str | None,
    artifact_dir: Path,
) -> PreviewArtifactPaths:
    """Render HUD primitives to a headless Arcade framebuffer and write artifacts."""

    arcade_runtime = _load_arcade()
    window_factory = cast(Callable[..., PreviewWindow], getattr(arcade_runtime, "Window"))  # noqa: B009
    window = window_factory(
        width=width,
        height=height,
        title="Warhammer 40k HUD Preview",
        resizable=False,
        visible=False,
    )
    try:
        framebuffer = cast(ReadableFramebuffer, window.ctx.screen)
        framebuffer.use()
        window.clear()
        _draw_primitives(arcade_runtime, primitives)
        window.ctx.finish()
        rgba = framebuffer.read(
            viewport=(0, 0, width, height),
            components=4,
            attachment=0,
            dtype="f1",
        )
        return _write_artifacts(
            rgba=rgba,
            width=width,
            height=height,
            profile=profile,
            component_id=component_id,
            artifact_dir=artifact_dir,
        )
    finally:
        window.close()


def run_interactive_preview(
    *,
    primitives: tuple[RenderPrimitive, ...],
    width: int,
    height: int,
    title: str,
) -> None:
    """Open an interactive Arcade preview window."""

    arcade_runtime = _load_arcade()
    window_factory = cast(Callable[..., PreviewWindow], getattr(arcade_runtime, "Window"))  # noqa: B009
    run_arcade = cast(Callable[[], None], getattr(arcade_runtime, "run"))  # noqa: B009

    window = window_factory(width=width, height=height, title=title, resizable=True)

    def on_draw() -> None:
        window.clear()
        _draw_primitives(arcade_runtime, primitives)

    push_handlers = cast(Callable[..., object], getattr(window, "push_handlers"))  # noqa: B009
    push_handlers(on_draw=on_draw)
    run_arcade()


def _draw_primitives(arcade_runtime: object, primitives: tuple[RenderPrimitive, ...]) -> None:
    draw_polygon_filled = cast(
        Callable[[tuple[tuple[float, float], ...], tuple[int, int, int, int]], None],
        getattr(arcade_runtime, "draw_polygon_filled"),  # noqa: B009
    )
    draw_polygon_outline = cast(
        Callable[[tuple[tuple[float, float], ...], tuple[int, int, int, int], float], None],
        getattr(arcade_runtime, "draw_polygon_outline"),  # noqa: B009
    )
    draw_circle_filled = cast(
        Callable[[float, float, float, tuple[int, int, int, int]], None],
        getattr(arcade_runtime, "draw_circle_filled"),  # noqa: B009
    )
    draw_circle_outline = cast(
        Callable[[float, float, float, tuple[int, int, int, int], float], None],
        getattr(arcade_runtime, "draw_circle_outline"),  # noqa: B009
    )
    draw_line = cast(
        Callable[[float, float, float, float, tuple[int, int, int, int], float], None],
        getattr(arcade_runtime, "draw_line"),  # noqa: B009
    )
    draw_text = cast(Callable[..., None], getattr(arcade_runtime, "draw_text"))  # noqa: B009
    for primitive in primitives:
        if type(primitive) is PolygonPrimitive:
            if primitive.fill_color[3] > 0:
                draw_polygon_filled(primitive.points, primitive.fill_color)
            if primitive.outline_color[3] > 0 and primitive.line_width > 0.0:
                draw_polygon_outline(
                    primitive.points,
                    primitive.outline_color,
                    primitive.line_width,
                )
        elif type(primitive) is CirclePrimitive:
            center_x, center_y = primitive.center
            if primitive.fill_color[3] > 0:
                draw_circle_filled(
                    center_x,
                    center_y,
                    primitive.radius,
                    primitive.fill_color,
                )
            if primitive.outline_color[3] > 0 and primitive.line_width > 0.0:
                draw_circle_outline(
                    center_x,
                    center_y,
                    primitive.radius,
                    primitive.outline_color,
                    primitive.line_width,
                )
        elif type(primitive) is PolylinePrimitive:
            for index in range(len(primitive.points) - 1):
                start = primitive.points[index]
                end = primitive.points[index + 1]
                draw_line(
                    start[0],
                    start[1],
                    end[0],
                    end[1],
                    primitive.color,
                    primitive.line_width,
                )
        elif type(primitive) is TextPrimitive:
            draw_text(
                primitive.text,
                primitive.position[0],
                primitive.position[1],
                primitive.color,
                font_size=primitive.font_size,
                anchor_x=primitive.anchor_x,
                anchor_y=primitive.anchor_y,
            )


def _write_artifacts(
    *,
    rgba: bytes,
    width: int,
    height: int,
    profile: HudCompositionProfile,
    component_id: str | None,
    artifact_dir: Path,
) -> PreviewArtifactPaths:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_artifact_name(
        f"{profile.profile_id}-{component_id}" if component_id is not None else profile.profile_id
    )
    image_path = artifact_dir / f"{safe_name}.png"
    metadata_path = artifact_dir / f"{safe_name}.json"
    image = Image.frombytes("RGBA", (width, height), rgba)
    image.transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(image_path)
    metadata = {
        "profile_id": profile.profile_id,
        "component_id": component_id,
        "layout_preset": profile.layout_preset,
        "source_path": str(profile.source_path) if profile.source_path is not None else None,
        "source": profile.source.display_name if profile.source is not None else None,
        "width": width,
        "height": height,
        "byte_length": len(rgba),
        "region_ids": [region.region_id for region in profile.regions],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return PreviewArtifactPaths(image_path=image_path, metadata_path=metadata_path)


def _write_diagnostics(result: HudCompositionValidationResult) -> None:
    for diagnostic in result.diagnostics:
        print(
            f"{diagnostic.severity}: {diagnostic.code} [{diagnostic.field}]: {diagnostic.message}",
            file=sys.stderr,
        )


def _safe_artifact_name(name: str) -> str:
    safe_name = "".join(
        character if character.isalnum() or character in "-_" else "-" for character in name
    )
    safe_name = safe_name.strip("-_")
    if not safe_name:
        raise ValueError("artifact name must contain at least one alphanumeric character")
    return safe_name


def _load_arcade() -> object:
    import arcade

    return arcade
