"""Conformance gates against the supported core Contract 10 examples."""

from __future__ import annotations

import copy
import json
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
    ANNOTATED_DECISION_REQUEST_SCHEMA_VERSION,
    SUPPORTED_EXTERNAL_CONTRACT_VERSION,
    require_supported_core_contract,
)
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientProtocolError,
    UiDecision,
    UiGameView,
    UiLifecycleStatusEnvelope,
    UiNetworkEventDelta,
    UiRulesCatalogView,
    UiSupportProfile,
    validate_json_value,
)
from warhammer40k_arcade_ui.render.core_projection import battlefield_view_from_game_view
from warhammer40k_arcade_ui.state.interaction_dispatch import (
    interaction_route_for_decision,
)

_CORE_EXAMPLES = verified_core_examples_root()
_PROJECTION_EXAMPLES = tuple(
    path
    for path in required_core_example_paths("projections/*.json")
    if path.name != "rules_catalog_view.json"
)
if not _PROJECTION_EXAMPLES:
    raise CoreContractFixtureError("No game-view projection examples remain after filtering.")
_INTERACTION_KINDS = {
    "battlefield_point_placement",
    "confirmation",
    "dice_selection",
    "entity_selection",
    "finite_option_list",
    "model_pose_placement",
    "multi_model_placement",
    "opportunity_window",
    "ordered_sequencing",
    "path_editor",
    "quantity_selection",
    "roster_construction",
    "weapon_allocation_matrix",
}


def test_supported_core_contract_declarations_match_installed_package() -> None:
    require_supported_core_contract()
    manifest = _json_object(_CORE_EXAMPLES.parent / "manifest.json")

    assert manifest["contract_version"] == SUPPORTED_EXTERNAL_CONTRACT_VERSION


@pytest.mark.parametrize(
    "path",
    _PROJECTION_EXAMPLES,
    ids=lambda path: cast(Path, path).name,
)
def test_current_game_view_examples_parse_strictly(path: Path) -> None:
    view = UiGameView.from_payload(_json_object(path))

    assert view.battlefield_view is not None
    assert view.rules_catalog is not None
    assert view.projection_state_hash


def test_current_post_deployment_battlefield_projection_renders_canonically() -> None:
    game_view = UiGameView.from_payload(
        _json_object(required_core_example_path("projections", "post_deployment_view.json"))
    )

    battlefield = battlefield_view_from_game_view(game_view)

    assert battlefield.table.width == 44.0
    assert battlefield.table.height == 60.0
    assert len(battlefield.deployment_zones) == 2
    assert len(battlefield.objectives) == 6
    assert len(battlefield.units) == 2
    assert len(battlefield.terrain) == 46
    assert sum(item.source_kind == "terrain_area" for item in battlefield.terrain) == 16
    assert sum(item.source_kind == "terrain_feature" for item in battlefield.terrain) == 30
    assert all(
        item.logical_terrain_area_id is not None
        for item in battlefield.terrain
        if item.source_kind == "terrain_area"
    )
    assert all(model.support_footprint for unit in battlefield.units for model in unit.models)
    assert all(model.measurement_footprints for unit in battlefield.units for model in unit.models)


def test_current_rules_catalog_example_parses_strictly() -> None:
    catalog = UiRulesCatalogView.from_payload(
        _json_object(required_core_example_path("projections", "rules_catalog_view.json"))
    )

    assert catalog.catalog_id
    assert catalog.source_hash
    assert catalog.display_maps["datasheet_display_by_id"]


@pytest.mark.parametrize(
    "path",
    required_core_example_paths("support-profile*.json"),
    ids=lambda path: cast(Path, path).name,
)
def test_current_support_profile_examples_parse_strictly(path: Path) -> None:
    profile = UiSupportProfile.from_payload(_json_object(path))

    assert profile.capability_manifest.interaction_kinds
    assert profile.capability_manifest.viewer_scope in {"omniscient", "player-a", "player-b"}


@pytest.mark.parametrize(
    "path",
    required_core_example_paths("statuses/*.json"),
    ids=lambda path: cast(Path, path).name,
)
def test_current_lifecycle_status_examples_parse_strictly(path: Path) -> None:
    status = UiLifecycleStatusEnvelope.from_payload(_json_object(path))

    assert status.game_id
    assert status.status_kind


