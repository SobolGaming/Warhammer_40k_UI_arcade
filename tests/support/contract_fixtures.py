"""Current-contract builders for focused synthetic UI tests."""

from __future__ import annotations

from copy import deepcopy
from typing import cast

from warhammer40k_arcade_ui.core_client.compatibility import (
    GAME_VIEW_SCHEMA_VERSION,
    RULES_CATALOG_SCHEMA_VERSION,
)
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiDecision,
    validate_json_value,
)

DECISION_SCHEMA_VERSION = "decision-request-view-v5-phase17n-step4"
INTERACTION_SCHEMA_VERSION = "interaction-descriptor-v2-variants"

_PATH_PROPOSAL_KINDS = {
    "advance",
    "charge_move",
    "consolidate",
    "fall_back",
    "normal_move",
    "pile_in",
    "scout_move",
    "surge_move",
}
_PLACEMENT_PROPOSAL_KINDS = {
    "cult_ambush_placement",
    "deep_strike_placement",
    "deployment_placement",
    "disembark_placement",
    "healing_revival_placement",
    "model_materialization_placement",
    "redeploy_placement",
    "reinforcement_placement",
    "return_on_death_placement",
    "scout_reserve_setup",
    "strategic_reserves_placement",
}


def decision_from_fixture(payload: object) -> UiDecision:
    """Parse one focused fixture after explicitly upgrading it to Contract 10."""

    return UiDecision.from_payload(current_decision_payload(payload))


def current_decision_payload(payload: object) -> JsonObject:
    """Return a copy carrying the complete current decision and interaction envelope."""

    decision = deepcopy(_json_object(payload))
    decision["schema_version"] = DECISION_SCHEMA_VERSION
    request_id = _required_string(decision, "request_id")
    decision_type = _required_string(decision, "decision_type")
    actor_id = _required_string(decision, "actor_id")
    is_parameterized = decision.get("is_parameterized") is True
    proposal_kind: str | None = None
    if is_parameterized:
        decision_payload = _object(decision, "payload")
        proposal = _object(decision_payload, "proposal_request")
        proposal["request_id"] = request_id
        proposal["decision_type"] = decision_type
        proposal["actor_id"] = actor_id
        proposal_kind = _required_string(proposal, "proposal_kind")
        if decision_type == "submit_movement_proposal":
            proposal.setdefault("spatial_context_hash", "fixture-spatial-context-hash")
        if decision_type == "submit_placement_proposal":
            _upgrade_generic_placement_request(proposal)
        if decision_type == "submit_deployment_placement":
            _upgrade_deployment_request(proposal)
        if decision_type in {"submit_redeploy_placement", "submit_scout_reserve_setup"}:
            _upgrade_prebattle_placement_request(proposal)
        if decision_type == "submit_scout_move":
            _upgrade_scout_request(proposal)
    options = decision.get("options")
    if type(options) is not list:
        raise AssertionError("Fixture decision options must be a list.")
    option_ids = tuple(
        _required_string(cast(JsonObject, option), "option_id")
        for option in cast(list[object], options)
    )
    if "interaction" not in decision:
        finite_kind = (
            _finite_interaction_kind(cast(list[object], options)) if not is_parameterized else None
        )
        decision["interaction"] = interaction_payload(
            decision_type=decision_type,
            is_parameterized=is_parameterized,
            proposal_kind=proposal_kind,
            candidate_option_ids=option_ids,
            interaction_kind_override=finite_kind,
        )
    return decision


def current_game_view_payload(payload: object) -> JsonObject:
    """Return a complete Contract 10 game view for focused synthetic tests."""

    view = deepcopy(_json_object(payload))
    view["projection_schema"] = GAME_VIEW_SCHEMA_VERSION
    view.setdefault("projection_state_hash", "fixture-projection-state-hash")
    view.setdefault("viewer_role", "player")
    view.setdefault(
        "rules_catalog",
        {
            "projection_schema": RULES_CATALOG_SCHEMA_VERSION,
            "catalog_id": "fixture-rules-catalog",
            "ruleset_id": {
                "edition": "fixture",
                "version": "fixture",
            },
            "source_package_id": "fixture-source-package",
            "source_hash": "fixture-source-hash",
        },
    )
    view.setdefault("primary_rules_unit_turn_start_snapshots", [])
    view.setdefault("primary_mission_progress_state", None)
    view.setdefault("unit_display_by_id", {})
    view.setdefault("model_display_by_id", {})
    view.setdefault("nested_interaction_requests", [])

    pending_decision = view.get("pending_decision")
    if type(pending_decision) is dict:
        current_decision = current_decision_payload(pending_decision)
        view["pending_decision"] = current_decision
        if current_decision["is_parameterized"] is True:
            decision_payload = _object(current_decision, "payload")
            view["pending_proposal"] = deepcopy(_object(decision_payload, "proposal_request"))
        else:
            view["pending_proposal"] = None
    elif pending_decision is None:
        view["pending_proposal"] = None
    else:
        raise AssertionError("Fixture pending_decision must be an object or null.")
    return view


