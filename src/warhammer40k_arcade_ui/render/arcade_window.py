"""Arcade window for the inspectable battlefield milestone."""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from itertools import pairwise
from pathlib import Path

import arcade

from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.protocol import (
    UiClientProtocolError,
    UiClientStatus,
    UiCoreClient,
    UiDecision,
    UiGameView,
)
from warhammer40k_arcade_ui.hud.view_models import (
    ContextMenuAction,
    ContextMenuView,
    build_context_menu,
    build_debug_inspector,
    build_finite_decision_panel,
    build_movement_draft_panel,
    build_unit_panel,
)
from warhammer40k_arcade_ui.input.commands import command_for_key
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.preferences.diagnostics import PreferenceDiagnostic
from warhammer40k_arcade_ui.preferences.io import PreferencesLoadResult, load_preferences
from warhammer40k_arcade_ui.preferences.schema import UiPreferences
from warhammer40k_arcade_ui.render.camera import WorldCamera, WorldPoint
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view
from warhammer40k_arcade_ui.render.primitives import (
    CirclePrimitive,
    PolygonPrimitive,
    PolylinePrimitive,
    RenderPrimitive,
    TextPrimitive,
    build_hud_primitives,
    build_world_primitives,
)
from warhammer40k_arcade_ui.render.view_models import BattlefieldView, RenderViewModelError
from warhammer40k_arcade_ui.state.entity_selection import entity_ref_for_model
from warhammer40k_arcade_ui.state.finite_decision import (
    FiniteDecisionUiState,
    submit_finite_option,
)
from warhammer40k_arcade_ui.state.movement_draft import MovementDraft
from warhammer40k_arcade_ui.state.movement_submission import (
    MovementSubmissionError,
    submit_movement_draft,
)
from warhammer40k_arcade_ui.state.selection import (
    SelectionState,
    model_hits_at,
    selected_unit,
    unit_center,
)

MOUSE_ZOOM_BASE = 1.12
CONTEXT_MENU_LINE_HEIGHT_WORLD = 1.1
CONTEXT_MENU_ACTION_WIDTH_WORLD = 18.0
CONTEXT_MENU_LINE_TOLERANCE_WORLD = 0.55
RIGHT_CLICK_REMOVE_DRAG_TOLERANCE_PX = 3.0
FATAL_ENGINE_EXIT_DELAY_SECONDS = 4.0

logger = logging.getLogger(__name__)

type FatalGameEngineException = (
    UiClientProtocolError | RenderViewModelError | MovementSubmissionError | KeyError
)


