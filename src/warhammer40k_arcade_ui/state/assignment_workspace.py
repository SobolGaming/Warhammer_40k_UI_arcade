"""Generic local assignment workspace for parameterized proposal requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    JsonValue,
    UiDecision,
    UiParameterizedProposalRequest,
    validate_json_value,
)

SHOOTING_DECLARATION_DECISION_TYPE = "submit_shooting_declaration"
MELEE_DECLARATION_DECISION_TYPE = "submit_melee_declaration"
STRATAGEM_TARGET_PROPOSAL_DECISION_TYPE = "submit_stratagem_target_proposal"

SHOOTING_DECLARATION_PROPOSAL_KIND = "shooting_declaration"
MELEE_DECLARATION_PROPOSAL_KIND = "melee_declaration"
STRATAGEM_TARGET_BINDING_PROPOSAL_KIND = "stratagem_target_binding"

ASSIGNMENT_PROPOSAL_KINDS = frozenset(
    (
        SHOOTING_DECLARATION_PROPOSAL_KIND,
        MELEE_DECLARATION_PROPOSAL_KIND,
        STRATAGEM_TARGET_BINDING_PROPOSAL_KIND,
    )
)
ASSIGNMENT_DECISION_TYPES = frozenset(
    (
        SHOOTING_DECLARATION_DECISION_TYPE,
        MELEE_DECLARATION_DECISION_TYPE,
        STRATAGEM_TARGET_PROPOSAL_DECISION_TYPE,
    )
)
DECLINE_STRATAGEM_WINDOW_PAYLOAD: JsonObject = {
    "submission_kind": "decline_stratagem_window",
}


@dataclass(frozen=True, slots=True)
class AssignmentWorkspaceRow:
    """One source-to-target assignment row built from engine-emitted candidate data."""

    row_id: str
    label: str
    source_ref_keys: tuple[str, ...]
    target_ref_keys: tuple[str, ...]
    summary_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssignmentWorkspace:
    """Request-keyed advisory assignment payload preview."""

    request_id: str
    decision_type: str
    actor_id: str
    proposal_kind: str
    rows: tuple[AssignmentWorkspaceRow, ...]
    payload_preview: JsonObject | None
    local_hint_lines: tuple[str, ...]
    diagnostic_lines: tuple[str, ...]
    declinable: bool = False
    decline_payload: JsonObject | None = None
    editable: bool = False

    @property
    def is_ready(self) -> bool:
        """Return whether the workspace has a JSON-safe assignment payload."""

        return self.payload_preview is not None and not self.diagnostic_lines

    @property
    def assigned_ref_keys(self) -> tuple[str, ...]:
        """Return all source refs covered by current rows."""

        return tuple(ref for row in self.rows for ref in row.source_ref_keys)

    @property
    def target_ref_keys(self) -> tuple[str, ...]:
        """Return all target refs covered by current rows."""

        return tuple(ref for row in self.rows for ref in row.target_ref_keys)

    @classmethod
    def start_for_pending(cls, pending_decision: UiDecision | None) -> AssignmentWorkspace | None:
        """Return an assignment workspace for supported parameterized requests."""

        if pending_decision is None or not is_assignment_parameterized_decision(pending_decision):
            return None
        proposal = pending_decision.parameterized_proposal
        if proposal is None:
            return None
        if proposal.proposal_kind == SHOOTING_DECLARATION_PROPOSAL_KIND:
            return _shooting_workspace(pending_decision)
        if proposal.proposal_kind == MELEE_DECLARATION_PROPOSAL_KIND:
            return _melee_workspace(pending_decision)
        if proposal.proposal_kind == STRATAGEM_TARGET_BINDING_PROPOSAL_KIND:
            return _stratagem_workspace(pending_decision)
        return None

    def is_for(self, pending_decision: UiDecision | None) -> bool:
        """Return whether this workspace still represents the pending request."""

        proposal = None if pending_decision is None else pending_decision.parameterized_proposal
        return (
            proposal is not None
            and proposal.request_id == self.request_id
            and proposal.decision_type == self.decision_type
            and proposal.actor_id == self.actor_id
            and proposal.proposal_kind == self.proposal_kind
        )


def is_assignment_parameterized_decision(pending_decision: UiDecision | None) -> bool:
    """Return whether a pending decision is a supported generic assignment request."""

    proposal = None if pending_decision is None else pending_decision.parameterized_proposal
    if proposal is None:
        return False
    return (
        proposal.decision_type in ASSIGNMENT_DECISION_TYPES
        and proposal.proposal_kind in ASSIGNMENT_PROPOSAL_KINDS
    )


def _shooting_workspace(pending_decision: UiDecision) -> AssignmentWorkspace:
    proposal = _required_parameterized_proposal(pending_decision)
    rows: list[AssignmentWorkspaceRow] = []
    declarations: list[JsonValue] = []
    diagnostics: list[str] = []
    available_weapons = _json_object_list(
        proposal.payload.get("available_weapons"),
        key="available_weapons",
        diagnostics=diagnostics,
    )
    target_candidates = _json_object_list(
        proposal.payload.get("target_candidates"),
        key="target_candidates",
        diagnostics=diagnostics,
    )
    visibility_cache_key = _text(proposal.payload.get("visibility_cache_key"))
    if not visibility_cache_key:
        diagnostics.append("Shooting request is missing visibility_cache_key.")
    for weapon in available_weapons:
        model_id = _text(weapon.get("model_instance_id"))
        wargear_id = _text(weapon.get("wargear_id"))
        weapon_profile_id = _text(weapon.get("weapon_profile_id"))
        if not model_id or not wargear_id or not weapon_profile_id:
            diagnostics.append("Shooting weapon candidate is missing model/wargear/profile IDs.")
            continue
        candidate = _first_legal_shooting_target(
            target_candidates=target_candidates,
            model_id=model_id,
            weapon_profile_id=weapon_profile_id,
            attacker_unit_id=_text(proposal.payload.get("unit_instance_id")),
        )
        if candidate is None:
            continue
        target_unit_id = _text(candidate.get("target_unit_instance_id"))
        shooting_type = _first_string(candidate.get("shooting_types"))
        candidate_visibility_key = _text(candidate.get("visibility_cache_key"))
        if not target_unit_id or not shooting_type:
            diagnostics.append("Shooting target candidate is missing target or shooting type.")
            continue
        selected_ability_ids = _selected_weapon_ability_ids(candidate, diagnostics=diagnostics)
        if selected_ability_ids is None:
            continue
        declaration: JsonObject = {
            "attacker_model_instance_id": model_id,
            "wargear_id": wargear_id,
            "weapon_profile_id": weapon_profile_id,
            "target_unit_instance_id": target_unit_id,
            "shooting_type": shooting_type,
        }
        if selected_ability_ids:
            selected_ability_id_values: list[JsonValue] = list(selected_ability_ids)
            declaration["selected_weapon_ability_ids"] = selected_ability_id_values
        _copy_optional_text_field(
            source=weapon,
            target=declaration,
            key="firing_deck_source_unit_instance_id",
        )
        _copy_optional_text_field(
            source=weapon,
            target=declaration,
            key="firing_deck_source_model_instance_id",
        )
        declarations.append(declaration)
        rows.append(
            AssignmentWorkspaceRow(
                row_id=f"shooting:{model_id}:{weapon_profile_id}",
                label=f"{_short(model_id)} -> {_short(target_unit_id)}",
                source_ref_keys=(f"model:{model_id}",),
                target_ref_keys=(f"unit:{target_unit_id}",),
                summary_lines=(
                    f"Weapon profile: {weapon_profile_id}",
                    f"Shooting type: {shooting_type}",
                ),
            )
        )
        if candidate_visibility_key:
            visibility_cache_key = candidate_visibility_key
    if not declarations:
        diagnostics.append("No legal shooting assignments were available from the request.")
    payload = None
    player_id: str | None = None
    battle_round: int | None = None
    unit_instance_id: str | None = None
    source_decision_request_id: str | None = None
    source_decision_result_id: str | None = None
    firing_deck_selection: JsonValue | None = None
    if not diagnostics:
        player_id = _required_text_or_diagnostic(
            proposal.payload,
            "active_player_id",
            diagnostics=diagnostics,
            fallback=proposal.actor_id,
        )
        battle_round = _required_int_or_diagnostic(
            proposal.payload,
            "battle_round",
            diagnostics=diagnostics,
        )
        unit_instance_id = _required_text_or_diagnostic(
            proposal.payload,
            "unit_instance_id",
            diagnostics=diagnostics,
        )
        source_decision_request_id = _required_text_or_diagnostic(
            proposal.payload,
            "source_decision_request_id",
            diagnostics=diagnostics,
        )
        source_decision_result_id = _required_text_or_diagnostic(
            proposal.payload,
            "source_decision_result_id",
            diagnostics=diagnostics,
        )
    if not diagnostics:
        assert player_id is not None
        assert battle_round is not None
        assert unit_instance_id is not None
        assert source_decision_request_id is not None
        assert source_decision_result_id is not None
        firing_deck_selection = _firing_deck_selection_preview(
            request_payload=proposal.payload,
            declarations=declarations,
            diagnostics=diagnostics,
        )
    if not diagnostics:
        assert player_id is not None
        assert battle_round is not None
        assert unit_instance_id is not None
        assert source_decision_request_id is not None
        assert source_decision_result_id is not None
        payload = _validate_json_object(
            {
                "proposal_request_id": proposal.request_id,
                "proposal_kind": SHOOTING_DECLARATION_PROPOSAL_KIND,
                "player_id": player_id,
                "battle_round": battle_round,
                "unit_instance_id": unit_instance_id,
                "source_decision_request_id": source_decision_request_id,
                "source_decision_result_id": source_decision_result_id,
                "declarations": declarations,
                "firing_deck_selection": firing_deck_selection,
                "visibility_cache_key": visibility_cache_key,
            }
        )
    return AssignmentWorkspace(
        request_id=proposal.request_id,
        decision_type=proposal.decision_type,
        actor_id=proposal.actor_id,
        proposal_kind=SHOOTING_DECLARATION_PROPOSAL_KIND,
        rows=tuple(rows),
        payload_preview=payload,
        local_hint_lines=(
            "Shooting declaration is seeded from engine-emitted legal target candidates.",
            "Split-fire editing is a follow-on interaction; submit only after review.",
        ),
        diagnostic_lines=tuple(diagnostics),
    )


def _melee_workspace(pending_decision: UiDecision) -> AssignmentWorkspace:
    proposal = _required_parameterized_proposal(pending_decision)
    rows: list[AssignmentWorkspaceRow] = []
    declarations: list[JsonValue] = []
    diagnostics: list[str] = []
    primary_model_ids: set[str] = set()
    available_weapons = _json_object_list(
        proposal.payload.get("available_weapons"),
        key="available_weapons",
        diagnostics=diagnostics,
    )
    for weapon in available_weapons:
        model_id = _text(weapon.get("model_instance_id"))
        wargear_id = _text(weapon.get("wargear_id"))
        weapon_profile_id = _text(weapon.get("weapon_profile_id"))
        if not model_id or not wargear_id or not weapon_profile_id:
            diagnostics.append("Melee weapon candidate is missing model/wargear/profile IDs.")
            continue
        if model_id in primary_model_ids or weapon.get("is_extra_attacks") is True:
            continue
        target_id = _first_string(weapon.get("engaged_target_unit_instance_ids"))
        if not target_id:
            continue
        primary_model_ids.add(model_id)
        target_allocations: list[JsonValue] = [
            {
                "target_unit_instance_id": target_id,
            }
        ]
        declarations.append(
            {
                "attacker_model_instance_id": model_id,
                "wargear_id": wargear_id,
                "weapon_profile_id": weapon_profile_id,
                "target_allocations": target_allocations,
            }
        )
        rows.append(
            AssignmentWorkspaceRow(
                row_id=f"melee:{model_id}:{weapon_profile_id}",
                label=f"{_short(model_id)} -> {_short(target_id)}",
                source_ref_keys=(f"model:{model_id}",),
                target_ref_keys=(f"unit:{target_id}",),
                summary_lines=(
                    f"Primary melee profile: {weapon_profile_id}",
                    "Single-target allocation uses full attack count.",
                ),
            )
        )
    if not declarations:
        diagnostics.append("No primary melee weapon assignments were available from the request.")
    payload = None
    player_id: str | None = None
    battle_round: int | None = None
    unit_instance_id: str | None = None
    source_decision_request_id: str | None = None
    source_decision_result_id: str | None = None
    if not diagnostics:
        player_id = _required_text_or_diagnostic(
            proposal.payload,
            "active_player_id",
            diagnostics=diagnostics,
            fallback=proposal.actor_id,
        )
        battle_round = _required_int_or_diagnostic(
            proposal.payload,
            "battle_round",
            diagnostics=diagnostics,
        )
        unit_instance_id = _required_text_or_diagnostic(
            proposal.payload,
            "unit_instance_id",
            diagnostics=diagnostics,
        )
        source_decision_request_id = _required_text_any_or_diagnostic(
            proposal.payload,
            ("source_decision_request_id", "source_fight_activation_request_id"),
            diagnostics=diagnostics,
        )
        source_decision_result_id = _required_text_any_or_diagnostic(
            proposal.payload,
            ("source_decision_result_id", "source_fight_activation_result_id"),
            diagnostics=diagnostics,
        )
    if not diagnostics:
        assert player_id is not None
        assert battle_round is not None
        assert unit_instance_id is not None
        assert source_decision_request_id is not None
        assert source_decision_result_id is not None
        payload = _validate_json_object(
            {
                "proposal_request_id": proposal.request_id,
                "proposal_kind": MELEE_DECLARATION_PROPOSAL_KIND,
                "player_id": player_id,
                "battle_round": battle_round,
                "unit_instance_id": unit_instance_id,
                "source_decision_request_id": source_decision_request_id,
                "source_decision_result_id": source_decision_result_id,
                "declarations": declarations,
            }
        )
    return AssignmentWorkspace(
        request_id=proposal.request_id,
        decision_type=proposal.decision_type,
        actor_id=proposal.actor_id,
        proposal_kind=MELEE_DECLARATION_PROPOSAL_KIND,
        rows=tuple(rows),
        payload_preview=payload,
        local_hint_lines=(
            "Melee declaration is seeded from engine-emitted engaged targets.",
            "Split attacks and optional extra-attacks editing are follow-on interactions.",
        ),
        diagnostic_lines=tuple(diagnostics),
    )


def _stratagem_workspace(pending_decision: UiDecision) -> AssignmentWorkspace:
    proposal = _required_parameterized_proposal(pending_decision)
    diagnostics: list[str] = []
    target_binding = _target_binding_for_stratagem(proposal.payload, diagnostics=diagnostics)
    declinable = _stratagem_request_is_declinable(pending_decision.payload)
    context = _required_object_or_diagnostic(proposal.payload, "context", diagnostics=diagnostics)
    catalog_record = _required_object_or_diagnostic(
        proposal.payload,
        "catalog_record",
        diagnostics=diagnostics,
    )
    rows: tuple[AssignmentWorkspaceRow, ...] = ()
    payload = None
    stratagem_hint_lines = _stratagem_hint_lines(
        proposal_payload=proposal.payload,
        catalog_record=catalog_record,
    )
    if target_binding is not None:
        target_kind = _text(target_binding.get("target_kind")) or "unknown"
        target_ref_keys = _stratagem_target_ref_keys(target_binding)
        rows = (
            AssignmentWorkspaceRow(
                row_id=f"stratagem-target:{proposal.request_id}",
                label=f"Target binding: {target_kind}",
                source_ref_keys=_stratagem_source_ref_keys(proposal.payload),
                target_ref_keys=target_ref_keys,
                summary_lines=(
                    f"Target kind: {target_kind}",
                    f"Target player: {_text(target_binding.get('target_player_id')) or 'none'}",
                    *stratagem_hint_lines[:2],
                ),
            ),
        )
        if context is not None and catalog_record is not None:
            payload = _validate_json_object(
                {
                    "proposal": {
                        "proposal_kind": STRATAGEM_TARGET_BINDING_PROPOSAL_KIND,
                        "context": context,
                        "catalog_record": catalog_record,
                        "target_binding": target_binding,
                        "effect_selection": proposal.payload.get("effect_selection"),
                    }
                }
            )
    if target_binding is None and not diagnostics:
        target_binding_missing_line = (
            "Stratagem request does not expose a selectable target binding candidate yet."
        )
        if declinable:
            stratagem_hint_lines = (
                *stratagem_hint_lines,
                "No selectable target is exposed yet; decline is available.",
            )
        else:
            diagnostics.append(target_binding_missing_line)
        rows = (
            AssignmentWorkspaceRow(
                row_id=f"stratagem-target:{proposal.request_id}:missing",
                label=_stratagem_label(catalog_record=catalog_record),
                source_ref_keys=_stratagem_source_ref_keys(proposal.payload),
                target_ref_keys=(),
                summary_lines=stratagem_hint_lines
                or ("No selectable target binding candidate was emitted.",),
            ),
        )
    hints = [
        "Stratagem target binding is submitted only from engine-emitted binding data.",
    ]
    hints.extend(stratagem_hint_lines)
    if declinable:
        hints.append("This optional Stratagem window can be declined.")
    return AssignmentWorkspace(
        request_id=proposal.request_id,
        decision_type=proposal.decision_type,
        actor_id=proposal.actor_id,
        proposal_kind=STRATAGEM_TARGET_BINDING_PROPOSAL_KIND,
        rows=rows,
        payload_preview=payload,
        local_hint_lines=tuple(hints),
        diagnostic_lines=tuple(diagnostics),
        declinable=declinable,
        decline_payload=DECLINE_STRATAGEM_WINDOW_PAYLOAD if declinable else None,
    )


def _required_parameterized_proposal(
    pending_decision: UiDecision,
) -> UiParameterizedProposalRequest:
    proposal = pending_decision.parameterized_proposal
    if proposal is None:
        raise AssignmentWorkspaceError("Assignment workspace requires a parameterized request.")
    return proposal


class AssignmentWorkspaceError(ValueError):
    """Raised when assignment workspace state is internally inconsistent."""


def _first_legal_shooting_target(
    *,
    target_candidates: tuple[JsonObject, ...],
    model_id: str,
    weapon_profile_id: str,
    attacker_unit_id: str,
) -> JsonObject | None:
    matching: list[JsonObject] = []
    unit_matching: list[JsonObject] = []
    fallback: list[JsonObject] = []
    for candidate in target_candidates:
        if candidate.get("is_legal") is not True:
            continue
        if _text(candidate.get("weapon_profile_id")) not in ("", weapon_profile_id):
            continue
        observer_model_id = _text(candidate.get("observer_model_id"))
        if observer_model_id == model_id:
            matching.append(candidate)
        elif (
            attacker_unit_id
            and _text(candidate.get("attacker_unit_instance_id")) == attacker_unit_id
        ):
            unit_matching.append(candidate)
        elif not observer_model_id:
            fallback.append(candidate)
    if matching:
        return matching[0]
    if unit_matching:
        return unit_matching[0]
    return fallback[0] if fallback else None


def _firing_deck_selection_preview(
    *,
    request_payload: JsonObject,
    declarations: list[JsonValue],
    diagnostics: list[str],
) -> JsonValue | None:
    explicit_selection = request_payload.get("firing_deck_selection")
    if explicit_selection is not None:
        return validate_json_value(explicit_selection)
    uses_firing_deck = any(
        type(declaration) is dict
        and (
            "firing_deck_source_unit_instance_id" in declaration
            or "firing_deck_source_model_instance_id" in declaration
        )
        for declaration in declarations
    )
    if uses_firing_deck:
        diagnostics.append("Firing Deck selection needs an explicit future UI choice.")
    return None


def _selected_weapon_ability_ids(
    candidate: JsonObject,
    *,
    diagnostics: list[str],
) -> tuple[str, ...] | None:
    selection_requests = candidate.get("required_weapon_ability_selections")
    if selection_requests is None:
        return ()
    if type(selection_requests) is not list:
        diagnostics.append("Required weapon ability selections are malformed.")
        return None
    selected_ids: list[str] = []
    for raw_request in selection_requests:
        if type(raw_request) is not dict:
            diagnostics.append("Required weapon ability selection request is malformed.")
            return None
        request = raw_request
        options = request.get("options")
        if type(options) is not list or len(options) != 1:
            diagnostics.append(
                "Duplicate weapon ability selection needs an explicit future UI choice."
            )
            return None
        option = options[0]
        if type(option) is not dict:
            diagnostics.append("Required weapon ability selection option is malformed.")
            return None
        option_id = _text(option.get("option_id"))
        if not option_id:
            diagnostics.append("Required weapon ability selection option is missing option_id.")
            return None
        selected_ids.append(option_id)
    return tuple(selected_ids)


def _target_binding_for_stratagem(
    payload: JsonObject,
    *,
    diagnostics: list[str],
) -> JsonObject | None:
    binding = payload.get("target_binding")
    if type(binding) is dict:
        return dict(binding)
    candidates = payload.get("target_binding_candidates")
    if candidates is None:
        return None
    if type(candidates) is not list:
        diagnostics.append("Stratagem target binding candidates are malformed.")
        return None
    object_candidates = tuple(candidate for candidate in candidates if type(candidate) is dict)
    if len(object_candidates) != len(candidates):
        diagnostics.append("Stratagem target binding candidate is malformed.")
        return None
    if len(object_candidates) != 1:
        diagnostics.append("Stratagem target binding needs an explicit future target choice.")
        return None
    return dict(object_candidates[0])


def _stratagem_request_is_declinable(payload: JsonValue) -> bool:
    return type(payload) is dict and payload.get("declinable") is True


def _stratagem_label(*, catalog_record: JsonObject | None) -> str:
    definition = None if catalog_record is None else catalog_record.get("definition")
    if type(definition) is dict:
        name = _text(definition.get("name"))
        if name:
            return name
        stratagem_id = _text(definition.get("stratagem_id"))
        if stratagem_id:
            return _short(stratagem_id).replace("_", " ").title()
    return "Stratagem target binding"


def _stratagem_hint_lines(
    *,
    proposal_payload: JsonObject,
    catalog_record: JsonObject | None,
) -> tuple[str, ...]:
    lines: list[str] = []
    definition = None if catalog_record is None else catalog_record.get("definition")
    if type(definition) is dict:
        name = _text(definition.get("name"))
        if name:
            lines.append(f"Stratagem: {name}")
        cp_cost = definition.get("command_point_cost")
        if not isinstance(cp_cost, int):
            cp_cost = definition.get("cp_cost")
        if type(cp_cost) is int:
            lines.append(f"CP cost: {cp_cost}")
        when_descriptor = _text(definition.get("when_descriptor"))
        if when_descriptor:
            lines.append(f"When: {when_descriptor}")
        target_descriptor = _text(definition.get("target_descriptor"))
        if target_descriptor:
            lines.append(f"Target: {target_descriptor}")
        effect_descriptor = _text(definition.get("effect_descriptor"))
        if effect_descriptor:
            lines.append(f"Effect: {effect_descriptor}")
    effect_selection = proposal_payload.get("effect_selection")
    if effect_selection is not None:
        lines.append("Effect selection is preserved from the engine request.")
    return tuple(lines[:6])


def _stratagem_source_ref_keys(payload: JsonObject) -> tuple[str, ...]:
    context = payload.get("context")
    if type(context) is not dict:
        return ()
    trigger_payload = context.get("trigger_payload")
    if type(trigger_payload) is not dict:
        return ()
    unit_id = (
        _text(trigger_payload.get("affected_unit_instance_id"))
        or _text(trigger_payload.get("unit_instance_id"))
        or _text(trigger_payload.get("moved_unit_instance_id"))
    )
    if unit_id:
        return (f"unit:{unit_id}",)
    return ()


def _stratagem_target_ref_keys(binding: JsonObject) -> tuple[str, ...]:
    unit_id = _text(binding.get("target_unit_instance_id"))
    if unit_id:
        return (f"unit:{unit_id}",)
    secondary_id = _text(binding.get("target_secondary_mission_id"))
    if secondary_id:
        return (f"secondary_mission:{secondary_id}",)
    return ()


def _json_object_list(
    value: JsonValue | object,
    *,
    key: str,
    diagnostics: list[str],
) -> tuple[JsonObject, ...]:
    if type(value) is not list:
        diagnostics.append(f"Assignment request field {key} must be a list.")
        return ()
    objects: list[JsonObject] = []
    for item in cast(list[object], value):
        validated_item = validate_json_value(item)
        if type(validated_item) is not dict:
            diagnostics.append(f"Assignment request field {key} contains a malformed object.")
            return ()
        objects.append(validated_item)
    return tuple(objects)


def _required_text_or_diagnostic(
    payload: JsonObject,
    key: str,
    *,
    diagnostics: list[str],
    fallback: str | None = None,
) -> str | None:
    value = _text(payload.get(key))
    if value:
        return value
    if fallback is not None:
        return fallback
    diagnostics.append(f"Assignment request is missing required text field {key}.")
    return None


def _required_text_any_or_diagnostic(
    payload: JsonObject,
    keys: tuple[str, ...],
    *,
    diagnostics: list[str],
) -> str | None:
    for key in keys:
        value = _text(payload.get(key))
        if value:
            return value
    joined_keys = ", ".join(keys)
    diagnostics.append(f"Assignment request is missing required text field {joined_keys}.")
    return None


def _required_int_or_diagnostic(
    payload: JsonObject,
    key: str,
    *,
    diagnostics: list[str],
) -> int | None:
    value = payload.get(key)
    if type(value) is int:
        return value
    diagnostics.append(f"Assignment request is missing required integer field {key}.")
    return None


def _required_object_or_diagnostic(
    payload: JsonObject,
    key: str,
    *,
    diagnostics: list[str],
) -> JsonObject | None:
    value = payload.get(key)
    if type(value) is dict:
        return dict(value)
    diagnostics.append(f"Stratagem request is missing required object field {key}.")
    return None


def _validate_json_object(payload: JsonObject) -> JsonObject:
    value = validate_json_value(payload)
    if type(value) is not dict:
        raise AssignmentWorkspaceError("Assignment payload preview must be an object.")
    return value


def _copy_optional_text_field(*, source: JsonObject, target: JsonObject, key: str) -> None:
    value = _text(source.get(key))
    if value:
        target[key] = value


def _first_string(value: object) -> str:
    if type(value) is list:
        for item in cast(list[object], value):
            if type(item) is str and item:
                return item
    return ""


def _text(value: object) -> str:
    return value if type(value) is str else ""


def _short(value: str) -> str:
    return value.rsplit(":", maxsplit=1)[-1]