def interaction_payload(
    *,
    decision_type: str,
    is_parameterized: bool,
    proposal_kind: str | None,
    candidate_option_ids: tuple[str, ...],
    interaction_kind_override: str | None = None,
) -> JsonObject:
    """Build the explicit descriptor used by a focused fixture decision."""

    interaction_kind, required_inputs = _interaction_shape(
        decision_type=decision_type,
        is_parameterized=is_parameterized,
        proposal_kind=proposal_kind,
    )
    if interaction_kind_override is not None:
        interaction_kind = interaction_kind_override
    variant_id = proposal_kind or "finite_option"
    submission_kind = "parameterized" if is_parameterized else "finite"
    proposal_schema_ref = (
        None if proposal_kind is None else f"proposal-payload.schema.json#/$defs/{proposal_kind}"
    )
    return {
        "schema_version": INTERACTION_SCHEMA_VERSION,
        "interaction_kind": interaction_kind,
        "submission_kind": submission_kind,
        "proposal_kind": proposal_kind,
        "selected_entity_ids": [],
        "required_inputs": list(required_inputs),
        "submission_variants": [
            {
                "variant_id": variant_id,
                "interaction_kind": interaction_kind,
                "required_inputs": list(required_inputs),
                "proposal_schema_ref": proposal_schema_ref,
                "display_label": "Submit" if is_parameterized else "Select",
            }
        ],
        "constraints": {
            "candidate_option_ids": list(candidate_option_ids),
            "entity_kinds": ["unit"] if interaction_kind == "entity_selection" else [],
            "minimum_selections": None,
            "maximum_selections": None,
            "maximum_distance_in": None,
            "minimum_enemy_distance_in": None,
            "exact_model_count": None,
            "must_preserve_coherency": None,
            "may_enter_engagement_range": None,
            "placement_kinds": [],
            "submission_schema_ref": (
                "parameterized-submission.schema.json"
                if is_parameterized
                else "finite-submission.schema.json"
            ),
            "proposal_schema_ref": proposal_schema_ref,
        },
        "display_hints": {
            "confirm_label": "Submit" if is_parameterized else "Select",
            "decline_label": None,
        },
    }


def _interaction_shape(
    *,
    decision_type: str,
    is_parameterized: bool,
    proposal_kind: str | None,
) -> tuple[str, tuple[str, ...]]:
    if not is_parameterized:
        return "finite_option_list", ("option_id",)
    if proposal_kind in _PATH_PROPOSAL_KINDS:
        return "path_editor", ("model_paths", "final_poses")
    if proposal_kind in _PLACEMENT_PROPOSAL_KINDS:
        kind = (
            "model_pose_placement"
            if proposal_kind in {"healing_revival_placement", "return_on_death_placement"}
            else "multi_model_placement"
        )
        return kind, ("model_pose",) if kind == "model_pose_placement" else ("model_poses",)
    if proposal_kind in {"shooting_declaration", "melee_declaration"}:
        return "weapon_allocation_matrix", ("assignments",)
    if proposal_kind == "stratagem_target_binding":
        return "entity_selection", ("target_bindings",)
    raise AssertionError(
        f"Focused fixture needs an explicit interaction mapping for {decision_type}/"
        f"{proposal_kind}."
    )


def _upgrade_scout_request(proposal: JsonObject) -> None:
    proposal.setdefault("component_unit_instance_ids", [])
    proposal.setdefault("model_instance_ids", [])
    proposal.setdefault("placement_kind", None)
    proposal.setdefault("deployment_zone_ids", [])
    proposal.setdefault("legal_deployment_zones", [])
    proposal.setdefault("mission_setup", {})
    proposal.pop("battle_round", None)
    proposal.pop("phase", None)
    proposal.pop("movement_phase_action", None)
    proposal.pop("placement_kinds", None)
    proposal.pop("spatial_context_hash", None)


def _upgrade_generic_placement_request(proposal: JsonObject) -> None:
    proposal.setdefault("battle_round", 1)
    proposal.setdefault("phase", "movement")
    proposal.setdefault("movement_phase_action", None)
    proposal.setdefault("spatial_context_hash", "fixture-spatial-context-hash")
    proposal.pop("model_instance_ids", None)


def _upgrade_deployment_request(proposal: JsonObject) -> None:
    proposal.setdefault("setup_step", "deploy_armies")
    proposal.setdefault("ruleset_descriptor_hash", "fixture-ruleset-hash")
    proposal.setdefault("component_unit_instance_ids", [])
    proposal.setdefault("deployment_zone_ids", ["fixture-deployment-zone"])
    proposal.setdefault("legal_deployment_zones", [])
    proposal.setdefault("mission_pack_id", "fixture-mission-pack")
    proposal.setdefault("source_id", "fixture-source")
    proposal.setdefault("deployment_map_id", "fixture-deployment-map")
    proposal.setdefault("terrain_layout_id", "fixture-terrain-layout")
    proposal.setdefault("mission_setup", {})
    proposal.pop("placement_kinds", None)


def _upgrade_prebattle_placement_request(proposal: JsonObject) -> None:
    proposal.setdefault("component_unit_instance_ids", [])
    proposal.setdefault("scout_distance_inches", None)
    proposal.setdefault("deployment_zone_ids", [])
    proposal.setdefault("legal_deployment_zones", [])
    proposal.setdefault("mission_setup", {})


def _finite_interaction_kind(options: list[object]) -> str:
    if options and all(_option_targets_unit(option) for option in options):
        return "entity_selection"
    return "finite_option_list"


def _option_targets_unit(option: object) -> bool:
    if type(option) is not dict:
        return False
    option_payload = cast(JsonObject, option).get("payload")
    return type(option_payload) is dict and type(option_payload.get("unit_instance_id")) is str


def _object(payload: JsonObject, key: str) -> JsonObject:
    value = payload.get(key)
    if type(value) is not dict:
        raise AssertionError(f"Fixture {key} must be an object.")
    return value


def _json_object(payload: object) -> JsonObject:
    value = validate_json_value(payload)
    if type(value) is not dict:
        raise AssertionError("Fixture payload must be a JSON object.")
    return value


def _required_string(payload: JsonObject, key: str) -> str:
    value = payload.get(key)
    if type(value) is not str or not value:
        raise AssertionError(f"Fixture {key} must be a non-empty string.")
    return value
