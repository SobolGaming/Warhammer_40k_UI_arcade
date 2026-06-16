"""Deterministic in-process GUI event driver for Arcade window tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import arcade

from warhammer40k_arcade_ui.config import AppConfig
from warhammer40k_arcade_ui.core_client.fake_client import (
    FakeCoreClient,
    SubmittedFiniteDecision,
    SubmittedMovementPayload,
)
from warhammer40k_arcade_ui.core_client.protocol import JsonObject, UiCoreClient
from warhammer40k_arcade_ui.debug_fixtures import (
    phase6_debug_core_client,
    phase6_debug_pending_decision,
)
from warhammer40k_arcade_ui.diagnostics.forensic_trace import (
    ForensicTraceWriter,
    trace_core_client,
)
from warhammer40k_arcade_ui.hud.toolkit import HudButtonHitRegion, HudScrollHitRegion
from warhammer40k_arcade_ui.hud.view_models import ContextMenuAction
from warhammer40k_arcade_ui.preferences.defaults import default_preferences
from warhammer40k_arcade_ui.preferences.schema import UiPreferences
from warhammer40k_arcade_ui.render.arcade_window import ArcadeWarhammerWindow
from warhammer40k_arcade_ui.render.camera import WorldPoint
from warhammer40k_arcade_ui.render.default_fixture import default_battlefield_view

if TYPE_CHECKING:
    from tests.support.render_capture import RenderCapture

type GuiCoreMode = Literal["phase6_debug", "live_core_smoke"]
type ScreenPoint = tuple[int, int]


@dataclass(slots=True)
class GuiTestDriver:
    """Drive a real `ArcadeWarhammerWindow` through deterministic event calls."""

    window: ArcadeWarhammerWindow
    core_client: UiCoreClient | None = None
    core_mode: GuiCoreMode | Literal["custom"] = "custom"
    viewer_player_id: str = "player_1"

    @classmethod
    def launch(
        cls,
        *,
        core_mode: GuiCoreMode = "phase6_debug",
        preferences: UiPreferences | None = None,
        trace_writer: ForensicTraceWriter | None = None,
    ) -> GuiTestDriver:
        """Launch a driver against the selected UI-facing core mode."""

        if core_mode == "phase6_debug":
            return cls.phase6_debug(preferences=preferences, trace_writer=trace_writer)
        return cls.live_core_smoke(preferences=preferences, trace_writer=trace_writer)

    @classmethod
    def phase6_debug(
        cls,
        *,
        preferences: UiPreferences | None = None,
        trace_writer: ForensicTraceWriter | None = None,
    ) -> GuiTestDriver:
        """Create the standard debug window used for finite and movement workflows."""

        core_client = phase6_debug_core_client()
        window_core_client: UiCoreClient = (
            trace_core_client(core_client, trace_writer)
            if trace_writer is not None
            else core_client
        )
        window = ArcadeWarhammerWindow(
            config=AppConfig(window_width=1280, window_height=800, resizable=False),
            battlefield_view=default_battlefield_view(),
            preferences=preferences or default_preferences(),
            pending_decision=phase6_debug_pending_decision(),
            core_client=window_core_client,
            viewer_player_id="player_1",
            trace_writer=trace_writer,
        )
        return cls(
            window=window,
            core_client=core_client,
            core_mode="phase6_debug",
            viewer_player_id="player_1",
        )

    @classmethod
    def live_core_smoke(
        cls,
        *,
        preferences: UiPreferences | None = None,
        trace_writer: ForensicTraceWriter | None = None,
        stop_at_phase: str | None = None,
    ) -> GuiTestDriver:
        """Create a driver backed by the real local core smoke session."""

        from warhammer40k_arcade_ui.core_client.live_smoke import build_live_core_smoke_startup

        startup = build_live_core_smoke_startup(stop_at_phase=stop_at_phase)
        window_core_client = (
            trace_core_client(startup.core_client, trace_writer)
            if trace_writer is not None
            else startup.core_client
        )
        window = ArcadeWarhammerWindow(
            config=AppConfig(window_width=1280, window_height=800, resizable=False),
            battlefield_view=startup.battlefield_view,
            preferences=preferences or default_preferences(),
            initial_status=startup.status,
            initial_game_view=startup.game_view,
            core_client=window_core_client,
            viewer_player_id=startup.viewer_player_id,
            event_cursor=startup.event_cursor,
            trace_writer=trace_writer,
        )
        return cls(
            window=window,
            core_client=startup.core_client,
            core_mode="live_core_smoke",
            viewer_player_id=startup.viewer_player_id,
        )

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

    def scroll_screen(
        self,
        x: int,
        y: int,
        *,
        scroll_x: float = 0.0,
        scroll_y: float = 0.0,
    ) -> GuiTestDriver:
        """Scroll a screen coordinate through the window mouse wheel handler."""

        self.window.on_mouse_scroll(x, y, scroll_x, scroll_y)
        return self

    def press_key(self, symbol: int, *, modifiers: int = 0) -> GuiTestDriver:
        """Press a key through the window key handler."""

        self.window.on_key_press(symbol, modifiers)
        return self

    def release_key(self, symbol: int, *, modifiers: int = 0) -> GuiTestDriver:
        """Release a key through the window key-release handler."""

        self.window.on_key_release(symbol, modifiers)
        return self

    def step_frames(self, count: int = 1, *, delta_time: float = 1.0 / 60.0) -> GuiTestDriver:
        """Advance deterministic update frames without drawing."""

        for _ in range(count):
            self.window.on_update(delta_time)
        return self

    def capture_frame(self, *, source_name: str) -> RenderCapture:
        """Render and capture the current window framebuffer."""

        from tests.support.render_capture import capture_window_frame

        return capture_window_frame(self.window, source_name=source_name)

    @property
    def selected_unit_id(self) -> str | None:
        """Return the currently selected unit ID."""

        return self.window.selection_state.selected_unit_id

    @property
    def selected_model_id(self) -> str | None:
        """Return the currently selected model ID."""

        return self.window.selection_state.selected_model_id

    @property
    def battlefield_unit_ids(self) -> tuple[str, ...]:
        """Return unit IDs in the current battlefield projection."""

        return tuple(unit.unit_id for unit in self.window.battlefield_view.units)

    def first_model_position_for_unit(self, unit_id: str) -> WorldPoint:
        """Return the first projected model position for a unit."""

        for unit in self.window.battlefield_view.units:
            if unit.unit_id == unit_id:
                return unit.models[0].position
        raise ValueError(f"Unit is not projected: {unit_id}")

    @property
    def active_overlay_ids(self) -> tuple[str, ...]:
        """Return currently active advisory overlay IDs."""

        return self.window.selection_state.active_overlay_ids

    @property
    def hud_button_hit_regions(self) -> tuple[HudButtonHitRegion, ...]:
        """Return HUD button hit regions from the latest drawn frame."""

        return self.window.hud_button_hit_regions

    @property
    def hud_scroll_hit_regions(self) -> tuple[HudScrollHitRegion, ...]:
        """Return HUD scroll hit regions from the latest drawn frame."""

        return self.window.hud_scroll_hit_regions

    @property
    def hud_scroll_offsets(self) -> dict[str, tuple[float, float]]:
        """Return current HUD scroll offsets keyed by component ID."""

        return self.window.hud_scroll_offsets

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

        if not isinstance(self.core_client, FakeCoreClient):
            return ()
        return tuple(self.core_client.finite_submissions)

    @property
    def movement_submissions(self) -> tuple[SubmittedMovementPayload, ...]:
        """Return movement submissions recorded by the fake client."""

        if not isinstance(self.core_client, FakeCoreClient):
            return ()
        return tuple(self.core_client.movement_submissions)
