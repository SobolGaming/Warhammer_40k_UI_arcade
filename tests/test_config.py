"""Tests for application configuration."""

from __future__ import annotations

import pytest

from warhammer40k_arcade_ui import AppConfig


def test_default_config_is_runnable_size() -> None:
    config = AppConfig()

    assert config.title == "Warhammer 40k Arcade UI"
    assert config.window_width == 1280
    assert config.window_height == 800
    assert config.resizable is True


def test_config_rejects_non_positive_window_width() -> None:
    with pytest.raises(ValueError, match="window_width must be positive"):
        AppConfig(window_width=0)


def test_config_rejects_non_positive_window_height() -> None:
    with pytest.raises(ValueError, match="window_height must be positive"):
        AppConfig(window_height=0)
