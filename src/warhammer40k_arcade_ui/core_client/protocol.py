"""UI-facing protocol types for core engine sessions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, Self, cast

PARAMETERIZED_DECISION_OPTION_ID = "submit_parameterized_payload"
PARAMETERIZED_DECISION_OPTION_PAYLOAD: JsonValue = {"submission_kind": "parameterized"}

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


class UiClientProtocolError(ValueError):
    """Raised when a core-facing payload cannot be represented by the UI protocol."""


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

    def submit_finite(
        self,
        *,
        request_id: str,
        selected_option_id: str,
        result_id: str | None = None,
    ) -> UiClientStatus:
        """Submit an engine-provided finite option for an explicit request ID."""

        ...

    def submit_movement_payload(
        self,
        *,
        request_id: str,
        payload: JsonValue,
        result_id: str | None = None,
    ) -> UiClientStatus:
        """Submit a movement proposal payload for an explicit request ID."""

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


@dataclass(frozen=True, slots=True)
class UiMovementProposalRequest:
    """UI view of an engine movement or placement proposal request."""

    request_id: str
    decision_type: str
    actor_id: str
    game_id: str
    battle_round: int
    phase: str
    unit_instance_id: str
    proposal_kind: str
    source_decision_request_id: str
    source_decision_result_id: str
    movement_phase_action: str | None
    placement_kinds: tuple[str, ...]
    context: JsonObject

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _non_empty_string("request_id", self.request_id))
        object.__setattr__(
            self,
            "decision_type",
            _non_empty_string("decision_type", self.decision_type),
        )
        object.__setattr__(self, "actor_id", _non_empty_string("actor_id", self.actor_id))
        object.__setattr__(self, "game_id", _non_empty_string("game_id", self.game_id))
        if type(self.battle_round) is not int or self.battle_round <= 0:
            raise UiClientProtocolError("battle_round must be a positive integer.")
        object.__setattr__(self, "phase", _non_empty_string("phase", self.phase))
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

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        proposal = _json_object("movement proposal request payload", payload)
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
        )

    @classmethod
    def from_decision_payload(cls, payload: JsonValue) -> Self:
        decision_payload = _json_object("parameterized decision payload", payload)
        return cls.from_payload(decision_payload["proposal_request"])


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
    ) -> Self:
        decision_payload = _json_object("parameterized decision payload", payload)
        proposal_payload = _json_object(
            "parameterized proposal request",
            decision_payload["proposal_request"],
        )
        return cls.from_payload(proposal_payload)


@dataclass(frozen=True, slots=True)
class UiDecision:
    """Current pending decision as a UI-facing view model."""

    request_id: str
    decision_type: str
    actor_id: str | None
    payload: JsonValue
    options: tuple[UiFiniteOption, ...]
    is_parameterized: bool
    parameterized_proposal: UiParameterizedProposalRequest | None = None
    movement_proposal: UiMovementProposalRequest | None = None

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

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        decision = _json_object("decision payload", payload)
        raw_options = _json_list("decision options", decision["options"])
        options = tuple(UiFiniteOption.from_payload(option) for option in raw_options)
        is_parameterized = _optional_bool(decision, "is_parameterized")
        if is_parameterized is None:
            is_parameterized = _options_are_parameterized(options)
        decision_payload = decision["payload"]
        request_id = _required_string(decision, "request_id")
        decision_type = _required_string(decision, "decision_type")
        actor_id = _optional_string_value(decision, "actor_id")
        parameterized_proposal = (
            UiParameterizedProposalRequest.from_decision_payload(
                payload=decision_payload,
            )
            if is_parameterized
            else None
        )
        return cls(
            request_id=request_id,
            decision_type=decision_type,
            actor_id=actor_id,
            payload=decision_payload,
            options=options,
            is_parameterized=is_parameterized,
            parameterized_proposal=parameterized_proposal,
            movement_proposal=_movement_proposal_from_parameterized(parameterized_proposal),
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
    event_count: int

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        view = _json_object("game view payload", payload)
        pending_decision_payload = view["pending_decision"]
        pending_proposal_payload = view["pending_proposal"]
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
            pending_decision=(
                None
                if pending_decision_payload is None
                else UiDecision.from_payload(pending_decision_payload)
            ),
            pending_proposal=(
                None
                if pending_proposal_payload is None
                else UiParameterizedProposalRequest.from_payload(pending_proposal_payload)
            ),
            event_count=_required_int(view, "event_count"),
        )


@dataclass(frozen=True, slots=True)
class UiEventDelta:
    """Viewer-scoped event-stream delta."""

    viewer_player_id: str
    cursor: int
    next_cursor: int
    events: tuple[JsonObject, ...]

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        event_payload = _json_object("event delta payload", payload)
        return cls(
            viewer_player_id=_required_string(event_payload, "viewer_player_id"),
            cursor=_required_int(event_payload, "cursor"),
            next_cursor=_required_int(event_payload, "next_cursor"),
            events=tuple(
                _json_object("event payload", event)
                for event in _json_list("events", event_payload["events"])
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
            return ()
        return (
            UiInvalidDiagnostic(
                violation_code="invalid_status",
                message=message,
            ),
        )
    body = _json_object("invalid status payload", payload)
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
        return ()
    return (
        UiInvalidDiagnostic(
            violation_code="invalid_status",
            message=message,
        ),
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
) -> UiMovementProposalRequest | None:
    if proposal is None or not _payload_has_movement_proposal_shape(proposal.payload):
        return None
    return UiMovementProposalRequest.from_payload(proposal.payload)


def _payload_has_movement_proposal_shape(payload: JsonObject) -> bool:
    required_keys = (
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
        "placement_kinds",
        "context",
    )
    return all(key in payload for key in required_keys)


def _options_are_parameterized(options: tuple[UiFiniteOption, ...]) -> bool:
    return options == (
        UiFiniteOption(
            option_id=PARAMETERIZED_DECISION_OPTION_ID,
            label="Submit Parameterized Payload",
            payload=PARAMETERIZED_DECISION_OPTION_PAYLOAD,
        ),
    )


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


def _required_int(payload: JsonObject, key: str) -> int:
    value = _required_value(payload, key)
    if type(value) is not int:
        raise UiClientProtocolError(f"{key} must be an integer.")
    return value


def _required_value(payload: JsonObject, key: str) -> JsonValue:
    if key not in payload:
        raise UiClientProtocolError(f"{key} is required.")
    return payload[key]


def _optional_bool(payload: JsonObject, key: str) -> bool | None:
    value = payload.get(key)
    if value is None:
        return None
    if type(value) is not bool:
        raise UiClientProtocolError(f"{key} must be a bool.")
    return value


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
