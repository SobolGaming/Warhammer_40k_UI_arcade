"""Local selection state and model-base hit detection."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from warhammer40k_arcade_ui.preferences.registries import overlay_registry
from warhammer40k_arcade_ui.preferences.schema import UiPreferences
from warhammer40k_arcade_ui.render.camera import WorldPoint
from warhammer40k_arcade_ui.render.view_models import BattlefieldView, ModelBaseView, UnitView


@dataclass(frozen=True, slots=True)
class ModelHit:
    """A model base hit by a world-space pointer."""

    unit_id: str
    model_id: str
    distance_from_center: float
    base_radius: float

    @property
    def hit_key(self) -> str:
        """Stable key used for overlap cycling."""

        return f"{self.unit_id}:{self.model_id}"


@dataclass(frozen=True, slots=True)
class SelectionState:
    """Local-only selection state for render, HUD, and input workflows."""

    selected_unit_id: str | None
    selected_model_id: str | None
    active_overlay_ids: tuple[str, ...]
    debug_inspector_visible: bool
    selected_unit_panel_visible: bool
    selected_model_panel_visible: bool
    context_menu_open: bool = False
    context_menu_anchor_world: WorldPoint | None = None
    last_hit_keys: tuple[str, ...] = ()
    last_hit_index: int = 0

    @classmethod
    def initial(cls, preferences: UiPreferences) -> SelectionState:
        """Create initial state from active preference defaults."""

        return cls(
            selected_unit_id=None,
            selected_model_id=None,
            active_overlay_ids=_active_overlay_ids(preferences.overlays.enabled_by_default),
            debug_inspector_visible=preferences.selection.show_debug_inspector,
            selected_unit_panel_visible=preferences.hud.show_selected_unit_panel,
            selected_model_panel_visible=preferences.hud.show_selected_model_panel,
        )

    def select_at(
        self,
        *,
        view: BattlefieldView,
        world_point: WorldPoint,
        preferences: UiPreferences,
        force_cycle: bool = False,
    ) -> SelectionState:
        """Select a model hit at a world-space point, cycling overlaps when configured."""

        hits = model_hits_at(view=view, world_point=world_point)
        if not hits:
            return self.clear_selection(preferences)
        hit_keys = tuple(hit.hit_key for hit in hits)
        should_cycle = (
            force_cycle or (preferences.selection.cycle_overlapping_bases and len(hit_keys) > 1)
        ) and hit_keys == self.last_hit_keys
        hit_index = (self.last_hit_index + 1) % len(hits) if should_cycle else 0
        hit = hits[hit_index]
        return SelectionState(
            selected_unit_id=hit.unit_id,
            selected_model_id=hit.model_id,
            active_overlay_ids=_selection_overlay_ids(preferences),
            debug_inspector_visible=self.debug_inspector_visible,
            selected_unit_panel_visible=self.selected_unit_panel_visible,
            selected_model_panel_visible=self.selected_model_panel_visible,
            context_menu_open=False,
            context_menu_anchor_world=None,
            last_hit_keys=hit_keys,
            last_hit_index=hit_index,
        )

    def cycle_existing_at(
        self,
        *,
        view: BattlefieldView,
        world_point: WorldPoint,
        preferences: UiPreferences,
    ) -> SelectionState:
        """Cycle only when the cursor is still over the last selected hit set."""

        hits = model_hits_at(view=view, world_point=world_point)
        hit_keys = tuple(hit.hit_key for hit in hits)
        if not hit_keys or hit_keys != self.last_hit_keys:
            return self
        return self.select_at(
            view=view,
            world_point=world_point,
            preferences=preferences,
            force_cycle=True,
        )

    def clear_selection(self, preferences: UiPreferences) -> SelectionState:
        """Clear selected model/unit and return to active default overlays."""

        return SelectionState(
            selected_unit_id=None,
            selected_model_id=None,
            active_overlay_ids=_active_overlay_ids(preferences.overlays.enabled_by_default),
            debug_inspector_visible=self.debug_inspector_visible,
            selected_unit_panel_visible=self.selected_unit_panel_visible,
            selected_model_panel_visible=self.selected_model_panel_visible,
        )

    def toggle_debug_inspector(self) -> SelectionState:
        """Toggle the local debug inspector."""

        return replace(self, debug_inspector_visible=not self.debug_inspector_visible)

    def show_selected_unit_panel(self) -> SelectionState:
        """Show the selected-unit information panel."""

        return replace(self, selected_unit_panel_visible=True)

    def show_selected_model_panel(self) -> SelectionState:
        """Show selected-model details inside the selection panel."""

        return replace(self, selected_model_panel_visible=True)

    def toggle_overlay(self, overlay_id: str) -> SelectionState:
        """Toggle a registered active advisory overlay."""

        overlay = overlay_registry().get(overlay_id)
        if overlay is None or overlay.status != "active":
            return self
        active_ids = list(self.active_overlay_ids)
        if overlay_id in active_ids:
            active_ids.remove(overlay_id)
        else:
            active_ids.append(overlay_id)
        return replace(self, active_overlay_ids=tuple(active_ids))

    def with_movement_draft_overlays(self, preferences: UiPreferences) -> SelectionState:
        """Enable preference-backed overlays while a local movement draft is active."""

        return replace(
            self,
            active_overlay_ids=_active_overlay_ids(
                (
                    *self.active_overlay_ids,
                    *preferences.overlays.default_on_movement_draft,
                )
            ),
        )

    def without_movement_draft_overlays(self, preferences: UiPreferences) -> SelectionState:
        """Remove movement-draft default overlays after canceling or losing the draft."""

        movement_overlay_ids = set(preferences.overlays.default_on_movement_draft)
        return replace(
            self,
            active_overlay_ids=tuple(
                overlay_id
                for overlay_id in self.active_overlay_ids
                if overlay_id not in movement_overlay_ids
            ),
        )

    def open_context_menu(self, anchor_world: WorldPoint) -> SelectionState:
        """Open the selected-unit context menu near the given world-space anchor."""

        if self.selected_unit_id is None:
            return self
        return replace(
            self,
            context_menu_open=True,
            context_menu_anchor_world=anchor_world,
        )

    def close_context_menu(self) -> SelectionState:
        """Close the local context menu."""

        return replace(self, context_menu_open=False, context_menu_anchor_world=None)


def model_hits_at(*, view: BattlefieldView, world_point: WorldPoint) -> tuple[ModelHit, ...]:
    """Return model bases containing a world-space point, nearest first."""

    _validate_world_point(world_point)
    hits: list[ModelHit] = []
    for unit in view.units:
        for model in unit.models:
            distance = math.dist(world_point, model.position)
            if distance <= model.base_radius:
                hits.append(
                    ModelHit(
                        unit_id=unit.unit_id,
                        model_id=model.model_id,
                        distance_from_center=distance,
                        base_radius=model.base_radius,
                    )
                )
    return tuple(
        sorted(
            hits,
            key=lambda hit: (hit.distance_from_center, hit.unit_id, hit.model_id),
        )
    )


def selected_unit(view: BattlefieldView, selection: SelectionState) -> UnitView | None:
    """Return the selected unit view, if it is still present in the projection."""

    if selection.selected_unit_id is None:
        return None
    for unit in view.units:
        if unit.unit_id == selection.selected_unit_id:
            return unit
    return None


def selected_model(view: BattlefieldView, selection: SelectionState) -> ModelBaseView | None:
    """Return the selected model view, if it is still present in the projection."""

    unit = selected_unit(view, selection)
    if unit is None or selection.selected_model_id is None:
        return None
    for model in unit.models:
        if model.model_id == selection.selected_model_id:
            return model
    return None


def unit_center(unit: UnitView) -> WorldPoint:
    """Return the mean model position for a unit."""

    x_total = sum(model.position[0] for model in unit.models)
    y_total = sum(model.position[1] for model in unit.models)
    return (x_total / len(unit.models), y_total / len(unit.models))


def _selection_overlay_ids(preferences: UiPreferences) -> tuple[str, ...]:
    return _active_overlay_ids(
        (
            *preferences.overlays.enabled_by_default,
            *preferences.overlays.default_on_model_selection,
            *preferences.overlays.default_on_unit_selection,
        )
    )


def _active_overlay_ids(overlay_ids: tuple[str, ...]) -> tuple[str, ...]:
    registry = overlay_registry()
    active_ids: list[str] = []
    for overlay_id in overlay_ids:
        overlay = registry.get(overlay_id)
        if overlay is None or overlay.status != "active" or overlay_id in active_ids:
            continue
        active_ids.append(overlay_id)
    return tuple(active_ids)


def _validate_world_point(world_point: WorldPoint) -> None:
    world_x, world_y = world_point
    if not math.isfinite(world_x) or not math.isfinite(world_y):
        raise ValueError("world_point must contain finite coordinates")