@pytest.mark.parametrize(
    "path",
    required_core_example_paths("events/*.json"),
    ids=lambda path: cast(Path, path).name,
)
def test_current_network_event_examples_parse_strictly(path: Path) -> None:
    delta = UiNetworkEventDelta.from_payload(_json_object(path))

    assert delta.next_cursor
    assert delta.to_revision >= delta.from_revision


@pytest.mark.parametrize(
    "path",
    [
        *required_core_example_paths("decisions/families/*.json"),
        required_core_example_path("decisions", "pending_movement_request.json"),
    ],
    ids=lambda path: cast(Path, path).name,
)
def test_current_top_level_decision_examples_parse_strictly(path: Path) -> None:
    decision = UiDecision.from_payload(_json_object(path))

    assert decision.interaction is not None
    assert interaction_route_for_decision(decision).interaction_kind == (
        decision.interaction.interaction_kind
    )


def test_all_current_interaction_conformance_cases_parse_and_dispatch() -> None:
    inventory = _json_object(_CORE_EXAMPLES / "decisions/interaction-conformance.json")
    cases = inventory["cases"]
    assert type(cases) is list
    assert len(cases) == 90
    observed_kinds: set[str] = set()

    for raw_case in cases:
        assert type(raw_case) is dict
        case = raw_case
        request = case["request"]
        decision = UiDecision.from_annotated_payload(request)
        interaction = decision.interaction
        assert interaction is not None
        route = interaction_route_for_decision(decision)
        variant_id = case["submission_variant_id"]
        assert type(variant_id) is str
        interaction.variant(variant_id)
        assert route.interaction_kind == interaction.interaction_kind
        assert route.diagnostic is not None or route.supported
        validate_json_value(case["proposal_payload"])
        observed_kinds.add(interaction.interaction_kind)

    assert observed_kinds == _INTERACTION_KINDS - {
        "quantity_selection",
        "roster_construction",
    }


@pytest.mark.parametrize("interaction_kind", ["quantity_selection", "roster_construction"])
def test_manifest_interaction_kind_without_conformance_case_still_dispatches(
    interaction_kind: str,
) -> None:
    inventory = _json_object(_CORE_EXAMPLES / "decisions/interaction-conformance.json")
    cases = inventory["cases"]
    assert type(cases) is list
    first_case = cases[0]
    assert type(first_case) is dict
    request = copy.deepcopy(first_case["request"])
    assert type(request) is dict
    interaction = request["interaction"]
    assert type(interaction) is dict
    interaction["interaction_kind"] = interaction_kind
    variants = interaction["submission_variants"]
    assert type(variants) is list
    variant = variants[0]
    assert type(variant) is dict
    variant["interaction_kind"] = interaction_kind

    route = interaction_route_for_decision(UiDecision.from_annotated_payload(request))

    assert route.interaction_kind == interaction_kind
    assert route.supported is (interaction_kind == "quantity_selection")


def test_unknown_interaction_kind_is_a_hard_contract_error() -> None:
    inventory = _json_object(_CORE_EXAMPLES / "decisions/interaction-conformance.json")
    cases = inventory["cases"]
    assert type(cases) is list
    first_case = cases[0]
    assert type(first_case) is dict
    request = copy.deepcopy(first_case["request"])
    assert type(request) is dict
    interaction = request["interaction"]
    assert type(interaction) is dict
    interaction["interaction_kind"] = "unknown_editor_kind"

    with pytest.raises(UiClientProtocolError, match="Unknown interaction_kind"):
        UiDecision.from_annotated_payload(request)


def test_annotated_decision_rejects_an_old_schema_discriminator() -> None:
    inventory = _json_object(_CORE_EXAMPLES / "decisions/interaction-conformance.json")
    cases = inventory["cases"]
    assert type(cases) is list
    first_case = cases[0]
    assert type(first_case) is dict
    request = copy.deepcopy(first_case["request"])
    assert type(request) is dict
    assert request["schema_version"] == ANNOTATED_DECISION_REQUEST_SCHEMA_VERSION
    request["schema_version"] = "annotated-decision-request-v1"

    with pytest.raises(UiClientProtocolError, match="schema_version mismatch"):
        UiDecision.from_annotated_payload(request)


def _json_object(path: Path) -> JsonObject:
    if not path.is_file():
        raise CoreContractFixtureError(f"Required core contract example is missing: {path}.")
    value = json.loads(path.read_text(encoding="utf-8"))
    assert type(value) is dict
    return cast(JsonObject, value)
