"""Shared pytest configuration for UI bootstrap tests."""

from __future__ import annotations

import os

os.environ.setdefault("PYGLET_HEADLESS", "true")