class ArcadeWarhammerWindow(arcade.Window):
    """Arcade window that renders a read-only battlefield projection."""

    def __init__(
        self,
        *,
        config: AppConfig | None = None,
        battlefield_view: BattlefieldView | None = None,
        preferences: UiPreferences | None = None,
        preferences_path: Path | None = None,
        pending_decision: UiDecision | None = None,
        initial_status: UiClientStatus | None = None,
        core_client: UiCoreClient | None = None,
        viewer_player_id: str = "player_1",
        event_cursor: int = 0,
    ) -> None:
        resolved_config = config or AppConfig()
        super().__init__(
            width=resolved_config.window_width,
            height=resolved_config.window_height,
            title=resolved_config.title,
            resizable=resolved_config.resizable,
        )
        self.background_color = arcade.color.DARK_SLATE_GRAY
        self._battlefield_view = battlefield_view or default_battlefield_view()
        if preferences is None:
            loaded_preferences = load_preferences(preferences_path)
            self._preferences = loaded_preferences.preferences or default_preferences()
            self._preference_diagnostics = loaded_preferences.diagnostics
            self._preference_source_label = _preference_source_label(loaded_preferences)
        else:
            self._preferences = preferences
            self._preference_diagnostics = ()
            self._preference_source_label = "injected preferences"
        self._selection_state = SelectionState.initial(self._preferences)
        self._core_client = core_client
        self._viewer_player_id = viewer_player_id
        self._finite_state = (
            FiniteDecisionUiState.from_status(
                initial_status,
                event_cursor=event_cursor,
                event_log_lines=self._battlefield_view.hud.event_log_lines,
            )
            if initial_status is not None
            else FiniteDecisionUiState(
                pending_decision=pending_decision,
                event_cursor=event_cursor,
                event_log_lines=self._battlefield_view.hud.event_log_lines,
            )
        )
        self._pending_decision = self._finite_state.pending_decision
        self._event_cursor = self._finite_state.event_cursor
        self._camera = WorldCamera.fit_table(
            viewport_width_px=resolved_config.window_width,
            viewport_height_px=resolved_config.window_height,
            table_width=self._battlefield_view.table.width,
            table_height=self._battlefield_view.table.height,
        )
        self._mouse_world_position: WorldPoint | None = None
        self._movement_draft: MovementDraft | None = None
        self._right_mouse_press_screen: tuple[float, float] | None = None
        self._right_mouse_drag_distance_px = 0.0
        self._fatal_exit_deadline_monotonic: float | None = None

    @property
    def camera(self) -> WorldCamera:
        """Current world camera."""

        return self._camera

    @property
    def mouse_world_position(self) -> WorldPoint | None:
        """Last mouse position converted into table coordinates."""

        return self._mouse_world_position

    @property
    def selection_state(self) -> SelectionState:
        """Current local selection state."""

        return self._selection_state

    @property
    def battlefield_view(self) -> BattlefieldView:
        """Current viewer-scoped battlefield projection."""

        return self._battlefield_view

    @property
    def pending_decision(self) -> UiDecision | None:
        """Current pending engine decision exposed to the UI."""

        return self._pending_decision

    @property
    def finite_state(self) -> FiniteDecisionUiState:
        """Current finite-decision UI state."""

        return self._finite_state

    @property
    def movement_draft(self) -> MovementDraft | None:
        """Current local movement draft, if one is active."""

        return self._movement_draft

    @property
    def event_cursor(self) -> int:
        """Current viewer event cursor."""

        return self._event_cursor

    @property
    def context_menu(self) -> ContextMenuView | None:
        """Current context menu view model, if the selected unit has finite actions."""

        return build_context_menu(
            view=self._battlefield_view,
            selection=self._selection_state,
            pending_decision=self._pending_decision,
            fallback_anchor_world=self._mouse_world_position,
        )

    @property
    def preference_diagnostics(self) -> tuple[PreferenceDiagnostic, ...]:
        """Diagnostics produced while loading UI preferences."""

        return self._preference_diagnostics

    @property
    def preference_source_label(self) -> str:
        """Display label for the active UI preferences source."""

        return self._preference_source_label

    def on_draw(self) -> None:
        """Render the battlefield and fixed HUD."""

        self.clear()
        unit_panel = (
            build_unit_panel(
                view=self._battlefield_view,
                selection=self._selection_state,
                pending_decision=self._pending_decision,
            )
            if self._selection_state.selected_unit_panel_visible
            else None
        )
        context_menu = build_context_menu(
            view=self._battlefield_view,
            selection=self._selection_state,
            pending_decision=self._pending_decision,
            fallback_anchor_world=self._mouse_world_position,
        )
        finite_decision_panel = build_finite_decision_panel(
            pending_decision=self._finite_state.pending_decision,
            highlighted_option_index=self._finite_state.highlighted_option_index,
            status_message=self._finite_state.status_message,
            diagnostics=self._finite_state.diagnostics,
        )
        movement_draft_panel = build_movement_draft_panel(
            movement_draft=self._movement_draft,
            pending_decision=self._pending_decision,
            status_message=self._finite_state.status_message,
            diagnostics=self._finite_state.diagnostics,
        )
        debug_inspector = build_debug_inspector(
            selection=self._selection_state,
            pending_decision=self._pending_decision,
            cursor_position=self._mouse_world_position,
            event_cursor=self._event_cursor,
            preference_source_label=self._preference_source_label,
        )
        world_primitives = build_world_primitives(
            self._battlefield_view,
            self._selection_state,
            self._movement_draft,
        )
        hud_primitives = build_hud_primitives(
            view=self._battlefield_view,
            viewport_width_px=self.width,
            viewport_height_px=self.height,
            mouse_world_position=self._mouse_world_position,
            unit_panel=unit_panel,
            context_menu=context_menu,
            finite_decision_panel=finite_decision_panel,
            movement_draft_panel=movement_draft_panel,
            debug_inspector=debug_inspector,
        )
        _draw_world_primitives(world_primitives, self._camera)
        _draw_text_primitives(hud_primitives, self._camera)

    def on_resize(self, width: int, height: int) -> None:
        """Keep camera viewport dimensions aligned with the Arcade window."""

        super().on_resize(width, height)
        self._camera = self._camera.resize_viewport(width_px=width, height_px=height)

    def on_update(self, delta_time: float) -> None:
        """Close cleanly after a fatal engine/client error has been displayed."""

        del delta_time
        if (
            self._fatal_exit_deadline_monotonic is not None
            and time.monotonic() >= self._fatal_exit_deadline_monotonic
        ):
            self.close()

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        """Track table coordinates under the mouse for debug display."""

        del dx, dy
        self._mouse_world_position = self._camera.screen_to_world((float(x), float(y)))
        if self._movement_draft is not None:
            self._movement_draft = self._movement_draft.with_cursor_preview(
                view=self._battlefield_view,
                world_point=self._mouse_world_position,
            )

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        """Select models with the configured default mouse button."""

        self._mouse_world_position = self._camera.screen_to_world((float(x), float(y)))
        if button == arcade.MOUSE_BUTTON_RIGHT and self._movement_draft is not None:
            self._right_mouse_press_screen = (float(x), float(y))
            self._right_mouse_drag_distance_px = 0.0
            return
        if _mouse_button_name(button) != self._preferences.selection.default_mouse_button:
            return
        selected_action = self._context_menu_action_at(self._mouse_world_position)
        if selected_action is not None:
            if selected_action.enabled:
                self._submit_finite_option(selected_action.option_id)
            else:
                self._set_finite_state(
                    self._finite_state.with_local_invalid(
                        violation_code="disabled_finite_option",
                        message=selected_action.disabled_reason
                        or "Finite option is disabled by the engine payload.",
                        field="selected_option_id",
                    )
                )
            return
        if self._movement_draft is not None:
            if self._apply_movement_selection_at(
                world_point=self._mouse_world_position,
                modifiers=modifiers,
            ):
                return
            self._movement_draft = self._movement_draft.add_waypoint(
                view=self._battlefield_view,
                world_point=self._mouse_world_position,
            )
            return
        self._selection_state = self._selection_state.select_at(
            view=self._battlefield_view,
            world_point=self._mouse_world_position,
            preferences=self._preferences,
        )
        self._sync_movement_draft()

    def on_mouse_drag(
        self,
        x: int,
        y: int,
        dx: int,
        dy: int,
        buttons: int,
        modifiers: int,
    ) -> None:
        """Pan the camera with right- or middle-button drag."""

        del modifiers
        pan_buttons = arcade.MOUSE_BUTTON_RIGHT | arcade.MOUSE_BUTTON_MIDDLE
        if buttons & pan_buttons:
            self._camera = self._camera.pan_screen(float(dx), float(dy))
            self._mouse_world_position = self._camera.screen_to_world((float(x), float(y)))
            if buttons & arcade.MOUSE_BUTTON_RIGHT:
                self._right_mouse_drag_distance_px += abs(float(dx)) + abs(float(dy))
        elif buttons & arcade.MOUSE_BUTTON_LEFT and self._movement_draft is not None:
            self._mouse_world_position = self._camera.screen_to_world((float(x), float(y)))
            self._movement_draft = self._movement_draft.with_cursor_preview(
                view=self._battlefield_view,
                world_point=self._mouse_world_position,
            )

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        """Use a right-click release to remove the last movement waypoint."""

        del modifiers
        self._mouse_world_position = self._camera.screen_to_world((float(x), float(y)))
        if button != arcade.MOUSE_BUTTON_RIGHT:
            return
        if (
            self._movement_draft is not None
            and self._right_mouse_press_screen is not None
            and self._right_mouse_drag_distance_px <= RIGHT_CLICK_REMOVE_DRAG_TOLERANCE_PX
        ):
            self._movement_draft = self._movement_draft.remove_last_waypoint(
                view=self._battlefield_view
            )
        self._right_mouse_press_screen = None
        self._right_mouse_drag_distance_px = 0.0

    def on_mouse_scroll(self, x: int, y: int, scroll_x: float, scroll_y: float) -> None:
        """Zoom the camera around the mouse cursor."""

        del scroll_x
        if scroll_y == 0.0:
            return
        self._camera = self._camera.zoom_at_screen_point(
            multiplier=MOUSE_ZOOM_BASE**scroll_y,
            screen_point=(float(x), float(y)),
        )
        self._mouse_world_position = self._camera.screen_to_world((float(x), float(y)))

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        """Apply configured local UI hotkeys."""

        if self._fatal_exit_deadline_monotonic is not None:
            return
        invocation = command_for_key(
            preferences=self._preferences,
            key=_key_name(symbol),
            modifiers=_modifier_names(modifiers),
        )
        if invocation is None:
            return
        if invocation.command_id == "toggle_debug_inspector":
            self._selection_state = self._selection_state.toggle_debug_inspector()
        elif invocation.command_id == "show_selected_unit":
            self._selection_state = self._selection_state.show_selected_unit_panel()
        elif invocation.command_id == "show_selected_model":
            self._selection_state = self._selection_state.show_selected_model_panel()
        elif invocation.command_id == "toggle_overlay" and invocation.overlay_id is not None:
            self._selection_state = self._selection_state.toggle_overlay(invocation.overlay_id)
        elif invocation.command_id == "open_selected_unit_actions":
            self._selection_state = self._selection_state.open_context_menu(
                self._context_anchor_world()
            )
        elif invocation.command_id == "cycle_selection":
            if self._finite_state.finite_options:
                self._set_finite_state(self._finite_state.cycle_option())
            elif self._movement_draft is not None:
                self._movement_draft = self._movement_draft.cycle_entity_focus(
                    view=self._battlefield_view
                )
            elif self._mouse_world_position is not None:
                self._selection_state = self._selection_state.cycle_existing_at(
                    view=self._battlefield_view,
                    world_point=self._mouse_world_position,
                    preferences=self._preferences,
                )
        elif invocation.command_id == "cycle_entity_layer" and self._movement_draft is not None:
            self._movement_draft = self._movement_draft.cycle_entity_layer(
                view=self._battlefield_view
            )
        elif (
            invocation.command_id == "select_current_entity_group"
            and self._movement_draft is not None
        ):
            self._movement_draft = self._movement_draft.select_current_group(
                view=self._battlefield_view
            )
        elif (
            invocation.command_id == "add_entity_selection"
            and self._movement_draft is not None
            and self._movement_draft.entity_selection.focused_ref is not None
        ):
            self._movement_draft = self._movement_draft.add_model_selection(
                view=self._battlefield_view,
                ref=self._movement_draft.entity_selection.focused_ref,
            )
        elif (
            invocation.command_id == "subtract_entity_selection"
            and self._movement_draft is not None
            and self._movement_draft.entity_selection.focused_ref is not None
        ):
            self._movement_draft = self._movement_draft.subtract_model_selection(
                view=self._battlefield_view,
                ref=self._movement_draft.entity_selection.focused_ref,
            )
        elif (
            invocation.command_id == "toggle_entity_selection"
            and self._movement_draft is not None
            and self._movement_draft.entity_selection.focused_ref is not None
        ):
            self._movement_draft = self._movement_draft.toggle_model_selection(
                view=self._battlefield_view,
                ref=self._movement_draft.entity_selection.focused_ref,
            )
        elif invocation.command_id == "confirm":
            if self._movement_draft is not None:
                if self._movement_draft.is_ready:
                    self._submit_movement_draft()
                else:
                    self._movement_draft = self._movement_draft.mark_ready(
                        view=self._battlefield_view
                    )
            else:
                self._submit_finite_option(None)
        elif invocation.command_id == "cancel":
            self._cancel_movement_draft()
            self._selection_state = self._selection_state.close_context_menu()

    def _submit_finite_option(self, selected_option_id: str | None) -> None:
        if self._core_client is None:
            self._set_finite_state(
                self._finite_state.with_local_invalid(
                    violation_code="no_core_client",
                    message="Finite submission requires a configured core client.",
                    field="client",
                )
            )
            return
        self._set_finite_state(self._submit_finite_option_or_fatal(selected_option_id))

    def _submit_finite_option_or_fatal(
        self,
        selected_option_id: str | None,
    ) -> FiniteDecisionUiState:
        client = self._core_client
        if client is None:
            return self._finite_state.with_local_invalid(
                violation_code="no_core_client",
                message="Finite submission requires a configured core client.",
                field="client",
            )
        try:
            return submit_finite_option(
                state=self._finite_state,
                client=client,
                selected_option_id=selected_option_id,
                viewer_player_id=self._viewer_player_id,
            )
        except UiClientProtocolError as exc:
            return self._fatal_game_engine_state(exc)
        except RenderViewModelError as exc:
            return self._fatal_game_engine_state(exc)
        except MovementSubmissionError as exc:
            return self._fatal_game_engine_state(exc)
        except KeyError as exc:
            return self._fatal_game_engine_state(exc)

    def _submit_movement_draft(self) -> None:
        try:
            result = submit_movement_draft(
                state=self._finite_state,
                movement_draft=self._movement_draft,
                client=self._core_client,
                viewer_player_id=self._viewer_player_id,
            )
        except UiClientProtocolError as exc:
            self._set_finite_state(self._fatal_game_engine_state(exc))
            return
        except RenderViewModelError as exc:
            self._set_finite_state(self._fatal_game_engine_state(exc))
            return
        except MovementSubmissionError as exc:
            self._set_finite_state(self._fatal_game_engine_state(exc))
            return
        except KeyError as exc:
            self._set_finite_state(self._fatal_game_engine_state(exc))
            return
        if result.refreshed_view is not None:
            self._apply_refreshed_game_view(
                view=result.refreshed_view,
                state=result.finite_state,
            )
        if result.clear_movement_draft:
            self._movement_draft = None
            self._selection_state = self._selection_state.without_movement_draft_overlays(
                self._preferences
            )
        self._set_finite_state(result.finite_state)

    def _fatal_game_engine_state(
        self,
        exc: FatalGameEngineException,
    ) -> FiniteDecisionUiState:
        logger.exception("Fatal game engine error during Arcade UI interaction.")
        self._movement_draft = None
        self._selection_state = self._selection_state.without_movement_draft_overlays(
            self._preferences
        )
        self._fatal_exit_deadline_monotonic = time.monotonic() + FATAL_ENGINE_EXIT_DELAY_SECONDS
        return self._finite_state.with_fatal_game_engine_error(
            message=(
                "Fatal game engine error. "
                f"Closing in {FATAL_ENGINE_EXIT_DELAY_SECONDS:.0f} seconds."
            ),
            detail=_fatal_game_engine_error_detail(exc),
        )

    def _set_finite_state(self, state: FiniteDecisionUiState) -> None:
        self._finite_state = state
        self._pending_decision = state.pending_decision
        self._event_cursor = state.event_cursor
        hud = replace(
            self._battlefield_view.hud,
            pending_decision_summary=_pending_decision_summary(state.pending_decision),
            event_log_lines=_hud_event_lines(
                current_lines=self._battlefield_view.hud.event_log_lines,
                state_lines=state.event_log_lines,
            ),
        )
        self._battlefield_view = replace(self._battlefield_view, hud=hud)
        self._sync_movement_draft()

    def _sync_movement_draft(self) -> None:
        current = self._movement_draft
        if current is not None and current.is_for(
            selection=self._selection_state,
            pending_decision=self._pending_decision,
        ):
            self._movement_draft = current.with_recomputed_hints(view=self._battlefield_view)
            return
        if (
            current is not None
            and self._pending_decision is not None
            and self._selection_state.selected_unit_id == current.selected_unit_id
            and current.can_retry_for(pending_decision=self._pending_decision)
        ):
            self._movement_draft = current.with_retry_request(
                view=self._battlefield_view,
                pending_decision=self._pending_decision,
            )
            self._selection_state = self._selection_state.with_movement_draft_overlays(
                self._preferences
            )
            return
        next_draft = MovementDraft.start_for_pending(
            view=self._battlefield_view,
            selection=self._selection_state,
            pending_decision=self._pending_decision,
        )
        if next_draft is not None:
            self._movement_draft = next_draft
            self._selection_state = self._selection_state.with_movement_draft_overlays(
                self._preferences
            )
            return
        if current is not None:
            self._movement_draft = None
            self._selection_state = self._selection_state.without_movement_draft_overlays(
                self._preferences
            )

    def _cancel_movement_draft(self) -> None:
        if self._movement_draft is None:
            return
        if self._movement_draft.has_assignments and self._movement_draft.selected_model_ids:
            self._movement_draft = self._movement_draft.clear_active_selection(
                view=self._battlefield_view
            )
            return
        self._movement_draft = None
        self._selection_state = self._selection_state.without_movement_draft_overlays(
            self._preferences
        )

    def _apply_movement_selection_at(
        self,
        *,
        world_point: WorldPoint,
        modifiers: int,
    ) -> bool:
        if self._movement_draft is None:
            return False
        for hit in model_hits_at(view=self._battlefield_view, world_point=world_point):
            if hit.unit_id != self._movement_draft.selected_unit_id:
                continue
            ref = entity_ref_for_model(
                view=self._battlefield_view,
                unit_id=hit.unit_id,
                model_id=hit.model_id,
            )
            if ref is None:
                return False
            if modifiers & arcade.key.MOD_CTRL:
                self._movement_draft = self._movement_draft.subtract_model_selection(
                    view=self._battlefield_view,
                    ref=ref,
                )
            elif modifiers & arcade.key.MOD_SHIFT:
                self._movement_draft = self._movement_draft.add_model_selection(
                    view=self._battlefield_view,
                    ref=ref,
                )
            else:
                self._movement_draft = self._movement_draft.replace_model_selection(
                    view=self._battlefield_view,
                    ref=ref,
                )
            return True
        return False

    def _context_menu_action_at(self, world_point: WorldPoint) -> ContextMenuAction | None:
        menu = build_context_menu(
            view=self._battlefield_view,
            selection=self._selection_state,
            pending_decision=self._pending_decision,
            fallback_anchor_world=self._mouse_world_position,
        )
        if menu is None:
            return None
        return _context_menu_action_at(menu=menu, world_point=world_point)

    def _context_anchor_world(self) -> WorldPoint:
        if self._mouse_world_position is not None:
            return self._mouse_world_position
        unit = selected_unit(self._battlefield_view, self._selection_state)
        if unit is not None:
            return unit_center(unit)
        return (0.0, 0.0)

    def _apply_refreshed_game_view(
        self,
        *,
        view: UiGameView,
        state: FiniteDecisionUiState,
    ) -> None:
        self._battlefield_view = self._battlefield_view.refreshed_from_projection(
            battlefield_state=view.battlefield_state,
            phase_label=view.current_battle_phase or view.stage,
            active_player_id=view.active_player_id or "none",
            pending_decision_summary=_pending_decision_summary(state.pending_decision),
            event_log_lines=_hud_event_lines(
                current_lines=self._battlefield_view.hud.event_log_lines,
                state_lines=state.event_log_lines,
            ),
        )


