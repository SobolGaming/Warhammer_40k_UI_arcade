"""Regressions for sibling contract-example provenance checks."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast

import pytest

from tests.support.core_contract_examples import (
    CoreContractFixtureError,
    required_core_example_path,
    required_core_example_paths,
    verified_core_examples_root,
)
from warhammer40k_arcade_ui.core_client.compatibility import (
    SUPPORTED_EXTERNAL_CONTRACT_VERSION,
)


@pytest.fixture
def fixture_checkout(tmp_path: Path) -> tuple[Path, str]:
    """Build a tiny separate Git checkout whose contract files have known provenance."""

    core = tmp_path / "Warhammer_40k_AI"
    core.mkdir()
    _git(core, "init", "--quiet")
    _git(core, "config", "user.name", "Contract Fixture Test")
    _git(core, "config", "user.email", "fixture@example.invalid")
    example = core / "contracts/examples/projections/view.json"
    example.parent.mkdir(parents=True)
    example.write_text("{}\n", encoding="utf-8")
    schema = core / "contracts/schemas/game-view.schema.json"
    schema.parent.mkdir(parents=True)
    schema.write_text("{}\n", encoding="utf-8")
    _write_manifest(core)
    return core, _commit(core)


def test_matching_checkout_is_accepted(fixture_checkout: tuple[Path, str]) -> None:
    core, revision = fixture_checkout

    assert verified_core_examples_root(core, expected_revision=revision) == (
        core / "contracts/examples"
    )
    assert required_core_example_path(
        "projections", "view.json", checkout=core, expected_revision=revision
    ) == (core / "contracts/examples/projections/view.json")


def test_wrong_revision_fails_before_examples_are_read(
    fixture_checkout: tuple[Path, str],
) -> None:
    core, revision = fixture_checkout

    with pytest.raises(CoreContractFixtureError, match="revision mismatch") as error:
        verified_core_examples_root(core, expected_revision="0" * 40)

    assert revision in str(error.value)
    assert "0" * 40 in str(error.value)


def test_missing_checkout_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(CoreContractFixtureError, match="checkout is missing"):
        verified_core_examples_root(tmp_path / "missing")


def test_non_git_directory_fails_clearly(tmp_path: Path) -> None:
    core = tmp_path / "Warhammer_40k_AI"
    core.mkdir()

    with pytest.raises(CoreContractFixtureError, match="Cannot inspect core fixture checkout"):
        verified_core_examples_root(core)


def test_wrong_manifest_version_fails_clearly(fixture_checkout: tuple[Path, str]) -> None:
    core, _ = fixture_checkout
    _write_manifest(core, contract_version="42.0.0")
    revision = _commit(core)

    with pytest.raises(CoreContractFixtureError, match="contract_version mismatch"):
        verified_core_examples_root(core, expected_revision=revision)


@pytest.mark.parametrize("manifest_text", ["{", '{"contract_version": "10.2.0"}'])
def test_malformed_manifest_fails_clearly(
    fixture_checkout: tuple[Path, str], manifest_text: str
) -> None:
    core, _ = fixture_checkout
    (core / "contracts/manifest.json").write_text(manifest_text, encoding="utf-8")
    revision = _commit(core)

    with pytest.raises(CoreContractFixtureError, match=r"manifest .*malformed"):
        verified_core_examples_root(core, expected_revision=revision)


def test_missing_manifest_fails_clearly(fixture_checkout: tuple[Path, str]) -> None:
    core, _ = fixture_checkout
    (core / "contracts/manifest.json").unlink()
    revision = _commit(core)

    with pytest.raises(CoreContractFixtureError, match="manifest is missing"):
        verified_core_examples_root(core, expected_revision=revision)


def test_dirty_contract_files_cannot_masquerade_as_pinned_examples(
    fixture_checkout: tuple[Path, str],
) -> None:
    core, revision = fixture_checkout
    (core / "contracts/examples/projections/view.json").write_text('{"changed": true}\n')

    with pytest.raises(CoreContractFixtureError, match="modified or untracked contracts"):
        verified_core_examples_root(core, expected_revision=revision)


def test_assume_unchanged_cannot_hide_an_edited_example(
    fixture_checkout: tuple[Path, str],
) -> None:
    core, revision = fixture_checkout
    _git(core, "update-index", "--assume-unchanged", "contracts/examples/projections/view.json")
    (core / "contracts/examples/projections/view.json").write_text('{"tampered": true}\n')
    assert _git(core, "status", "--porcelain", "--untracked-files=all", "--", "contracts") == ""

    with pytest.raises(CoreContractFixtureError, match="manifest hash mismatch"):
        required_core_example_path(
            "projections", "view.json", checkout=core, expected_revision=revision
        )


def test_assume_unchanged_cannot_hide_an_edited_manifest(
    fixture_checkout: tuple[Path, str],
) -> None:
    core, revision = fixture_checkout
    _git(core, "update-index", "--assume-unchanged", "contracts/manifest.json")
    manifest = _manifest(core)
    manifest["contract_version"] = "42.0.0"
    _save_manifest(core, manifest)
    assert _git(core, "status", "--porcelain", "--untracked-files=all", "--", "contracts") == ""

    with pytest.raises(CoreContractFixtureError, match="manifest differs from pinned Git tree"):
        verified_core_examples_root(core, expected_revision=revision)


def test_committed_incorrect_example_hash_is_rejected(
    fixture_checkout: tuple[Path, str],
) -> None:
    core, _ = fixture_checkout
    manifest = _manifest(core)
    cast(dict[str, str], manifest["file_sha256"])["examples/projections/view.json"] = "0" * 64
    _save_manifest(core, manifest)
    revision = _commit(core)

    with pytest.raises(CoreContractFixtureError, match="manifest hash mismatch"):
        required_core_example_path(
            "projections", "view.json", checkout=core, expected_revision=revision
        )


def test_unresolved_schema_reference_is_rejected(
    fixture_checkout: tuple[Path, str],
) -> None:
    core, _ = fixture_checkout
    manifest = _manifest(core)
    cast(dict[str, str], manifest["example_schema_by_path"])["examples/projections/view.json"] = (
        "missing.json"
    )
    _save_manifest(core, manifest)
    revision = _commit(core)

    with pytest.raises(CoreContractFixtureError, match="unresolved example schema"):
        verified_core_examples_root(core, expected_revision=revision)


def test_committed_missing_schema_file_is_rejected(
    fixture_checkout: tuple[Path, str],
) -> None:
    core, _ = fixture_checkout
    (core / "contracts/schemas/game-view.schema.json").unlink()
    revision = _commit(core)

    with pytest.raises(CoreContractFixtureError, match="missing schema file"):
        verified_core_examples_root(core, expected_revision=revision)


def test_committed_incorrect_schema_hash_is_rejected(
    fixture_checkout: tuple[Path, str],
) -> None:
    core, _ = fixture_checkout
    manifest = _manifest(core)
    cast(dict[str, str], manifest["file_sha256"])["schemas/game-view.schema.json"] = "0" * 64
    _save_manifest(core, manifest)
    revision = _commit(core)

    with pytest.raises(CoreContractFixtureError, match="schema manifest hash mismatch"):
        verified_core_examples_root(core, expected_revision=revision)


def test_tracked_but_unlisted_glob_match_is_rejected(
    fixture_checkout: tuple[Path, str],
) -> None:
    core, _ = fixture_checkout
    (core / "contracts/examples/projections/unlisted.json").write_text("{}\n")
    revision = _commit(core)

    with pytest.raises(CoreContractFixtureError, match="not manifest-listed"):
        required_core_example_paths("projections/*.json", checkout=core, expected_revision=revision)


def test_missing_examples_directory_fails_clearly(fixture_checkout: tuple[Path, str]) -> None:
    core, _ = fixture_checkout
    (core / "contracts/examples/projections/view.json").unlink()
    (core / "contracts/examples/projections").rmdir()
    (core / "contracts/examples").rmdir()
    revision = _commit(core)

    with pytest.raises(CoreContractFixtureError, match="examples directory is missing"):
        verified_core_examples_root(core, expected_revision=revision)


def test_missing_example_and_empty_family_fail_instead_of_collecting_zero_tests(
    fixture_checkout: tuple[Path, str],
) -> None:
    core, revision = fixture_checkout

    with pytest.raises(CoreContractFixtureError, match="example is missing"):
        required_core_example_path(
            "projections", "missing.json", checkout=core, expected_revision=revision
        )
    with pytest.raises(CoreContractFixtureError, match="has no complete files"):
        required_core_example_paths("statuses/*.json", checkout=core, expected_revision=revision)


def _write_manifest(
    core: Path, *, contract_version: str = SUPPORTED_EXTERNAL_CONTRACT_VERSION
) -> None:
    content = (core / "contracts/examples/projections/view.json").read_bytes()
    schema_content = (core / "contracts/schemas/game-view.schema.json").read_bytes()
    relative_path = "examples/projections/view.json"
    manifest = {
        "contract_version": contract_version,
        "file_sha256": {
            relative_path: hashlib.sha256(content).hexdigest(),
            "schemas/game-view.schema.json": hashlib.sha256(schema_content).hexdigest(),
        },
        "example_schema_by_path": {relative_path: "game-view.schema.json"},
        "schema_ids": {"game-view.schema.json": "https://example.invalid/game-view.schema.json"},
        "interaction_conformance_case_count": 1,
        "interaction_kind_count": 1,
        "known_external_decision_token_count": 1,
        "live_decision_scenario_count": 1,
        "parameterized_payload_kind_count": 1,
        "proposal_kind_count": 1,
        "registered_decision_type_count": 1,
    }
    (core / "contracts/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _manifest(core: Path) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((core / "contracts/manifest.json").read_text(encoding="utf-8")),
    )


def _save_manifest(core: Path, manifest: dict[str, object]) -> None:
    (core / "contracts/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _commit(core: Path) -> str:
    _git(core, "add", "contracts")
    _git(core, "commit", "--quiet", "-m", "fixture")
    return _git(core, "rev-parse", "HEAD")


def _git(core: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(core), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()
