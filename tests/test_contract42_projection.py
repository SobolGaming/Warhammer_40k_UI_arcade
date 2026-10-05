"""Contract 42 model display and physical presence regressions."""

from __future__ import annotations

import copy
import json
import math
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from tests.support.core_contract_examples import required_core_example_path
from tests.support.render_capture import capture_window_frame
from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.fake_client import FakeCoreClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    UiClientProtocolError,
    UiClientStatus,
    UiEventDelta,
    UiGameView,
)
from warhammer40k_arcade_ui.hud.view_models import build_finite_decision_panel
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow
from warhammer40k_arcade_ui.render.core_projection import (
    CoreProjectionRenderError,
    battlefield_view_from_game_view,
)
from warhammer40k_arcade_ui.render.primitives import PLAYER_1_COLOR
from warhammer40k_arcade_ui.state.entity_selection import (
    EntitySelectionError,
    movement_entity_selection_profile,
    movement_proposal_unit,
)
from warhammer40k_arcade_ui.state.finite_decision import FiniteDecisionUiState
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft, MovementDraftError
from warhammer40k_arcade_ui.state.selection import SelectionState


def test_random_characteristic_keeps_source_expression_and_nullable_values() -> None:
    raw = _post_deployment_payload()
    model_id = next(iter(cast(JsonObject, raw["model_display_by_id"])))
    display = cast(JsonObject, cast(JsonObject, raw["model_display_by_id"])[model_id])
    assert display["keywords"]
    for category in ("base_characteristics", "current_characteristics"):
        characteristics = cast(JsonObject, display[category])
        movement = cast(JsonObject, characteristics["M"])
        movement.update(
            value_kind="random",
            raw=None,
            base=None,
            final=None,
            display_value="D6+2",
            random_expression={"quantity": 1, "sides": 6, "modifier": 2},
        )

    view = UiGameView.from_payload(raw)
    parsed_display = cast(JsonObject, view.model_display_by_id[model_id])
    current = cast(JsonObject, cast(JsonObject, parsed_display["current_characteristics"])["M"])
    assert current["display_value"] == "D6+2"
    assert current["random_expression"] == {"quantity": 1, "sides": 6, "modifier": 2}
    assert current["final"] is None
    model = next(
        model
        for unit in battlefield_view_from_game_view(view).units
        for model in unit.models
        if model.model_id == model_id
    )
    assert model.base_movement_inches is None

    for invalid in (
        {**current, "random_expression": None},
        {**current, "display_value": None},
        {**current, "final": "guessed 5"},
    ):
        changed = copy.deepcopy(raw)
        changed_display = cast(
            JsonObject, cast(JsonObject, changed["model_display_by_id"])[model_id]
        )
        cast(JsonObject, changed_display["current_characteristics"])["M"] = invalid
        with pytest.raises(UiClientProtocolError):
            UiGameView.from_payload(changed)


def test_destroyed_model_remains_rendered_while_projected_pose_exists() -> None:
    raw = _post_deployment_payload()
    battlefield = cast(JsonObject, raw["battlefield_view"])
    authoritative = cast(JsonObject, battlefield["authoritative"])
    models = cast(JsonObject, authoritative["models_by_id"])
    model_id = next(iter(models))
    model = cast(JsonObject, models[model_id])
    model["state"] = "destroyed"
    cast(JsonObject, cast(JsonObject, raw["model_display_by_id"])[model_id])["wounds_remaining"] = 0

    retained = battlefield_view_from_game_view(UiGameView.from_payload(raw))
    assert any(model.model_id == model_id for unit in retained.units for model in unit.models)

    model["pose"] = None
    removed = battlefield_view_from_game_view(UiGameView.from_payload(raw))
    assert all(model.model_id != model_id for unit in removed.units for model in unit.models)


