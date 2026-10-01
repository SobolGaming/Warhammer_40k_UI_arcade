"""Declared compatibility with the supported Warhammer 40k core contract."""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, distribution

from warhammer40k_core.adapters.battlefield_projection import (
    BATTLEFIELD_VIEW_SCHEMA_VERSION as INSTALLED_BATTLEFIELD_VIEW_SCHEMA_VERSION,
)
from warhammer40k_core.adapters.capability_manifest import (
    CAPABILITY_MANIFEST_SCHEMA_VERSION as INSTALLED_CAPABILITY_MANIFEST_SCHEMA_VERSION,
)
from warhammer40k_core.adapters.event_stream import (
    ADAPTER_EVENT_STREAM_DELTA_SCHEMA_VERSION as INSTALLED_LOCAL_EVENT_DELTA_SCHEMA_VERSION,
)
from warhammer40k_core.adapters.external_contract import (
    DECISION_REQUEST_VIEW_SCHEMA_VERSION as INSTALLED_DECISION_REQUEST_SCHEMA_VERSION,
)
from warhammer40k_core.adapters.external_contract import (
    EVENT_STREAM_DELTA_SCHEMA_VERSION as INSTALLED_NETWORK_EVENT_DELTA_SCHEMA_VERSION,
)
from warhammer40k_core.adapters.external_contract import (
    EXTERNAL_CONTRACT_VERSION as INSTALLED_EXTERNAL_CONTRACT_VERSION,
)
from warhammer40k_core.adapters.external_contract import (
    LIFECYCLE_STATUS_SCHEMA_VERSION as INSTALLED_LIFECYCLE_STATUS_SCHEMA_VERSION,
)
from warhammer40k_core.adapters.projection import (
    PROJECTION_SCHEMA_VERSION as INSTALLED_GAME_VIEW_SCHEMA_VERSION,
)
from warhammer40k_core.adapters.projection import (
    RULES_CATALOG_VIEW_SCHEMA_VERSION as INSTALLED_RULES_CATALOG_SCHEMA_VERSION,
)
from warhammer40k_core.adapters.support_profile import (
    SUPPORT_PROFILE_SCHEMA_VERSION as INSTALLED_SUPPORT_PROFILE_SCHEMA_VERSION,
)
from warhammer40k_core.build_identity import (
    EngineBuildIdentityError,
    verified_engine_build_identity,
)
from warhammer40k_core.engine.interaction_metadata import (
    INTERACTION_DESCRIPTOR_SCHEMA_VERSION as INSTALLED_INTERACTION_DESCRIPTOR_SCHEMA_VERSION,
)

SUPPORTED_CORE_REVISION = "6e86f44b87c4559a9297596d5d18dc4247b8cbc3"
SUPPORTED_EXTERNAL_CONTRACT_VERSION = "42.0.0"
SUPPORTED_CORE_BUILD_ID = (
    "warhammer40k-core-v2:runtime-tree-sha256-v1:"
    "03db16dacfdb6152c4f6b841cab170561348f4ee29d60b581ce3215c6ab15765"
)

GAME_VIEW_SCHEMA_VERSION = "game-view-v13-random-profiles"
BATTLEFIELD_VIEW_SCHEMA_VERSION = "battlefield-view-v4-phase17n-step3"
DECISION_REQUEST_SCHEMA_VERSION = "decision-request-view-v5-phase17n-step4"
ANNOTATED_DECISION_REQUEST_SCHEMA_VERSION = "annotated-decision-request-v2-primary-assignments"
INTERACTION_DESCRIPTOR_SCHEMA_VERSION = "interaction-descriptor-v2-variants"
LIFECYCLE_STATUS_SCHEMA_VERSION = "lifecycle-status-v4-phase17n-step4"
LOCAL_EVENT_DELTA_SCHEMA_VERSION = "event-delta-v4-phase17n-step4"
NETWORK_EVENT_DELTA_SCHEMA_VERSION = "event-delta-v5-phase17n-step4"
RULES_CATALOG_SCHEMA_VERSION = "rules-catalog-view-v2"
SUPPORT_PROFILE_SCHEMA_VERSION = "support-profile-v4-directed-primary"
CAPABILITY_MANIFEST_SCHEMA_VERSION = "capability-manifest-v2-directed-primary"


