"""Exact installed-core identity checks for Contract 42 startup."""

from __future__ import annotations

from dataclasses import replace

import pytest
from warhammer40k_core.build_identity import verified_engine_build_identity

from warhammer40k_arcade_ui.core_client import compatibility


def test_installed_core_build_matches_declared_revision() -> None:
    identity = verified_engine_build_identity()

    assert identity.build_id == compatibility.SUPPORTED_CORE_BUILD_ID
    compatibility.require_supported_core_contract()


def test_undeclared_core_build_fails_before_play(monkeypatch: pytest.MonkeyPatch) -> None:
    installed = verified_engine_build_identity()
    monkeypatch.setattr(
        compatibility,
        "verified_engine_build_identity",
        lambda: replace(installed, build_id="warhammer40k-core-v2:unknown-build"),
    )

    with pytest.raises(compatibility.CoreCompatibilityError, match="core build ID") as error:
        compatibility.require_supported_core_contract()

    assert compatibility.SUPPORTED_CORE_REVISION in str(error.value)
    assert compatibility.SUPPORTED_CORE_BUILD_ID in str(error.value)
    assert "warhammer40k-core-v2:unknown-build" in str(error.value)


def test_declared_revision_mismatch_fails_before_play(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(compatibility, "SUPPORTED_CORE_REVISION", "0" * 40)

    with pytest.raises(compatibility.CoreCompatibilityError, match="core revision") as error:
        compatibility.require_supported_core_contract()

    assert "0" * 40 in str(error.value)
    assert "6e86f44b87c4559a9297596d5d18dc4247b8cbc3" in str(error.value)