def _context_menu_action_at(
    *,
    menu: ContextMenuView,
    world_point: WorldPoint,
) -> ContextMenuAction | None:
    anchor_x, anchor_y = menu.anchor_world
    world_x, world_y = world_point
    menu_x = anchor_x + 1.0
    if not menu_x - 0.25 <= world_x <= menu_x + CONTEXT_MENU_ACTION_WIDTH_WORLD:
        return None
    relative_y = (anchor_y + 1.0) - world_y
    line_index = round(relative_y / CONTEXT_MENU_LINE_HEIGHT_WORLD)
    if abs(relative_y - (line_index * CONTEXT_MENU_LINE_HEIGHT_WORLD)) > (
        CONTEXT_MENU_LINE_TOLERANCE_WORLD
    ):
        return None
    action_index = line_index - 1
    if action_index < 0 or action_index >= len(menu.actions):
        return None
    return menu.actions[action_index]


def _pending_decision_summary(pending_decision: UiDecision | None) -> str:
    if pending_decision is None:
        return "No pending engine decision"
    if pending_decision.is_parameterized:
        proposal = pending_decision.parameterized_proposal
        label = (
            proposal.proposal_kind
            if proposal is not None and proposal.proposal_kind is not None
            else pending_decision.decision_type
        )
        return f"Proposal required: {label}"
    return f"{pending_decision.decision_type}: {len(pending_decision.options)} options"