class CoreCompatibilityError(RuntimeError):
    """Raised before play when the installed core contract is unsupported."""


def require_supported_core_contract() -> None:
    """Fail fast when the installed package does not match the declared contract."""

    installed = {
        "external contract": INSTALLED_EXTERNAL_CONTRACT_VERSION,
        "game view": INSTALLED_GAME_VIEW_SCHEMA_VERSION,
        "battlefield view": INSTALLED_BATTLEFIELD_VIEW_SCHEMA_VERSION,
        "decision request": INSTALLED_DECISION_REQUEST_SCHEMA_VERSION,
        "interaction descriptor": INSTALLED_INTERACTION_DESCRIPTOR_SCHEMA_VERSION,
        "lifecycle status": INSTALLED_LIFECYCLE_STATUS_SCHEMA_VERSION,
        "local event delta": INSTALLED_LOCAL_EVENT_DELTA_SCHEMA_VERSION,
        "network event delta": INSTALLED_NETWORK_EVENT_DELTA_SCHEMA_VERSION,
        "rules catalog": INSTALLED_RULES_CATALOG_SCHEMA_VERSION,
        "support profile": INSTALLED_SUPPORT_PROFILE_SCHEMA_VERSION,
        "capability manifest": INSTALLED_CAPABILITY_MANIFEST_SCHEMA_VERSION,
    }
    expected = {
        "external contract": SUPPORTED_EXTERNAL_CONTRACT_VERSION,
        "game view": GAME_VIEW_SCHEMA_VERSION,
        "battlefield view": BATTLEFIELD_VIEW_SCHEMA_VERSION,
        "decision request": DECISION_REQUEST_SCHEMA_VERSION,
        "interaction descriptor": INTERACTION_DESCRIPTOR_SCHEMA_VERSION,
        "lifecycle status": LIFECYCLE_STATUS_SCHEMA_VERSION,
        "local event delta": LOCAL_EVENT_DELTA_SCHEMA_VERSION,
        "network event delta": NETWORK_EVENT_DELTA_SCHEMA_VERSION,
        "rules catalog": RULES_CATALOG_SCHEMA_VERSION,
        "support profile": SUPPORT_PROFILE_SCHEMA_VERSION,
        "capability manifest": CAPABILITY_MANIFEST_SCHEMA_VERSION,
    }
    mismatches = [
        f"{name}: expected {expected[name]}, installed {actual}"
        for name, actual in installed.items()
        if actual != expected[name]
    ]
    if not mismatches:
        try:
            direct_url_text = distribution("warhammer40k-core-v2").read_text("direct_url.json")
        except PackageNotFoundError as exc:
            raise CoreCompatibilityError(
                "Incompatible Warhammer_40k_AI installation. "
                "The pinned warhammer40k-core-v2 distribution is unavailable."
            ) from exc
        try:
            direct_url = json.loads(direct_url_text or "")
            installed_revision = direct_url["vcs_info"]["commit_id"]
        except (KeyError, TypeError, ValueError) as exc:
            raise CoreCompatibilityError(
                "Incompatible Warhammer_40k_AI installation. "
                f"The UI requires the VCS-pinned core revision {SUPPORTED_CORE_REVISION}; "
                "installed direct_url.json does not declare a commit ID."
            ) from exc
        if installed_revision != SUPPORTED_CORE_REVISION:
            mismatches.append(
                f"core revision: expected {SUPPORTED_CORE_REVISION}, installed {installed_revision}"
            )
    if not mismatches:
        try:
            installed_build_id = verified_engine_build_identity().build_id
        except EngineBuildIdentityError as exc:
            raise CoreCompatibilityError(
                "Incompatible Warhammer_40k_AI build identity. "
                f"The UI supports core revision {SUPPORTED_CORE_REVISION} "
                f"with build ID {SUPPORTED_CORE_BUILD_ID}. Verification failed: {exc}"
            ) from exc
        if installed_build_id != SUPPORTED_CORE_BUILD_ID:
            mismatches.append(
                f"core build ID: expected {SUPPORTED_CORE_BUILD_ID}, installed {installed_build_id}"
            )
    if mismatches:
        details = "; ".join(mismatches)
        raise CoreCompatibilityError(
            "Incompatible Warhammer_40k_AI adapter contract. "
            f"The UI supports core revision {SUPPORTED_CORE_REVISION}. {details}."
        )