def test_canonical_model_projection_preserves_elevation_and_facing() -> None:
    raw = _post_deployment_payload()
    battlefield = cast(JsonObject, raw["battlefield_view"])
    models = cast(JsonObject, cast(JsonObject, battlefield["authoritative"])["models_by_id"])
    model_id = next(iter(models))
    pose = cast(JsonObject, cast(JsonObject, models[model_id])["pose"])
    cast(JsonObject, pose["position"])["z_inches"] = 2.5
    pose["facing_degrees"] = 45.0

    projected = battlefield_view_from_game_view(UiGameView.from_payload(raw))
    model = next(
        model for unit in projected.units for model in unit.models if model.model_id == model_id
    )
    assert model.elevation_z_inches == 2.5
    assert model.facing_degrees == 45.0


def test_canonical_ellipse_display_radius_uses_longer_semiaxis() -> None:
    raw = _post_deployment_payload()
    models = cast(
        JsonObject,
        cast(JsonObject, cast(JsonObject, raw["battlefield_view"])["authoritative"])[
            "models_by_id"
        ],
    )
    model_id = next(iter(models))
    model = cast(JsonObject, models[model_id])
    geometry = cast(JsonObject, model["geometry"])
    circle = cast(JsonObject, geometry["support_shape"])
    assert circle["kind"] == "circle"
    circle_view = battlefield_view_from_game_view(UiGameView.from_payload(raw))
    circle_model = next(
        member
        for unit in circle_view.units
        for member in unit.models
        if member.model_id == model_id
    )
    assert math.isclose(
        circle_model.base_radius,
        cast(float, circle["radius_inches"]),
        rel_tol=0.0,
        abs_tol=1.0e-9,
    )

    conformance = json.loads(
        required_core_example_path("battlefield", "geometry-conformance.json").read_text(
            encoding="utf-8"
        )
    )
    oval = cast(
        JsonObject,
        cast(JsonObject, cast(JsonObject, conformance["authoritative"])["models_by_id"])[
            "geometry-conformance-oval-model"
        ],
    )
    support_shape = copy.deepcopy(
        cast(JsonObject, cast(JsonObject, oval["geometry"])["support_shape"])
    )
    assert support_shape["kind"] == "ellipse"
    support_shape["length_inches"] = 2.0
    support_shape["width_inches"] = 1.0
    geometry["support_shape"] = support_shape

    ellipse_view = battlefield_view_from_game_view(UiGameView.from_payload(raw))
    ellipse_model = next(
        member
        for unit in ellipse_view.units
        for member in unit.models
        if member.model_id == model_id
    )
    assert math.isclose(ellipse_model.base_radius, 1.0, rel_tol=0.0, abs_tol=1.0e-9)
    assert ellipse_model.support_footprint is not None
    assert len(ellipse_model.support_footprint) == 32

    support_shape["kind"] = "rectangle"
    rectangle_view = battlefield_view_from_game_view(UiGameView.from_payload(raw))
    rectangle_model = next(
        member
        for unit in rectangle_view.units
        for member in unit.models
        if member.model_id == model_id
    )
    assert math.isclose(
        rectangle_model.base_radius,
        math.hypot(1.0, 0.5),
        rel_tol=0.0,
        abs_tol=1.0e-9,
    )
    assert rectangle_model.support_footprint is not None
    assert len(rectangle_model.support_footprint) == 4


@pytest.mark.parametrize("field", ["z_inches", "facing_degrees"])
@pytest.mark.parametrize("malformed", [False, True])
def test_canonical_model_pose_requires_finite_elevation_and_facing(
    field: str, malformed: bool
) -> None:
    raw = _post_deployment_payload()
    battlefield = cast(JsonObject, raw["battlefield_view"])
    models = cast(JsonObject, cast(JsonObject, battlefield["authoritative"])["models_by_id"])
    model = cast(JsonObject, next(iter(models.values())))
    pose = cast(JsonObject, model["pose"])
    target = cast(JsonObject, pose["position"]) if field == "z_inches" else pose
    if malformed:
        target[field] = "not-a-number"
    else:
        del target[field]

    with pytest.raises(CoreProjectionRenderError, match=f"{field} must be a number"):
        battlefield_view_from_game_view(UiGameView.from_payload(raw))