def _fatal_game_engine_error_detail(exc: FatalGameEngineException) -> str:
    if type(exc) is KeyError:
        return f"Missing engine projection field: {exc!s}."
    return f"{type(exc).__name__}: {exc}"


def _hud_event_lines(
    *,
    current_lines: tuple[str, ...],
    state_lines: tuple[str, ...],
) -> tuple[str, ...]:
    if state_lines:
        return state_lines
    return current_lines


def _preference_source_label(result: PreferencesLoadResult) -> str:
    if result.source_path is not None:
        if result.has_errors:
            return f"{result.source_path.name} (load diagnostics)"
        return result.source_path.name
    if result.used_builtin_default:
        return "built-in default"
    return "unknown preferences"


def _draw_world_primitives(
    primitives: tuple[RenderPrimitive, ...],
    camera: WorldCamera,
) -> None:
    for primitive in primitives:
        if type(primitive) is PolygonPrimitive:
            _draw_polygon_primitive(primitive, camera)
        elif type(primitive) is CirclePrimitive:
            _draw_circle_primitive(primitive, camera)
        elif type(primitive) is PolylinePrimitive:
            _draw_polyline_primitive(primitive, camera)
        elif type(primitive) is TextPrimitive:
            _draw_text_primitive(primitive, camera)


