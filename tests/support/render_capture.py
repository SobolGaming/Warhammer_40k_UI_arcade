"""Headless framebuffer capture helpers for GUI render evidence tests."""

from __future__ import annotations

import json
import os
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from PIL import Image

from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow

type RgbaColor = tuple[int, int, int, int]
type PixelRegion = tuple[int, int, int, int]

DEFAULT_BACKGROUND: RgbaColor = (47, 79, 79, 255)
DEFAULT_ARTIFACT_DIR = Path(
    os.environ.get("WARHAMMER40K_ARCADE_UI_RENDER_ARTIFACT_DIR", ".test-artifacts/render")
)


class RenderEvidenceError(AssertionError):
    """Raised when a render capture cannot satisfy a semantic visual check."""


class ReadableFramebuffer(Protocol):
    """Typed subset of Arcade's framebuffer used for readback evidence."""

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


@dataclass(frozen=True, slots=True)
class RenderArtifactPaths:
    """Paths written for a render evidence artifact bundle."""

    image_path: Path
    metadata_path: Path


@dataclass(frozen=True, slots=True)
class RenderCapture:
    """Raw RGBA framebuffer capture plus semantic pixel helpers."""

    width: int
    height: int
    rgba: bytes
    source_name: str

    @classmethod
    def blank(
        cls,
        *,
        width: int,
        height: int,
        color: RgbaColor = (0, 0, 0, 255),
        source_name: str = "blank",
    ) -> RenderCapture:
        """Create a synthetic blank capture for diagnostics tests."""

        _validate_size(width=width, height=height)
        return cls(
            width=width,
            height=height,
            rgba=bytes(color) * (width * height),
            source_name=source_name,
        )

    @property
    def expected_byte_length(self) -> int:
        """Return the expected RGBA byte length."""

        return self.width * self.height * 4

    @property
    def pixel_count(self) -> int:
        """Return the number of pixels represented by this capture."""

        return self.width * self.height

    @property
    def is_empty(self) -> bool:
        """Return whether readback returned no bytes."""

        return not self.rgba

    @property
    def is_all_black(self) -> bool:
        """Return whether every pixel is black or transparent black."""

        if self.is_empty:
            return False
        return all(pixel[:3] == (0, 0, 0) for pixel in self._pixels())

    def unique_color_count(self) -> int:
        """Return the number of exact RGBA colors in the capture."""

        return len(set(self._pixels()))

    def exact_color_count(self, color: RgbaColor, *, region: PixelRegion | None = None) -> int:
        """Count exact color matches in the whole capture or a screen-space region."""

        return sum(1 for pixel in self._pixels(region=region) if pixel == color)

    def close_color_count(
        self,
        color: RgbaColor,
        *,
        tolerance: int,
        region: PixelRegion | None = None,
    ) -> int:
        """Count pixels within a per-channel tolerance of a target color."""

        return sum(
            1 for pixel in self._pixels(region=region) if _color_close(pixel, color, tolerance)
        )

    def non_background_pixel_count(
        self,
        *,
        background: RgbaColor = DEFAULT_BACKGROUND,
        tolerance: int = 0,
        region: PixelRegion | None = None,
    ) -> int:
        """Count pixels not matching the configured background color."""

        return sum(
            1
            for pixel in self._pixels(region=region)
            if not _color_close(pixel, background, tolerance)
        )

    def save_artifacts(
        self,
        *,
        artifact_name: str,
        artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
        metadata: dict[str, object] | None = None,
    ) -> RenderArtifactPaths:
        """Write a PNG plus JSON metadata for this capture."""

        safe_name = _safe_artifact_name(artifact_name)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        image_path = artifact_dir / f"{safe_name}.png"
        metadata_path = artifact_dir / f"{safe_name}.json"
        image = Image.frombytes("RGBA", (self.width, self.height), self.rgba)
        image.transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(image_path)
        metadata_body = {
            "source_name": self.source_name,
            "width": self.width,
            "height": self.height,
            "byte_length": len(self.rgba),
            "expected_byte_length": self.expected_byte_length,
            "unique_color_count": self.unique_color_count(),
            "most_common_colors": _most_common_color_metadata(self._pixels(), limit=8),
            **(metadata or {}),
        }
        metadata_path.write_text(
            json.dumps(metadata_body, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return RenderArtifactPaths(image_path=image_path, metadata_path=metadata_path)

    def assert_nonblank(
        self,
        *,
        min_non_background_pixels: int,
        background: RgbaColor = DEFAULT_BACKGROUND,
        artifact_name: str,
        artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    ) -> None:
        """Assert the capture contains meaningful non-background pixels."""

        if len(self.rgba) != self.expected_byte_length:
            self.fail_with_artifacts(
                message=(
                    "Framebuffer readback returned an unexpected byte length: "
                    f"{len(self.rgba)} bytes, expected {self.expected_byte_length}."
                ),
                artifact_name=artifact_name,
                artifact_dir=artifact_dir,
            )
        if self.is_empty:
            self.fail_with_artifacts(
                message="Framebuffer readback returned an empty buffer.",
                artifact_name=artifact_name,
                artifact_dir=artifact_dir,
            )
        if self.is_all_black:
            self.fail_with_artifacts(
                message=(
                    "Framebuffer readback returned an all-black buffer; verify the intended "
                    "framebuffer was bound and GPU commands were synchronized before reading."
                ),
                artifact_name=artifact_name,
                artifact_dir=artifact_dir,
            )
        non_background_pixels = self.non_background_pixel_count(background=background)
        if non_background_pixels < min_non_background_pixels:
            self.fail_with_artifacts(
                message=(
                    "Framebuffer readback contains too few non-background pixels: "
                    f"{non_background_pixels}, expected at least {min_non_background_pixels}."
                ),
                artifact_name=artifact_name,
                artifact_dir=artifact_dir,
                metadata={"non_background_pixels": non_background_pixels},
            )

    def fail_with_artifacts(
        self,
        *,
        message: str,
        artifact_name: str,
        artifact_dir: Path,
        metadata: dict[str, object] | None = None,
    ) -> None:
        paths = self.save_artifacts(
            artifact_name=artifact_name,
            artifact_dir=artifact_dir,
            metadata={"failure": message, **(metadata or {})},
        )
        raise RenderEvidenceError(
            f"{message} Artifacts: {paths.image_path}, {paths.metadata_path}."
        )

    def _pixels(self, *, region: PixelRegion | None = None) -> Iterable[RgbaColor]:
        if region is None:
            for index in range(0, len(self.rgba), 4):
                yield _rgba_at(self.rgba, index)
            return
        left, bottom, width, height = _clamped_region(region, self.width, self.height)
        for y in range(bottom, bottom + height):
            row_start = y * self.width * 4
            for x in range(left, left + width):
                yield _rgba_at(self.rgba, row_start + (x * 4))


def capture_window_frame(
    window: ArcadeWarhammerWindow,
    *,
    source_name: str,
) -> RenderCapture:
    """Draw the real window to its screen framebuffer and read RGBA pixels."""

    width = int(window.width)
    height = int(window.height)
    _validate_size(width=width, height=height)
    framebuffer = cast(ReadableFramebuffer, window.ctx.screen)
    framebuffer.use()
    window.on_draw()
    window.ctx.finish()
    rgba = framebuffer.read(
        viewport=(0, 0, width, height),
        components=4,
        attachment=0,
        dtype="f1",
    )
    return RenderCapture(width=width, height=height, rgba=rgba, source_name=source_name)


def assert_region_has_non_background(
    capture: RenderCapture,
    *,
    region: PixelRegion,
    min_non_background_pixels: int,
    artifact_name: str,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    background: RgbaColor = DEFAULT_BACKGROUND,
) -> None:
    """Assert a screen-space region contains visible non-background pixels."""

    count = capture.non_background_pixel_count(background=background, region=region)
    if count < min_non_background_pixels:
        capture.fail_with_artifacts(
            message=(
                "Render region contains too few non-background pixels: "
                f"{count}, expected at least {min_non_background_pixels}; region={region}."
            ),
            artifact_name=artifact_name,
            artifact_dir=artifact_dir,
            metadata={"region": region, "non_background_pixels": count},
        )


def assert_color_present(
    capture: RenderCapture,
    *,
    color: RgbaColor,
    min_pixels: int,
    artifact_name: str,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    tolerance: int = 0,
    region: PixelRegion | None = None,
) -> None:
    """Assert a color cluster is visible in the capture."""

    count = (
        capture.exact_color_count(color, region=region)
        if tolerance == 0
        else capture.close_color_count(color, tolerance=tolerance, region=region)
    )
    if count < min_pixels:
        capture.fail_with_artifacts(
            message=(
                "Render capture does not contain enough pixels for color "
                f"{color}: {count}, expected at least {min_pixels}; region={region}."
            ),
            artifact_name=artifact_name,
            artifact_dir=artifact_dir,
            metadata={"target_color": color, "matched_pixels": count, "region": region},
        )


def _validate_size(*, width: int, height: int) -> None:
    if width <= 0 or height <= 0:
        raise ValueError("Render capture dimensions must be positive.")


def _rgba_at(rgba: bytes, index: int) -> RgbaColor:
    return (rgba[index], rgba[index + 1], rgba[index + 2], rgba[index + 3])


def _color_close(left: RgbaColor, right: RgbaColor, tolerance: int) -> bool:
    return all(abs(left[index] - right[index]) <= tolerance for index in range(4))


def _clamped_region(region: PixelRegion, width: int, height: int) -> PixelRegion:
    left, bottom, region_width, region_height = region
    if region_width <= 0 or region_height <= 0:
        raise ValueError("Pixel region dimensions must be positive.")
    clamped_left = max(0, min(width, left))
    clamped_bottom = max(0, min(height, bottom))
    clamped_right = max(clamped_left, min(width, left + region_width))
    clamped_top = max(clamped_bottom, min(height, bottom + region_height))
    return (
        clamped_left,
        clamped_bottom,
        clamped_right - clamped_left,
        clamped_top - clamped_bottom,
    )


def _safe_artifact_name(name: str) -> str:
    safe_name = "".join(
        character if character.isalnum() or character in "-_" else "-" for character in name
    )
    safe_name = safe_name.strip("-_")
    if not safe_name:
        raise ValueError("artifact_name must contain at least one alphanumeric character.")
    return safe_name


def _most_common_color_metadata(
    pixels: Iterable[RgbaColor],
    *,
    limit: int,
) -> list[dict[str, object]]:
    counter: Counter[RgbaColor] = Counter(pixels)
    return [{"rgba": color, "count": count} for color, count in counter.most_common(limit)]