@pytest.mark.parametrize("pose_value", ["absent", "null"])
def test_placed_attached_actor_requires_whole_canonical_pose(pose_value: str) -> None:
    raw = _attached_charge_payload()
    view = UiGameView.from_payload(raw)
    assert view.pending_decision is not None
    proposal = view.pending_decision.movement_proposal
    assert proposal is not None
    battlefield = battlefield_view_from_game_view(view)
    actor = movement_proposal_unit(view=battlefield, proposal=proposal)
    assert actor is not None
    assert len(actor.models) == 6
    selection = SelectionState.initial(default_preferences()).select_model_id(
        unit_id=proposal.unit_instance_id,
        model_id=None,
        preferences=default_preferences(),
    )
    draft = MovementDraft.start_for_pending(
        view=battlefield,
        selection=selection,
        pending_decision=view.pending_decision,
    )
    assert draft is not None
    assert {path.model_id for path in draft.model_paths} == {
        model.model_id for model in actor.models
    }

    model_id = actor.models[0].model_id
    invalid_raw = copy.deepcopy(raw)
    models = cast(
        JsonObject,
        cast(JsonObject, cast(JsonObject, invalid_raw["battlefield_view"])["authoritative"])[
            "models_by_id"
        ],
    )
    model = cast(JsonObject, models[model_id])
    if pose_value == "absent":
        del model["pose"]
    else:
        model["pose"] = None
    with pytest.raises(UiClientProtocolError, match=rf"{model_id}\.pose is required"):
        UiGameView.from_payload(invalid_raw)

    assert view.battlefield_view is not None
    authoritative_models = cast(JsonObject, view.battlefield_view.authoritative["models_by_id"])
    parsed_model = cast(JsonObject, authoritative_models[model_id])
    if pose_value == "absent":
        del parsed_model["pose"]
    else:
        parsed_model["pose"] = None
    with pytest.raises(CoreProjectionRenderError, match=rf"{model_id} is missing pose"):
        battlefield_view_from_game_view(view)


@pytest.mark.parametrize("state", ["undeployed", "reserves", "embarked", "removed", "destroyed"])
def test_unplaced_or_removed_model_keeps_explicit_null_pose(state: str) -> None:
    raw = _post_deployment_payload()
    models = cast(
        JsonObject,
        cast(JsonObject, cast(JsonObject, raw["battlefield_view"])["authoritative"])[
            "models_by_id"
        ],
    )
    model_id = next(iter(models))
    model = cast(JsonObject, models[model_id])
    model["state"] = state
    model["pose"] = None

    battlefield = battlefield_view_from_game_view(UiGameView.from_payload(raw))
    assert all(member.model_id != model_id for unit in battlefield.units for member in unit.models)


def test_canonical_membership_is_required_nullable_and_separate_from_physical_owner() -> None:
    raw = _post_deployment_payload()
    battlefield = cast(JsonObject, raw["battlefield_view"])
    models = cast(JsonObject, cast(JsonObject, battlefield["authoritative"])["models_by_id"])
    model_id = next(iter(models))
    model = cast(JsonObject, models[model_id])
    physical_owner = model["unit_instance_id"]
    assert type(model["rules_unit_instance_id"]) is str
    parsed = UiGameView.from_payload(raw)
    rendered = next(
        member
        for unit in battlefield_view_from_game_view(parsed).units
        for member in unit.models
        if member.model_id == model_id
    )
    assert rendered.rules_unit_instance_id == model["rules_unit_instance_id"]
    assert model["unit_instance_id"] == physical_owner

    model["rules_unit_instance_id"] = None
    redacted = UiGameView.from_payload(raw)
    assert redacted.battlefield_view is not None
    assert (
        cast(JsonObject, redacted.battlefield_view.models_by_id[model_id])["rules_unit_instance_id"]
        is None
    )
    assert model["unit_instance_id"] == physical_owner

    del model["rules_unit_instance_id"]
    with pytest.raises(UiClientProtocolError, match="rules_unit_instance_id"):
        UiGameView.from_payload(raw)


