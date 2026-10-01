"""Generic local assignment workspace for parameterized proposal requests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import chain, product
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
class ShootingAssignmentSelection:
    """Local choice of one engine-offered physical weapon/profile row."""

    model_instance_id: str
    weapon_instance_id: str
    weapon_profile_id: str
    target_unit_instance_id: str | None
    firing_deck_source_unit_instance_id: str | None = None
    firing_deck_source_model_instance_id: str | None = None
    selected_weapon_ability_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ShootingAssignmentChoice:
    """One request-scoped Shooting row and its emitted source options."""

    choice_id: str
    selection: ShootingAssignmentSelection
    label: str
    source_ref_keys: tuple[str, ...]
    target_ref_keys: tuple[str, ...]
    summary_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MeleeAssignmentSelection:
    """One engine-offered melee weapon, target, and ability source choice."""

    model_instance_id: str
    weapon_instance_id: str
    weapon_profile_id: str
    target_unit_instance_id: str
    selected_weapon_ability_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MeleeAssignmentChoice:
    """One request-scoped melee choice displayed by the assignment HUD."""

    choice_id: str
    selection: MeleeAssignmentSelection
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
    shooting_choices: tuple[ShootingAssignmentChoice, ...] = ()
    shooting_selections: tuple[ShootingAssignmentSelection, ...] = ()
    melee_choices: tuple[MeleeAssignmentChoice, ...] = ()
    melee_selections: tuple[MeleeAssignmentSelection, ...] = ()
    stratagem_mode_choices: tuple[str, ...] = ()
    stratagem_selected_mode: str | None = None
    stratagem_target_unit_id: str | None = None
    stratagem_target_selectable: bool = False

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

    def with_shooting_selections(
        self,
        pending_decision: UiDecision,
        selections: tuple[ShootingAssignmentSelection, ...],
        *,
        firing_deck_selection: JsonObject | None = None,
    ) -> AssignmentWorkspace:
        """Rebuild an advisory Shooting preview from explicit local choices.

        An empty tuple means an explicitly empty declaration. The engine still
        validates the resulting proposal when it is submitted.
        """

        if self.proposal_kind != SHOOTING_DECLARATION_PROPOSAL_KIND or not self.is_for(
            pending_decision
        ):
            raise AssignmentWorkspaceError("Shooting selections require the current request.")
        return _shooting_workspace(
            pending_decision,
            selections=selections,
            firing_deck_selection=firing_deck_selection,
        )

    def with_stratagem_intent(
        self,
        pending_decision: UiDecision,
        *,
        target_unit_id: str,
        source_mode: str | None = None,
    ) -> AssignmentWorkspace:
        """Preview a friendly target and any source-offered effect mode."""

        if self.proposal_kind != STRATAGEM_TARGET_BINDING_PROPOSAL_KIND or not self.is_for(
            pending_decision
        ):
            raise AssignmentWorkspaceError("Stratagem intent requires the current request.")
        if not self.stratagem_target_selectable:
            raise AssignmentWorkspaceError("Stratagem source has no selectable friendly target.")
        if self.stratagem_mode_choices:
            if source_mode not in self.stratagem_mode_choices:
                raise AssignmentWorkspaceError(
                    "Stratagem mode was not offered by the current source."
                )
        elif source_mode is not None:
            raise AssignmentWorkspaceError("Stratagem source has no selectable effect mode.")
        if not target_unit_id:
            raise AssignmentWorkspaceError("Stratagem target unit is required.")
        return _stratagem_workspace(
            pending_decision,
            target_unit_id=target_unit_id,
            source_mode=source_mode,
        )

    def with_melee_selection(
        self,
        pending_decision: UiDecision,
        selection: MeleeAssignmentSelection,
    ) -> AssignmentWorkspace:
        """Choose a current emitted melee row for one model."""

        if self.proposal_kind != MELEE_DECLARATION_PROPOSAL_KIND or not self.is_for(
            pending_decision
        ):
            raise AssignmentWorkspaceError("Melee selection requires the current request.")
        if selection not in (choice.selection for choice in self.melee_choices):
            raise AssignmentWorkspaceError(
                "Melee selection was not offered by the current request."
            )
        selections = (
            *(
                current
                for current in self.melee_selections
                if current.model_instance_id != selection.model_instance_id
            ),
            selection,
        )
        return _melee_workspace(pending_decision, selections=selections)


def is_assignment_parameterized_decision(pending_decision: UiDecision | None) -> bool:
    """Return whether a pending decision is a supported generic assignment request."""

    if pending_decision is None or pending_decision.interaction is None:
        return False
    if not pending_decision.is_parameterized:
        return False
    if pending_decision.interaction.interaction_kind not in {
        "entity_selection",
        "weapon_allocation_matrix",
    }:
        return False
    proposal = pending_decision.parameterized_proposal
    if proposal is None:
        return False
    return proposal.proposal_kind in ASSIGNMENT_PROPOSAL_KINDS


def _shooting_workspace(
    pending_decision: UiDecision,
    *,
    selections: tuple[ShootingAssignmentSelection, ...] | None = None,
    firing_deck_selection: JsonObject | None = None,
) -> AssignmentWorkspace:
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
    targetless_candidates = _optional_json_object_list(
        proposal.payload,
        key="targetless_weapon_candidates",
        diagnostics=diagnostics,
    )
    selection_limits = _json_object_list(
        proposal.payload.get("shooting_weapon_selection_limits"),
        key="shooting_weapon_selection_limits",
        diagnostics=diagnostics,
    )
    _diagnose_shooting_inventory(
        available_weapons=available_weapons,
        target_candidates=target_candidates,
        targetless_candidates=targetless_candidates,
        selection_limits=selection_limits,
        diagnostics=diagnostics,
    )
    shooting_choices = _shooting_choices(
        request_id=proposal.request_id,
        proposal_payload=proposal.payload,
        available_weapons=available_weapons,
        target_candidates=target_candidates,
        targetless_candidates=targetless_candidates,
        selection_limits=selection_limits,
        diagnostics=diagnostics,
    )
    visibility_cache_key = _text(proposal.payload.get("visibility_cache_key"))
    if not visibility_cache_key:
        diagnostics.append("Shooting request is missing visibility_cache_key.")
    if selections is None:
        default_rows = tuple(
            (weapon, selection)
            for weapon in available_weapons
            if (
                selection := _default_shooting_selection(
                    weapon=weapon,
                    target_candidates=target_candidates,
                )
            )
            is not None
        )
        current_selections = [selection for _, selection in default_rows]
        selected_rows: tuple[tuple[int, JsonObject, ShootingAssignmentSelection], ...] = tuple(
            (index, weapon, selection) for index, (weapon, selection) in enumerate(default_rows)
        )
    else:
        current_selections = list(selections)
        selected_rows = tuple(
            (index, weapon, selection)
            for index, selection in enumerate(selections)
            if (
                weapon := _shooting_weapon_for_selection(
                    available_weapons=available_weapons,
                    selection=selection,
                    diagnostics=diagnostics,
                )
            )
            is not None
        )
    for index, weapon, selection in selected_rows:
        model_id = _text(weapon.get("model_instance_id"))
        weapon_instance_id = _text(weapon.get("weapon_instance_id"))
        wargear_id = _text(weapon.get("wargear_id"))
        weapon_profile_id = _text(weapon.get("weapon_profile_id"))
        if not model_id or not weapon_instance_id or not wargear_id or not weapon_profile_id:
            diagnostics.append(
                "Shooting weapon candidate is missing physical/model/wargear/profile IDs."
            )
            continue
        candidate = _shooting_candidate_for_selection(
            target_candidates=target_candidates,
            targetless_candidates=targetless_candidates,
            selection=selection,
        )
        if selection.target_unit_instance_id is not None and candidate is None:
            diagnostics.append("Selected Shooting target is not an engine-emitted legal candidate.")
            continue
        shooting_type = _shooting_type_for_selection(
            proposal_payload=proposal.payload,
            selection=selection,
            candidate=candidate,
            target_candidates=target_candidates,
        )
        if not shooting_type:
            diagnostics.append("Shooting selection has no engine-emitted shooting type.")
            continue
        selected_ability_ids = _selected_weapon_ability_ids(
            {} if candidate is None else candidate,
            selected_ids=selection.selected_weapon_ability_ids,
            diagnostics=diagnostics,
        )
        if selected_ability_ids is None:
            continue
        current_selections[index] = replace(
            selection, selected_weapon_ability_ids=selected_ability_ids
        )
        declaration: JsonObject = {
            "attacker_model_instance_id": model_id,
            "weapon_instance_id": weapon_instance_id,
            "wargear_id": wargear_id,
            "weapon_profile_id": weapon_profile_id,
            "target_unit_instance_id": selection.target_unit_instance_id,
            "shooting_type": shooting_type,
            "selected_weapon_ability_ids": list(selected_ability_ids),
            "firing_deck_source_unit_instance_id": (selection.firing_deck_source_unit_instance_id),
            "firing_deck_source_model_instance_id": (
                selection.firing_deck_source_model_instance_id
            ),
        }
        declarations.append(declaration)
        rows.append(
            AssignmentWorkspaceRow(
                row_id=_shooting_row_id(selection),
                label=(
                    f"{_short(model_id)} -> {_short(selection.target_unit_instance_id)}"
                    if selection.target_unit_instance_id is not None
                    else f"{_short(model_id)} -> no target"
                ),
                source_ref_keys=(f"model:{model_id}",),
                target_ref_keys=(
                    (f"unit:{selection.target_unit_instance_id}",)
                    if selection.target_unit_instance_id is not None
                    else ()
                ),
                summary_lines=(
                    f"Physical weapon: {weapon_instance_id}",
                    f"Weapon profile: {weapon_profile_id}",
                    f"Shooting type: {shooting_type}",
                    *_shooting_limit_lines(
                        selection_limits=selection_limits,
                        model_id=model_id,
                        weapon_profile_id=weapon_profile_id,
                    ),
                ),
            )
        )
        candidate_visibility_key = (
            "" if candidate is None else _text(candidate.get("visibility_cache_key"))
        )
        if selection.target_unit_instance_id is not None and candidate_visibility_key:
            visibility_cache_key = candidate_visibility_key
    payload = None
    player_id: str | None = None
    battle_round: int | None = None
    unit_instance_id: str | None = None
    source_decision_request_id: str | None = None
    source_decision_result_id: str | None = None
    resolved_firing_deck_selection: JsonValue | None = None
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
        resolved_firing_deck_selection = _firing_deck_selection_preview(
            request_payload=proposal.payload,
            declarations=declarations,
            diagnostics=diagnostics,
            explicit_selection=firing_deck_selection,
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
                "firing_deck_selection": resolved_firing_deck_selection,
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
            "Shooting preview is advisory; the engine validates the selected physical weapons.",
            "An empty declaration and a selected weapon with no target are distinct choices.",
        ),
        diagnostic_lines=tuple(diagnostics),
        editable=True,
        shooting_choices=shooting_choices,
        shooting_selections=tuple(current_selections),
    )


def _melee_workspace(
    pending_decision: UiDecision,
    *,
    selections: tuple[MeleeAssignmentSelection, ...] | None = None,
) -> AssignmentWorkspace:
    proposal = _required_parameterized_proposal(pending_decision)
    rows: list[AssignmentWorkspaceRow] = []
    declarations: list[JsonValue] = []
    diagnostics: list[str] = []
    available_weapons = _json_object_list(
        proposal.payload.get("available_weapons"),
        key="available_weapons",
        diagnostics=diagnostics,
    )
    choices = _melee_choices(
        request_id=proposal.request_id,
        available_weapons=available_weapons,
        diagnostics=diagnostics,
    )
    if selections is None:
        current_selections: list[MeleeAssignmentSelection] = []
        default_models: set[str] = set()
        for weapon in available_weapons:
            model_id = _text(weapon.get("model_instance_id"))
            target_id = _first_string(weapon.get("engaged_target_unit_instance_ids"))
            if not model_id or not target_id or model_id in default_models:
                continue
            if weapon.get("is_extra_attacks") is True:
                continue
            default_models.add(model_id)
            matching = tuple(
                choice.selection
                for choice in choices
                if choice.selection.model_instance_id == model_id
                and choice.selection.weapon_instance_id == weapon.get("weapon_instance_id")
                and choice.selection.weapon_profile_id == weapon.get("weapon_profile_id")
                and choice.selection.target_unit_instance_id == target_id
            )
            if len(matching) == 1:
                current_selections.append(matching[0])
    else:
        current_selections = list(selections)
    offered_models = {choice.selection.model_instance_id for choice in choices}
    selected_models = [selection.model_instance_id for selection in current_selections]
    if len(selected_models) != len(set(selected_models)):
        diagnostics.append("Melee choices must select at most one primary weapon per model.")
    if offered_models.difference(selected_models):
        diagnostics.append("Select an emitted melee weapon and ability source for each model.")
    for selection in current_selections:
        matches = tuple(
            weapon
            for weapon in available_weapons
            if weapon.get("model_instance_id") == selection.model_instance_id
            and weapon.get("weapon_instance_id") == selection.weapon_instance_id
            and weapon.get("weapon_profile_id") == selection.weapon_profile_id
            and weapon.get("is_extra_attacks") is not True
            and selection.target_unit_instance_id
            in _string_list(weapon.get("engaged_target_unit_instance_ids"))
        )
        if len(matches) != 1 or selection not in (choice.selection for choice in choices):
            diagnostics.append("Melee selection must reference one current emitted weapon choice.")
            continue
        weapon = matches[0]
        model_id = selection.model_instance_id
        weapon_instance_id = selection.weapon_instance_id
        weapon_profile_id = selection.weapon_profile_id
        target_id = selection.target_unit_instance_id
        wargear_id = _text(weapon.get("wargear_id"))
        selected_ids = _selected_weapon_ability_ids(
            weapon,
            selected_ids=selection.selected_weapon_ability_ids,
            diagnostics=diagnostics,
        )
        if not wargear_id or selected_ids is None:
            diagnostics.append("Melee weapon candidate is missing wargear or ability source IDs.")
            continue
        target_allocations: list[JsonValue] = [
            {
                "target_unit_instance_id": target_id,
            }
        ]
        declarations.append(
            {
                "attacker_model_instance_id": model_id,
                "weapon_instance_id": weapon_instance_id,
                "wargear_id": wargear_id,
                "weapon_profile_id": weapon_profile_id,
                "target_allocations": target_allocations,
                "selected_weapon_ability_ids": list(selected_ids),
            }
        )
        rows.append(
            AssignmentWorkspaceRow(
                row_id=f"melee:{model_id}:{weapon_instance_id}:{weapon_profile_id}",
                label=f"{_short(model_id)} -> {_short(target_id)}",
                source_ref_keys=(f"model:{model_id}",),
                target_ref_keys=(f"unit:{target_id}",),
                summary_lines=(
                    f"Physical weapon: {weapon_instance_id}",
                    f"Primary melee profile: {weapon_profile_id}",
                    *(f"Weapon ability source: {option_id}" for option_id in selected_ids),
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
            "Melee preview uses engine-emitted physical weapons, targets, and ability sources.",
            "Split attacks and optional extra-attacks editing are follow-on interactions.",
        ),
        diagnostic_lines=tuple(diagnostics),
        editable=True,
        melee_choices=choices,
        melee_selections=tuple(current_selections),
    )


def _melee_choices(
    *,
    request_id: str,
    available_weapons: tuple[JsonObject, ...],
    diagnostics: list[str],
) -> tuple[MeleeAssignmentChoice, ...]:
    choices: list[MeleeAssignmentChoice] = []
    for weapon_index, weapon in enumerate(available_weapons):
        model_id = _text(weapon.get("model_instance_id"))
        weapon_instance_id = _text(weapon.get("weapon_instance_id"))
        wargear_id = _text(weapon.get("wargear_id"))
        profile_id = _text(weapon.get("weapon_profile_id"))
        if not model_id or not weapon_instance_id or not wargear_id or not profile_id:
            diagnostics.append(
                "Melee weapon candidate is missing physical/model/wargear/profile IDs."
            )
            continue
        if weapon.get("is_extra_attacks") is True:
            continue
        target_ids = _string_list(weapon.get("engaged_target_unit_instance_ids"))
        if not target_ids:
            continue
        option_sets = _shooting_ability_option_sets(weapon, diagnostics=diagnostics)
        if option_sets is None:
            continue
        for target_id in target_ids:
            for chosen_options in product(*option_sets):
                selected_ids = tuple(option_id for option_id, _ in chosen_options)
                selection = MeleeAssignmentSelection(
                    model_instance_id=model_id,
                    weapon_instance_id=weapon_instance_id,
                    weapon_profile_id=profile_id,
                    target_unit_instance_id=target_id,
                    selected_weapon_ability_ids=selected_ids,
                )
                source_labels = tuple(label for _, label in chosen_options)
                label = f"{_short(model_id)} {_short(weapon_instance_id)} -> {_short(target_id)}"
                if source_labels:
                    label += f" ({', '.join(source_labels)})"
                parts = (request_id, str(weapon_index), target_id, *selected_ids)
                choices.append(
                    MeleeAssignmentChoice(
                        choice_id="melee-choice:"
                        + "".join(f"{len(part)}:{part}" for part in parts),
                        selection=selection,
                        label=label,
                        source_ref_keys=(f"model:{model_id}",),
                        target_ref_keys=(f"unit:{target_id}",),
                        summary_lines=(
                            f"Physical weapon: {weapon_instance_id}",
                            f"Weapon profile: {profile_id}",
                            *(f"Weapon ability source: {option_id}" for option_id in selected_ids),
                        ),
                    )
                )
    return tuple(choices)


def _stratagem_workspace(
    pending_decision: UiDecision,
    *,
    target_unit_id: str | None = None,
    source_mode: str | None = None,
) -> AssignmentWorkspace:
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
    heroic_modes = _heroic_source_modes(catalog_record, diagnostics=diagnostics)
    selectable_friendly_target = bool(heroic_modes) or (
        target_binding is None and _source_allows_friendly_target_intent(catalog_record)
    )
    if selectable_friendly_target and target_unit_id is not None:
        intent_binding: JsonObject = {
            "target_kind": "friendly_unit",
            "target_player_id": proposal.actor_id,
            "target_unit_instance_id": target_unit_id,
        }
        target_binding = intent_binding
    if heroic_modes and source_mode is not None and source_mode not in heroic_modes:
        diagnostics.append("Heroic Intervention mode is not in the current source.")
    rows: tuple[AssignmentWorkspaceRow, ...] = ()
    payload = None
    stratagem_hint_lines = _stratagem_hint_lines(
        proposal_payload=proposal.payload,
        catalog_record=catalog_record,
    )
    if heroic_modes:
        rows = tuple(
            AssignmentWorkspaceRow(
                row_id=f"stratagem-mode:{proposal.request_id}:{mode}",
                label=f"{'[x]' if mode == source_mode else '[ ]'} {mode.replace('_', ' ').title()}",
                source_ref_keys=_stratagem_source_ref_keys(proposal.payload),
                target_ref_keys=(f"unit:{target_unit_id}",) if target_unit_id else (),
                summary_lines=(
                    f"Source-authorized mode: {mode}",
                    f"Selected friendly unit: {target_unit_id or 'none'}",
                    "Core validates target eligibility and the Charge continuation.",
                ),
            )
            for mode in heroic_modes
        )
        stratagem_hint_lines = (
            *stratagem_hint_lines,
            "Select a friendly unit, then choose one of the source modes.",
        )
    elif target_binding is not None:
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
    if target_binding is None and not diagnostics and not heroic_modes:
        target_binding_missing_line = (
            "Stratagem request does not expose a selectable target binding candidate yet."
        )
        if selectable_friendly_target:
            stratagem_hint_lines = (
                *stratagem_hint_lines,
                "Select a projected friendly unit, then choose this Stratagem target row.",
            )
        elif declinable:
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
    if (
        not diagnostics
        and target_binding is not None
        and context is not None
        and catalog_record is not None
        and (not heroic_modes or source_mode is not None)
    ):
        effect_selection: JsonValue = (
            {"mode": source_mode} if heroic_modes else proposal.payload.get("effect_selection")
        )
        proposal_payload: JsonObject = {
            "proposal_kind": STRATAGEM_TARGET_BINDING_PROPOSAL_KIND,
            "context": context,
            "catalog_record": catalog_record,
            "target_binding": target_binding,
            "effect_selection": effect_selection,
        }
        payload = _validate_json_object({"proposal": proposal_payload})
    hints = [
        "The engine validates this Stratagem target and source mode."
        if heroic_modes
        else "Stratagem target binding is submitted only from engine-emitted binding data.",
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
        editable=selectable_friendly_target,
        stratagem_mode_choices=heroic_modes,
        stratagem_selected_mode=source_mode,
        stratagem_target_unit_id=target_unit_id,
        stratagem_target_selectable=selectable_friendly_target,
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


def _diagnose_shooting_inventory(
    *,
    available_weapons: tuple[JsonObject, ...],
    target_candidates: tuple[JsonObject, ...],
    targetless_candidates: tuple[JsonObject, ...],
    selection_limits: tuple[JsonObject, ...],
    diagnostics: list[str],
) -> None:
    for weapon in available_weapons:
        if not all(
            _text(weapon.get(key))
            for key in (
                "model_instance_id",
                "weapon_instance_id",
                "wargear_id",
                "weapon_profile_id",
            )
        ):
            diagnostics.append(
                "Shooting weapon candidate is missing physical/model/wargear/profile IDs."
            )
        source_unit = weapon.get("firing_deck_source_unit_instance_id")
        source_model = weapon.get("firing_deck_source_model_instance_id")
        if (source_unit is None) != (source_model is None):
            diagnostics.append("Shooting Firing Deck source unit and model must be paired.")
    for candidate in target_candidates:
        if candidate.get("is_legal") is not True:
            continue
        if not all(
            _text(candidate.get(key))
            for key in (
                "weapon_instance_id",
                "weapon_profile_id",
                "target_unit_instance_id",
            )
        ) or not _string_list(candidate.get("shooting_types")):
            diagnostics.append(
                "Legal Shooting target candidate lacks physical/profile/target/type data."
            )
    for candidate in targetless_candidates:
        if (
            not all(
                _text(candidate.get(key))
                for key in ("model_instance_id", "weapon_instance_id", "weapon_profile_id")
            )
            or candidate.get("target_unit_instance_id") is not None
            or not _text(candidate.get("shooting_type"))
        ):
            diagnostics.append("Targetless Shooting candidate lacks physical/profile/type data.")
    for limit in selection_limits:
        if (
            not _text(limit.get("model_instance_id"))
            or not _text(limit.get("weapon_keyword"))
            or type(limit.get("max_selections")) is not int
            or not _string_list(limit.get("weapon_profile_ids"))
        ):
            diagnostics.append("Shooting weapon selection limit is missing projected display data.")


def _shooting_row_id(selection: ShootingAssignmentSelection) -> str:
    parts = (
        selection.model_instance_id,
        selection.weapon_instance_id,
        selection.weapon_profile_id,
        selection.firing_deck_source_unit_instance_id or "",
        selection.firing_deck_source_model_instance_id or "",
    )
    return "shooting:" + "".join(f"{len(part)}:{part}" for part in parts)


def _shooting_choices(
    *,
    request_id: str,
    proposal_payload: JsonObject,
    available_weapons: tuple[JsonObject, ...],
    target_candidates: tuple[JsonObject, ...],
    targetless_candidates: tuple[JsonObject, ...],
    selection_limits: tuple[JsonObject, ...],
    diagnostics: list[str],
) -> tuple[ShootingAssignmentChoice, ...]:
    choices: list[ShootingAssignmentChoice] = []
    emitted_candidates = chain(
        (("target", index, candidate) for index, candidate in enumerate(target_candidates)),
        (("targetless", index, candidate) for index, candidate in enumerate(targetless_candidates)),
    )
    candidate_rows = tuple(emitted_candidates)
    for weapon in available_weapons:
        model_id = _text(weapon.get("model_instance_id"))
        weapon_instance_id = _text(weapon.get("weapon_instance_id"))
        profile_id = _text(weapon.get("weapon_profile_id"))
        if not model_id or not weapon_instance_id or not profile_id:
            continue
        source_unit_id = _text(weapon.get("firing_deck_source_unit_instance_id")) or None
        source_model_id = _text(weapon.get("firing_deck_source_model_instance_id")) or None
        nullable_selection = ShootingAssignmentSelection(
            model_instance_id=model_id,
            weapon_instance_id=weapon_instance_id,
            weapon_profile_id=profile_id,
            target_unit_instance_id=None,
            firing_deck_source_unit_instance_id=source_unit_id,
            firing_deck_source_model_instance_id=source_model_id,
        )
        has_targetless_inventory = any(
            candidate.get("model_instance_id") == model_id
            and candidate.get("weapon_instance_id") == weapon_instance_id
            and candidate.get("weapon_profile_id") == profile_id
            and candidate.get("firing_deck_source_unit_instance_id") == source_unit_id
            and candidate.get("firing_deck_source_model_instance_id") == source_model_id
            for candidate in targetless_candidates
        )
        nullable_type = _shooting_type_for_selection(
            proposal_payload=proposal_payload,
            selection=nullable_selection,
            candidate=None,
            target_candidates=target_candidates,
        )
        fallback_rows: tuple[tuple[str, int, JsonObject], ...] = (
            ()
            if has_targetless_inventory or not nullable_type
            else (
                (
                    "nullable",
                    0,
                    {
                        "model_instance_id": model_id,
                        "weapon_instance_id": weapon_instance_id,
                        "weapon_profile_id": profile_id,
                        "firing_deck_source_unit_instance_id": source_unit_id,
                        "firing_deck_source_model_instance_id": source_model_id,
                        "shooting_type": nullable_type,
                    },
                ),
            )
        )
        for candidate_kind, candidate_index, candidate in (*candidate_rows, *fallback_rows):
            if (
                candidate.get("weapon_instance_id") != weapon_instance_id
                or candidate.get("weapon_profile_id") != profile_id
            ):
                continue
            if candidate_kind == "target":
                if candidate.get("is_legal") is not True:
                    continue
                target_id = _text(candidate.get("target_unit_instance_id")) or None
                shooting_type = _first_string(candidate.get("shooting_types"))
                if "firing_deck_source_unit_instance_id" in candidate and (
                    candidate.get("firing_deck_source_unit_instance_id") != source_unit_id
                    or candidate.get("firing_deck_source_model_instance_id") != source_model_id
                ):
                    continue
            else:
                if (
                    candidate.get("model_instance_id") != model_id
                    or candidate.get("firing_deck_source_unit_instance_id") != source_unit_id
                    or candidate.get("firing_deck_source_model_instance_id") != source_model_id
                ):
                    continue
                target_id = None
                shooting_type = _text(candidate.get("shooting_type"))
            if (candidate_kind == "target" and target_id is None) or not shooting_type:
                continue
            option_sets = _shooting_ability_option_sets(candidate, diagnostics=diagnostics)
            if option_sets is None:
                continue
            for chosen_options in product(*option_sets):
                selected_ids = tuple(option_id for option_id, _ in chosen_options)
                selection = ShootingAssignmentSelection(
                    model_instance_id=model_id,
                    weapon_instance_id=weapon_instance_id,
                    weapon_profile_id=profile_id,
                    target_unit_instance_id=target_id,
                    firing_deck_source_unit_instance_id=source_unit_id,
                    firing_deck_source_model_instance_id=source_model_id,
                    selected_weapon_ability_ids=selected_ids,
                )
                source_labels = tuple(label for _, label in chosen_options)
                target_label = "no target" if target_id is None else _short(target_id)
                label = f"{_short(model_id)} {_short(weapon_instance_id)} -> {target_label}"
                if source_labels:
                    label += f" ({', '.join(source_labels)})"
                choices.append(
                    ShootingAssignmentChoice(
                        choice_id=_shooting_choice_id(
                            request_id=request_id,
                            candidate_kind=candidate_kind,
                            candidate_index=candidate_index,
                            selection=selection,
                        ),
                        selection=selection,
                        label=label,
                        source_ref_keys=(f"model:{model_id}",),
                        target_ref_keys=() if target_id is None else (f"unit:{target_id}",),
                        summary_lines=(
                            f"Physical weapon: {weapon_instance_id}",
                            f"Weapon profile: {profile_id}",
                            f"Shooting type: {shooting_type}",
                            *(f"Weapon ability source: {option_id}" for option_id in selected_ids),
                            *(
                                (f"Firing Deck source: {source_unit_id} / {source_model_id}",)
                                if source_unit_id is not None
                                else ()
                            ),
                            *_shooting_limit_lines(
                                selection_limits=selection_limits,
                                model_id=model_id,
                                weapon_profile_id=profile_id,
                            ),
                        ),
                    )
                )
    return tuple(choices)


def _shooting_choice_id(
    *,
    request_id: str,
    candidate_kind: str,
    candidate_index: int,
    selection: ShootingAssignmentSelection,
) -> str:
    parts = (
        request_id,
        candidate_kind,
        str(candidate_index),
        selection.model_instance_id,
        selection.weapon_instance_id,
        selection.weapon_profile_id,
        selection.target_unit_instance_id or "",
        selection.firing_deck_source_unit_instance_id or "",
        selection.firing_deck_source_model_instance_id or "",
        *selection.selected_weapon_ability_ids,
    )
    return "shooting-choice:" + "".join(f"{len(part)}:{part}" for part in parts)


def _shooting_weapon_matches_selection(
    weapon: JsonObject,
    selection: ShootingAssignmentSelection,
) -> bool:
    return (
        weapon.get("model_instance_id") == selection.model_instance_id
        and weapon.get("weapon_instance_id") == selection.weapon_instance_id
        and weapon.get("weapon_profile_id") == selection.weapon_profile_id
        and weapon.get("firing_deck_source_unit_instance_id")
        == selection.firing_deck_source_unit_instance_id
        and weapon.get("firing_deck_source_model_instance_id")
        == selection.firing_deck_source_model_instance_id
    )


def _shooting_weapon_for_selection(
    *,
    available_weapons: tuple[JsonObject, ...],
    selection: ShootingAssignmentSelection,
    diagnostics: list[str],
) -> JsonObject | None:
    matches = tuple(
        weapon
        for weapon in available_weapons
        if _shooting_weapon_matches_selection(weapon, selection)
    )
    if len(matches) != 1:
        diagnostics.append("Shooting selection must reference one engine-offered physical row.")
        return None
    return matches[0]


def _default_shooting_selection(
    *,
    weapon: JsonObject,
    target_candidates: tuple[JsonObject, ...],
) -> ShootingAssignmentSelection | None:
    model_id = _text(weapon.get("model_instance_id"))
    weapon_instance_id = _text(weapon.get("weapon_instance_id"))
    profile_id = _text(weapon.get("weapon_profile_id"))
    if not model_id or not weapon_instance_id or not profile_id:
        return None
    selection = ShootingAssignmentSelection(
        model_instance_id=model_id,
        weapon_instance_id=weapon_instance_id,
        weapon_profile_id=profile_id,
        target_unit_instance_id=None,
        firing_deck_source_unit_instance_id=_text(weapon.get("firing_deck_source_unit_instance_id"))
        or None,
        firing_deck_source_model_instance_id=_text(
            weapon.get("firing_deck_source_model_instance_id")
        )
        or None,
    )
    for candidate in target_candidates:
        if (
            candidate.get("is_legal") is True
            and candidate.get("weapon_instance_id") == weapon_instance_id
            and candidate.get("weapon_profile_id") == profile_id
            and _first_string(candidate.get("shooting_types"))
            and (target_id := _text(candidate.get("target_unit_instance_id")))
        ):
            return ShootingAssignmentSelection(
                model_instance_id=selection.model_instance_id,
                weapon_instance_id=selection.weapon_instance_id,
                weapon_profile_id=selection.weapon_profile_id,
                target_unit_instance_id=target_id,
                firing_deck_source_unit_instance_id=(selection.firing_deck_source_unit_instance_id),
                firing_deck_source_model_instance_id=(
                    selection.firing_deck_source_model_instance_id
                ),
            )
    return None


def _shooting_candidate_for_selection(
    *,
    target_candidates: tuple[JsonObject, ...],
    targetless_candidates: tuple[JsonObject, ...],
    selection: ShootingAssignmentSelection,
) -> JsonObject | None:
    if selection.target_unit_instance_id is None:
        return next(
            (
                candidate
                for candidate in targetless_candidates
                if candidate.get("weapon_instance_id") == selection.weapon_instance_id
                and candidate.get("weapon_profile_id") == selection.weapon_profile_id
                and candidate.get("model_instance_id") == selection.model_instance_id
                and candidate.get("firing_deck_source_unit_instance_id")
                == selection.firing_deck_source_unit_instance_id
                and candidate.get("firing_deck_source_model_instance_id")
                == selection.firing_deck_source_model_instance_id
            ),
            None,
        )
    return next(
        (
            candidate
            for candidate in target_candidates
            if candidate.get("is_legal") is True
            and candidate.get("weapon_instance_id") == selection.weapon_instance_id
            and candidate.get("weapon_profile_id") == selection.weapon_profile_id
            and candidate.get("target_unit_instance_id") == selection.target_unit_instance_id
            and _first_string(candidate.get("shooting_types"))
        ),
        None,
    )


def _shooting_type_for_selection(
    *,
    proposal_payload: JsonObject,
    selection: ShootingAssignmentSelection,
    candidate: JsonObject | None,
    target_candidates: tuple[JsonObject, ...],
) -> str:
    if selection.target_unit_instance_id is not None:
        return "" if candidate is None else _first_string(candidate.get("shooting_types"))
    if candidate is not None:
        return _text(candidate.get("shooting_type"))
    selected_type = _text(proposal_payload.get("selected_shooting_type"))
    if selected_type:
        return selected_type
    for row in target_candidates:
        if (
            row.get("is_legal") is True
            and row.get("weapon_instance_id") == selection.weapon_instance_id
            and row.get("weapon_profile_id") == selection.weapon_profile_id
            and (shooting_type := _first_string(row.get("shooting_types")))
        ):
            return shooting_type
    return ""


def _shooting_limit_lines(
    *,
    selection_limits: tuple[JsonObject, ...],
    model_id: str,
    weapon_profile_id: str,
) -> tuple[str, ...]:
    return tuple(
        f"Engine selection limit: {limit['max_selections']} "
        f"{_text(limit.get('weapon_keyword'))} per model"
        for limit in selection_limits
        if limit.get("model_instance_id") == model_id
        and type(limit.get("max_selections")) is int
        and weapon_profile_id in _string_list(limit.get("weapon_profile_ids"))
    )


def _firing_deck_selection_preview(
    *,
    request_payload: JsonObject,
    declarations: list[JsonValue],
    diagnostics: list[str],
    explicit_selection: JsonObject | None,
) -> JsonValue | None:
    if explicit_selection is not None:
        return validate_json_value(explicit_selection)
    request_selection = request_payload.get("firing_deck_selection")
    if request_selection is not None:
        return validate_json_value(request_selection)
    uses_firing_deck = any(
        type(declaration) is dict
        and (
            declaration.get("firing_deck_source_unit_instance_id") is not None
            or declaration.get("firing_deck_source_model_instance_id") is not None
        )
        for declaration in declarations
    )
    if uses_firing_deck:
        diagnostics.append(
            "Firing Deck needs public already-shot-unit and weapon selection evidence."
        )
    return None


def _selected_weapon_ability_ids(
    candidate: JsonObject,
    *,
    selected_ids: tuple[str, ...],
    diagnostics: list[str],
) -> tuple[str, ...] | None:
    option_sets = _shooting_ability_option_sets(candidate, diagnostics=diagnostics)
    if option_sets is None:
        return None
    if not option_sets:
        if selected_ids:
            diagnostics.append("Selected weapon ability ID was not offered for this weapon choice.")
            return None
        return ()
    resolved_ids: list[str] = []
    if len(selected_ids) > len(option_sets):
        diagnostics.append("Selected weapon ability IDs exceed the emitted source families.")
        return None
    for index, options in enumerate(option_sets):
        if index < len(selected_ids):
            if selected_ids[index] not in (option_id for option_id, _ in options):
                diagnostics.append(
                    "Selected weapon ability ID was not emitted for its source family."
                )
                return None
            option_id = selected_ids[index]
        elif len(options) == 1:
            option_id = options[0][0]
        else:
            diagnostics.append(
                "Duplicate weapon ability selection needs an explicit source choice."
            )
            return None
        resolved_ids.append(option_id)
    return tuple(resolved_ids)


def _shooting_ability_option_sets(
    candidate: JsonObject,
    *,
    diagnostics: list[str],
) -> tuple[tuple[tuple[str, str], ...], ...] | None:
    selection_requests = candidate.get("required_weapon_ability_selections")
    if selection_requests is None:
        return ()
    if type(selection_requests) is not list:
        diagnostics.append("Required weapon ability selections are malformed.")
        return None
    option_sets: list[tuple[tuple[str, str], ...]] = []
    for raw_request in selection_requests:
        if type(raw_request) is not dict:
            diagnostics.append("Required weapon ability selection request is malformed.")
            return None
        options = raw_request.get("options")
        if type(options) is not list or not options:
            diagnostics.append("Required weapon ability selection options are malformed.")
            return None
        option_set: list[tuple[str, str]] = []
        for raw_option in options:
            if type(raw_option) is not dict:
                diagnostics.append("Required weapon ability selection option is malformed.")
                return None
            option_id = _text(raw_option.get("option_id"))
            if not option_id:
                diagnostics.append("Required weapon ability selection option is missing option_id.")
                return None
            option_set.append((option_id, _text(raw_option.get("label")) or option_id))
        option_sets.append(tuple(option_set))
    return tuple(option_sets)


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


def _heroic_source_modes(
    catalog_record: JsonObject | None, *, diagnostics: list[str]
) -> tuple[str, ...]:
    if catalog_record is None:
        return ()
    definition = catalog_record.get("definition")
    if type(definition) is not dict or definition.get("handler_id") != "core:heroic-intervention":
        return ()
    target_spec = definition.get("target_spec")
    effect = definition.get("effect_payload")
    mode_rows = None if type(effect) is not dict else effect.get("modes")
    if (
        type(target_spec) is not dict
        or target_spec.get("target_kind") != "friendly_unit"
        or type(mode_rows) is not list
    ):
        diagnostics.append("Heroic Intervention source lacks a friendly target or mode list.")
        return ()
    modes: list[str] = []
    for row in mode_rows:
        mode = None if type(row) is not dict else _text(row.get("mode"))
        if not mode or mode in modes:
            diagnostics.append("Heroic Intervention source contains an invalid mode.")
            return ()
        modes.append(mode)
    if not modes:
        diagnostics.append("Heroic Intervention source offers no effect modes.")
    return tuple(modes)


def _source_allows_friendly_target_intent(catalog_record: JsonObject | None) -> bool:
    if catalog_record is None:
        return False
    definition = catalog_record.get("definition")
    target_spec = None if type(definition) is not dict else definition.get("target_spec")
    return (
        type(target_spec) is dict
        and target_spec.get("target_kind") == "friendly_unit"
        and target_spec.get("enumerable") is False
    )


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


def _optional_json_object_list(
    payload: JsonObject,
    *,
    key: str,
    diagnostics: list[str],
) -> tuple[JsonObject, ...]:
    if key not in payload:
        return ()
    return _json_object_list(payload[key], key=key, diagnostics=diagnostics)


def _string_list(value: object) -> tuple[str, ...]:
    if type(value) is not list:
        return ()
    return tuple(item for item in cast(list[object], value) if type(item) is str)


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
