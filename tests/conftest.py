"""Pytest configuration for deterministic GUI tests."""

from __future__ import annotations

import os

os.environ.setdefault("PYGLET_HEADLESS", "true")
os.environ.setdefault("ARCADE_HEADLESS", "true")