def test_owned_placed_member_with_null_membership_fails_before_movement_witness() -> None:
    raw = _attached_charge_payload()
    view = UiGameView.from_payload(raw)
    assert view.pending_decision is not None
    proposal = view.pending_decision.movement_proposal
    assert proposal is not None
    battlefield = battlefield_view_from_game_view(view)
    actor = movement_proposal_unit(view=battlefield, proposal=proposal)
    assert actor is not None
    assert len(actor.models) == 6
    model_id = actor.models[0].model_id

    models = cast(
        JsonObject,
        cast(JsonObject, cast(JsonObject, raw["battlefield_view"])["authoritative"])[
            "models_by_id"
        ],
    )
    cast(JsonObject, models[model_id])["rules_unit_instance_id"] = None
    malformed = UiGameView.from_payload(raw)
    with pytest.raises(CoreProjectionRenderError, match="missing rules_unit_instance_id"):
        battlefield_view_from_game_view(malformed)

    malformed_battlefield = replace(
        battlefield,
        units=tuple(
            replace(
                unit,
                models=tuple(
                    replace(member, rules_unit_instance_id=None)
                    if member.model_id == model_id
                    else member
                    for member in unit.models
                ),
            )
            for unit in battlefield.units
        ),
    )
    with pytest.raises(EntitySelectionError, match="missing current rules_unit_instance_id"):
        movement_proposal_unit(view=malformed_battlefield, proposal=proposal)
    profile = movement_entity_selection_profile(
        view=malformed_battlefield,
        decision=view.pending_decision,
    )
    assert profile.candidate_refs == ()
    assert profile.unsupported_reason is not None
    assert "missing current rules_unit_instance_id" in profile.unsupported_reason
    selection = SelectionState.initial(default_preferences()).select_model_id(
        unit_id=proposal.unit_instance_id,
        model_id=None,
        preferences=default_preferences(),
    )
    with pytest.raises(MovementDraftError, match="missing current rules_unit_instance_id"):
        MovementDraft.start_for_pending(
            view=malformed_battlefield,
            selection=selection,
            pending_decision=view.pending_decision,
        )


def test_owned_ordinary_placed_member_with_null_membership_fails_projection() -> None:
    raw = _post_deployment_payload()
    models = cast(
        JsonObject,
        cast(JsonObject, cast(JsonObject, raw["battlefield_view"])["authoritative"])[
            "models_by_id"
        ],
    )
    model_id = next(iter(models))
    model = cast(JsonObject, models[model_id])
    assert model["state"] == "placed"
    assert model["owner_player_id"] == raw["viewer_player_id"]
    model["rules_unit_instance_id"] = None

    with pytest.raises(CoreProjectionRenderError, match="missing rules_unit_instance_id"):
        battlefield_view_from_game_view(UiGameView.from_payload(raw))


def test_hidden_opponent_unplaced_membership_and_pose_may_be_null() -> None:
    raw = _core_projection_payload("initial_setup_view_player1.json")
    view = UiGameView.from_payload(raw)
    assert view.battlefield_view is not None
    opponent_rows = tuple(
        cast(JsonObject, model)
        for model in view.battlefield_view.models_by_id.values()
        if cast(JsonObject, model)["owner_player_id"] != view.viewer_player_id
    )
    assert opponent_rows
    assert all(
        model["state"] == "undeployed"
        and model["pose"] is None
        and model["rules_unit_instance_id"] is None
        for model in opponent_rows
    )
    assert battlefield_view_from_game_view(view).units == ()


