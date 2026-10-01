"""Public-facade live-core startup harness for manual UI smoke testing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from warhammer40k_core.adapters.setup_smoke import canonical_setup_prebattle_smoke_config

from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    JsonValue,
    UiClientStatus,
    UiDecision,
    UiGameView,
    UiRulesCatalogView,
    UiSupportProfile,
    validate_json_value,
)
from warhammer40k_arcade_ui.render.core_projection import (
    CoreProjectionRenderError,
    battlefield_view_from_game_view,
)
from warhammer40k_arcade_ui.render.view_models import BattlefieldView

LIVE_CORE_SMOKE_VIEWER_PLAYER_ID = "player-a"
LIVE_CORE_SMOKE_FIXED_SECONDARY_OPTION_ID = "fixed:assassination:bring_it_down"
type LiveCoreSmokeStopPhase = Literal[
    "setup",
    "secondary-missions",
    "reserve-declarations",
    "deployment",
    "redeploy",
    "prebattle",
    "scout-move",
    "movement",
    "shooting",
    "charge",
    "fight",
]
LIVE_CORE_SMOKE_STOP_PHASES: tuple[LiveCoreSmokeStopPhase, ...] = (
    "setup",
    "secondary-missions",
    "reserve-declarations",
    "deployment",
    "redeploy",
    "prebattle",
    "scout-move",
    "movement",
    "shooting",
    "charge",
    "fight",
)

_SETUP_STOP_DECISION_TYPES = {
    "setup": "select_secondary_missions",
    "secondary-missions": "select_secondary_missions",
    "reserve-declarations": "select_reserve_declaration",
    "deployment": "select_deployment_unit",
    "redeploy": "select_redeploy_unit",
    "prebattle": "select_prebattle_action",
    "scout-move": "submit_scout_move",
}
_BATTLE_STOP_PHASES = {"movement", "shooting", "charge", "fight"}
_MAX_AUTOMATED_DECISIONS = 200


class LiveCoreSmokeError(ValueError):
    """Raised when public decisions cannot reach the requested smoke checkpoint."""


@dataclass(frozen=True, slots=True)
class LiveCoreSmokeStartup:
    """Prepared real-core session state for Arcade launch."""

    core_client: LocalSessionClient
    status: UiClientStatus
    game_view: UiGameView
    battlefield_view: BattlefieldView
    viewer_player_id: str
    event_cursor: int
    rules_catalog: UiRulesCatalogView
    support_profile: UiSupportProfile


def build_live_core_smoke_startup(
    *,
    viewer_player_id: str = LIVE_CORE_SMOKE_VIEWER_PLAYER_ID,
    stop_at_phase: str | None = None,
) -> LiveCoreSmokeStartup:
    """Start a canonical core session and reach a checkpoint using public decisions only."""

    stop_phase = _validated_stop_phase(stop_at_phase)
    client = LocalSessionClient()
    client.start_game(canonical_setup_prebattle_smoke_config())
    status = client.advance_until_decision_or_terminal()
    status = _drive_to_checkpoint(client=client, status=status, stop_phase=stop_phase)
    return _startup_from_status(
        client=client,
        status=status,
        stop_phase=stop_phase,
        default_viewer_player_id=viewer_player_id,
    )


def _drive_to_checkpoint(
    *,
    client: LocalSessionClient,
    status: UiClientStatus,
    stop_phase: LiveCoreSmokeStopPhase,
) -> UiClientStatus:
    current = status
    for result_index in range(1, _MAX_AUTOMATED_DECISIONS + 1):
        _raise_for_invalid_status(current)
        decision = current.decision
        if decision is None:
            if current.status_kind in {"complete", "terminal"}:
                raise LiveCoreSmokeError(
                    f"Game became terminal before smoke checkpoint {stop_phase!r}."
                )
            current = client.advance_until_decision_or_terminal()
            continue
        viewer_id = decision.actor_id or LIVE_CORE_SMOKE_VIEWER_PLAYER_ID
        view = client.get_view(viewer_id)
        if _is_requested_checkpoint(
            stop_phase=stop_phase,
            decision=decision,
            view=view,
        ):
            return current
        result_id = f"ui-live-smoke-{result_index:06d}"
        if decision.is_parameterized:
            payload = _automated_parameterized_payload(decision=decision, view=view)
            current = client.submit_parameterized_payload(
                request_id=decision.request_id,
                payload=payload,
                result_id=result_id,
            )
        else:
            current = client.submit_finite(
                request_id=decision.request_id,
                selected_option_id=_automated_option_id(decision),
                result_id=result_id,
            )
    raise LiveCoreSmokeError(
        f"Smoke checkpoint {stop_phase!r} was not reached within "
        f"{_MAX_AUTOMATED_DECISIONS} public decisions."
    )


def _is_requested_checkpoint(
    *,
    stop_phase: LiveCoreSmokeStopPhase,
    decision: UiDecision,
    view: UiGameView,
) -> bool:
    expected_decision_type = _SETUP_STOP_DECISION_TYPES.get(stop_phase)
    if expected_decision_type is not None:
        return decision.decision_type == expected_decision_type
    return (
        stop_phase in _BATTLE_STOP_PHASES
        and view.stage == "battle"
        and view.current_battle_phase == stop_phase
    )


def _automated_option_id(decision: UiDecision) -> str:
    option_ids = tuple(option.option_id for option in decision.options)
    if not option_ids:
        raise LiveCoreSmokeError(
            f"Finite smoke decision {decision.decision_type!r} exposes no options."
        )
    if decision.decision_type == "select_secondary_missions":
        return _required_option(decision, LIVE_CORE_SMOKE_FIXED_SECONDARY_OPTION_ID)
    if decision.decision_type == "use_stratagem":
        return _required_option(decision, "decline_stratagem_window")
    if decision.decision_type == "select_reserve_declaration":
        return _required_option(decision, "complete_reserve_declarations")
    if decision.decision_type == "select_deployment_unit":
        return option_ids[0]
    if decision.decision_type == "resolve_ordering":
        player_b_order = next(
            (option_id for option_id in option_ids if option_id.endswith(":player-b")),
            None,
        )
        return player_b_order or option_ids[0]
    if decision.decision_type == "select_redeploy_unit":
        redeploy = next(
            (option_id for option_id in option_ids if option_id.startswith("redeploy:")),
            None,
        )
        return redeploy or _preferred_completion_option(option_ids)
    if decision.decision_type == "select_prebattle_action":
        scout = next(
            (option_id for option_id in option_ids if option_id.startswith("scout_move:")),
            None,
        )
        return scout or _preferred_completion_option(option_ids)
    if decision.decision_type == "select_movement_action":
        return _first_available_option(
            option_ids,
            ("remain_stationary", "normal_move", "fall_back"),
        )
    return _preferred_completion_option(option_ids)


def _preferred_completion_option(option_ids: tuple[str, ...]) -> str:
    for token in ("complete", "decline", "pass", "skip", "none", "no_"):
        option = next((value for value in option_ids if token in value.lower()), None)
        if option is not None:
            return option
    return option_ids[0]


def _first_available_option(
    option_ids: tuple[str, ...],
    preferred: tuple[str, ...],
) -> str:
    for option_id in preferred:
        if option_id in option_ids:
            return option_id
    return _preferred_completion_option(option_ids)


def _required_option(decision: UiDecision, option_id: str) -> str:
    if option_id not in {option.option_id for option in decision.options}:
        raise LiveCoreSmokeError(
            f"Expected smoke option {option_id!r} for {decision.decision_type!r}."
        )
    return option_id


def _automated_parameterized_payload(
    *,
    decision: UiDecision,
    view: UiGameView,
) -> JsonObject:
    interaction = decision.interaction
    proposal = decision.parameterized_proposal
    if interaction is None or proposal is None:
        raise LiveCoreSmokeError("Parameterized smoke request is missing contract metadata.")
    if len(interaction.submission_variants) != 1:
        raise LiveCoreSmokeError(
            f"Smoke request {decision.decision_type!r} requires explicit variant selection."
        )
    if decision.decision_type == "submit_stratagem_target_proposal":
        request = decision.payload
        if type(request) is dict and request.get("declinable") is True:
            return {"submission_kind": "decline_stratagem_window"}
        raise LiveCoreSmokeError("Smoke Stratagem proposal does not declare a decline option.")
    kind = interaction.interaction_kind
    if kind in {"model_pose_placement", "multi_model_placement"}:
        return _placement_payload(proposal.payload, view=view)
    if kind == "path_editor" and proposal.proposal_kind == "scout_move":
        return _scout_move_payload(proposal.payload, view=view)
    raise LiveCoreSmokeError(
        f"Smoke automation cannot safely answer {kind!r} for "
        f"{decision.decision_type!r}; stop at this phase and use the UI."
    )


def _placement_payload(request: JsonObject, *, view: UiGameView) -> JsonObject:
    decision_type = _required_string(request, "decision_type")
    unit_id = _required_string(request, "unit_instance_id")
    player_id = _optional_string(request, "player_id") or _required_string(request, "actor_id")
    model_ids = tuple(_string_list(request, "model_instance_ids"))
    if not model_ids:
        raise LiveCoreSmokeError("Smoke placement request has no model_instance_ids.")
    model_placements: list[JsonValue] = [
        {
            "army_id": unit_id.split(":", maxsplit=1)[0],
            "player_id": player_id,
            "unit_instance_id": unit_id,
            "model_instance_id": model_id,
            "pose": _placement_pose_payload(
                index=index,
                player_id=player_id,
                unit_id=unit_id,
                model_id=model_id,
                view=view,
            ),
        }
        for index, model_id in enumerate(model_ids)
    ]
    payload: JsonObject = {
        "proposal_request_id": _required_string(request, "request_id"),
        "proposal_kind": _required_string(request, "proposal_kind"),
        "game_id": _required_string(request, "game_id"),
        "ruleset_descriptor_hash": _required_string(request, "ruleset_descriptor_hash"),
        "setup_step": _required_string(request, "setup_step"),
        "player_id": player_id,
        "unit_instance_id": unit_id,
        "placement_kind": _placement_kind(request),
        "model_placements": model_placements,
    }
    if decision_type != "submit_deployment_placement":
        payload["action_kind"] = _required_string(request, "action_kind")
        payload["source_rule_id"] = _required_string(request, "source_rule_id")
    context = _optional_object(request, "context")
    if context:
        payload["context"] = context
    return _json_object(payload)


def _placement_pose_payload(
    *,
    index: int,
    player_id: str,
    unit_id: str,
    model_id: str,
    view: UiGameView,
) -> JsonObject:
    projected = _projected_model(view, model_id)
    if projected is not None and projected.get("pose") is not None:
        return _proposal_pose_from_projected(_required_object(projected, "pose"))
    row = index // 3
    column = index % 3
    unit_slot = _unit_slot(unit_id)
    if player_id == "player-b":
        x = 40.0 - (unit_slot * 9.0) - (row * 1.8)
        y = 8.0 + (column * 1.8)
        facing = 180.0
    else:
        x = 4.0 + (unit_slot * 14.0) + (row * 1.8)
        y = 51.0 + (column * 1.8)
        facing = 0.0
    return _proposal_pose(x=x, y=y, z=0.0, facing_degrees=facing)


def _unit_slot(unit_id: str) -> int:
    if "scout-redeploy" in unit_id:
        return 0
    if "strategic-reserve" in unit_id:
        return 1
    if "deep-strike" in unit_id:
        return 2
    return 0


def _scout_move_payload(request: JsonObject, *, view: UiGameView) -> JsonObject:
    unit_id = _required_string(request, "unit_instance_id")
    model_ids = tuple(_string_list(request, "model_instance_ids"))
    if not model_ids:
        model_ids = _placed_model_ids_for_unit(view, unit_id)
    model_paths: list[JsonValue] = []
    for model_id in model_ids:
        model = _projected_model(view, model_id)
        if model is None or model.get("pose") is None:
            raise LiveCoreSmokeError(f"Scout model {model_id!r} has no projected pose.")
        start = _proposal_pose_from_projected(_required_object(model, "pose"))
        position = _required_object(start, "position")
        x = _required_number(position, "x")
        y = _required_number(position, "y")
        z = _required_number(position, "z")
        facing = _required_number(_required_object(start, "facing"), "degrees")
        model_paths.append(
            {
                "model_id": model_id,
                "poses": [
                    start,
                    _proposal_pose(x=x + 0.5, y=y, z=z, facing_degrees=facing),
                    _proposal_pose(x=x + 1.0, y=y, z=z, facing_degrees=facing),
                ],
            }
        )
    payload: JsonObject = {
        "proposal_request_id": _required_string(request, "request_id"),
        "proposal_kind": _required_string(request, "proposal_kind"),
        "game_id": _required_string(request, "game_id"),
        "ruleset_descriptor_hash": _required_string(request, "ruleset_descriptor_hash"),
        "setup_step": _required_string(request, "setup_step"),
        "player_id": _required_string(request, "player_id"),
        "unit_instance_id": unit_id,
        "action_kind": _required_string(request, "action_kind"),
        "source_rule_id": _required_string(request, "source_rule_id"),
        "scout_distance_inches": _required_number(request, "scout_distance_inches"),
        "witness": {"model_paths": model_paths},
    }
    context = _optional_object(request, "context")
    if context:
        payload["context"] = context
    return _json_object(payload)


def _projected_model(view: UiGameView, model_id: str) -> JsonObject | None:
    battlefield = view.battlefield_view
    if battlefield is None:
        raise LiveCoreSmokeError("Smoke proposal requires canonical battlefield_view.")
    models = _required_object(battlefield.authoritative, "models_by_id")
    value = models.get(model_id)
    return None if value is None else _required_object(models, model_id)


def _placed_model_ids_for_unit(view: UiGameView, unit_id: str) -> tuple[str, ...]:
    battlefield = view.battlefield_view
    if battlefield is None:
        raise LiveCoreSmokeError("Smoke proposal requires canonical battlefield_view.")
    models = _required_object(battlefield.authoritative, "models_by_id")
    return tuple(
        model_id
        for model_id in sorted(models)
        if _required_string(_required_object(models, model_id), "unit_instance_id") == unit_id
        and _required_object(models, model_id).get("pose") is not None
    )


def _proposal_pose_from_projected(pose: JsonObject) -> JsonObject:
    position = _required_object(pose, "position")
    return _proposal_pose(
        x=_required_number(position, "x_inches"),
        y=_required_number(position, "y_inches"),
        z=_required_number(position, "z_inches"),
        facing_degrees=_required_number(pose, "facing_degrees"),
    )


def _proposal_pose(
    *,
    x: float,
    y: float,
    z: float,
    facing_degrees: float,
) -> JsonObject:
    return {
        "position": {"x": x, "y": y, "z": z},
        "facing": {"degrees": facing_degrees},
    }


def _placement_kind(request: JsonObject) -> str:
    value = _optional_string(request, "placement_kind")
    if value is not None:
        return value
    context = _optional_object(request, "context")
    value = _optional_string(context, "placement_kind")
    if value is not None:
        return value
    kinds = tuple(_string_list(request, "placement_kinds"))
    if kinds:
        return kinds[0]
    raise LiveCoreSmokeError("Placement request has no placement_kind.")


def _startup_from_status(
    *,
    client: LocalSessionClient,
    status: UiClientStatus,
    stop_phase: LiveCoreSmokeStopPhase,
    default_viewer_player_id: str,
) -> LiveCoreSmokeStartup:
    _raise_for_invalid_status(status)
    decision = _required_decision(status)
    viewer_player_id = decision.actor_id or default_viewer_player_id
    game_view = client.get_view(viewer_player_id)
    try:
        battlefield_view = battlefield_view_from_game_view(game_view)
    except CoreProjectionRenderError as exc:
        raise LiveCoreSmokeError(str(exc)) from exc
    event_delta = client.get_events_since(0, viewer_player_id)
    rules_catalog = client.get_rules_catalog()
    catalog_reference = game_view.rules_catalog
    if catalog_reference is None or (
        catalog_reference.catalog_id,
        catalog_reference.source_hash,
    ) != (rules_catalog.catalog_id, rules_catalog.source_hash):
        raise LiveCoreSmokeError("Rules catalog projection does not match the game-view reference.")
    support_profile = client.get_support_profile(viewer_player_id)
    if support_profile.game_id != game_view.game_id:
        raise LiveCoreSmokeError("Support profile game_id does not match the game projection.")
    if not _is_requested_checkpoint(
        stop_phase=stop_phase,
        decision=decision,
        view=game_view,
    ):
        raise LiveCoreSmokeError(f"Smoke startup stopped before requested phase {stop_phase!r}.")
    return LiveCoreSmokeStartup(
        core_client=client,
        status=status,
        game_view=game_view,
        battlefield_view=battlefield_view,
        viewer_player_id=viewer_player_id,
        event_cursor=event_delta.next_cursor,
        rules_catalog=rules_catalog,
        support_profile=support_profile,
    )


def _required_decision(status: UiClientStatus) -> UiDecision:
    if status.decision is None:
        raise LiveCoreSmokeError("Smoke checkpoint does not expose a visible decision.")
    return status.decision


def _raise_for_invalid_status(status: UiClientStatus) -> None:
    if status.status_kind != "invalid":
        return
    diagnostic = status.invalid_diagnostics[0] if status.invalid_diagnostics else None
    detail = (
        status.message
        if diagnostic is None
        else f"{diagnostic.violation_code} [{diagnostic.field or 'request'}]: {diagnostic.message}"
    )
    raise LiveCoreSmokeError(f"Core rejected smoke automation: {detail or 'invalid status'}")


def _validated_stop_phase(stop_at_phase: str | None) -> LiveCoreSmokeStopPhase:
    value = "movement" if stop_at_phase is None else stop_at_phase
    if value not in LIVE_CORE_SMOKE_STOP_PHASES:
        raise LiveCoreSmokeError(f"Unsupported live-core smoke stop phase: {value}.")
    return value


def _json_object(value: object) -> JsonObject:
    validated = validate_json_value(value)
    if type(validated) is not dict:
        raise LiveCoreSmokeError("Smoke payload must be a JSON object.")
    return validated


def _required_object(payload: JsonObject, key: str) -> JsonObject:
    value = payload.get(key)
    if type(value) is not dict:
        raise LiveCoreSmokeError(f"Smoke payload field {key!r} must be an object.")
    return value


def _optional_object(payload: JsonObject, key: str) -> JsonObject:
    value = payload.get(key)
    if value is None:
        return {}
    if type(value) is not dict:
        raise LiveCoreSmokeError(f"Smoke payload field {key!r} must be an object.")
    return value


def _required_string(payload: JsonObject, key: str) -> str:
    value = payload.get(key)
    if type(value) is not str or not value:
        raise LiveCoreSmokeError(f"Smoke payload field {key!r} must be a string.")
    return value


def _optional_string(payload: JsonObject, key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if type(value) is not str or not value:
        raise LiveCoreSmokeError(f"Smoke payload field {key!r} must be a string or null.")
    return value


def _required_number(payload: JsonObject, key: str) -> float:
    value = payload.get(key)
    if type(value) not in {int, float}:
        raise LiveCoreSmokeError(f"Smoke payload field {key!r} must be numeric.")
    return float(cast(int | float, value))


def _string_list(payload: JsonObject, key: str) -> list[str]:
    value = payload.get(key)
    if value is None:
        return []
    if type(value) is not list or any(type(item) is not str or not item for item in value):
        raise LiveCoreSmokeError(f"Smoke payload field {key!r} must be a string list.")
    return cast(list[str], value)
