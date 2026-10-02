"""Regenerate the exact-Core pending Damage-to-zero checkpoint for UI tests.

Run explicitly from this UI repository after ``uv sync --locked --all-groups``:

    uv run python scripts/generate_contract42_damage_zero_fixture.py

Only this generator imports the pinned Core's test helper. The UI regression loads the
committed checkpoint and imports no Core test modules.
"""

from __future__ import annotations

import gzip
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from warhammer40k_core.engine.lifecycle import GameLifecycle

from warhammer40k_arcade_ui.core_client.compatibility import (
    SUPPORTED_CORE_BUILD_ID,
    SUPPORTED_CORE_REVISION,
    require_supported_core_contract,
)

UI_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = UI_ROOT.parent / "Warhammer_40k_AI"
TARGET = UI_ROOT / "tests/fixtures/contract42_damage_zero_checkpoint.json.gz"
SOURCE_ROW_ID = "000002532:4"


def main() -> None:
    require_supported_core_contract()
    actual_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=CORE_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if actual_sha != SUPPORTED_CORE_REVISION:
        raise RuntimeError(
            f"Core fixture requires revision {SUPPORTED_CORE_REVISION}; found {actual_sha}."
        )

    sys.path.insert(0, str(CORE_ROOT))
    helpers: Any = importlib.import_module("tests.order93_save_damage_helpers")
    session = helpers.save_damage_session(damage_zero_replacement=True)
    request = helpers.reach_save_damage_request(
        session,
        kind="damage_characteristic",
        stage="failed-save-damage-replacement",
    )
    if request.decision_type != "select_modifier_ignores" or request.actor_id != "player-a":
        raise RuntimeError("Core did not emit the expected Damage modifier decision.")
    if session.decision_record_count() != 12 or request.request_id != "decision-request-000013":
        raise RuntimeError("Core Damage checkpoint decision history changed.")
    if {option.option_id for option in request.options} != {
        "keep-remaining",
        "ignore-remaining",
    }:
        raise RuntimeError("Core Damage checkpoint option inventory changed.")

    lifecycle_payload = session.lifecycle.to_payload()
    restored = GameLifecycle.from_payload(lifecycle_payload)
    if restored.to_payload() != lifecycle_payload:
        raise RuntimeError("Core Damage checkpoint did not round-trip exactly.")

    fixture = {
        "schema_version": "contract42-damage-zero-checkpoint-v1",
        "core_sha": SUPPORTED_CORE_REVISION,
        "core_build_id": SUPPORTED_CORE_BUILD_ID,
        "source_row_id": SOURCE_ROW_ID,
        "owner": "player-a",
        "opponent": "player-b",
        "pending_request_id": request.request_id,
        "lifecycle": lifecycle_payload,
    }
    raw = json.dumps(fixture, sort_keys=True, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    TARGET.write_bytes(compressed)
    print(f"Wrote {TARGET.relative_to(UI_ROOT)} ({len(compressed)} bytes)")
    print(f"Raw SHA256: {hashlib.sha256(raw).hexdigest()}")
    print(f"Gzip SHA256: {hashlib.sha256(compressed).hexdigest()}")


if __name__ == "__main__":
    main()
