"""Current public membership for a finite attached Scout option's local focus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeGuard

from warhammer40k_arcade_ui.core_client.protocol import JsonValue, UiDecision, UiFiniteOption
from warhammer40k_arcade_ui.render.view_models import BattlefieldView, UnitView


@dataclass(frozen=True, slots=True)
class AttachedScoutSelection:
    """Validated physical members of one current canonical Scout option."""

    option_id: str
    canonical_unit_id: str
    player_id: str
    component_unit_ids: tuple[str, ...]
    model_ids: tuple[str, ...]

    def unit_view(self, view: BattlefieldView) -> UnitView | None:
        """Represent current component bases as one advisory selection overlay."""

        components = tuple(unit for unit in view.units if unit.unit_id in self.component_unit_ids)
        if (
            len(components) != len(self.component_unit_ids)
            or {unit.unit_id for unit in components} != set(self.component_unit_ids)
            or any(unit.player_id != self.player_id for unit in components)
        ):
            return None
        physical_model_ids = tuple(model.model_id for unit in components for model in unit.models)
        if len(physical_model_ids) != len(self.model_ids) or set(physical_model_ids) != set(
            self.model_ids
        ):
            return None
        return UnitView(
            unit_id=self.canonical_unit_id,
            player_id=self.player_id,
            label=self.canonical_unit_id,
            models=tuple(model for unit in components for model in unit.models),
        )


def is_attached_scout_option(option: UiFiniteOption) -> bool:
    """Identify the option shape that requires physical component membership."""

    payload = option.payload
    return (
        type(payload) is dict
        and payload.get("action_kind") == "scout_move"
        and payload.get("is_attached_rules_unit") is True
    )


def attached_scout_selection(
    *,
    decision: UiDecision | None,
    option: UiFiniteOption | None,
    view: BattlefieldView,
    viewer_player_id: str,
) -> AttachedScoutSelection | None:
    """Resolve only exact current option membership visible to its acting viewer."""

    if (
        decision is None
        or option is None
        or not viewer_player_id
        or decision.decision_type != "select_prebattle_action"
        or decision.is_parameterized
        or decision.actor_id != viewer_player_id
        or option not in decision.options
        or not is_attached_scout_option(option)
    ):
        return None
    payload = option.payload
    assert type(payload) is dict
    canonical_id = payload.get("unit_instance_id")
    component_ids = payload.get("component_unit_instance_ids")
    model_ids = payload.get("model_instance_ids")
    if (
        payload.get("player_id") != decision.actor_id
        or type(canonical_id) is not str
        or not canonical_id
        or any(unit.unit_id == canonical_id for unit in view.units)
        or not _unique_nonempty_strings(component_ids)
        or not _unique_nonempty_strings(model_ids)
    ):
        return None
    components = tuple(unit for unit in view.units if unit.unit_id in component_ids)
    if (
        len(components) != len(component_ids)
        or {unit.unit_id for unit in components} != set(component_ids)
        or any(unit.player_id != decision.actor_id for unit in components)
    ):
        return None
    physical_model_ids = tuple(model.model_id for unit in components for model in unit.models)
    if len(physical_model_ids) != len(model_ids) or set(physical_model_ids) != set(model_ids):
        return None
    return AttachedScoutSelection(
        option_id=option.option_id,
        canonical_unit_id=canonical_id,
        player_id=viewer_player_id,
        component_unit_ids=tuple(component_ids),
        model_ids=tuple(model_ids),
    )


def _unique_nonempty_strings(value: JsonValue) -> TypeGuard[list[str]]:
    return (
        type(value) is list
        and bool(value)
        and all(type(item) is str and bool(item) for item in value)
        and len(value) == len(set(value))
    )