def _draw_text_primitives(
    primitives: tuple[TextPrimitive, ...],
    camera: WorldCamera,
) -> None:
    for primitive in primitives:
        _draw_text_primitive(primitive, camera)


def _draw_polygon_primitive(primitive: PolygonPrimitive, camera: WorldCamera) -> None:
    points = tuple(
        _screen_point(point, primitive.coordinate_space, camera) for point in primitive.points
    )
    if primitive.fill_color[3] > 0:
        arcade.draw_polygon_filled(points, primitive.fill_color)
    arcade.draw_polygon_outline(points, primitive.outline_color, primitive.line_width)


def _draw_circle_primitive(primitive: CirclePrimitive, camera: WorldCamera) -> None:
    center_x, center_y = _screen_point(primitive.center, primitive.coordinate_space, camera)
    radius = (
        primitive.radius
        if primitive.coordinate_space == "screen"
        else primitive.radius * camera.zoom
    )
    if primitive.fill_color[3] > 0:
        arcade.draw_circle_filled(center_x, center_y, radius, primitive.fill_color)
    arcade.draw_circle_outline(
        center_x,
        center_y,
        radius,
        primitive.outline_color,
        primitive.line_width,
    )


def _draw_polyline_primitive(primitive: PolylinePrimitive, camera: WorldCamera) -> None:
    points = tuple(
        _screen_point(point, primitive.coordinate_space, camera) for point in primitive.points
    )
    for start, end in pairwise(points):
        arcade.draw_line(
            start[0],
            start[1],
            end[0],
            end[1],
            primitive.color,
            primitive.line_width,
        )


