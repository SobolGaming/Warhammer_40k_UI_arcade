"""UI-facing protocol types for core engine sessions."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol, Self, cast

from warhammer40k_arcade_ui.core_client.compatibility import (
    ANNOTATED_DECISION_REQUEST_SCHEMA_VERSION,
    BATTLEFIELD_VIEW_SCHEMA_VERSION,
    CAPABILITY_MANIFEST_SCHEMA_VERSION,
    DECISION_REQUEST_SCHEMA_VERSION,
    GAME_VIEW_SCHEMA_VERSION,
    INTERACTION_DESCRIPTOR_SCHEMA_VERSION,
    LIFECYCLE_STATUS_SCHEMA_VERSION,
    LOCAL_EVENT_DELTA_SCHEMA_VERSION,
    NETWORK_EVENT_DELTA_SCHEMA_VERSION,
    RULES_CATALOG_SCHEMA_VERSION,
    SUPPORT_PROFILE_SCHEMA_VERSION,
)

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


def _empty_json_object() -> JsonObject:
    return {}


class UiClientProtocolError(ValueError):
    """Raised when a core-facing payload cannot be represented by the UI protocol."""


class UiClientSubmissionError(UiClientProtocolError):
    """Raised when the public adapter rejects a submitted request envelope."""


class UiCoreClient(Protocol):
    """UI-facing client facade shared by local, network, and fake clients."""

    def start_game(self, config: object) -> UiClientStatus:
        """Start a game session."""

        ...

    def advance_until_decision_or_terminal(self) -> UiClientStatus:
        """Advance engine lifecycle until a decision or terminal status is reached."""

        ...

    def get_view(self, viewer_player_id: str) -> UiGameView:
        """Return a viewer-scoped game projection."""

        ...

    def get_events_since(self, cursor: int, viewer_player_id: str) -> UiEventDelta:
        """Return a viewer-scoped event delta."""

        ...

    def get_rules_catalog(self) -> UiRulesCatalogView:
        """Return the source-hashed public rules catalog projection."""

        ...

    def get_support_profile(self, viewer_player_id: str) -> UiSupportProfile:
        """Return a viewer-redacted support profile."""

        ...

    def submit_finite(
        self,
        *,
        request_id: str,
        selected_option_id: str,
        result_id: str,
    ) -> UiClientStatus:
        """Submit an engine-provided finite option for an explicit request ID."""

        ...

    def submit_movement_payload(
        self,
        *,
        request_id: str,
        payload: JsonValue,
        result_id: str,
    ) -> UiClientStatus:
        """Submit a movement proposal payload for an explicit request ID."""

        ...

    def submit_parameterized_payload(
        self,
        *,
        request_id: str,
        payload: JsonValue,
        result_id: str,
    ) -> UiClientStatus:
        """Submit a generic parameterized proposal payload for an explicit request ID."""

        ...


@dataclass(frozen=True, slots=True)
class UiFiniteOption:
    """Finite option exposed by the current engine decision request."""

    option_id: str
    label: str
    payload: JsonValue = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "option_id", _non_empty_string("option_id", self.option_id))
        object.__setattr__(self, "label", _non_empty_string("label", self.label))
        object.__setattr__(self, "payload", validate_json_value(self.payload))

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        option_payload = _json_object("finite option payload", payload)
        return cls(
            option_id=_required_string(option_payload, "option_id"),
            label=_required_string(option_payload, "label"),
            payload=option_payload["payload"],
        )


_INTERACTION_KINDS = frozenset(
    {
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
)


@dataclass(frozen=True, slots=True)
class UiInteractionConstraints:
    """Engine-authored limits and schema references for one interaction."""

    candidate_option_ids: tuple[str, ...]
    entity_kinds: tuple[str, ...]
    minimum_selections: int | None
    maximum_selections: int | None
    maximum_distance_in: float | None
    minimum_enemy_distance_in: float | None
    exact_model_count: int | None
    must_preserve_coherency: bool | None
    may_enter_engagement_range: bool | None
    placement_kinds: tuple[str, ...]
    submission_schema_ref: str
    proposal_schema_ref: str | None

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        value = _json_object("interaction constraints", payload)
        _require_exact_keys(
            value,
            {
                "candidate_option_ids",
                "entity_kinds",
                "minimum_selections",
                "maximum_selections",
                "maximum_distance_in",
                "minimum_enemy_distance_in",
                "exact_model_count",
                "must_preserve_coherency",
                "may_enter_engagement_range",
                "placement_kinds",
                "submission_schema_ref",
                "proposal_schema_ref",
            },
            "interaction constraints",
        )
        candidate_option_ids = tuple(_string_list(value, "candidate_option_ids"))
        entity_kinds = tuple(_string_list(value, "entity_kinds"))
        placement_kinds = tuple(_string_list(value, "placement_kinds"))
        _require_unique(candidate_option_ids, "candidate_option_ids")
        _require_unique(entity_kinds, "entity_kinds")
        _require_unique(placement_kinds, "placement_kinds")
        return cls(
            candidate_option_ids=candidate_option_ids,
            entity_kinds=entity_kinds,
            minimum_selections=_nullable_non_negative_int(value, "minimum_selections"),
            maximum_selections=_nullable_non_negative_int(value, "maximum_selections"),
            maximum_distance_in=_nullable_non_negative_number(value, "maximum_distance_in"),
            minimum_enemy_distance_in=_nullable_non_negative_number(
                value,
                "minimum_enemy_distance_in",
            ),
            exact_model_count=_nullable_non_negative_int(value, "exact_model_count"),
            must_preserve_coherency=_nullable_bool(value, "must_preserve_coherency"),
            may_enter_engagement_range=_nullable_bool(value, "may_enter_engagement_range"),
            placement_kinds=placement_kinds,
            submission_schema_ref=_required_string(value, "submission_schema_ref"),
            proposal_schema_ref=_optional_string_value(value, "proposal_schema_ref"),
        )


@dataclass(frozen=True, slots=True)
class UiInteractionDisplayHints:
    """Engine-authored player-facing labels for an interaction."""

    confirm_label: str
    decline_label: str | None

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        value = _json_object("interaction display hints", payload)
        _require_exact_keys(value, {"confirm_label", "decline_label"}, "display hints")
        return cls(
            confirm_label=_required_string(value, "confirm_label"),
            decline_label=_optional_string_value(value, "decline_label"),
        )


@dataclass(frozen=True, slots=True)
class UiInteractionSubmissionVariant:
    """One explicit engine-published submission shape."""

    variant_id: str
    interaction_kind: str
    required_inputs: tuple[str, ...]
    proposal_schema_ref: str | None
    display_label: str

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        value = _json_object("interaction submission variant", payload)
        _require_exact_keys(
            value,
            {
                "variant_id",
                "interaction_kind",
                "required_inputs",
                "proposal_schema_ref",
                "display_label",
            },
            "interaction submission variant",
        )
        interaction_kind = _known_interaction_kind(value, "interaction_kind")
        required_inputs = tuple(_string_list(value, "required_inputs"))
        _require_unique(required_inputs, "required_inputs")
        return cls(
            variant_id=_required_string(value, "variant_id"),
            interaction_kind=interaction_kind,
            required_inputs=required_inputs,
            proposal_schema_ref=_optional_string_value(value, "proposal_schema_ref"),
            display_label=_required_string(value, "display_label"),
        )


@dataclass(frozen=True, slots=True)
class UiInteractionDescriptor:
    """Strict UI representation of Contract 10 interaction metadata."""

    schema_version: str
    interaction_kind: str
    submission_kind: str
    proposal_kind: str | None
    selected_entity_ids: tuple[str, ...]
    required_inputs: tuple[str, ...]
    submission_variants: tuple[UiInteractionSubmissionVariant, ...]
    constraints: UiInteractionConstraints
    display_hints: UiInteractionDisplayHints

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        value = _json_object("interaction descriptor", payload)
        _require_exact_keys(
            value,
            {
                "schema_version",
                "interaction_kind",
                "submission_kind",
                "proposal_kind",
                "selected_entity_ids",
                "required_inputs",
                "submission_variants",
                "constraints",
                "display_hints",
            },
            "interaction descriptor",
        )
        _require_discriminator(
            value,
            "schema_version",
            INTERACTION_DESCRIPTOR_SCHEMA_VERSION,
            "interaction descriptor",
        )
        submission_kind = _required_string(value, "submission_kind")
        if submission_kind not in {"finite", "parameterized"}:
            raise UiClientProtocolError("submission_kind must be finite or parameterized.")
        selected_entity_ids = tuple(_string_list(value, "selected_entity_ids"))
        required_inputs = tuple(_string_list(value, "required_inputs"))
        _require_unique(selected_entity_ids, "selected_entity_ids")
        _require_unique(required_inputs, "required_inputs")
        variants = tuple(
            UiInteractionSubmissionVariant.from_payload(item)
            for item in _json_list("submission_variants", value["submission_variants"])
        )
        if not variants:
            raise UiClientProtocolError("submission_variants must not be empty.")
        _require_unique(tuple(item.variant_id for item in variants), "submission variant IDs")
        return cls(
            schema_version=INTERACTION_DESCRIPTOR_SCHEMA_VERSION,
            interaction_kind=_known_interaction_kind(value, "interaction_kind"),
            submission_kind=submission_kind,
            proposal_kind=_optional_string_value(value, "proposal_kind"),
            selected_entity_ids=selected_entity_ids,
            required_inputs=required_inputs,
            submission_variants=variants,
            constraints=UiInteractionConstraints.from_payload(value["constraints"]),
            display_hints=UiInteractionDisplayHints.from_payload(value["display_hints"]),
        )

    def variant(self, variant_id: str) -> UiInteractionSubmissionVariant:
        """Return one explicit published variant or reject an invented ID."""

        normalized = _non_empty_string("variant_id", variant_id)
        for variant in self.submission_variants:
            if variant.variant_id == normalized:
                return variant
        raise UiClientProtocolError(
            f"submission variant {normalized!r} is not published by this interaction."
        )


@dataclass(frozen=True, slots=True)
class UiBattlefieldProjection:
    """Canonical render-facing battlefield projection and identity."""

    schema_version: str
    battlefield_id: str
    coordinate_space: str
    coordinate_spec_version: str
    authoritative_geometry_hash: str
    bounds: JsonObject
    authoritative: JsonObject
    interaction: JsonObject
    render: JsonObject

    @property
    def models_by_id(self) -> JsonObject:
        """Return the viewer-scoped physical model identities."""

        return _json_object("battlefield models_by_id", self.authoritative["models_by_id"])

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        value = _json_object("battlefield view", payload)
        _require_exact_keys(
            value,
            {
                "schema_version",
                "battlefield_id",
                "coordinate_space",
                "coordinate_spec_version",
                "authoritative_geometry_hash",
                "bounds",
                "authoritative",
                "interaction",
                "render",
            },
            "battlefield view",
        )
        _require_discriminator(
            value,
            "schema_version",
            BATTLEFIELD_VIEW_SCHEMA_VERSION,
            "battlefield view",
        )
        bounds = _json_object("battlefield bounds", value["bounds"])
        _require_exact_keys(
            bounds,
            {
                "min_x_inches",
                "min_y_inches",
                "min_z_inches",
                "max_x_inches",
                "max_y_inches",
            },
            "battlefield bounds",
        )
        for key in bounds:
            _required_number(bounds, key)
        authoritative = _json_object("battlefield authoritative", value["authoritative"])
        _require_exact_keys(
            authoritative,
            {
                "battlefield_regions_by_id",
                "deployment_zones_by_id",
                "models_by_id",
                "objectives_by_id",
                "terrain_areas_by_id",
                "terrain_features_by_id",
            },
            "battlefield authoritative",
        )
        for key in authoritative:
            _json_object(key, authoritative[key])
        for model_id, raw_model in _json_object(
            "models_by_id", authoritative["models_by_id"]
        ).items():
            model = _json_object(f"models_by_id.{model_id}", raw_model)
            _required_matching_string(model, "model_instance_id", model_id, "battlefield model key")
            _required_string(model, "unit_instance_id")
            state = _required_string(model, "state")
            if "pose" not in model:
                raise UiClientProtocolError(f"models_by_id.{model_id}.pose is required.")
            if state == "placed" and model["pose"] is None:
                raise UiClientProtocolError(
                    f"models_by_id.{model_id}.pose is required for a placed model."
                )
            rules_unit_id = _required_value(model, "rules_unit_instance_id")
            if rules_unit_id is not None:
                _non_empty_string("rules_unit_instance_id", rules_unit_id)
        interaction = _json_object("battlefield interaction", value["interaction"])
        _require_exact_keys(
            interaction,
            {
                "request_id",
                "selected_or_acting_entity_ids",
                "legal_candidate_refs",
                "measurement_overlays",
                "path_overlays",
            },
            "battlefield interaction",
        )
        render = _json_object("battlefield render", value["render"])
        _require_exact_keys(
            render,
            {"hints_by_entity_id", "hit_regions_by_entity_id"},
            "battlefield render",
        )
        return cls(
            schema_version=BATTLEFIELD_VIEW_SCHEMA_VERSION,
            battlefield_id=_required_string(value, "battlefield_id"),
            coordinate_space=_required_string(value, "coordinate_space"),
            coordinate_spec_version=_required_string(value, "coordinate_spec_version"),
            authoritative_geometry_hash=_required_string(
                value,
                "authoritative_geometry_hash",
            ),
            bounds=bounds,
            authoritative=authoritative,
            interaction=interaction,
            render=render,
        )


@dataclass(frozen=True, slots=True)
class UiRulesCatalogReference:
    """Source identity embedded in each game projection."""

    projection_schema: str
    catalog_id: str
    ruleset_id: JsonObject
    source_package_id: str
    source_hash: str

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        value = _json_object("rules catalog reference", payload)
        _require_exact_keys(
            value,
            {"projection_schema", "catalog_id", "ruleset_id", "source_package_id", "source_hash"},
            "rules catalog reference",
        )
        _require_discriminator(
            value,
            "projection_schema",
            RULES_CATALOG_SCHEMA_VERSION,
            "rules catalog reference",
        )
        return cls(
            projection_schema=RULES_CATALOG_SCHEMA_VERSION,
            catalog_id=_required_string(value, "catalog_id"),
            ruleset_id=_json_object("ruleset_id", value["ruleset_id"]),
            source_package_id=_required_string(value, "source_package_id"),
            source_hash=_required_string(value, "source_hash"),
        )


@dataclass(frozen=True, slots=True)
class UiRulesCatalogView:
    """Strict source-hashed catalog projection retained for HUD consumers."""

    projection_schema: str
    catalog_id: str
    ruleset_id: JsonObject
    source_package_id: str
    source_hash: str
    display_maps: JsonObject

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        value = _json_object("rules catalog", payload)
        required = {
            "projection_schema",
            "catalog_id",
            "ruleset_id",
            "source_package_id",
            "source_hash",
            "datasheet_display_by_id",
            "model_profile_display_by_id",
            "wargear_display_by_id",
            "weapon_profile_display_by_id",
            "faction_display_by_id",
            "detachment_display_by_id",
            "army_rule_display_by_id",
            "stratagem_display_by_id",
            "enhancement_display_by_id",
            "wargear_option_display_by_id",
            "base_size_display_by_id",
        }
        _require_exact_keys(value, required, "rules catalog")
        _require_discriminator(
            value,
            "projection_schema",
            RULES_CATALOG_SCHEMA_VERSION,
            "rules catalog",
        )
        display_maps: JsonObject = {}
        for key in required - {
            "projection_schema",
            "catalog_id",
            "ruleset_id",
            "source_package_id",
            "source_hash",
        }:
            display_maps[key] = _json_object(key, value[key])
        return cls(
            projection_schema=RULES_CATALOG_SCHEMA_VERSION,
            catalog_id=_required_string(value, "catalog_id"),
            ruleset_id=_json_object("ruleset_id", value["ruleset_id"]),
            source_package_id=_required_string(value, "source_package_id"),
            source_hash=_required_string(value, "source_hash"),
            display_maps=display_maps,
        )


@dataclass(frozen=True, slots=True)
class UiCapabilityManifest:
    """Strict viewer-scoped capability evidence retained for diagnostics and HUDs."""

    schema_version: str
    manifest_id: str
    viewer_scope: str
    selection_hash: str
    interaction_kinds: tuple[str, ...]
    decision_family_rows: tuple[JsonObject, ...]
    payload: JsonObject

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        value = _json_object("capability manifest", payload)
        required = {
            "schema_version",
            "manifest_id",
            "viewer_scope",
            "selection_hash",
            "identities",
            "mode_capabilities",
            "capability_counts",
            "roster_rows",
            "unit_rows",
            "rule_rows",
            "mission_rows",
            "geometry_rows",
            "unsupported_effects",
            "interaction_kinds",
            "decision_family_rows",
            "hidden_information_status",
            "replay_evidence_refs",
            "certified_scenario_evidence_refs",
            "certification_claims",
        }
        _require_exact_keys(value, required, "capability manifest")
        _require_discriminator(
            value,
            "schema_version",
            CAPABILITY_MANIFEST_SCHEMA_VERSION,
            "capability manifest",
        )
        _required_string(value, "viewer_scope")
        for key in (
            "identities",
            "capability_counts",
            "hidden_information_status",
            "certification_claims",
        ):
            _json_object(key, value[key])
        for key in (
            "mode_capabilities",
            "roster_rows",
            "unit_rows",
            "rule_rows",
            "mission_rows",
            "geometry_rows",
            "unsupported_effects",
            "decision_family_rows",
            "replay_evidence_refs",
            "certified_scenario_evidence_refs",
        ):
            _json_list(key, value[key])
        interaction_kinds = tuple(_string_list(value, "interaction_kinds"))
        _require_unique(interaction_kinds, "capability interaction_kinds")
        return cls(
            schema_version=CAPABILITY_MANIFEST_SCHEMA_VERSION,
            manifest_id=_required_string(value, "manifest_id"),
            viewer_scope=_required_string(value, "viewer_scope"),
            selection_hash=_required_string(value, "selection_hash"),
            interaction_kinds=interaction_kinds,
            decision_family_rows=tuple(
                _json_object("decision family row", row)
                for row in _json_list("decision_family_rows", value["decision_family_rows"])
            ),
            payload=value,
        )


@dataclass(frozen=True, slots=True)
class UiSupportProfile:
    """Viewer-redacted support and capability evidence."""

    schema_version: str
    game_id: str
    catalog_id: str
    capability_manifest: UiCapabilityManifest
    payload: JsonObject

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        value = _json_object("support profile", payload)
        required = {
            "schema_version",
            "game_id",
            "catalog_id",
            "source_package_id",
            "ruleset_descriptor_hash",
            "overall_status",
            "eligible_for_headless_self_play_smoke",
            "status_counts",
            "mustering_support_rows",
            "datasheet_support_rows",
            "detachment_faction_support_rows",
            "interaction_kinds",
            "decision_interaction_support_rows",
            "capability_manifest",
        }
        _require_exact_keys(value, required, "support profile")
        _require_discriminator(
            value,
            "schema_version",
            SUPPORT_PROFILE_SCHEMA_VERSION,
            "support profile",
        )
        _required_bool(value, "eligible_for_headless_self_play_smoke")
        _json_object("status_counts", value["status_counts"])
        for key in (
            "mustering_support_rows",
            "datasheet_support_rows",
            "detachment_faction_support_rows",
            "decision_interaction_support_rows",
        ):
            _json_list(key, value[key])
        interaction_kinds = tuple(_string_list(value, "interaction_kinds"))
        _require_unique(interaction_kinds, "support profile interaction_kinds")
        return cls(
            schema_version=SUPPORT_PROFILE_SCHEMA_VERSION,
            game_id=_required_string(value, "game_id"),
            catalog_id=_required_string(value, "catalog_id"),
            capability_manifest=UiCapabilityManifest.from_payload(value["capability_manifest"]),
            payload=value,
        )


@dataclass(frozen=True, slots=True)
class UiMovementProposalRequest:
    """UI view of an engine movement proposal request."""

    request_id: str
    decision_type: str
    actor_id: str
    game_id: str
    battle_round: int | None
    phase: str | None
    unit_instance_id: str
    proposal_kind: str
    source_decision_request_id: str
    source_decision_result_id: str
    movement_phase_action: str | None
    placement_kinds: tuple[str, ...]
    context: JsonObject
    player_id: str | None = None
    setup_step: str | None = None
    action_kind: str | None = None
    source_rule_id: str | None = None
    ruleset_descriptor_hash: str | None = None
    scout_distance_inches: float | None = None
    spatial_context_hash: str | None = None
    component_unit_instance_ids: tuple[str, ...] = ()
    required_model_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _non_empty_string("request_id", self.request_id))
        object.__setattr__(
            self,
            "decision_type",
            _non_empty_string("decision_type", self.decision_type),
        )
        object.__setattr__(self, "actor_id", _non_empty_string("actor_id", self.actor_id))
        object.__setattr__(self, "game_id", _non_empty_string("game_id", self.game_id))
        if self.battle_round is not None and (
            type(self.battle_round) is not int or self.battle_round <= 0
        ):
            raise UiClientProtocolError("battle_round must be a positive integer when present.")
        object.__setattr__(self, "phase", _optional_string("phase", self.phase))
        object.__setattr__(
            self,
            "unit_instance_id",
            _non_empty_string("unit_instance_id", self.unit_instance_id),
        )
        object.__setattr__(
            self,
            "proposal_kind",
            _non_empty_string("proposal_kind", self.proposal_kind),
        )
        object.__setattr__(
            self,
            "source_decision_request_id",
            _non_empty_string("source_decision_request_id", self.source_decision_request_id),
        )
        object.__setattr__(
            self,
            "source_decision_result_id",
            _non_empty_string("source_decision_result_id", self.source_decision_result_id),
        )
        object.__setattr__(
            self,
            "movement_phase_action",
            _optional_string("movement_phase_action", self.movement_phase_action),
        )
        if type(self.placement_kinds) is not tuple:
            raise UiClientProtocolError("placement_kinds must be a tuple.")
        object.__setattr__(
            self,
            "placement_kinds",
            tuple(_non_empty_string("placement_kind", kind) for kind in self.placement_kinds),
        )
        object.__setattr__(self, "context", _json_object("context", self.context))
        object.__setattr__(self, "player_id", _optional_string("player_id", self.player_id))
        object.__setattr__(self, "setup_step", _optional_string("setup_step", self.setup_step))
        object.__setattr__(self, "action_kind", _optional_string("action_kind", self.action_kind))
        object.__setattr__(
            self,
            "source_rule_id",
            _optional_string("source_rule_id", self.source_rule_id),
        )
        object.__setattr__(
            self,
            "ruleset_descriptor_hash",
            _optional_string("ruleset_descriptor_hash", self.ruleset_descriptor_hash),
        )
        if self.scout_distance_inches is not None:
            scout_distance = self.scout_distance_inches
            if type(scout_distance) is not int and type(scout_distance) is not float:
                raise UiClientProtocolError("scout_distance_inches must be a number.")
            if not math.isfinite(float(scout_distance)) or float(scout_distance) <= 0.0:
                raise UiClientProtocolError("scout_distance_inches must be positive.")
            object.__setattr__(self, "scout_distance_inches", float(scout_distance))
        object.__setattr__(
            self,
            "spatial_context_hash",
            _optional_string("spatial_context_hash", self.spatial_context_hash),
        )
        for field_name in ("component_unit_instance_ids", "required_model_ids"):
            values: tuple[str, ...] = (
                self.component_unit_instance_ids
                if field_name == "component_unit_instance_ids"
                else self.required_model_ids
            )
            if type(values) is not tuple:
                raise UiClientProtocolError(f"{field_name} must be a tuple of unique IDs.")
            normalized = tuple(_non_empty_string(field_name, value) for value in values)
            if len(normalized) != len(set(normalized)):
                raise UiClientProtocolError(f"{field_name} must be a tuple of unique IDs.")
            object.__setattr__(self, field_name, normalized)
        if self.decision_type == "submit_scout_move" and (
            not self.component_unit_instance_ids or not self.required_model_ids
        ):
            raise UiClientProtocolError("Scout Move requires component and model inventories.")

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        proposal = _json_object("movement proposal request payload", payload)
        if proposal.get("decision_type") == "submit_scout_move":
            _require_exact_keys(
                proposal,
                {
                    "request_id",
                    "decision_type",
                    "actor_id",
                    "game_id",
                    "setup_step",
                    "player_id",
                    "unit_instance_id",
                    "component_unit_instance_ids",
                    "model_instance_ids",
                    "proposal_kind",
                    "action_kind",
                    "source_rule_id",
                    "placement_kind",
                    "scout_distance_inches",
                    "deployment_zone_ids",
                    "legal_deployment_zones",
                    "mission_setup",
                    "ruleset_descriptor_hash",
                    "source_decision_request_id",
                    "source_decision_result_id",
                    "context",
                },
                "Scout Move proposal request",
            )
            action_kind = _required_string(proposal, "action_kind")
            if proposal["placement_kind"] is not None:
                raise UiClientProtocolError(
                    "Scout Move proposal request placement_kind must be null."
                )
            component_ids = tuple(_string_list(proposal, "component_unit_instance_ids"))
            model_ids = tuple(_string_list(proposal, "model_instance_ids"))
            _string_list(proposal, "deployment_zone_ids")
            _json_list("legal_deployment_zones", proposal["legal_deployment_zones"])
            _json_object("mission_setup", proposal["mission_setup"])
            return cls(
                request_id=_required_string(proposal, "request_id"),
                decision_type=_required_string(proposal, "decision_type"),
                actor_id=_required_string(proposal, "actor_id"),
                game_id=_required_string(proposal, "game_id"),
                battle_round=None,
                phase=None,
                unit_instance_id=_required_string(proposal, "unit_instance_id"),
                proposal_kind=_required_string(proposal, "proposal_kind"),
                source_decision_request_id=_required_string(
                    proposal,
                    "source_decision_request_id",
                ),
                source_decision_result_id=_required_string(
                    proposal,
                    "source_decision_result_id",
                ),
                movement_phase_action=None,
                placement_kinds=(),
                context=_json_object("proposal context", proposal["context"]),
                player_id=_required_string(proposal, "player_id"),
                setup_step=_required_string(proposal, "setup_step"),
                action_kind=action_kind,
                source_rule_id=_required_string(proposal, "source_rule_id"),
                ruleset_descriptor_hash=_required_string(proposal, "ruleset_descriptor_hash"),
                scout_distance_inches=_required_number(proposal, "scout_distance_inches"),
                spatial_context_hash=None,
                component_unit_instance_ids=component_ids,
                required_model_ids=model_ids,
            )
        _require_exact_keys(
            proposal,
            {
                "request_id",
                "decision_type",
                "actor_id",
                "game_id",
                "battle_round",
                "phase",
                "unit_instance_id",
                "proposal_kind",
                "source_decision_request_id",
                "source_decision_result_id",
                "spatial_context_hash",
                "movement_phase_action",
                "placement_kinds",
                "context",
            },
            "movement proposal request",
        )
        return cls(
            request_id=_required_string(proposal, "request_id"),
            decision_type=_required_string(proposal, "decision_type"),
            actor_id=_required_string(proposal, "actor_id"),
            game_id=_required_string(proposal, "game_id"),
            battle_round=_required_int(proposal, "battle_round"),
            phase=_required_string(proposal, "phase"),
            unit_instance_id=_required_string(proposal, "unit_instance_id"),
            proposal_kind=_required_string(proposal, "proposal_kind"),
            source_decision_request_id=_required_string(
                proposal,
                "source_decision_request_id",
            ),
            source_decision_result_id=_required_string(
                proposal,
                "source_decision_result_id",
            ),
            movement_phase_action=_optional_string_value(proposal, "movement_phase_action"),
            placement_kinds=tuple(_string_list(proposal, "placement_kinds")),
            context=_json_object("proposal context", proposal["context"]),
            spatial_context_hash=_required_string(proposal, "spatial_context_hash"),
        )

    @classmethod
    def from_decision_payload(cls, payload: JsonValue) -> Self:
        decision_payload = _json_object("parameterized decision payload", payload)
        return cls.from_payload(decision_payload["proposal_request"])


@dataclass(frozen=True, slots=True)
class UiPlacementProposalRequest:
    """UI view of an engine placement proposal request."""

    request_id: str
    decision_type: str
    actor_id: str
    game_id: str | None
    player_id: str
    unit_instance_id: str
    proposal_kind: str
    placement_kind: str
    placement_kinds: tuple[str, ...]
    required_model_ids: tuple[str, ...]
    source_decision_request_id: str | None
    source_decision_result_id: str | None
    ruleset_descriptor_hash: str | None
    setup_step: str | None
    action_kind: str | None
    source_rule_id: str | None
    context: JsonObject
    spatial_context_hash: str | None = None
    army_id: str | None = None
    materialized_models: tuple[JsonObject, ...] = ()
    component_unit_instance_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _non_empty_string("request_id", self.request_id))
        object.__setattr__(
            self,
            "decision_type",
            _non_empty_string("decision_type", self.decision_type),
        )
        object.__setattr__(self, "actor_id", _non_empty_string("actor_id", self.actor_id))
        object.__setattr__(self, "game_id", _optional_string("game_id", self.game_id))
        object.__setattr__(self, "player_id", _non_empty_string("player_id", self.player_id))
        object.__setattr__(
            self,
            "unit_instance_id",
            _non_empty_string("unit_instance_id", self.unit_instance_id),
        )
        object.__setattr__(
            self,
            "proposal_kind",
            _non_empty_string("proposal_kind", self.proposal_kind),
        )
        object.__setattr__(
            self,
            "placement_kind",
            _non_empty_string("placement_kind", self.placement_kind),
        )
        if type(self.placement_kinds) is not tuple:
            raise UiClientProtocolError("placement_kinds must be a tuple.")
        object.__setattr__(
            self,
            "placement_kinds",
            tuple(_non_empty_string("placement_kind", kind) for kind in self.placement_kinds),
        )
        if self.placement_kind not in self.placement_kinds:
            raise UiClientProtocolError("placement_kind must be one of placement_kinds.")
        if type(self.required_model_ids) is not tuple:
            raise UiClientProtocolError("required_model_ids must be a tuple.")
        object.__setattr__(
            self,
            "required_model_ids",
            tuple(
                _non_empty_string("model_instance_id", model_id)
                for model_id in self.required_model_ids
            ),
        )
        object.__setattr__(
            self,
            "source_decision_request_id",
            _optional_string("source_decision_request_id", self.source_decision_request_id),
        )
        object.__setattr__(
            self,
            "source_decision_result_id",
            _optional_string("source_decision_result_id", self.source_decision_result_id),
        )
        object.__setattr__(
            self,
            "ruleset_descriptor_hash",
            _optional_string("ruleset_descriptor_hash", self.ruleset_descriptor_hash),
        )
        object.__setattr__(self, "setup_step", _optional_string("setup_step", self.setup_step))
        object.__setattr__(self, "action_kind", _optional_string("action_kind", self.action_kind))
        object.__setattr__(
            self,
            "source_rule_id",
            _optional_string("source_rule_id", self.source_rule_id),
        )
        object.__setattr__(self, "context", _json_object("context", self.context))
        object.__setattr__(
            self,
            "spatial_context_hash",
            _optional_string("spatial_context_hash", self.spatial_context_hash),
        )
        object.__setattr__(self, "army_id", _optional_string("army_id", self.army_id))
        if type(self.materialized_models) is not tuple:
            raise UiClientProtocolError("materialized_models must be a tuple.")
        models = tuple(
            _json_object("materialized model", model) for model in self.materialized_models
        )
        if self.decision_type == "submit_catalog_model_materialization_placement":
            if self.army_id is None or not models:
                raise UiClientProtocolError(
                    "Model materialization requires an army and emitted models."
                )
            model_ids = tuple(_required_string(model, "model_instance_id") for model in models)
            if model_ids != self.required_model_ids or len(set(model_ids)) != len(model_ids):
                raise UiClientProtocolError(
                    "Materialized models must match the emitted model_instance_ids exactly."
                )
            for model in models:
                _json_object("materialized model base_size", _required_value(model, "base_size"))
        elif self.army_id is not None or models:
            raise UiClientProtocolError(
                "Only model materialization may carry request-created model authority."
            )
        object.__setattr__(self, "materialized_models", models)
        component_ids = self.component_unit_instance_ids
        if type(component_ids) is not tuple:
            raise UiClientProtocolError("component_unit_instance_ids must be unique IDs.")
        normalized_component_ids = tuple(
            _non_empty_string("component_unit_instance_id", value) for value in component_ids
        )
        if len(normalized_component_ids) != len(set(normalized_component_ids)):
            raise UiClientProtocolError("component_unit_instance_ids must be unique IDs.")
        object.__setattr__(
            self,
            "component_unit_instance_ids",
            normalized_component_ids,
        )
        if self.decision_type in {
            "submit_deployment_placement",
            "submit_redeploy_placement",
            "submit_scout_reserve_setup",
        } and (not component_ids or not self.required_model_ids):
            raise UiClientProtocolError("Pre-battle placement requires component and model IDs.")

    @classmethod
    def from_payload(
        cls,
        payload: object,
        *,
        interaction: UiInteractionDescriptor,
    ) -> Self:
        proposal = _json_object("placement proposal request payload", payload)
        request_id = _required_string(proposal, "request_id")
        decision_type = _required_string(proposal, "decision_type")
        actor_id = _required_string(proposal, "actor_id")
        proposal_kind = _descriptor_proposal_kind(
            proposal=proposal,
            interaction=interaction,
        )
        if decision_type == "submit_cult_ambush_marker_placement":
            _require_exact_keys(
                proposal,
                _CULT_AMBUSH_MARKER_REQUEST_KEYS,
                "Cult Ambush marker placement request",
            )
            player_id = _required_matching_string(
                proposal,
                "player_id",
                actor_id,
                "placement request actor_id",
            )
            marker_diameter = _required_number(proposal, "marker_diameter_inches")
            required_enemy_distance = _required_number(
                proposal,
                "required_enemy_horizontal_distance_inches",
            )
            if marker_diameter <= 0.0 or required_enemy_distance < 0.0:
                raise UiClientProtocolError(
                    "Cult Ambush marker geometry values must be positive/non-negative."
                )
            return cls(
                request_id=request_id,
                decision_type=decision_type,
                actor_id=actor_id,
                game_id=None,
                player_id=player_id,
                unit_instance_id=_required_string(
                    proposal,
                    "replacement_unit_instance_id",
                ),
                proposal_kind=proposal_kind,
                placement_kind="cult_ambush_marker_placement",
                placement_kinds=("cult_ambush_marker_placement",),
                required_model_ids=(),
                source_decision_request_id=_required_string(
                    proposal,
                    "source_decision_request_id",
                ),
                source_decision_result_id=_required_string(
                    proposal,
                    "source_decision_result_id",
                ),
                ruleset_descriptor_hash=None,
                setup_step=None,
                action_kind=None,
                source_rule_id=_required_string(proposal, "source_rule_id"),
                context={
                    "marker_id": _required_string(proposal, "marker_id"),
                    "destroyed_unit_instance_id": _required_string(
                        proposal,
                        "destroyed_unit_instance_id",
                    ),
                    "marker_diameter_inches": marker_diameter,
                    "required_enemy_horizontal_distance_inches": required_enemy_distance,
                },
            )
        if decision_type == "submit_placement_proposal":
            _require_exact_keys(
                proposal,
                {
                    "request_id",
                    "decision_type",
                    "actor_id",
                    "game_id",
                    "battle_round",
                    "phase",
                    "unit_instance_id",
                    "proposal_kind",
                    "source_decision_request_id",
                    "source_decision_result_id",
                    "spatial_context_hash",
                    "movement_phase_action",
                    "placement_kinds",
                    "context",
                },
                "generic placement proposal request",
            )
            placement_kinds = tuple(_string_list(proposal, "placement_kinds"))
            if len(placement_kinds) != 1:
                raise UiClientProtocolError(
                    "Generic placement editor requires exactly one published placement_kind."
                )
            if proposal["movement_phase_action"] is not None:
                raise UiClientProtocolError(
                    "Generic placement proposal movement_phase_action must be null."
                )
            return cls(
                request_id=request_id,
                decision_type=decision_type,
                actor_id=actor_id,
                game_id=_required_string(proposal, "game_id"),
                player_id=actor_id,
                unit_instance_id=_required_string(proposal, "unit_instance_id"),
                proposal_kind=proposal_kind,
                placement_kind=placement_kinds[0],
                placement_kinds=placement_kinds,
                required_model_ids=(),
                source_decision_request_id=_required_string(
                    proposal,
                    "source_decision_request_id",
                ),
                source_decision_result_id=_required_string(
                    proposal,
                    "source_decision_result_id",
                ),
                ruleset_descriptor_hash=None,
                setup_step=None,
                action_kind=None,
                source_rule_id=None,
                context=_json_object("proposal context", proposal["context"]),
                spatial_context_hash=_required_string(proposal, "spatial_context_hash"),
            )
        if decision_type == "submit_deployment_placement":
            _require_exact_keys(
                proposal,
                _DEPLOYMENT_PLACEMENT_REQUEST_KEYS,
                "deployment placement proposal request",
            )
            player_id = _required_matching_string(
                proposal,
                "player_id",
                actor_id,
                "placement request actor_id",
            )
            return cls(
                request_id=request_id,
                decision_type=decision_type,
                actor_id=actor_id,
                game_id=_required_string(proposal, "game_id"),
                player_id=player_id,
                unit_instance_id=_required_string(proposal, "unit_instance_id"),
                proposal_kind=proposal_kind,
                placement_kind=_required_string(proposal, "placement_kind"),
                placement_kinds=(_required_string(proposal, "placement_kind"),),
                required_model_ids=tuple(_string_list(proposal, "model_instance_ids")),
                source_decision_request_id=_required_string(
                    proposal,
                    "source_decision_request_id",
                ),
                source_decision_result_id=_required_string(
                    proposal,
                    "source_decision_result_id",
                ),
                ruleset_descriptor_hash=_required_string(
                    proposal,
                    "ruleset_descriptor_hash",
                ),
                setup_step=_required_string(proposal, "setup_step"),
                action_kind=None,
                source_rule_id=None,
                context=_json_object("proposal context", proposal["context"]),
                component_unit_instance_ids=tuple(
                    _string_list(proposal, "component_unit_instance_ids")
                ),
            )
        if decision_type in {"submit_redeploy_placement", "submit_scout_reserve_setup"}:
            _require_exact_keys(
                proposal,
                _PREBATTLE_PROPOSAL_REQUEST_KEYS,
                "pre-battle placement proposal request",
            )
            placement_kind = _required_string(proposal, "placement_kind")
            player_id = _required_matching_string(
                proposal,
                "player_id",
                actor_id,
                "placement request actor_id",
            )
            return cls(
                request_id=request_id,
                decision_type=decision_type,
                actor_id=actor_id,
                game_id=_required_string(proposal, "game_id"),
                player_id=player_id,
                unit_instance_id=_required_string(proposal, "unit_instance_id"),
                proposal_kind=proposal_kind,
                placement_kind=placement_kind,
                placement_kinds=(placement_kind,),
                required_model_ids=tuple(_string_list(proposal, "model_instance_ids")),
                source_decision_request_id=_required_string(
                    proposal,
                    "source_decision_request_id",
                ),
                source_decision_result_id=_required_string(
                    proposal,
                    "source_decision_result_id",
                ),
                ruleset_descriptor_hash=_required_string(
                    proposal,
                    "ruleset_descriptor_hash",
                ),
                setup_step=_required_string(proposal, "setup_step"),
                action_kind=_required_string(proposal, "action_kind"),
                source_rule_id=_required_string(proposal, "source_rule_id"),
                context=_json_object("proposal context", proposal["context"]),
                component_unit_instance_ids=tuple(
                    _string_list(proposal, "component_unit_instance_ids")
                ),
            )
        if decision_type == "submit_catalog_model_materialization_placement":
            _require_exact_keys(
                proposal,
                _MODEL_MATERIALIZATION_REQUEST_KEYS,
                "model materialization placement request",
            )
            _required_matching_string(
                proposal,
                "submission_kind",
                decision_type,
                "placement request decision_type",
            )
            models = tuple(
                _json_object("materialized model", model)
                for model in _json_list("materialized models", proposal["models"])
            )
            placement_kind = _required_string(proposal, "placement_kind")
            player_id = _required_matching_string(
                proposal,
                "player_id",
                actor_id,
                "placement request actor_id",
            )
            return cls(
                request_id=request_id,
                decision_type=decision_type,
                actor_id=actor_id,
                game_id=None,
                player_id=player_id,
                unit_instance_id=_required_string(proposal, "source_unit_instance_id"),
                proposal_kind=proposal_kind,
                placement_kind=placement_kind,
                placement_kinds=(placement_kind,),
                required_model_ids=tuple(_string_list(proposal, "model_instance_ids")),
                source_decision_request_id=None,
                source_decision_result_id=None,
                ruleset_descriptor_hash=None,
                setup_step=None,
                action_kind=_required_string(proposal, "action_phase"),
                source_rule_id=_required_string(proposal, "source_rule_id"),
                context={},
                army_id=_required_string(proposal, "army_id"),
                materialized_models=models,
            )
        if decision_type == "submit_healing_revival_placement":
            _require_exact_keys(
                proposal,
                _HEALING_REVIVAL_REQUEST_KEYS,
                "healing revival placement request",
            )
            _required_matching_string(
                proposal,
                "submission_kind",
                decision_type,
                "placement request decision_type",
            )
            effect = _json_object("healing effect", proposal["effect"])
            target_unit_instance_id = _required_string(effect, "target_unit_instance_id")
            component_unit_instance_id = _required_string(proposal, "component_unit_instance_id")
            phase_start = _json_object("revival_phase_start", proposal["revival_phase_start"])
            _require_exact_keys(
                phase_start,
                _HEALING_REVIVAL_PHASE_START_KEYS,
                "revival phase-start witness",
            )
            for key in _HEALING_REVIVAL_PHASE_START_KEYS - {"battle_round", "model_ids"}:
                _required_string(phase_start, key)
            if _required_int(phase_start, "battle_round") < 1:
                raise UiClientProtocolError("Revival phase-start battle_round must be positive.")
            model_ids = _string_list(phase_start, "model_ids")
            if model_ids != sorted(set(model_ids)):
                raise UiClientProtocolError(
                    "Revival phase-start model_ids must be sorted and unique."
                )
            if phase_start["target_unit_instance_id"] != target_unit_instance_id:
                raise UiClientProtocolError(
                    "Revival phase-start target differs from the healing effect."
                )
            return cls(
                request_id=request_id,
                decision_type=decision_type,
                actor_id=actor_id,
                game_id=None,
                player_id=actor_id,
                unit_instance_id=component_unit_instance_id,
                proposal_kind=proposal_kind,
                placement_kind="return_to_battlefield",
                placement_kinds=("return_to_battlefield",),
                required_model_ids=(_required_string(proposal, "model_instance_id"),),
                source_decision_request_id=_optional_string_value(
                    proposal,
                    "source_selection_request_id",
                ),
                source_decision_result_id=_optional_string_value(
                    proposal,
                    "source_selection_result_id",
                ),
                ruleset_descriptor_hash=None,
                setup_step=None,
                action_kind=None,
                source_rule_id=_required_string(effect, "source_rule_id"),
                context={
                    "target_rules_unit_instance_id": target_unit_instance_id,
                    "step_index": _required_int(proposal, "step_index"),
                    "effect": effect,
                    "revival_phase_start": phase_start,
                },
            )
        if decision_type == "submit_return_on_death_placement":
            _require_exact_keys(
                proposal,
                _RETURN_ON_DEATH_REQUEST_KEYS,
                "return-on-death placement request",
            )
            _required_matching_string(
                proposal,
                "submission_kind",
                decision_type,
                "placement request decision_type",
            )
            _json_object("return-on-death restriction", proposal["restriction"])
            destroyed_model_id = _optional_string_value(
                proposal,
                "destroyed_model_instance_id",
            )
            return cls(
                request_id=request_id,
                decision_type=decision_type,
                actor_id=actor_id,
                game_id=None,
                player_id=actor_id,
                unit_instance_id=_required_string(
                    proposal,
                    "destroyed_unit_instance_id",
                ),
                proposal_kind=proposal_kind,
                placement_kind=_required_string(proposal, "placement_kind"),
                placement_kinds=(_required_string(proposal, "placement_kind"),),
                required_model_ids=() if destroyed_model_id is None else (destroyed_model_id,),
                source_decision_request_id=None,
                source_decision_result_id=None,
                ruleset_descriptor_hash=None,
                setup_step=None,
                action_kind=None,
                source_rule_id=_required_string(proposal, "source_rule_id"),
                context={},
            )
        raise UiClientProtocolError(
            f"Placement request decision_type is unsupported: {decision_type}."
        )


_FLAT_PARAMETERIZED_DECISION_TYPES = frozenset(
    {
        "submit_cult_ambush_marker_placement",
        "submit_healing_revival_placement",
        "submit_catalog_model_materialization_placement",
        "submit_return_on_death_placement",
    }
)


@dataclass(frozen=True, slots=True)
class UiParameterizedProposalRequest:
    """Generic UI view of a parameterized proposal request."""

    request_id: str
    decision_type: str
    actor_id: str
    proposal_kind: str | None
    payload: JsonObject

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _non_empty_string("request_id", self.request_id))
        object.__setattr__(
            self,
            "decision_type",
            _non_empty_string("decision_type", self.decision_type),
        )
        object.__setattr__(self, "actor_id", _non_empty_string("actor_id", self.actor_id))
        object.__setattr__(
            self,
            "proposal_kind",
            _optional_string("proposal_kind", self.proposal_kind),
        )
        object.__setattr__(self, "payload", _json_object("parameterized proposal", self.payload))

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        proposal = _json_object("parameterized proposal payload", payload)
        return cls(
            request_id=_required_string(proposal, "request_id"),
            decision_type=_required_string(proposal, "decision_type"),
            actor_id=_required_string(proposal, "actor_id"),
            proposal_kind=_optional_string_value(proposal, "proposal_kind"),
            payload=proposal,
        )

    @classmethod
    def from_decision_payload(
        cls,
        *,
        payload: JsonValue,
        decision_request_id: str,
        decision_type: str,
        actor_id: str | None,
    ) -> Self:
        decision_payload = _json_object("parameterized decision payload", payload)
        if actor_id is None:
            raise UiClientProtocolError(
                "decision_request.actor_id is required for parameterized proposals."
            )
        is_flat = decision_type in _FLAT_PARAMETERIZED_DECISION_TYPES
        if is_flat:
            if "proposal_request" in decision_payload:
                raise UiClientProtocolError(
                    f"{decision_type} requires a flat parameterized request."
                )
            context = decision_payload
        else:
            if "proposal_request" not in decision_payload:
                raise UiClientProtocolError(f"{decision_type} requires a nested proposal_request.")
            context = _json_object(
                "parameterized proposal request",
                decision_payload["proposal_request"],
            )
        identity = {
            "request_id": decision_request_id,
            "decision_type": decision_type,
            "actor_id": actor_id,
        }
        for key, expected in identity.items():
            if not is_flat and key not in context:
                raise UiClientProtocolError(f"nested parameterized request requires {key}.")
            if key in context and context[key] != expected:
                raise UiClientProtocolError(
                    f"parameterized {key} must match decision_request.{key}."
                )
        return cls.from_payload({**context, **identity})


@dataclass(frozen=True, slots=True)
class UiDecision:
    """Current pending decision as a UI-facing view model."""

    request_id: str
    decision_type: str
    actor_id: str | None
    payload: JsonValue
    options: tuple[UiFiniteOption, ...]
    is_parameterized: bool
    schema_version: str = DECISION_REQUEST_SCHEMA_VERSION
    interaction: UiInteractionDescriptor | None = None
    parameterized_proposal: UiParameterizedProposalRequest | None = None
    movement_proposal: UiMovementProposalRequest | None = None
    placement_proposal: UiPlacementProposalRequest | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _non_empty_string("request_id", self.request_id))
        object.__setattr__(
            self,
            "decision_type",
            _non_empty_string("decision_type", self.decision_type),
        )
        object.__setattr__(self, "actor_id", _optional_string("actor_id", self.actor_id))
        object.__setattr__(self, "payload", validate_json_value(self.payload))
        if type(self.options) is not tuple:
            raise UiClientProtocolError("options must be a tuple.")
        if type(self.is_parameterized) is not bool:
            raise UiClientProtocolError("is_parameterized must be a bool.")
        if self.schema_version not in {
            DECISION_REQUEST_SCHEMA_VERSION,
            ANNOTATED_DECISION_REQUEST_SCHEMA_VERSION,
        }:
            raise UiClientProtocolError("decision schema_version is unsupported.")
        if self.interaction is not None and type(self.interaction) is not UiInteractionDescriptor:
            raise UiClientProtocolError("interaction must be a UiInteractionDescriptor.")
        if (
            self.parameterized_proposal is not None
            and type(self.parameterized_proposal) is not UiParameterizedProposalRequest
        ):
            raise UiClientProtocolError(
                "parameterized_proposal must be a UiParameterizedProposalRequest."
            )
        if (
            self.movement_proposal is not None
            and type(self.movement_proposal) is not UiMovementProposalRequest
        ):
            raise UiClientProtocolError("movement_proposal must be a UiMovementProposalRequest.")
        if (
            self.placement_proposal is not None
            and type(self.placement_proposal) is not UiPlacementProposalRequest
        ):
            raise UiClientProtocolError("placement_proposal must be a UiPlacementProposalRequest.")

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        return cls._from_payload(
            payload,
            expected_schema=DECISION_REQUEST_SCHEMA_VERSION,
            parse_parameterized_proposal=True,
        )

    @classmethod
    def from_annotated_payload(cls, payload: object) -> Self:
        """Parse a nested or conformance request with its annotated discriminator."""

        return cls._from_payload(
            payload,
            expected_schema=ANNOTATED_DECISION_REQUEST_SCHEMA_VERSION,
            parse_parameterized_proposal=False,
        )

    @classmethod
    def _from_payload(
        cls,
        payload: object,
        *,
        expected_schema: str,
        parse_parameterized_proposal: bool,
    ) -> Self:
        decision = _json_object("decision payload", payload)
        _require_exact_keys(
            decision,
            {
                "schema_version",
                "request_id",
                "decision_type",
                "actor_id",
                "payload",
                "options",
                "is_parameterized",
                "interaction",
            },
            "decision request",
        )
        _require_discriminator(
            decision,
            "schema_version",
            expected_schema,
            "decision request",
        )
        raw_options = _json_list("decision options", decision["options"])
        options = tuple(UiFiniteOption.from_payload(option) for option in raw_options)
        is_parameterized = _required_bool(decision, "is_parameterized")
        decision_payload = decision["payload"]
        request_id = _required_string(decision, "request_id")
        decision_type = _required_string(decision, "decision_type")
        actor_id = _optional_string_value(decision, "actor_id")
        raw_interaction = decision["interaction"]
        interaction = (
            None
            if raw_interaction is None
            else UiInteractionDescriptor.from_payload(raw_interaction)
        )
        if interaction is None:
            if actor_id is not None or decision_type != "hidden_decision":
                raise UiClientProtocolError(
                    "Only a hidden decision may omit its interaction descriptor."
                )
        else:
            expected_submission_kind = "parameterized" if is_parameterized else "finite"
            if interaction.submission_kind != expected_submission_kind:
                raise UiClientProtocolError(
                    "interaction submission_kind must match is_parameterized."
                )
            option_ids = tuple(option.option_id for option in options)
            if interaction.constraints.candidate_option_ids != option_ids:
                raise UiClientProtocolError(
                    "interaction candidate_option_ids must match decision options in order."
                )
        parameterized_proposal = (
            UiParameterizedProposalRequest.from_decision_payload(
                payload=decision_payload,
                decision_request_id=request_id,
                decision_type=decision_type,
                actor_id=actor_id,
            )
            if is_parameterized and parse_parameterized_proposal
            else None
        )
        if (
            parameterized_proposal is not None
            and interaction is not None
            and parameterized_proposal.proposal_kind is not None
            and parameterized_proposal.proposal_kind != interaction.proposal_kind
        ):
            raise UiClientProtocolError(
                "parameterized proposal_kind must match the interaction descriptor."
            )
        return cls(
            request_id=request_id,
            decision_type=decision_type,
            actor_id=actor_id,
            payload=decision_payload,
            options=options,
            is_parameterized=is_parameterized,
            schema_version=expected_schema,
            interaction=interaction,
            parameterized_proposal=parameterized_proposal,
            movement_proposal=_movement_proposal_from_parameterized(
                parameterized_proposal,
                interaction,
            ),
            placement_proposal=_placement_proposal_from_parameterized(
                parameterized_proposal,
                interaction,
            ),
        )


@dataclass(frozen=True, slots=True)
class UiInvalidDiagnostic:
    """Invalid status diagnostic safe to show in UI state."""

    violation_code: str
    message: str
    field: str | None = None
    proposal_request_id: str | None = None
    proposal_kind: str | None = None
    status: str = "invalid"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "violation_code",
            _non_empty_string("violation_code", self.violation_code),
        )
        object.__setattr__(self, "message", _non_empty_string("message", self.message))
        object.__setattr__(self, "field", _optional_string("field", self.field))
        object.__setattr__(
            self,
            "proposal_request_id",
            _optional_string("proposal_request_id", self.proposal_request_id),
        )
        object.__setattr__(
            self,
            "proposal_kind",
            _optional_string("proposal_kind", self.proposal_kind),
        )
        object.__setattr__(self, "status", _non_empty_string("status", self.status))


@dataclass(frozen=True, slots=True)
class UiClientStatus:
    """Lifecycle status represented at the UI boundary."""

    stage: str
    status_kind: str
    decision: UiDecision | None = None
    message: str | None = None
    payload: JsonValue = None
    invalid_diagnostics: tuple[UiInvalidDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage", _non_empty_string("stage", self.stage))
        object.__setattr__(
            self,
            "status_kind",
            _non_empty_string("status_kind", self.status_kind),
        )
        if self.decision is not None and type(self.decision) is not UiDecision:
            raise UiClientProtocolError("decision must be a UiDecision.")
        object.__setattr__(self, "message", _optional_string("message", self.message))
        object.__setattr__(self, "payload", validate_json_value(self.payload))
        if type(self.invalid_diagnostics) is not tuple:
            raise UiClientProtocolError("invalid_diagnostics must be a tuple.")

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        status_payload = _json_object("status payload", payload)
        raw_decision = status_payload["decision_request"]
        decision = None if raw_decision is None else UiDecision.from_payload(raw_decision)
        status_kind = _required_string(status_payload, "status_kind")
        message = _optional_string_value(status_payload, "message")
        status_body = status_payload["payload"]
        return cls(
            stage=_required_string(status_payload, "stage"),
            status_kind=status_kind,
            decision=decision,
            message=message,
            payload=status_body,
            invalid_diagnostics=invalid_diagnostics_from_status(
                status_kind=status_kind,
                message=message,
                payload=status_body,
            ),
        )

    @classmethod
    def invalid(
        cls,
        *,
        stage: str,
        violation_code: str,
        message: str,
        field: str | None = None,
        payload: JsonObject | None = None,
        decision: UiDecision | None = None,
    ) -> Self:
        diagnostic = UiInvalidDiagnostic(
            violation_code=violation_code,
            message=message,
            field=field,
        )
        body: JsonObject = (
            {
                "invalid_reason": violation_code,
                "field": field,
            }
            if payload is None
            else payload
        )
        return cls(
            stage=stage,
            status_kind="invalid",
            decision=decision,
            message=message,
            payload=body,
            invalid_diagnostics=(diagnostic,),
        )


@dataclass(frozen=True, slots=True)
class UiGameView:
    """Viewer-scoped game projection consumed by render, input, and HUD code."""

    viewer_player_id: str
    game_id: str
    stage: str
    battle_round: int
    active_player_id: str | None
    current_setup_step: str | None
    current_battle_phase: str | None
    player_ids: tuple[str, ...]
    battlefield_state: JsonValue
    mission_setup: JsonValue
    public_secondary_mission_choices: tuple[JsonValue, ...]
    public_secondary_mission_card_states: tuple[JsonValue, ...]
    public_command_point_ledgers: tuple[JsonValue, ...]
    public_victory_point_ledgers: tuple[JsonValue, ...]
    public_stratagem_use_records: tuple[JsonValue, ...]
    pending_decision: UiDecision | None
    pending_proposal: UiParameterizedProposalRequest | None
    unit_display_by_id: JsonObject = field(default_factory=_empty_json_object)
    model_display_by_id: JsonObject = field(default_factory=_empty_json_object)
    projection_schema: str = "ui-fixture-v1"
    projection_state_hash: str = "fixture-projection"
    viewer_role: str = "player"
    rules_catalog: UiRulesCatalogReference | None = None
    battlefield_view: UiBattlefieldProjection | None = None
    primary_rules_unit_turn_start_snapshots: tuple[JsonValue, ...] = ()
    primary_mission_progress_state: JsonValue = None
    nested_interaction_requests: tuple[UiDecision, ...] = ()

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        view = _json_object("game view payload", payload)
        required_keys = {
            "projection_schema",
            "projection_state_hash",
            "rules_catalog",
            "viewer_role",
            "viewer_player_id",
            "game_id",
            "stage",
            "battle_round",
            "active_player_id",
            "current_setup_step",
            "current_battle_phase",
            "player_ids",
            "battlefield_state",
            "mission_setup",
            "public_secondary_mission_choices",
            "public_secondary_mission_card_states",
            "primary_rules_unit_turn_start_snapshots",
            "primary_mission_progress_state",
            "public_command_point_ledgers",
            "public_victory_point_ledgers",
            "public_stratagem_use_records",
            "unit_display_by_id",
            "model_display_by_id",
            "pending_decision",
            "pending_proposal",
            "nested_interaction_requests",
        }
        _require_keys(
            view,
            required=required_keys,
            allowed=required_keys | {"battlefield_view"},
            field_name="game view",
        )
        _require_discriminator(
            view,
            "projection_schema",
            GAME_VIEW_SCHEMA_VERSION,
            "game view",
        )
        pending_decision_payload = view["pending_decision"]
        pending_proposal_payload = view["pending_proposal"]
        pending_decision = (
            None
            if pending_decision_payload is None
            else UiDecision.from_payload(pending_decision_payload)
        )
        pending_proposal = (
            None
            if pending_proposal_payload is None
            else UiParameterizedProposalRequest.from_payload(pending_proposal_payload)
        )
        if pending_decision is None and pending_proposal is not None:
            raise UiClientProtocolError("pending_proposal requires pending_decision.")
        if pending_decision is not None:
            expected_proposal = pending_decision.parameterized_proposal
            if pending_proposal != expected_proposal:
                raise UiClientProtocolError(
                    "pending_proposal must exactly match pending_decision proposal_request."
                )
        raw_battlefield_view = view.get("battlefield_view")
        return cls(
            viewer_player_id=_required_string(view, "viewer_player_id"),
            game_id=_required_string(view, "game_id"),
            stage=_required_string(view, "stage"),
            battle_round=_required_int(view, "battle_round"),
            active_player_id=_optional_string_value(view, "active_player_id"),
            current_setup_step=_optional_string_value(view, "current_setup_step"),
            current_battle_phase=_optional_string_value(view, "current_battle_phase"),
            player_ids=tuple(_string_list(view, "player_ids")),
            battlefield_state=view["battlefield_state"],
            mission_setup=view["mission_setup"],
            public_secondary_mission_choices=tuple(
                _json_list(
                    "public_secondary_mission_choices",
                    view["public_secondary_mission_choices"],
                )
            ),
            public_secondary_mission_card_states=tuple(
                _json_list(
                    "public_secondary_mission_card_states",
                    view["public_secondary_mission_card_states"],
                )
            ),
            public_command_point_ledgers=tuple(
                _json_list("public_command_point_ledgers", view["public_command_point_ledgers"])
            ),
            public_victory_point_ledgers=tuple(
                _json_list("public_victory_point_ledgers", view["public_victory_point_ledgers"])
            ),
            public_stratagem_use_records=tuple(
                _json_list("public_stratagem_use_records", view["public_stratagem_use_records"])
            ),
            pending_decision=pending_decision,
            pending_proposal=pending_proposal,
            unit_display_by_id=_validated_unit_displays(view),
            model_display_by_id=_validated_model_displays(view),
            projection_schema=GAME_VIEW_SCHEMA_VERSION,
            projection_state_hash=_required_string(view, "projection_state_hash"),
            viewer_role=_required_viewer_role(view),
            rules_catalog=UiRulesCatalogReference.from_payload(view["rules_catalog"]),
            battlefield_view=(
                None
                if raw_battlefield_view is None
                else UiBattlefieldProjection.from_payload(raw_battlefield_view)
            ),
            primary_rules_unit_turn_start_snapshots=tuple(
                _json_list(
                    "primary_rules_unit_turn_start_snapshots",
                    view["primary_rules_unit_turn_start_snapshots"],
                )
            ),
            primary_mission_progress_state=validate_json_value(
                view["primary_mission_progress_state"]
            ),
            nested_interaction_requests=tuple(
                UiDecision.from_annotated_payload(item)
                for item in _json_list(
                    "nested_interaction_requests",
                    view["nested_interaction_requests"],
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class UiEventDelta:
    """Viewer-scoped event-stream delta."""

    viewer_player_id: str
    cursor: int
    next_cursor: int
    events: tuple[JsonObject, ...]
    schema_version: str = LOCAL_EVENT_DELTA_SCHEMA_VERSION

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        event_payload = _json_object("event delta payload", payload)
        _require_exact_keys(
            event_payload,
            {"schema_version", "viewer_player_id", "cursor", "next_cursor", "events"},
            "local event delta",
        )
        _require_discriminator(
            event_payload,
            "schema_version",
            LOCAL_EVENT_DELTA_SCHEMA_VERSION,
            "local event delta",
        )
        return cls(
            viewer_player_id=_required_string(event_payload, "viewer_player_id"),
            cursor=_required_int(event_payload, "cursor"),
            next_cursor=_required_int(event_payload, "next_cursor"),
            events=tuple(
                _json_object("event payload", event)
                for event in _json_list("events", event_payload["events"])
            ),
            schema_version=LOCAL_EVENT_DELTA_SCHEMA_VERSION,
        )


@dataclass(frozen=True, slots=True)
class UiLifecycleStatusEnvelope:
    """Strict external lifecycle status envelope for future transports."""

    schema_version: str
    game_id: str
    stage: str
    status_kind: str
    pending_request_id: str | None
    decision_type: str | None
    actor_id: str | None
    message: str | None
    payload: JsonValue

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        envelope = _json_object("lifecycle status envelope", payload)
        _require_exact_keys(
            envelope,
            {"schema_version", "game_id", "status"},
            "lifecycle status envelope",
        )
        _require_discriminator(
            envelope,
            "schema_version",
            LIFECYCLE_STATUS_SCHEMA_VERSION,
            "lifecycle status envelope",
        )
        status = _json_object("lifecycle status", envelope["status"])
        _require_exact_keys(
            status,
            {
                "stage",
                "status_kind",
                "message",
                "payload",
                "pending_request_id",
                "decision_type",
                "actor_id",
            },
            "lifecycle status",
        )
        return cls(
            schema_version=LIFECYCLE_STATUS_SCHEMA_VERSION,
            game_id=_required_string(envelope, "game_id"),
            stage=_required_string(status, "stage"),
            status_kind=_required_string(status, "status_kind"),
            pending_request_id=_optional_string_value(status, "pending_request_id"),
            decision_type=_optional_string_value(status, "decision_type"),
            actor_id=_optional_string_value(status, "actor_id"),
            message=_optional_string_value(status, "message"),
            payload=validate_json_value(status["payload"]),
        )


@dataclass(frozen=True, slots=True)
class UiNetworkEventDelta:
    """Opaque-cursor event delta used by a future network client."""

    schema_version: str
    session_id: str
    game_id: str
    visibility_role: str
    from_revision: int
    to_revision: int
    projection_state_hash: str
    supplied_cursor: str | None
    next_cursor: str
    has_more: bool
    resync_required: bool
    resync_reason: str | None
    command_id: str | None
    retention_limit: int
    revision_retention_limit: int
    events: tuple[JsonObject, ...]

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        value = _json_object("network event delta", payload)
        keys = {
            "schema_version",
            "session_id",
            "game_id",
            "visibility_role",
            "from_revision",
            "to_revision",
            "projection_state_hash",
            "supplied_cursor",
            "next_cursor",
            "has_more",
            "resync_required",
            "resync_reason",
            "command_id",
            "retention_limit",
            "revision_retention_limit",
            "events",
        }
        _require_exact_keys(value, keys, "network event delta")
        _require_discriminator(
            value,
            "schema_version",
            NETWORK_EVENT_DELTA_SCHEMA_VERSION,
            "network event delta",
        )
        return cls(
            schema_version=NETWORK_EVENT_DELTA_SCHEMA_VERSION,
            session_id=_required_string(value, "session_id"),
            game_id=_required_string(value, "game_id"),
            visibility_role=_required_string(value, "visibility_role"),
            from_revision=_required_int(value, "from_revision"),
            to_revision=_required_int(value, "to_revision"),
            projection_state_hash=_required_string(value, "projection_state_hash"),
            supplied_cursor=_optional_string_value(value, "supplied_cursor"),
            next_cursor=_required_string(value, "next_cursor"),
            has_more=_required_bool(value, "has_more"),
            resync_required=_required_bool(value, "resync_required"),
            resync_reason=_optional_string_value(value, "resync_reason"),
            command_id=_optional_string_value(value, "command_id"),
            retention_limit=_required_int(value, "retention_limit"),
            revision_retention_limit=_required_int(value, "revision_retention_limit"),
            events=tuple(
                _json_object("network event", event)
                for event in _json_list("events", value["events"])
            ),
        )


def invalid_diagnostics_from_status(
    *,
    status_kind: str,
    message: str | None,
    payload: JsonValue,
) -> tuple[UiInvalidDiagnostic, ...]:
    """Convert lifecycle invalid payloads into UI diagnostics."""

    if status_kind != "invalid":
        return ()
    if payload is None:
        if message is None:
            return (_malformed_invalid_status_diagnostic("did not include diagnostics"),)
        return (
            UiInvalidDiagnostic(
                violation_code="invalid_status",
                message=message,
            ),
        )
    if type(payload) is not dict:
        return (_malformed_invalid_status_diagnostic("payload must be an object"),)
    body = payload
    proposal_validation = body.get("proposal_validation")
    if proposal_validation is not None:
        validation = _json_object("proposal validation", proposal_validation)
        proposal_request_id = _required_string(validation, "proposal_request_id")
        proposal_kind = _required_string(validation, "proposal_kind")
        status = _required_string(validation, "status")
        return tuple(
            _invalid_diagnostic_from_violation(
                violation=violation,
                proposal_request_id=proposal_request_id,
                proposal_kind=proposal_kind,
                status=status,
            )
            for violation in _json_list("proposal validation violations", validation["violations"])
        )
    resolution = body.get("resolution")
    if resolution is not None:
        return _invalid_diagnostics_from_resolution(body=body, resolution=resolution)
    if "violations" in body:
        violations = _json_list("invalid status violations", body["violations"])
        if not violations:
            return (_malformed_invalid_status_diagnostic("has no violations"),)
        request_id = _optional_string_value(body, "request_id")
        top_level_kind = _optional_string_value(body, "proposal_kind") or _optional_string_value(
            body, "placement_kind"
        )
        return tuple(
            _invalid_diagnostic_from_top_level_violation(
                violation=violation,
                proposal_request_id=request_id,
                proposal_kind=top_level_kind,
            )
            for violation in violations
        )
    invalid_reason = body.get("invalid_reason")
    field = body.get("field")
    if invalid_reason is not None:
        return (
            UiInvalidDiagnostic(
                violation_code=_non_empty_string("invalid_reason", invalid_reason),
                message=message or _non_empty_string("invalid_reason", invalid_reason),
                field=_optional_string("field", field),
            ),
        )
    if message is None:
        return (_malformed_invalid_status_diagnostic("payload is missing diagnostics"),)
    return (
        UiInvalidDiagnostic(
            violation_code="invalid_status",
            message=message,
        ),
    )


def _invalid_diagnostics_from_resolution(
    *,
    body: dict[str, JsonValue],
    resolution: JsonValue,
) -> tuple[UiInvalidDiagnostic, ...]:
    resolution_payload = _json_object("proposal resolution", resolution)
    proposal = _json_object("proposal resolution proposal", resolution_payload["proposal"])
    proposal_request_id = (
        _optional_string_value(proposal, "proposal_request_id")
        or _optional_string_value(proposal, "request_id")
        or _optional_string_value(body, "request_id")
    )
    if proposal_request_id is None:
        raise UiClientProtocolError("proposal resolution must include proposal_request_id.")
    proposal_kind = _optional_string_value(proposal, "proposal_kind") or _optional_string_value(
        body,
        "proposal_kind",
    )
    if proposal_kind is None:
        raise UiClientProtocolError("proposal resolution must include proposal_kind.")
    status = _optional_string_value(resolution_payload, "status") or "invalid"
    return tuple(
        _invalid_diagnostic_from_violation(
            violation=violation,
            proposal_request_id=proposal_request_id,
            proposal_kind=proposal_kind,
            status=status,
        )
        for violation in _json_list(
            "proposal resolution violations",
            resolution_payload["violations"],
        )
    )


def _invalid_diagnostic_from_top_level_violation(
    *,
    violation: JsonValue,
    proposal_request_id: str | None,
    proposal_kind: str | None,
) -> UiInvalidDiagnostic:
    payload = _json_object("invalid status violation", violation)
    return UiInvalidDiagnostic(
        violation_code=_required_string(payload, "violation_code"),
        message=_required_string(payload, "message"),
        field=_optional_string_value(payload, "field"),
        proposal_request_id=proposal_request_id,
        proposal_kind=proposal_kind,
        status="invalid",
    )


def _malformed_invalid_status_diagnostic(reason: str) -> UiInvalidDiagnostic:
    return UiInvalidDiagnostic(
        violation_code="malformed_invalid_status_payload",
        message=f"Invalid lifecycle status {reason}.",
        field="payload",
    )


def validate_json_value(value: object) -> JsonValue:
    """Validate that a value is deterministic JSON-safe data."""

    if value is None:
        return None
    if type(value) is bool:
        return value
    if type(value) is int:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise UiClientProtocolError("JSON float values must be finite.")
        return value
    if type(value) is str:
        return value
    if type(value) is list:
        return [validate_json_value(item) for item in cast(list[object], value)]
    if type(value) is dict:
        return {
            _non_empty_string("JSON object key", key): validate_json_value(item)
            for key, item in cast(dict[object, object], value).items()
        }
    raise UiClientProtocolError("Value must be JSON-safe.")


def _invalid_diagnostic_from_violation(
    *,
    violation: JsonValue,
    proposal_request_id: str,
    proposal_kind: str,
    status: str,
) -> UiInvalidDiagnostic:
    violation_payload = _json_object("proposal violation", violation)
    return UiInvalidDiagnostic(
        violation_code=_required_string(violation_payload, "violation_code"),
        message=_required_string(violation_payload, "message"),
        field=_optional_string_value(violation_payload, "field"),
        proposal_request_id=proposal_request_id,
        proposal_kind=proposal_kind,
        status=status,
    )


def _movement_proposal_from_parameterized(
    proposal: UiParameterizedProposalRequest | None,
    interaction: UiInteractionDescriptor | None,
) -> UiMovementProposalRequest | None:
    if proposal is None or interaction is None or interaction.interaction_kind != "path_editor":
        return None
    return UiMovementProposalRequest.from_payload(proposal.payload)


def _placement_proposal_from_parameterized(
    proposal: UiParameterizedProposalRequest | None,
    interaction: UiInteractionDescriptor | None,
) -> UiPlacementProposalRequest | None:
    if (
        proposal is None
        or interaction is None
        or interaction.interaction_kind
        not in {
            "battlefield_point_placement",
            "model_pose_placement",
            "multi_model_placement",
        }
    ):
        return None
    return UiPlacementProposalRequest.from_payload(
        proposal.payload,
        interaction=interaction,
    )


_DEPLOYMENT_PLACEMENT_REQUEST_KEYS = {
    "request_id",
    "decision_type",
    "actor_id",
    "game_id",
    "setup_step",
    "player_id",
    "unit_instance_id",
    "component_unit_instance_ids",
    "model_instance_ids",
    "placement_kind",
    "deployment_zone_ids",
    "legal_deployment_zones",
    "mission_pack_id",
    "source_id",
    "deployment_map_id",
    "terrain_layout_id",
    "mission_setup",
    "ruleset_descriptor_hash",
    "source_decision_request_id",
    "source_decision_result_id",
    "proposal_kind",
    "context",
}

_CULT_AMBUSH_MARKER_REQUEST_KEYS = {
    "request_id",
    "decision_type",
    "actor_id",
    "source_rule_id",
    "marker_id",
    "player_id",
    "replacement_unit_instance_id",
    "destroyed_unit_instance_id",
    "marker_diameter_inches",
    "required_enemy_horizontal_distance_inches",
    "source_decision_request_id",
    "source_decision_result_id",
}

_PREBATTLE_PROPOSAL_REQUEST_KEYS = {
    "request_id",
    "decision_type",
    "actor_id",
    "game_id",
    "setup_step",
    "player_id",
    "unit_instance_id",
    "component_unit_instance_ids",
    "model_instance_ids",
    "proposal_kind",
    "action_kind",
    "source_rule_id",
    "placement_kind",
    "scout_distance_inches",
    "deployment_zone_ids",
    "legal_deployment_zones",
    "mission_setup",
    "ruleset_descriptor_hash",
    "source_decision_request_id",
    "source_decision_result_id",
    "context",
}

_MODEL_MATERIALIZATION_REQUEST_KEYS = {
    "request_id",
    "decision_type",
    "actor_id",
    "submission_kind",
    "proposal_kind",
    "placement_kind",
    "attack_sequence_id",
    "source_phase",
    "action_phase",
    "parent_battle_phase",
    "roll_event_id",
    "catalog_record_id",
    "clause_id",
    "source_rule_id",
    "materialization_descriptor_id",
    "source_unit_instance_id",
    "army_id",
    "player_id",
    "models",
    "model_instance_ids",
}

_HEALING_REVIVAL_REQUEST_KEYS = {
    "request_id",
    "decision_type",
    "actor_id",
    "submission_kind",
    "proposal_kind",
    "effect",
    "revival_phase_start",
    "step_index",
    "model_instance_id",
    "component_unit_instance_id",
    "source_selection_request_id",
    "source_selection_result_id",
}

_HEALING_REVIVAL_PHASE_START_KEYS = {
    "rule_source_id",
    "source_package_hash",
    "game_id",
    "battle_round",
    "turn_owner_player_id",
    "phase",
    "phase_start_event_id",
    "phase_start_window_id",
    "target_unit_instance_id",
    "model_ids",
}

_RETURN_ON_DEATH_REQUEST_KEYS = {
    "request_id",
    "decision_type",
    "actor_id",
    "submission_kind",
    "pending_id",
    "source_rule_id",
    "destroyed_unit_instance_id",
    "destroyed_model_instance_id",
    "placement_anchor",
    "placement_preference",
    "placement_kind",
    "restriction",
}


def _descriptor_proposal_kind(
    *,
    proposal: JsonObject,
    interaction: UiInteractionDescriptor,
) -> str:
    descriptor_kind = interaction.proposal_kind
    if descriptor_kind is None:
        raise UiClientProtocolError("Placement interaction descriptor must publish proposal_kind.")
    payload_kind = _optional_string_value(proposal, "proposal_kind")
    if payload_kind is not None and payload_kind != descriptor_kind:
        raise UiClientProtocolError("Placement proposal_kind must match interaction.proposal_kind.")
    return descriptor_kind


def _require_exact_keys(
    payload: JsonObject,
    expected: set[str],
    field_name: str,
) -> None:
    _require_keys(payload, required=expected, allowed=expected, field_name=field_name)


def _require_keys(
    payload: JsonObject,
    *,
    required: set[str],
    allowed: set[str],
    field_name: str,
) -> None:
    missing = sorted(required - set(payload))
    extra = sorted(set(payload) - allowed)
    if missing:
        raise UiClientProtocolError(f"{field_name} is missing required field: {missing[0]}.")
    if extra:
        raise UiClientProtocolError(f"{field_name} contains unsupported field: {extra[0]}.")


def _require_discriminator(
    payload: JsonObject,
    key: str,
    expected: str,
    field_name: str,
) -> None:
    actual = _required_string(payload, key)
    if actual != expected:
        raise UiClientProtocolError(
            f"{field_name} {key} mismatch: expected {expected}, got {actual}."
        )


def _known_interaction_kind(payload: JsonObject, key: str) -> str:
    value = _required_string(payload, key)
    if value not in _INTERACTION_KINDS:
        raise UiClientProtocolError(f"Unknown interaction_kind: {value}.")
    return value


def _require_unique(values: tuple[str, ...], field_name: str) -> None:
    if len(values) != len(set(values)):
        raise UiClientProtocolError(f"{field_name} must contain unique values.")


def _nullable_non_negative_int(payload: JsonObject, key: str) -> int | None:
    value = _required_value(payload, key)
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise UiClientProtocolError(f"{key} must be a non-negative integer or null.")
    return value


def _nullable_non_negative_number(payload: JsonObject, key: str) -> float | None:
    value = _required_value(payload, key)
    if value is None:
        return None
    number = _required_number(payload, key)
    if number < 0.0:
        raise UiClientProtocolError(f"{key} must be non-negative or null.")
    return number


def _nullable_bool(payload: JsonObject, key: str) -> bool | None:
    value = _required_value(payload, key)
    if value is None:
        return None
    if type(value) is not bool:
        raise UiClientProtocolError(f"{key} must be a bool or null.")
    return value


def _required_viewer_role(payload: JsonObject) -> str:
    value = _required_string(payload, "viewer_role")
    if value not in {"player", "coach", "delayed_spectator", "administrator"}:
        raise UiClientProtocolError(f"Unsupported viewer_role: {value}.")
    return value


def _json_object(field_name: str, value: object) -> JsonObject:
    json_value = validate_json_value(value)
    if type(json_value) is not dict:
        raise UiClientProtocolError(f"{field_name} must be a JSON object.")
    return json_value


def _json_list(field_name: str, value: object) -> list[JsonValue]:
    json_value = validate_json_value(value)
    if type(json_value) is not list:
        raise UiClientProtocolError(f"{field_name} must be a JSON array.")
    return json_value


def _required_string(payload: JsonObject, key: str) -> str:
    return _non_empty_string(key, _required_value(payload, key))


def _optional_string_value(payload: JsonObject, key: str) -> str | None:
    return _optional_string(key, payload.get(key))


def _validated_unit_displays(view: JsonObject) -> JsonObject:
    displays = _json_object("unit_display_by_id", view["unit_display_by_id"])
    for unit_id, value in displays.items():
        display = _json_object(f"unit_display_by_id.{unit_id}", value)
        _required_matching_string(display, "unit_instance_id", unit_id, "unit display key")
        _string_list(display, "keywords")
        _string_list(display, "faction_keywords")
        _string_list(display, "model_instance_ids")
    return displays


def _validated_model_displays(view: JsonObject) -> JsonObject:
    displays = _json_object("model_display_by_id", view["model_display_by_id"])
    for model_id, value in displays.items():
        display = _json_object(f"model_display_by_id.{model_id}", value)
        _required_matching_string(display, "model_instance_id", model_id, "model display key")
        _required_string(display, "unit_instance_id")
        for key in ("keywords", "faction_keywords", "keyword_source_ids"):
            _string_list(display, key)
        for category in ("base_characteristics", "current_characteristics"):
            characteristics = _json_object(category, _required_value(display, category))
            for label, raw_characteristic in characteristics.items():
                characteristic = _json_object(f"{category}.{label}", raw_characteristic)
                _validate_characteristic_display(characteristic, label=label)
    return displays


def _validate_characteristic_display(characteristic: JsonObject, *, label: str) -> None:
    required = {
        "characteristic",
        "label",
        "value_kind",
        "raw",
        "base",
        "final",
        "display_value",
        "applied_modifier_ids",
        "redaction",
    }
    _require_keys(
        characteristic,
        required=required,
        allowed=required | {"random_expression"},
        field_name=f"characteristic {label}",
    )
    _required_matching_string(characteristic, "label", label, "characteristic key")
    _required_string(characteristic, "characteristic")
    value_kind = _required_string(characteristic, "value_kind")
    if value_kind not in {
        "random",
        "numeric",
        "source_dash",
        "replacement_dash",
        "replacement_zero",
        "replacement_star",
        "unknown",
    }:
        raise UiClientProtocolError(f"Unsupported characteristic value_kind: {value_kind}.")
    for key in ("raw", "base", "final"):
        value = characteristic[key]
        if value is not None and type(value) is not int:
            raise UiClientProtocolError(f"characteristic {label}.{key} must be integer or null.")
    display_value = characteristic["display_value"]
    if display_value is not None and type(display_value) is not str:
        raise UiClientProtocolError(f"characteristic {label}.display_value must be text or null.")
    _string_list(characteristic, "applied_modifier_ids")
    redaction = _json_object("characteristic redaction", characteristic["redaction"])
    _require_exact_keys(redaction, {"hidden", "reason"}, "characteristic redaction")
    _required_bool(redaction, "hidden")
    _optional_string_value(redaction, "reason")
    if value_kind == "random":
        if display_value is None or not display_value:
            raise UiClientProtocolError("random characteristic requires display_value.")
        expression = _json_object(
            "random_expression", _required_value(characteristic, "random_expression")
        )
        _require_exact_keys(expression, {"quantity", "sides", "modifier"}, "random_expression")
        if _required_int(expression, "quantity") < 1 or _required_int(expression, "sides") < 2:
            raise UiClientProtocolError("random_expression requires positive dice dimensions.")
        _required_int(expression, "modifier")
    elif "random_expression" in characteristic:
        raise UiClientProtocolError("Only random characteristics may contain random_expression.")


def _required_matching_string(
    payload: JsonObject,
    key: str,
    expected: str,
    expected_field_name: str,
) -> str:
    value = _required_string(payload, key)
    if value != expected:
        raise UiClientProtocolError(f"{key} must match {expected_field_name}.")
    return value


def _required_int(payload: JsonObject, key: str) -> int:
    value = _required_value(payload, key)
    if type(value) is not int:
        raise UiClientProtocolError(f"{key} must be an integer.")
    return value


def _required_number(payload: JsonObject, key: str) -> float:
    value = _required_value(payload, key)
    if type(value) is not int and type(value) is not float:
        raise UiClientProtocolError(f"{key} must be a number.")
    float_value = float(value)
    if not math.isfinite(float_value):
        raise UiClientProtocolError(f"{key} must be finite.")
    return float_value


def _required_bool(payload: JsonObject, key: str) -> bool:
    value = _required_value(payload, key)
    if type(value) is not bool:
        raise UiClientProtocolError(f"{key} must be a bool.")
    return value


def _required_value(payload: JsonObject, key: str) -> JsonValue:
    if key not in payload:
        raise UiClientProtocolError(f"{key} is required.")
    return payload[key]


def _string_list(payload: JsonObject, key: str) -> list[str]:
    return [_non_empty_string(key, value) for value in _json_list(key, payload[key])]


def _non_empty_string(field_name: str, value: object) -> str:
    if type(value) is not str:
        raise UiClientProtocolError(f"{field_name} must be a string.")
    stripped = value.strip()
    if not stripped:
        raise UiClientProtocolError(f"{field_name} must not be empty.")
    return stripped


def _optional_string(field_name: str, value: object | None) -> str | None:
    if value is None:
        return None
    return _non_empty_string(field_name, value)
