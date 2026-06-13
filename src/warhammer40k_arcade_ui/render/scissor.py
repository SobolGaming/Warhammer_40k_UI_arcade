"""Small helpers for Arcade scissor clipping."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from math import ceil, floor
from typing import Any, Protocol, TypeGuard, cast

from warhammer40k_arcade_ui.hud.layouts import ScreenRect

type ScissorTuple = tuple[int, int, int, int]


class ScissorContext(Protocol):
    """Minimal Arcade context protocol used for scissor clipping."""

    @property
    def scissor(self) -> Any:
        """Current scissor setting."""

        ...

    @scissor.setter
    def scissor(self, value: Any) -> None:
        """Set the current scissor setting."""

        ...


def scissor_tuple(rect: ScreenRect) -> ScissorTuple:
    """Return an integer lower-left scissor tuple that contains ``rect``."""

    left = floor(rect.x)
    bottom = floor(rect.y)
    right = ceil(rect.right)
    top = ceil(rect.top)
    return (left, bottom, max(0, right - left), max(0, top - bottom))


def intersect_scissors(first: ScissorTuple, second: ScissorTuple) -> ScissorTuple:
    """Return the intersection of two lower-left scissor rectangles."""

    first_left, first_bottom, first_width, first_height = first
    second_left, second_bottom, second_width, second_height = second
    left = max(first_left, second_left)
    bottom = max(first_bottom, second_bottom)
    right = min(first_left + first_width, second_left + second_width)
    top = min(first_bottom + first_height, second_bottom + second_height)
    return (left, bottom, max(0, right - left), max(0, top - bottom))


@contextmanager
def scoped_scissor(ctx: ScissorContext | None, rect: ScreenRect | None) -> Generator[None]:
    """Temporarily apply a scissor rect, intersecting with any active context scissor."""

    if ctx is None or rect is None:
        yield
        return

    previous = getattr(ctx, "scissor", None)
    next_scissor = scissor_tuple(rect)
    if _is_scissor_tuple(previous):
        next_scissor = intersect_scissors(previous, next_scissor)
    ctx.scissor = next_scissor
    try:
        yield
    finally:
        ctx.scissor = previous


def _is_scissor_tuple(value: object) -> TypeGuard[ScissorTuple]:
    if type(value) is not tuple:
        return False
    items = cast(tuple[object, ...], value)
    return len(items) == 4 and all(type(item) is int for item in items)
