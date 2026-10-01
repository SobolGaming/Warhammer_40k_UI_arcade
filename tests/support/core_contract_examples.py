"""Provenance gate for examples read from the sibling core checkout."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import cast

from warhammer40k_arcade_ui.core_client.compatibility import (
    SUPPORTED_CORE_REVISION,
    SUPPORTED_EXTERNAL_CONTRACT_VERSION,
    require_supported_core_contract,
)


class CoreContractFixtureError(RuntimeError):
    """The sibling examples do not belong to the UI's declared core contract."""


def verified_core_examples_root(
    checkout: Path | None = None,
    *,
    expected_revision: str = SUPPORTED_CORE_REVISION,
    expected_contract_version: str = SUPPORTED_EXTERNAL_CONTRACT_VERSION,
) -> Path:
    """Return examples only after checking the installed and sibling core versions."""

    require_supported_core_contract()
    core = (
        Path(__file__).resolve().parents[3] / "Warhammer_40k_AI" if checkout is None else checkout
    )
    if not core.is_dir():
        raise CoreContractFixtureError(
            f"Core fixture checkout is missing: {core}. Check out "
            f"Warhammer_40k_AI at {expected_revision}."
        )
    root = _git_output(core, "rev-parse", "--show-toplevel")
    if Path(root).resolve() != core.resolve():
        raise CoreContractFixtureError(
            f"Core fixture path {core} is not the root of its own Git checkout."
        )
    actual_revision = _git_output(core, "rev-parse", "HEAD")
    if actual_revision != expected_revision:
        raise CoreContractFixtureError(
            f"Core fixture checkout revision mismatch at {core}: expected "
            f"{expected_revision}, found {actual_revision}. Align the sibling checkout "
            "with the UI's supported core revision before reading contract examples."
        )
    changes = _git_output(
        core,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        "contracts",
    )
    if changes:
        raise CoreContractFixtureError(
            f"Core fixture checkout has modified or untracked contracts at {core}: {changes}."
        )
    manifest_path = core / "contracts/manifest.json"
    if not manifest_path.is_file():
        raise CoreContractFixtureError(f"Core fixture manifest is missing: {manifest_path}.")
    try:
        manifest: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CoreContractFixtureError(
            f"Core fixture manifest is unreadable or malformed: {manifest_path}: {exc}"
        ) from exc
    if type(manifest) is not dict:
        raise CoreContractFixtureError(f"Core fixture manifest must be an object: {manifest_path}.")
    version = cast(dict[str, object], manifest).get("contract_version")
    if version != expected_contract_version:
        raise CoreContractFixtureError(
            f"Core fixture manifest contract_version mismatch at {manifest_path}: "
            f"expected {expected_contract_version}, found {version!r}."
        )
    manifest_object = cast(dict[str, object], manifest)
    hashes = manifest_object.get("file_sha256")
    schemas = manifest_object.get("example_schema_by_path")
    schema_ids = manifest_object.get("schema_ids")
    if (
        not _valid_hash_map(hashes)
        or not _valid_string_map(schemas)
        or not _valid_string_map(schema_ids)
    ):
        raise CoreContractFixtureError(
            f"Core fixture manifest has malformed file or schema inventories: {manifest_path}."
        )
    count_keys = (
        "interaction_conformance_case_count",
        "interaction_kind_count",
        "known_external_decision_token_count",
        "live_decision_scenario_count",
        "parameterized_payload_kind_count",
        "proposal_kind_count",
        "registered_decision_type_count",
    )
    if any(not _is_positive_int(manifest_object.get(key)) for key in count_keys):
        raise CoreContractFixtureError(
            f"Core fixture manifest has malformed contract inventory counts: {manifest_path}."
        )
    examples = core / "contracts/examples"
    if not examples.is_dir():
        raise CoreContractFixtureError(f"Core fixture examples directory is missing: {examples}.")
    return examples


def required_core_example_path(
    *parts: str,
    checkout: Path | None = None,
    expected_revision: str = SUPPORTED_CORE_REVISION,
) -> Path:
    """Return one declared-core example and fail when it is absent."""

    root = verified_core_examples_root(checkout, expected_revision=expected_revision)
    path = root.joinpath(*parts)
    if not path.is_file():
        raise CoreContractFixtureError(f"Required core contract example is missing: {path}.")
    return path


def required_core_example_paths(
    pattern: str,
    *,
    checkout: Path | None = None,
    expected_revision: str = SUPPORTED_CORE_REVISION,
) -> tuple[Path, ...]:
    """Collect an example family without silently producing zero test cases."""

    root = verified_core_examples_root(checkout, expected_revision=expected_revision)
    paths = tuple(sorted(root.glob(pattern)))
    if not paths or any(not path.is_file() for path in paths):
        raise CoreContractFixtureError(
            f"Core contract example pattern {pattern!r} has no complete files under {root}."
        )
    return paths


def _git_output(core: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(core), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise CoreContractFixtureError(
            f"Cannot inspect core fixture checkout {core}: {exc}"
        ) from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        raise CoreContractFixtureError(f"Cannot inspect core fixture checkout {core}: {detail}")
    return result.stdout.strip()


def _is_positive_int(value: object) -> bool:
    return type(value) is int and value > 0


def _valid_hash_map(value: object) -> bool:
    if type(value) is not dict:
        return False
    entries = cast(dict[object, object], value)
    if not entries:
        return False
    for path, digest in entries.items():
        if (
            type(path) is not str
            or not path
            or type(digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            return False
    return True


def _valid_string_map(value: object) -> bool:
    if type(value) is not dict:
        return False
    entries = cast(dict[object, object], value)
    return bool(entries) and all(
        type(key) is str and bool(key) and type(item) is str and bool(item)
        for key, item in entries.items()
    )
