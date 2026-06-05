"""Deterministic in-process GUI event driver for Arcade window tests."""

from __future__ import annotations

from dataclasses import dataclass

import arcade

from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.fake_client import (
    FakeCoreClient,
    SubmittedFiniteDecision,
    SubmittedMovementPayload,
)
from warhammer40k_arcade_ui.core_client.protocol import JsonObject
from warhammer40k_arcade_ui.debug_fixtures import (
    phase6_debug_core_client,
    phase6_debug_pending_decision,
)
from warhammer40k_arcade_ui.hud.view_models import ContextMenuAction
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.preferences.schema import UiPreferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow
from warhammer40k_arcade_ui.render.camera import WorldPoint
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view

type ScreenPoint = tuple[int, int]


@dataclass(slots=True)
class GuiTestDriver:
    """Drive a real `ArcadeWarhammerWindow` through deterministic event calls."""

    window: ArcadeWarhammerWindow
    core_client: FakeCoreClient | None = None

    @classmethod
    def phase6_debug(
        cls,
        *,
        preferences: UiPreferences | None = None,
    ) -> GuiTestDriver:
        """Create the standard debug window used for finite and movement workflows."""

        core_client = phase6_debug_core_client()
        window = ArcadeWarhammerWindow(
            config=AppConfig(window_width=1280, window_height=800, resizable=False),
            battlefield_view=default_battlefield_view(),
            preferences=preferences or default_preferences(),
            pending_decision=phase6_debug_pending_decision(),
            core_client=core_client,
            viewer_player_id="player_1",
        )
        return cls(window=window, core_client=core_client)

    def close(self) -> None:
        """Close the underlying headless Arcade window."""

        self.window.close()

    def screen_for_world(self, point: WorldPoint) -> ScreenPoint:
        """Return the screen pixel nearest to a world-space table coordinate."""

        screen_x, screen_y = self.window.camera.world_to_screen(point)
        return (round(screen_x), round(screen_y))

    def move_mouse_world(self, point: WorldPoint) -> GuiTestDriver:
        """Move the test cursor to a table coordinate through the window motion handler."""

        x, y = self.screen_for_world(point)
        return self.move_mouse_screen(x, y)

    def move_mouse_screen(self, x: int, y: int) -> GuiTestDriver:
        """Move the test cursor to a screen coordinate through the window motion handler."""

        self.window.on_mouse_motion(x, y, 0, 0)
        return self

    def click_world(
        self,
        point: WorldPoint,
        *,
        button: int = arcade.MOUSE_BUTTON_LEFT,
        modifiers: int = 0,
    ) -> GuiTestDriver:
        """Click a table coordinate through the window mouse handlers."""

        x, y = self.screen_for_world(point)
        return self.click_screen(x, y, button=button, modifiers=modifiers)

    def click_screen(
        self,
        x: int,
        y: int,
        *,
        button: int = arcade.MOUSE_BUTTON_LEFT,
        modifiers: int = 0,
    ) -> GuiTestDriver:
        """Click a screen coordinate through the window mouse handlers."""

        self.window.on_mouse_press(x, y, button, modifiers)
        self.window.on_mouse_release(x, y, button, modifiers)
        return self

    def press_key(self, symbol: int, *, modifiers: int = 0) -> GuiTestDriver:
        """Press a key through the window key handler."""

        self.window.on_key_press(symbol, modifiers)
        return self

    def release_key(self, symbol: int, *, modifiers: int = 0) -> GuiTestDriver:
        """Release a key through pyglet's event dispatch path."""

        self.window.dispatch_event("on_key_release", symbol, modifiers)
        return self

    def step_frames(self, count: int = 1, *, delta_time: float = 1.0 / 60.0) -> GuiTestDriver:
        """Advance deterministic update frames without drawing."""

        for _ in range(count):
            self.window.on_update(delta_time)
        return self

    @property
    def selected_unit_id(self) -> str | None:
        """Return the currently selected unit ID."""

        return self.window.selection_state.selected_unit_id

    @property
    def selected_model_id(self) -> str | None:
        """Return the currently selected model ID."""

        return self.window.selection_state.selected_model_id

    @property
    def active_overlay_ids(self) -> tuple[str, ...]:
        """Return currently active advisory overlay IDs."""

        return self.window.selection_state.active_overlay_ids

    @property
    def debug_inspector_visible(self) -> bool:
        """Return whether the debug inspector is currently visible."""

        return self.window.selection_state.debug_inspector_visible

    @property
    def context_menu_visible(self) -> bool:
        """Return whether a context menu is currently available to render."""

        return self.window.context_menu is not None

    @property
    def context_menu_actions(self) -> tuple[ContextMenuAction, ...]:
        """Return current context menu actions."""

        menu = self.window.context_menu
        if menu is None:
            return ()
        return menu.actions

    @property
    def finite_status_kind(self) -> str:
        """Return the finite-decision status kind."""

        return self.window.finite_state.status_kind

    @property
    def finite_status_message(self) -> str:
        """Return the finite-decision status message."""

        return self.window.finite_state.status_message

    @property
    def highlighted_finite_option_id(self) -> str | None:
        """Return the highlighted finite option ID."""

        option = self.window.finite_state.highlighted_option
        return None if option is None else option.option_id

    @property
    def pending_decision_type(self) -> str | None:
        """Return the current pending decision type."""

        decision = self.window.pending_decision
        return None if decision is None else decision.decision_type

    @property
    def pending_proposal_kind(self) -> str | None:
        """Return the current pending proposal kind, if any."""

        decision = self.window.pending_decision
        proposal = None if decision is None else decision.movement_proposal
        return None if proposal is None else proposal.proposal_kind

    @property
    def movement_draft_ready(self) -> bool:
        """Return whether the local movement draft has a payload preview."""

        draft = self.window.movement_draft
        return False if draft is None else draft.is_ready

    @property
    def movement_assigned_model_count(self) -> int:
        """Return the number of models with non-zero drafted movement."""

        draft = self.window.movement_draft
        return 0 if draft is None else draft.assigned_model_count

    @property
    def movement_unchanged_model_count(self) -> int:
        """Return the number of models represented by no-op movement paths."""

        draft = self.window.movement_draft
        return 0 if draft is None else draft.unchanged_model_count

    @property
    def movement_selected_model_ids(self) -> tuple[str, ...]:
        """Return active movement-draft model IDs."""

        draft = self.window.movement_draft
        return () if draft is None else draft.selected_model_ids

    @property
    def movement_payload_ready(self) -> bool:
        """Return whether the current movement draft exposes a payload preview."""

        draft = self.window.movement_draft
        return False if draft is None else draft.payload_preview is not None

    @property
    def movement_payload(self) -> JsonObject | None:
        """Return the ready movement payload, if any."""

        draft = self.window.movement_draft
        if draft is None:
            return None
        payload = draft.payload_preview
        if payload is None:
            return None
        return payload

    @property
    def finite_submissions(self) -> tuple[SubmittedFiniteDecision, ...]:
        """Return finite submissions recorded by the fake client."""

        if self.core_client is None:
            return ()
        return tuple(self.core_client.finite_submissions)

    @property
    def movement_submissions(self) -> tuple[SubmittedMovementPayload, ...]:
        """Return movement submissions recorded by the fake client."""

        if self.core_client is None:
            return ()
        return tuple(self.core_client.movement_submissions)
