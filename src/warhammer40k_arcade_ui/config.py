"""Application configuration for the Arcade UI client."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppConfig:
    """User-interface configuration for the Phase 0 window."""

    title: str = "Warhammer 40k Arcade UI"
    window_width: int = 1280
    window_height: int = 800
    resizable: bool = True

    def __post_init__(self) -> None:
        if self.window_width <= 0:
            raise ValueError("window_width must be positive")
        if self.window_height <= 0:
            raise ValueError("window_height must be positive")