def test_retained_model_appears_in_headless_frame_until_pose_is_removed() -> None:
    raw = _post_deployment_payload()
    battlefield = cast(JsonObject, raw["battlefield_view"])
    models = cast(JsonObject, cast(JsonObject, battlefield["authoritative"])["models_by_id"])
    model_id = next(iter(models))
    model = cast(JsonObject, models[model_id])
    model["state"] = "destroyed"
    pose = cast(JsonObject, model["pose"])
    position = cast(JsonObject, pose["position"])
    view = UiGameView.from_payload(raw)
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=battlefield_view_from_game_view(view),
        preferences=default_preferences(),
        initial_game_view=view,
        viewer_player_id=view.viewer_player_id,
    )
    try:
        x, y = window.camera.world_to_screen(
            (cast(float, position["x_inches"]), cast(float, position["y_inches"]))
        )
        region = (round(x) - 8, round(y) - 8, 16, 16)
        retained = capture_window_frame(window, source_name="contract42-retained-model")
        assert retained.close_color_count(PLAYER_1_COLOR, tolerance=0, region=region) > 0

        model["pose"] = None
        removed_view = UiGameView.from_payload(raw)
        window._apply_refreshed_game_view(view=removed_view, state=FiniteDecisionUiState())  # pyright: ignore[reportPrivateUsage]
        removed = capture_window_frame(window, source_name="contract42-model-removed")
        assert removed.close_color_count(PLAYER_1_COLOR, tolerance=0, region=region) == 0
    finally:
        window.close()


def test_alternating_viewer_refresh_drops_hidden_display_rows_and_event_lines() -> None:
    raw = _post_deployment_payload()
    own = UiGameView.from_payload(raw)
    own_unit_id = next(iter(own.unit_display_by_id))
    own_model_id = next(iter(own.model_display_by_id))
    opponent = replace(
        own,
        viewer_player_id="player-b",
        unit_display_by_id={
            key: value for key, value in own.unit_display_by_id.items() if key != own_unit_id
        },
        model_display_by_id={
            key: value for key, value in own.model_display_by_id.items() if key != own_model_id
        },
    )
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=battlefield_view_from_game_view(own),
        preferences=default_preferences(),
        initial_game_view=own,
        viewer_player_id=own.viewer_player_id,
    )
    try:
        assert own_unit_id in window._known_unit_display_by_id  # pyright: ignore[reportPrivateUsage]
        assert own_model_id in window._known_model_display_by_id  # pyright: ignore[reportPrivateUsage]
        state = FiniteDecisionUiState(event_log_lines=("player-b public event",))
        window._apply_refreshed_game_view(view=opponent, state=state)  # pyright: ignore[reportPrivateUsage]
        assert own_unit_id not in window._known_unit_display_by_id  # pyright: ignore[reportPrivateUsage]
        assert own_model_id not in window._known_model_display_by_id  # pyright: ignore[reportPrivateUsage]
        assert window.viewer_player_id == "player-b"
        assert "player-b public event" in window.battlefield_view.hud.event_log_lines
        window._apply_refreshed_game_view(view=own, state=FiniteDecisionUiState())  # pyright: ignore[reportPrivateUsage]
        assert own_unit_id in window._known_unit_display_by_id  # pyright: ignore[reportPrivateUsage]
        assert own_model_id in window._known_model_display_by_id  # pyright: ignore[reportPrivateUsage]
        assert "player-b public event" not in window.battlefield_view.hud.event_log_lines
    finally:
        window.close()


