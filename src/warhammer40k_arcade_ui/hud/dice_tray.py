"""Presentation-only dice tray view models and event reducers."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import cast

from warhammer40k_arcade_ui.core_client.protocol import UiDecision, UiFiniteOption
from warhammer40k_arcade_ui.preferences.schema import JsonObject, JsonValue

DICE_REROLL_DECISION_TYPE = "select_dice_reroll"
AELDARI_D6_FACE_ASSET_IDS: dict[int, str] = {
    1: "dice.aeldari.d6.face_1",
    2: "dice.aeldari.d6.face_2",
    3: "dice.aeldari.d6.face_3",
    4: "dice.aeldari.d6.face_4",
    5: "dice.aeldari.d6.face_5",
    6: "dice.aeldari.d6.face_6",
}


@dataclass(frozen=True, slots=True)
class DiceComponentView:
    """One displayed die component."""

    index: int
    value: int
    sides: int
    selectable: bool = False
    rerolled: bool = False


@dataclass(frozen=True, slots=True)
class DiceFaceColumnView:
    """One D6 face column in the tray."""

    face: int
    asset_id: str
    count: int
    component_indices: tuple[int, ...]
    selectable_count: int = 0


@dataclass(frozen=True, slots=True)
class DiceRerollOptionView:
    """One engine-provided reroll option."""

    option_id: str
    label: str
    selected_indices: tuple[int, ...]
    is_decline: bool = False


@dataclass(frozen=True, slots=True)
class DiceRerollRequestView:
    """Pending dice reroll request summary."""

    request_id: str
    roll_id: str
    roll_type: str
    current_values: tuple[int, ...]
    allowed_selections: tuple[tuple[int, ...], ...]
    options: tuple[DiceRerollOptionView, ...]


@dataclass(frozen=True, slots=True)
class DiceRollView:
    """Latest viewer-visible dice roll snapshot."""

    roll_id: str
    roll_type: str
    title: str
    subtitle: str
    values: tuple[int, ...]
    sides: int
    total: int | None
    source: str
    components: tuple[DiceComponentView, ...]


@dataclass(frozen=True, slots=True)
class DiceTrayView:
    """Full presentation snapshot for the HUD dice tray."""

    title: str
    subtitle: str
    active_roll: DiceRollView | None
    face_columns: tuple[DiceFaceColumnView, ...]
    reroll_request: DiceRerollRequestView | None
    diagnostics: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        """Return whether the tray has no active roll or reroll request."""

        return self.active_roll is None and self.reroll_request is None


def build_dice_tray_view(
    *,
    event_payloads: tuple[JsonObject, ...],
    pending_decision: UiDecision | None,
) -> DiceTrayView:
    """Build the presentation-only dice tray from viewer-scoped events and current decision."""

    diagnostics: list[str] = []
    reroll_request = _pending_reroll_request(pending_decision, diagnostics=diagnostics)
    active_roll = _latest_roll(event_payloads)
    if reroll_request is not None and (
        active_roll is None or active_roll.roll_id != reroll_request.roll_id
    ):
        active_roll = _roll_from_pending_reroll(reroll_request)
    face_columns = _face_columns(active_roll, reroll_request)
    return DiceTrayView(
        title="Dice Tray",
        subtitle=_tray_subtitle(active_roll, reroll_request),
        active_roll=active_roll,
        face_columns=face_columns,
        reroll_request=reroll_request,
        diagnostics=tuple(diagnostics),
    )


def dice_tray_runtime_data(view: DiceTrayView) -> JsonObject:
    """Convert a dice tray view into JSON-safe HUD runtime data."""

    active_roll = view.active_roll
    reroll_request = view.reroll_request
    return {
        "title": view.title,
        "subtitle": view.subtitle,
        "summary": view.subtitle,
        "roll_id": "" if active_roll is None else active_roll.roll_id,
        "roll_type": "" if active_roll is None else active_roll.roll_type,
        "values": [] if active_roll is None else list(active_roll.values),
        "total": None if active_roll is None else active_roll.total,
        "source": "" if active_roll is None else active_roll.source,
        "faces": [
            {
                "face": column.face,
                "asset_id": column.asset_id,
                "count": column.count,
                "component_indices": list(column.component_indices),
                "selectable_count": column.selectable_count,
            }
            for column in view.face_columns
        ],
        "reroll_request": None
        if reroll_request is None
        else {
            "request_id": reroll_request.request_id,
            "roll_id": reroll_request.roll_id,
            "roll_type": reroll_request.roll_type,
            "current_values": list(reroll_request.current_values),
            "allowed_selections": [
                list(selection) for selection in reroll_request.allowed_selections
            ],
            "options": [
                {
                    "option_id": option.option_id,
                    "label": option.label,
                    "selected_indices": list(option.selected_indices),
                    "is_decline": option.is_decline,
                }
                for option in reroll_request.options
            ],
        },
        "diagnostics": list(view.diagnostics),
    }


def _latest_roll(event_payloads: tuple[JsonObject, ...]) -> DiceRollView | None:
    for event in reversed(event_payloads):
        event_type = _string(event.get("event_type")) or _string(event.get("type")) or ""
        payload = _object_or_none(event.get("payload"))
        if payload is None:
            continue
        if event_type == "dice_rolled":
            roll = _roll_from_result_payload(payload, title=None)
            if roll is not None:
                return roll
        if event_type == "advance_roll_resolved":
            advance_roll = _object_or_none(payload.get("advance_roll"))
            if advance_roll is not None:
                roll = _roll_from_roll_state_envelope(
                    advance_roll,
                    title="Advance roll",
                    subtitle=_unit_subtitle(advance_roll),
                    source_key="value",
                )
                if roll is not None:
                    return roll
        if event_type == "charge_roll_resolved":
            roll_result = _object_or_none(payload.get("roll_result"))
            if roll_result is not None:
                roll = _roll_from_roll_state_envelope(
                    roll_result,
                    title="Charge roll",
                    subtitle=_charge_subtitle(payload),
                    source_key="value",
                )
                if roll is not None:
                    return roll
        roll = _first_roll_from_payload(payload, event_type=event_type)
        if roll is not None:
            return roll
    return None


def _first_roll_from_payload(payload: JsonObject, *, event_type: str) -> DiceRollView | None:
    roll_state = _find_roll_state(payload)
    if roll_state is None:
        return None
    return _roll_from_roll_state_payload(
        roll_state,
        title=_friendly_roll_title(event_type),
        subtitle=event_type,
    )


def _find_roll_state(value: JsonValue) -> JsonObject | None:
    if type(value) is dict:
        if "original_result" in value and "current_values" in value:
            return value
        for nested in value.values():
            found = _find_roll_state(nested)
            if found is not None:
                return found
    if type(value) is list:
        for nested in value:
            found = _find_roll_state(nested)
            if found is not None:
                return found
    return None


def _roll_from_roll_state_envelope(
    payload: JsonObject,
    *,
    title: str,
    subtitle: str,
    source_key: str,
) -> DiceRollView | None:
    roll_state = _object_or_none(payload.get("roll_state"))
    if roll_state is None:
        return None
    roll = _roll_from_roll_state_payload(roll_state, title=title, subtitle=subtitle)
    if roll is None:
        return None
    value = _int_or_none(payload.get(source_key))
    if value is None:
        return roll
    return DiceRollView(
        roll_id=roll.roll_id,
        roll_type=roll.roll_type,
        title=roll.title,
        subtitle=roll.subtitle,
        values=roll.values,
        sides=roll.sides,
        total=value,
        source=roll.source,
        components=roll.components,
    )


def _roll_from_roll_state_payload(
    roll_state: JsonObject,
    *,
    title: str,
    subtitle: str,
) -> DiceRollView | None:
    original = _object_or_none(roll_state.get("original_result"))
    if original is None:
        return None
    current_values = _int_tuple(roll_state.get("current_values"))
    current_total = _int_or_none(roll_state.get("current_total"))
    roll = _roll_from_result_payload(original, title=title)
    if roll is None:
        return None
    values = current_values or roll.values
    return DiceRollView(
        roll_id=roll.roll_id,
        roll_type=roll.roll_type,
        title=title,
        subtitle=subtitle or roll.subtitle,
        values=values,
        sides=roll.sides,
        total=current_total if current_total is not None else roll.total,
        source=roll.source,
        components=_components(values=values, sides=roll.sides, roll_state=roll_state),
    )


def _roll_from_result_payload(payload: JsonObject, *, title: str | None) -> DiceRollView | None:
    roll_id = _string(payload.get("roll_id"))
    spec = _object_or_none(payload.get("spec"))
    values = _int_tuple(payload.get("values"))
    if roll_id is None or spec is None or not values:
        return None
    expression = _object_or_none(spec.get("expression")) or {}
    sides = _positive_int_or_default(expression.get("sides"), default=6)
    roll_type = _string(spec.get("roll_type")) or "dice_roll"
    reason = _string(spec.get("reason")) or _friendly_roll_title(roll_type)
    return DiceRollView(
        roll_id=roll_id,
        roll_type=roll_type,
        title=title or _friendly_roll_title(roll_type),
        subtitle=reason,
        values=values,
        sides=sides,
        total=_int_or_none(payload.get("total")),
        source=_string(payload.get("source")) or "",
        components=_components(values=values, sides=sides, roll_state=None),
    )


def _components(
    *,
    values: tuple[int, ...],
    sides: int,
    roll_state: JsonObject | None,
) -> tuple[DiceComponentView, ...]:
    rerolled_indices = _rerolled_indices(roll_state)
    return tuple(
        DiceComponentView(
            index=index,
            value=value,
            sides=sides,
            rerolled=index in rerolled_indices,
        )
        for index, value in enumerate(values)
    )


def _rerolled_indices(roll_state: JsonObject | None) -> frozenset[int]:
    if roll_state is None:
        return frozenset()
    rerolls = roll_state.get("rerolls")
    if type(rerolls) is not list:
        return frozenset()
    indices: set[int] = set()
    for reroll in rerolls:
        reroll_payload = _object_or_none(reroll)
        if reroll_payload is None:
            continue
        selected = _int_tuple(reroll_payload.get("selected_indices"))
        indices.update(selected)
    return frozenset(indices)


def _pending_reroll_request(
    pending_decision: UiDecision | None,
    *,
    diagnostics: list[str],
) -> DiceRerollRequestView | None:
    if pending_decision is None or pending_decision.decision_type != DICE_REROLL_DECISION_TYPE:
        return None
    payload = _object_or_none(pending_decision.payload)
    if payload is None:
        diagnostics.append("Pending dice reroll request has no object payload.")
        return None
    roll_id = _string(payload.get("roll_id"))
    roll_type = _string(payload.get("roll_type")) or "dice_reroll"
    current_values = _int_tuple(payload.get("current_values"))
    allowed = _selection_tuple(payload.get("allowed_selections"))
    if roll_id is None:
        diagnostics.append("Pending dice reroll request is missing roll_id.")
        roll_id = "unknown-roll"
    options = tuple(_reroll_option(option) for option in pending_decision.options)
    return DiceRerollRequestView(
        request_id=pending_decision.request_id,
        roll_id=roll_id,
        roll_type=roll_type,
        current_values=current_values,
        allowed_selections=allowed,
        options=options,
    )


def _reroll_option(option: UiFiniteOption) -> DiceRerollOptionView:
    selected_indices = _selected_indices_from_option(option)
    return DiceRerollOptionView(
        option_id=option.option_id,
        label=option.label,
        selected_indices=selected_indices,
        is_decline=option.option_id == "decline",
    )


def _selected_indices_from_option(option: UiFiniteOption) -> tuple[int, ...]:
    payload = _object_or_none(option.payload)
    if payload is not None:
        indices = _int_tuple(payload.get("selected_indices"))
        if indices:
            return indices
    if option.option_id.startswith("reroll:"):
        raw_indices = option.option_id.removeprefix("reroll:").split(",")
        parsed: list[int] = []
        for raw_index in raw_indices:
            try:
                parsed.append(int(raw_index))
            except ValueError:
                return ()
        return tuple(parsed)
    return ()


def _roll_from_pending_reroll(request: DiceRerollRequestView) -> DiceRollView:
    values = request.current_values
    return DiceRollView(
        roll_id=request.roll_id,
        roll_type=request.roll_type,
        title=_friendly_roll_title(request.roll_type),
        subtitle="Pending reroll decision",
        values=values,
        sides=6,
        total=sum(values) if values else None,
        source="current",
        components=tuple(
            DiceComponentView(
                index=index,
                value=value,
                sides=6,
                selectable=any(index in selection for selection in request.allowed_selections),
            )
            for index, value in enumerate(values)
        ),
    )


def _face_columns(
    active_roll: DiceRollView | None,
    reroll_request: DiceRerollRequestView | None,
) -> tuple[DiceFaceColumnView, ...]:
    values = () if active_roll is None else active_roll.values
    counts = Counter(values)
    selectable_indices = _selectable_indices(reroll_request)
    component_indices_by_face: dict[int, list[int]] = {face: [] for face in range(1, 7)}
    selectable_counts: dict[int, int] = dict.fromkeys(range(1, 7), 0)
    if active_roll is not None:
        for component in active_roll.components:
            if 1 <= component.value <= 6:
                component_indices_by_face[component.value].append(component.index)
                if component.index in selectable_indices:
                    selectable_counts[component.value] += 1
    return tuple(
        DiceFaceColumnView(
            face=face,
            asset_id=AELDARI_D6_FACE_ASSET_IDS[face],
            count=counts[face],
            component_indices=tuple(component_indices_by_face[face]),
            selectable_count=selectable_counts[face],
        )
        for face in range(1, 7)
    )


def _selectable_indices(request: DiceRerollRequestView | None) -> frozenset[int]:
    if request is None:
        return frozenset()
    indices: set[int] = set()
    for selection in request.allowed_selections:
        indices.update(selection)
    return frozenset(indices)


def _tray_subtitle(
    active_roll: DiceRollView | None,
    reroll_request: DiceRerollRequestView | None,
) -> str:
    if reroll_request is not None:
        return f"Reroll decision: {reroll_request.roll_type}"
    if active_roll is not None:
        total = "" if active_roll.total is None else f" total {active_roll.total}"
        return f"{active_roll.roll_type}{total}"
    return "No recent visible dice roll"


def _unit_subtitle(payload: JsonObject) -> str:
    request = _object_or_none(payload.get("request"))
    unit_id = "" if request is None else _string(request.get("unit_instance_id")) or ""
    value = _int_or_none(payload.get("value"))
    if unit_id and value is not None:
        return f"{unit_id}: +{value} in"
    if value is not None:
        return f"+{value} in"
    return unit_id


def _charge_subtitle(payload: JsonObject) -> str:
    unit_id = _string(payload.get("unit_instance_id")) or ""
    distance = _int_or_none(payload.get("maximum_distance_inches"))
    if unit_id and distance is not None:
        return f"{unit_id}: {distance} in"
    if distance is not None:
        return f"{distance} in"
    return unit_id


def _friendly_roll_title(roll_type: str) -> str:
    text = roll_type.replace("attack_sequence.", "").replace("_", " ").replace(".", " ")
    if not text:
        return "Dice roll"
    return text[:1].upper() + text[1:]


def _selection_tuple(value: JsonValue | None) -> tuple[tuple[int, ...], ...]:
    if type(value) is not list:
        return ()
    selections: list[tuple[int, ...]] = []
    for item in value:
        selection = _int_tuple(item)
        selections.append(selection)
    return tuple(selections)


def _int_tuple(value: JsonValue | None) -> tuple[int, ...]:
    if type(value) is not list:
        return ()
    values: list[int] = []
    for item in value:
        if type(item) is not int:
            return ()
        values.append(item)
    return tuple(values)


def _positive_int_or_default(value: JsonValue | None, *, default: int) -> int:
    if type(value) is int and value > 0:
        return value
    return default


def _int_or_none(value: JsonValue | None) -> int | None:
    if type(value) is int:
        return value
    return None


def _string(value: JsonValue | None) -> str | None:
    if type(value) is str and value:
        return value
    return None


def _object_or_none(value: object) -> JsonObject | None:
    if type(value) is dict:
        return cast(JsonObject, value)
    return None