def _draw_text_primitive(primitive: TextPrimitive, camera: WorldCamera) -> None:
    x, y = _screen_point(primitive.position, primitive.coordinate_space, camera)
    arcade.draw_text(
        primitive.text,
        x,
        y,
        primitive.color,
        font_size=primitive.font_size,
        anchor_x=primitive.anchor_x,
        anchor_y=primitive.anchor_y,
    )


def _screen_point(
    point: WorldPoint,
    coordinate_space: str,
    camera: WorldCamera,
) -> tuple[float, float]:
    if coordinate_space == "world":
        return camera.world_to_screen(point)
    return point


def _mouse_button_name(button: int) -> str:
    if button == arcade.MOUSE_BUTTON_LEFT:
        return "left"
    if button == arcade.MOUSE_BUTTON_RIGHT:
        return "right"
    if button == arcade.MOUSE_BUTTON_MIDDLE:
        return "middle"
    return "unknown"


def _key_name(key: int) -> str:
    special_keys = {
        arcade.key.ESCAPE: "escape",
        arcade.key.ENTER: "enter",
        arcade.key.RETURN: "enter",
        arcade.key.TAB: "tab",
        arcade.key.SPACE: "space",
        arcade.key.BACKSPACE: "backspace",
        arcade.key.DELETE: "delete",
        arcade.key.UP: "up",
        arcade.key.DOWN: "down",
        arcade.key.LEFT: "left",
        arcade.key.RIGHT: "right",
        arcade.key.PAGEUP: "pageup",
        arcade.key.PAGEDOWN: "pagedown",
        arcade.key.HOME: "home",
        arcade.key.END: "end",
        arcade.key.F1: "f1",
        arcade.key.F2: "f2",
        arcade.key.F3: "f3",
        arcade.key.F4: "f4",
        arcade.key.F5: "f5",
        arcade.key.F6: "f6",
        arcade.key.F7: "f7",
        arcade.key.F8: "f8",
        arcade.key.F9: "f9",
        arcade.key.F10: "f10",
        arcade.key.F11: "f11",
        arcade.key.F12: "f12",
    }
    if key in special_keys:
        return special_keys[key]
    if arcade.key.A <= key <= arcade.key.Z:
        return chr(key).lower()
    if ord("0") <= key <= ord("9"):
        return chr(key)
    return "unknown"


def _modifier_names(modifiers: int) -> tuple[str, ...]:
    names: list[str] = []
    if modifiers & arcade.key.MOD_CTRL:
        names.append("ctrl")
    if modifiers & arcade.key.MOD_ALT:
        names.append("alt")
    if modifiers & arcade.key.MOD_SHIFT:
        names.append("shift")
    if modifiers & arcade.key.MOD_COMMAND:
        names.append("meta")
    return tuple(names)