@pytest.mark.parametrize("failure_kind", ["membership", "pose"])
def test_failed_viewer_refresh_clears_prior_viewer_from_fatal_frame(
    failure_kind: str,
    tmp_path: Path,
) -> None:
    raw = _post_deployment_payload()
    old = UiGameView.from_payload(raw)
    assert old.pending_decision is not None
    next_decision = replace(old.pending_decision, actor_id="player-b")
    changed = copy.deepcopy(raw)
    changed["viewer_player_id"] = "player-b"
    changed["unit_display_by_id"] = {}
    changed["model_display_by_id"] = {}
    models = cast(
        JsonObject,
        cast(JsonObject, cast(JsonObject, changed["battlefield_view"])["authoritative"])[
            "models_by_id"
        ],
    )
    model_id = next(
        key
        for key, row in models.items()
        if cast(JsonObject, row)["owner_player_id"] == "player-b"
        and cast(JsonObject, row)["state"] == "placed"
    )
    model = cast(JsonObject, models[model_id])
    if failure_kind == "membership":
        model["rules_unit_instance_id"] = None
    else:
        cast(JsonObject, cast(JsonObject, model["pose"])["position"])["z_inches"] = "bad"
    cast(JsonObject, cast(JsonObject, changed["battlefield_view"])["authoritative"])[
        "models_by_id"
    ] = {model_id: model}
    malformed = replace(UiGameView.from_payload(changed), pending_decision=next_decision)
    client = FakeCoreClient(
        status=UiClientStatus(
            stage="battle",
            status_kind="waiting_for_decision",
            decision=next_decision,
        ),
        view=malformed,
        event_delta=UiEventDelta(
            viewer_player_id="player-b",
            cursor=0,
            next_cursor=0,
            events=(),
        ),
    )
    battlefield = battlefield_view_from_game_view(old).with_hud(
        phase_label="movement",
        active_player_id="player-a",
        pending_decision_summary="Prior viewer action",
        event_log_lines=("prior viewer private event",),
    )
    window = ArcadeWarhammerWindow(
        config=AppConfig(window_width=1280, window_height=800, resizable=False),
        battlefield_view=battlefield,
        preferences=default_preferences(),
        pending_decision=old.pending_decision,
        initial_game_view=old,
        viewer_player_id="player-a",
        crash_report_dir=tmp_path,
    )
    try:
        old_frame = capture_window_frame(window, source_name="old-viewer-before-fatal-refresh")
        assert old_frame.close_color_count(PLAYER_1_COLOR, tolerance=0) > 0
        assert window.battlefield_view.units
        assert window._known_model_display_by_id  # pyright: ignore[reportPrivateUsage]
        window._core_client = client  # pyright: ignore[reportPrivateUsage]

        window._submit_finite_option(old.pending_decision.options[0].option_id)  # pyright: ignore[reportPrivateUsage]

        assert window.finite_state.status_kind == "fatal"
        assert window.finite_state.diagnostics[0].violation_code == "fatal_game_engine_error"
        expected_field = "rules_unit_instance_id" if failure_kind == "membership" else "z_inches"
        assert expected_field in window.finite_state.diagnostics[0].message
        assert window.viewer_player_id == "none"
        assert window.battlefield_view.units == ()
        assert window.battlefield_view.hud.event_log_lines == ()
        assert window.finite_state.event_log_lines == ()
        assert window.finite_state.event_payloads == ()
        assert window._last_game_view is None  # pyright: ignore[reportPrivateUsage]
        assert window._known_unit_display_by_id == {}  # pyright: ignore[reportPrivateUsage]
        assert window._known_model_display_by_id == {}  # pyright: ignore[reportPrivateUsage]
        assert window._selection_state.selected_unit_id is None  # pyright: ignore[reportPrivateUsage]
        panel = build_finite_decision_panel(
            pending_decision=window.finite_state.pending_decision,
            highlighted_option_index=window.finite_state.highlighted_option_index,
            status_message=window.finite_state.status_message,
            diagnostics=window.finite_state.diagnostics,
        )
        assert panel.diagnostic_lines
        fatal_frame = capture_window_frame(window, source_name="fatal-viewer-refresh")
        assert fatal_frame.close_color_count(PLAYER_1_COLOR, tolerance=0) == 0
    finally:
        window.close()


def _post_deployment_payload() -> JsonObject:
    return _core_projection_payload("post_deployment_view.json")


def _attached_charge_payload() -> JsonObject:
    return _core_projection_payload("attached_charge_view.json")


def _core_projection_payload(name: str) -> JsonObject:
    path = required_core_example_path("projections", name)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert type(payload) is dict
    return cast(JsonObject, payload)
