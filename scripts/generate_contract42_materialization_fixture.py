"""Regenerate the exact-Core pending materialization checkpoint used by UI tests.

Run from this UI repository after ``uv sync --locked --all-groups``:

    uv run python scripts/generate_contract42_materialization_fixture.py

This generator imports pinned Core's test helpers only while explicitly regenerating the
fixture. The UI regression itself loads the committed checkpoint and imports no Core tests.
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

from warhammer40k_arcade_ui.core_client.compatibility import require_supported_core_contract

CORE_SHA = "6e86f44b87c4559a9297596d5d18dc4247b8cbc3"
UI_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = UI_ROOT.parent / "Warhammer_40k_AI"
TARGET = UI_ROOT / "tests/fixtures/contract42_materialization_checkpoint.json.gz"


def main() -> None:
    require_supported_core_contract()
    actual_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=CORE_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if actual_sha != CORE_SHA:
        raise RuntimeError(f"Core fixture requires revision {CORE_SHA}; found {actual_sha}.")

    sys.path.insert(0, str(CORE_ROOT))
    scenario_module: Any = importlib.import_module(
        "tests.integration.test_horror_split_materialization"
    )
    destruction_helpers: Any = importlib.import_module("tests.horror_destruction_helpers")
    scenario = scenario_module._split_scenario(
        pink_datasheet_id="000002584",
        blue_datasheet_id="000002583",
        destruction_kind="attack",
    )
    status = destruction_helpers.resolve_horror_completion(scenario.runtime, scenario.context)
    if status is None or status.status_kind.value != "waiting_for_decision":
        raise RuntimeError("Core did not emit a pending model materialization decision.")

    lifecycle = GameLifecycle(state=scenario.state, decision_controller=scenario.decisions)
    lifecycle_payload = lifecycle.to_payload()
    # The Core helper's ad hoc muster config is intentionally kept separate. Restoring it
    # inside the lifecycle invokes normal roster consistency, while this fixture starts at
    # a source-authenticated pending decision assembled by the Core integration helper.
    lifecycle_payload["config"] = None
    payload = {
        "core_sha": CORE_SHA,
        "lifecycle": lifecycle_payload,
        "config": scenario_module._game_config(scenario).to_payload(),
        "owner": scenario.source_army.player_id,
        "opponent": scenario.enemy_army.player_id,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    TARGET.write_bytes(compressed)
    print(f"Wrote {TARGET.relative_to(UI_ROOT)} ({len(compressed)} bytes)")
    print(f"Raw SHA256: {hashlib.sha256(raw).hexdigest()}")
    print(f"Gzip SHA256: {hashlib.sha256(compressed).hexdigest()}")


if __name__ == "__main__":
    main()
