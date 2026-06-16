"""Request-scoped entity selection profiles and local selection state."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Literal, cast

from warhammer40k_arcade_ui.core_client.protocol import UiDecision
from warhammer40k_arcade_ui.render.camera import WorldPoint
from warhammer40k_arcade_ui.render.view_models import (
    BattlefieldView,
    ModelBaseView,
    UnitView,
)
from warhammer40k_arcade_ui.state.selection import unit_center

MOVEMENT_PROPOSAL_DECISION_TYPE = "submit_movement_proposal"
SCOUT_MOVE_DECISION_TYPE = "submit_scout_move"
MOVEMENT_SHAPED_DECISION_TYPES = frozenset(
    (
        MOVEMENT_PROPOSAL_DECISION_TYPE,
        SCOUT_MOVE_DECISION_TYPE,
    )
)

type EntityLayer = Literal[
    "model",
    "model_group",
    "unit",
    "attached_unit",
    "army",
    "objective",
    "terrain",
    "card",
    "dice",
    "custom",
]
type EntityKind = EntityLayer
type EntityLayerStatus = Literal["active", "planned"]
type EntitySelectionSeverity = Literal["info", "warning", "error"]

_ENTITY_LAYERS: tuple[EntityLayer, ...] = (
    "model",
    "model_group",
    "unit",
    "attached_unit",
    "army",
    "objective",
    "terrain",
    "card",
    "dice",
    "custom",
)
_FINITE_UNIT_ID_KEYS = (
    "unit_instance_id",
    "selected_unit_instance_id",
    "target_unit_instance_id",
    "unit_id",
)


class EntitySelectionError(ValueError):
    """Raised when request-scoped entity selection state is malformed."""


@dataclass(frozen=True, slots=True)
class EntityLayerDefinition:
    """A known entity-selection layer."""

    layer_id: EntityLayer
    label: str
    status: EntityLayerStatus

    def __post_init__(self) -> None:
        _validate_entity_layer(self.layer_id)
        object.__setattr__(self, "label", _non_empty_string("label", self.label))


@dataclass(frozen=True, slots=True)
class EntitySelectionDiagnostic:
    """A local typed diagnostic for request-scoped selection."""

    code: str
    message: str
    field: str | None = None
    entity_ref_key: str | None = None
    severity: EntitySelectionSeverity = "warning"

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _non_empty_string("code", self.code))
        object.__setattr__(self, "message", _non_empty_string("message", self.message))
        object.__setattr__(self, "field", _optional_string("field", self.field))
        object.__setattr__(
            self,
            "entity_ref_key",
            _optional_string("entity_ref_key", self.entity_ref_key),
        )
        if self.severity not in ("info", "warning", "error"):
            raise EntitySelectionError("severity must be info, warning, or error.")


@dataclass(frozen=True, slots=True)
class EntityRef:
    """A UI-local pointer to a projected or request-provided selectable entity."""

    kind: EntityKind
    entity_id: str
    owner_player_id: str | None = None
    parent_refs: tuple[EntityRef, ...] = ()
    display_label: str | None = None
    visual_anchor_world: WorldPoint | None = None

    def __post_init__(self) -> None:
        _validate_entity_layer(self.kind)
        object.__setattr__(self, "entity_id", _non_empty_string("entity_id", self.entity_id))
        object.__setattr__(
            self,
            "owner_player_id",
            _optional_string("owner_player_id", self.owner_player_id),
        )
        if type(self.parent_refs) is not tuple:
            raise EntitySelectionError("parent_refs must be a tuple.")
        if any(type(parent) is not EntityRef for parent in self.parent_refs):
            raise EntitySelectionError("parent_refs must contain EntityRef items.")
        object.__setattr__(
            self,
            "display_label",
            _optional_string("display_label", self.display_label),
        )
        object.__setattr__(
            self,
            "visual_anchor_world",
            _optional_world_point("visual_anchor_world", self.visual_anchor_world),
        )

    @property
    def selection_key(self) -> str:
        """Return the deterministic identity used for local set operations."""

        return f"{self.kind}:{self.entity_id}"


@dataclass(frozen=True, slots=True)
class EntityAliasRule:
    """A request-profile-specific alias from one entity ref to one or more target refs."""

    source_layer: EntityLayer
    target_layer: EntityLayer
    source_ref: EntityRef
    target_refs: tuple[EntityRef, ...]
    label: str

    def __post_init__(self) -> None:
        _validate_entity_layer(self.source_layer)
        _validate_entity_layer(self.target_layer)
        if type(self.source_ref) is not EntityRef:
            raise EntitySelectionError("source_ref must be an EntityRef.")
        if self.source_ref.kind != self.source_layer:
            raise EntitySelectionError("source_ref kind must match source_layer.")
        if type(self.target_refs) is not tuple or not self.target_refs:
            raise EntitySelectionError("target_refs must be a non-empty tuple.")
        if any(type(target) is not EntityRef for target in self.target_refs):
            raise EntitySelectionError("target_refs must contain EntityRef items.")
        if any(target.kind != self.target_layer for target in self.target_refs):
            raise EntitySelectionError("target_ref kind must match target_layer.")
        object.__setattr__(self, "label", _non_empty_string("label", self.label))


@dataclass(frozen=True, slots=True)
class SelectionCardinality:
    """Allowed local selection counts for the active request profile."""

    min_count: int = 0
    max_count: int | None = None

    def __post_init__(self) -> None:
        if type(self.min_count) is not int or self.min_count < 0:
            raise EntitySelectionError("min_count must be a non-negative integer.")
        if self.max_count is not None and (
            type(self.max_count) is not int or self.max_count < self.min_count
        ):
            raise EntitySelectionError("max_count must be None or at least min_count.")


@dataclass(frozen=True, slots=True)
class EntitySelectionProfile:
    """What entity selection means for the current pending request."""

    request_id: str | None
    decision_type: str
    actor_id: str | None
    selectable_layers: tuple[EntityLayer, ...]
    active_layer: EntityLayer | None
    candidate_refs: tuple[EntityRef, ...]
    alias_rules: tuple[EntityAliasRule, ...]
    cardinality: SelectionCardinality
    additive_allowed: bool
    subtractive_allowed: bool
    unsupported_reason: str | None = None
    diagnostics: tuple[EntitySelectionDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _optional_string("request_id", self.request_id))
        object.__setattr__(
            self,
            "decision_type",
            _non_empty_string("decision_type", self.decision_type),
        )
        object.__setattr__(self, "actor_id", _optional_string("actor_id", self.actor_id))
        if type(self.selectable_layers) is not tuple:
            raise EntitySelectionError("selectable_layers must be a tuple.")
        for layer in self.selectable_layers:
            _validate_entity_layer(layer)
        if self.active_layer is not None:
            _validate_entity_layer(self.active_layer)
            if self.active_layer not in self.selectable_layers:
                raise EntitySelectionError("active_layer must be selectable.")
        if type(self.candidate_refs) is not tuple:
            raise EntitySelectionError("candidate_refs must be a tuple.")
        if any(type(ref) is not EntityRef for ref in self.candidate_refs):
            raise EntitySelectionError("candidate_refs must contain EntityRef items.")
        _validate_unique_ref_keys("candidate_refs", self.candidate_refs)
        if type(self.alias_rules) is not tuple:
            raise EntitySelectionError("alias_rules must be a tuple.")
        if any(type(rule) is not EntityAliasRule for rule in self.alias_rules):
            raise EntitySelectionError("alias_rules must contain EntityAliasRule items.")
        if type(self.cardinality) is not SelectionCardinality:
            raise EntitySelectionError("cardinality must be a SelectionCardinality.")
        if type(self.additive_allowed) is not bool:
            raise EntitySelectionError("additive_allowed must be a bool.")
        if type(self.subtractive_allowed) is not bool:
            raise EntitySelectionError("subtractive_allowed must be a bool.")
        object.__setattr__(
            self,
            "unsupported_reason",
            _optional_string("unsupported_reason", self.unsupported_reason),
        )
        if type(self.diagnostics) is not tuple:
            raise EntitySelectionError("diagnostics must be a tuple.")
        if any(
            type(diagnostic) is not EntitySelectionDiagnostic for diagnostic in self.diagnostics
        ):
            raise EntitySelectionError("diagnostics must contain EntitySelectionDiagnostic items.")

    @property
    def is_supported(self) -> bool:
        """Return whether this profile exposes at least one selectable layer."""

        return self.unsupported_reason is None and self.active_layer is not None

    @property
    def request_scope_key(self) -> tuple[str | None, str, str | None]:
        """Return the identity used to decide whether selections can reconcile."""

        return (self.request_id, self.decision_type, self.actor_id)

    def candidates_for_layer(self, layer: EntityLayer) -> tuple[EntityRef, ...]:
        """Return candidates available in the given layer in stable profile order."""

        _validate_entity_layer(layer)
        return tuple(ref for ref in self.candidate_refs if ref.kind == layer)

    def candidate_for_ref(self, ref: EntityRef) -> EntityRef | None:
        """Return the profile candidate matching a ref's stable key."""

        for candidate in self.candidate_refs:
            if candidate.selection_key == ref.selection_key:
                return candidate
        return None

    def available_layers(self) -> tuple[EntityLayer, ...]:
        """Return selectable layers that currently have candidates."""

        return tuple(layer for layer in self.selectable_layers if self.candidates_for_layer(layer))


@dataclass(frozen=True, slots=True)
class EntitySelectionState:
    """Local request-scoped selection state for the active entity profile."""

    profile: EntitySelectionProfile
    selected_refs: tuple[EntityRef, ...]
    focused_ref: EntityRef | None
    active_layer: EntityLayer | None
    diagnostics: tuple[EntitySelectionDiagnostic, ...]

    def __post_init__(self) -> None:
        if type(self.profile) is not EntitySelectionProfile:
            raise EntitySelectionError("profile must be an EntitySelectionProfile.")
        if type(self.selected_refs) is not tuple:
            raise EntitySelectionError("selected_refs must be a tuple.")
        if any(type(ref) is not EntityRef for ref in self.selected_refs):
            raise EntitySelectionError("selected_refs must contain EntityRef items.")
        _validate_unique_ref_keys("selected_refs", self.selected_refs)
        if self.focused_ref is not None and type(self.focused_ref) is not EntityRef:
            raise EntitySelectionError("focused_ref must be an EntityRef.")
        if self.active_layer is not None:
            _validate_entity_layer(self.active_layer)
            if self.active_layer not in self.profile.selectable_layers:
                raise EntitySelectionError("active_layer must be selectable for profile.")
        if type(self.diagnostics) is not tuple:
            raise EntitySelectionError("diagnostics must be a tuple.")
        if any(
            type(diagnostic) is not EntitySelectionDiagnostic for diagnostic in self.diagnostics
        ):
            raise EntitySelectionError("diagnostics must contain EntitySelectionDiagnostic items.")

    @classmethod
    def initial(cls, profile: EntitySelectionProfile) -> EntitySelectionState:
        """Create an empty state for a profile."""

        return cls(
            profile=profile,
            selected_refs=(),
            focused_ref=_first_candidate_for_layer(profile, profile.active_layer),
            active_layer=profile.active_layer,
            diagnostics=profile.diagnostics,
        )

    @classmethod
    def reconcile(
        cls,
        *,
        previous: EntitySelectionState | None,
        profile: EntitySelectionProfile,
    ) -> EntitySelectionState:
        """Clear or preserve selection when a refreshed request profile arrives."""

        if previous is None:
            return cls.initial(profile)
        if previous.profile.request_scope_key != profile.request_scope_key:
            return cls.initial(profile)
        active_layer = (
            previous.active_layer
            if previous.active_layer in profile.available_layers()
            else profile.active_layer
        )
        retained: list[EntityRef] = []
        missing: list[EntitySelectionDiagnostic] = []
        for ref in previous.selected_refs:
            candidate = profile.candidate_for_ref(ref)
            if candidate is None:
                missing.append(
                    _diagnostic(
                        code="candidate_missing_after_refresh",
                        message=f"Selected entity is no longer available: {ref.selection_key}.",
                        field="selected_refs",
                        entity_ref_key=ref.selection_key,
                    )
                )
                continue
            retained.append(candidate)
        selected_refs = _ordered_candidates(profile=profile, refs=tuple(retained))
        focused_ref = (
            profile.candidate_for_ref(previous.focused_ref)
            if previous.focused_ref is not None
            else None
        )
        if focused_ref is None and selected_refs:
            focused_ref = selected_refs[0]
        if focused_ref is None:
            focused_ref = _first_candidate_for_layer(profile, active_layer)
        return cls(
            profile=profile,
            selected_refs=selected_refs,
            focused_ref=focused_ref,
            active_layer=active_layer,
            diagnostics=(*profile.diagnostics, *missing),
        )

    def replace_selection(self, ref: EntityRef) -> EntitySelectionState:
        """Replace request-scoped selection with the resolved ref or alias targets."""

        resolved, diagnostics = self._resolve_active_refs(ref)
        if not resolved:
            return self._with_operation_diagnostics(diagnostics)
        return self._with_selected_refs(resolved, diagnostics)

    def add_selection(self, ref: EntityRef) -> EntitySelectionState:
        """Add a resolved ref to request-scoped selection when the profile allows it."""

        if self.selected_refs and not self.profile.additive_allowed:
            return self._with_operation_diagnostics(
                (
                    _diagnostic(
                        code="additive_selection_not_allowed",
                        message="The current request profile does not allow additive selection.",
                        field="additive_allowed",
                        entity_ref_key=ref.selection_key,
                    ),
                )
            )
        resolved, diagnostics = self._resolve_active_refs(ref)
        if not resolved:
            return self._with_operation_diagnostics(diagnostics)
        return self._with_selected_refs((*self.selected_refs, *resolved), diagnostics)

    def subtract_selection(self, ref: EntityRef) -> EntitySelectionState:
        """Remove a resolved ref from request-scoped selection when allowed."""

        if not self.profile.subtractive_allowed:
            return self._with_operation_diagnostics(
                (
                    _diagnostic(
                        code="subtractive_selection_not_allowed",
                        message="The current request profile does not allow subtractive selection.",
                        field="subtractive_allowed",
                        entity_ref_key=ref.selection_key,
                    ),
                )
            )
        resolved, diagnostics = self._resolve_active_refs(ref)
        if not resolved:
            return self._with_operation_diagnostics(diagnostics)
        removal_keys = {target.selection_key for target in resolved}
        remaining = tuple(
            selected
            for selected in self.selected_refs
            if selected.selection_key not in removal_keys
        )
        return self._with_selected_refs(remaining, diagnostics)

    def toggle_selection(self, ref: EntityRef) -> EntitySelectionState:
        """Add or remove a resolved ref based on current selection membership."""

        resolved, diagnostics = self._resolve_active_refs(ref)
        if not resolved:
            return self._with_operation_diagnostics(diagnostics)
        selected_keys = {selected.selection_key for selected in self.selected_refs}
        if all(target.selection_key in selected_keys for target in resolved):
            return self.subtract_selection(ref)
        return self.add_selection(ref) if self.selected_refs else self.replace_selection(ref)

    def clear_selection(self) -> EntitySelectionState:
        """Clear request-scoped selection without changing ordinary inspect selection."""

        return replace(
            self,
            selected_refs=(),
            focused_ref=_first_candidate_for_layer(self.profile, self.active_layer),
            diagnostics=self.profile.diagnostics,
        )

    def cycle_focus(self, step: int = 1) -> EntitySelectionState:
        """Cycle focus within the current active layer without changing selection."""

        if self.active_layer is None:
            return self._with_operation_diagnostics(
                (
                    _diagnostic(
                        code="no_active_entity_layer",
                        message="The current request profile has no active entity layer.",
                        field="active_layer",
                        severity="error",
                    ),
                )
            )
        candidates = self.profile.candidates_for_layer(self.active_layer)
        if not candidates:
            return self._with_operation_diagnostics(
                (
                    _diagnostic(
                        code="entity_layer_unavailable",
                        message=f"No candidates are available for layer: {self.active_layer}.",
                        field="active_layer",
                        severity="warning",
                    ),
                )
            )
        current_index = _candidate_index(candidates, self.focused_ref)
        next_index = (current_index + step) % len(candidates)
        return replace(
            self,
            focused_ref=candidates[next_index],
            diagnostics=self.profile.diagnostics,
        )

    def cycle_active_layer(self, step: int = 1) -> EntitySelectionState:
        """Cycle to another layer allowed by the current profile."""

        layers = self.profile.available_layers()
        if not layers:
            return self._with_operation_diagnostics(
                (
                    _diagnostic(
                        code="entity_layer_unavailable",
                        message="The current request profile has no available entity layers.",
                        field="selectable_layers",
                        severity="error",
                    ),
                )
            )
        current_index = 0
        if self.active_layer in layers:
            current_index = layers.index(self.active_layer)
        active_layer = layers[(current_index + step) % len(layers)]
        return replace(
            self,
            active_layer=active_layer,
            focused_ref=_first_candidate_for_layer(self.profile, active_layer),
            diagnostics=self.profile.diagnostics,
        )

    def select_current_group(self) -> EntitySelectionState:
        """Select the current focus's parent group when an alias supports it."""

        source = self.focused_ref or (self.selected_refs[0] if self.selected_refs else None)
        if source is None:
            return self._with_operation_diagnostics(
                (
                    _diagnostic(
                        code="no_focused_entity",
                        message="A focused entity is required to select the current group.",
                        field="focused_ref",
                    ),
                )
            )
        for parent in source.parent_refs:
            resolved, diagnostics = self._resolve_active_refs(parent)
            if resolved:
                return self._with_selected_refs(resolved, diagnostics)
        resolved, diagnostics = self._resolve_active_refs(source)
        if not resolved:
            return self._with_operation_diagnostics(diagnostics)
        return self._with_selected_refs(resolved, diagnostics)

    def visual_anchor_diagnostics(self) -> tuple[EntitySelectionDiagnostic, ...]:
        """Return diagnostics for selected refs without a safe visual anchor."""

        return visual_anchor_diagnostics(self.selected_refs)

    def _resolve_active_refs(
        self,
        ref: EntityRef,
    ) -> tuple[tuple[EntityRef, ...], tuple[EntitySelectionDiagnostic, ...]]:
        if self.active_layer is None or self.profile.unsupported_reason is not None:
            return (
                (),
                (
                    _diagnostic(
                        code="unsupported_request_profile",
                        message=(
                            self.profile.unsupported_reason
                            or "The current request profile is unsupported."
                        ),
                        field="unsupported_reason",
                        entity_ref_key=ref.selection_key,
                        severity="error",
                    ),
                ),
            )
        direct = self.profile.candidate_for_ref(ref)
        if direct is not None and direct.kind == self.active_layer:
            return ((direct,), ())
        alias_targets = _alias_targets_for_layer(
            rules=self.profile.alias_rules,
            source_ref=ref,
            target_layer=self.active_layer,
        )
        if alias_targets:
            candidates = _ordered_candidates(profile=self.profile, refs=alias_targets)
            if candidates:
                return (candidates, ())
        return (
            (),
            (
                _diagnostic(
                    code="entity_ref_not_selectable",
                    message=(
                        f"Entity {ref.selection_key} cannot be selected in "
                        f"{self.active_layer} layer."
                    ),
                    field="candidate_refs",
                    entity_ref_key=ref.selection_key,
                ),
            ),
        )

    def _with_selected_refs(
        self,
        refs: tuple[EntityRef, ...],
        diagnostics: tuple[EntitySelectionDiagnostic, ...] = (),
    ) -> EntitySelectionState:
        ordered = _ordered_candidates(profile=self.profile, refs=refs)
        if self.profile.cardinality.max_count is not None and (
            len(ordered) > self.profile.cardinality.max_count
        ):
            return self._with_operation_diagnostics(
                (
                    *diagnostics,
                    _diagnostic(
                        code="selection_cardinality_exceeded",
                        message=(
                            "Selection exceeds the maximum count for the current request "
                            f"profile: {self.profile.cardinality.max_count}."
                        ),
                        field="selected_refs",
                        severity="error",
                    ),
                )
            )
        focused_ref = (
            ordered[0]
            if ordered
            else _first_candidate_for_layer(
                self.profile,
                self.active_layer,
            )
        )
        return replace(
            self,
            selected_refs=ordered,
            focused_ref=focused_ref,
            diagnostics=(*self.profile.diagnostics, *diagnostics),
        )

    def _with_operation_diagnostics(
        self,
        diagnostics: tuple[EntitySelectionDiagnostic, ...],
    ) -> EntitySelectionState:
        return replace(self, diagnostics=(*self.profile.diagnostics, *diagnostics))


def entity_layer_registry() -> dict[EntityLayer, EntityLayerDefinition]:
    """Return known entity-selection layers and their current implementation status."""

    return {
        "model": EntityLayerDefinition("model", "Model", "active"),
        "model_group": EntityLayerDefinition("model_group", "Model group", "planned"),
        "unit": EntityLayerDefinition("unit", "Unit", "active"),
        "attached_unit": EntityLayerDefinition("attached_unit", "Attached unit", "planned"),
        "army": EntityLayerDefinition("army", "Army", "planned"),
        "objective": EntityLayerDefinition("objective", "Objective", "planned"),
        "terrain": EntityLayerDefinition("terrain", "Terrain", "planned"),
        "card": EntityLayerDefinition("card", "Card", "planned"),
        "dice": EntityLayerDefinition("dice", "Dice", "planned"),
        "custom": EntityLayerDefinition("custom", "Request-specific custom entity", "planned"),
    }


def build_entity_selection_profile(
    *,
    view: BattlefieldView,
    pending_decision: UiDecision | None,
) -> EntitySelectionProfile:
    """Build a request-scoped entity selection profile from projection/request data."""

    if pending_decision is None:
        return inspection_entity_selection_profile(view)
    if pending_decision.movement_proposal is not None:
        return movement_entity_selection_profile(view=view, decision=pending_decision)
    if pending_decision.is_parameterized:
        return unsupported_entity_selection_profile(
            decision=pending_decision,
            reason="Parameterized request does not expose an entity-selection profile yet.",
        )
    return finite_unit_entity_selection_profile(view=view, decision=pending_decision)


def inspection_entity_selection_profile(view: BattlefieldView) -> EntitySelectionProfile:
    """Build the fallback profile used when no engine request is pending."""

    refs: list[EntityRef] = []
    alias_rules: list[EntityAliasRule] = []
    for unit in view.units:
        unit_ref = unit_entity_ref(unit)
        model_refs = tuple(model_entity_ref(unit=unit, model=model) for model in unit.models)
        refs.extend(model_refs)
        refs.append(unit_ref)
        alias_rules.extend(_model_to_unit_aliases(model_refs=model_refs, unit_ref=unit_ref))
        alias_rules.append(
            EntityAliasRule(
                source_layer="unit",
                target_layer="model",
                source_ref=unit_ref,
                target_refs=model_refs,
                label="Expand unit to models",
            )
        )
    return _profile_with_layer_diagnostics(
        request_id=None,
        decision_type="inspection",
        actor_id=None,
        selectable_layers=("model", "unit"),
        requested_active_layer="model",
        candidate_refs=tuple(refs),
        alias_rules=tuple(alias_rules),
        cardinality=SelectionCardinality(),
        additive_allowed=True,
        subtractive_allowed=True,
        unsupported_reason=None,
        diagnostics=(),
    )


def movement_entity_selection_profile(
    *,
    view: BattlefieldView,
    decision: UiDecision,
) -> EntitySelectionProfile:
    """Build a model-first profile for an engine movement proposal request."""

    proposal = decision.movement_proposal
    if proposal is None or proposal.decision_type not in MOVEMENT_SHAPED_DECISION_TYPES:
        return unsupported_entity_selection_profile(
            decision=decision,
            reason="Decision is not a movement-shaped proposal request.",
        )
    unit = _unit_by_id(view, proposal.unit_instance_id)
    if unit is None:
        diagnostic = _diagnostic(
            code="candidate_missing",
            message=(
                "Movement proposal unit is not available in the current viewer projection: "
                f"{proposal.unit_instance_id}."
            ),
            field="candidate_refs",
            entity_ref_key=f"unit:{proposal.unit_instance_id}",
            severity="error",
        )
        return _profile_with_layer_diagnostics(
            request_id=proposal.request_id,
            decision_type=proposal.decision_type,
            actor_id=proposal.actor_id,
            selectable_layers=("model", "unit"),
            requested_active_layer="model",
            candidate_refs=(),
            alias_rules=(),
            cardinality=SelectionCardinality(),
            additive_allowed=True,
            subtractive_allowed=True,
            unsupported_reason="Movement proposal unit is unavailable in the current projection.",
            diagnostics=(diagnostic,),
        )
    unit_ref = unit_entity_ref(unit)
    model_refs = tuple(model_entity_ref(unit=unit, model=model) for model in unit.models)
    alias_rules: list[EntityAliasRule] = [
        *_model_to_unit_aliases(model_refs=model_refs, unit_ref=unit_ref),
        EntityAliasRule(
            source_layer="unit",
            target_layer="model",
            source_ref=unit_ref,
            target_refs=model_refs,
            label="Expand moving unit to models",
        ),
    ]
    return _profile_with_layer_diagnostics(
        request_id=proposal.request_id,
        decision_type=proposal.decision_type,
        actor_id=proposal.actor_id,
        selectable_layers=("model", "unit"),
        requested_active_layer="model",
        candidate_refs=(*model_refs, unit_ref),
        alias_rules=tuple(alias_rules),
        cardinality=SelectionCardinality(),
        additive_allowed=True,
        subtractive_allowed=True,
        unsupported_reason=None,
        diagnostics=(),
    )


def finite_unit_entity_selection_profile(
    *,
    view: BattlefieldView,
    decision: UiDecision,
) -> EntitySelectionProfile:
    """Build a unit profile for finite requests whose options expose unit candidates."""

    candidate_ids = _finite_unit_candidate_ids(decision)
    if not candidate_ids:
        return unsupported_entity_selection_profile(
            decision=decision,
            reason="Finite request does not expose unit candidate IDs in option payloads.",
        )
    refs: list[EntityRef] = []
    alias_rules: list[EntityAliasRule] = []
    diagnostics: list[EntitySelectionDiagnostic] = []
    for unit_id in candidate_ids:
        unit = _unit_by_id(view, unit_id)
        if unit is None:
            diagnostics.append(
                _diagnostic(
                    code="candidate_missing",
                    message=(
                        "Finite unit candidate is not available in the current projection: "
                        f"{unit_id}."
                    ),
                    field="candidate_refs",
                    entity_ref_key=f"unit:{unit_id}",
                    severity="error",
                )
            )
            continue
        unit_ref = unit_entity_ref(unit)
        model_refs = tuple(model_entity_ref(unit=unit, model=model) for model in unit.models)
        refs.append(unit_ref)
        alias_rules.extend(_model_to_unit_aliases(model_refs=model_refs, unit_ref=unit_ref))
    unsupported_reason = (
        "Finite unit candidates are unavailable in the current projection." if not refs else None
    )
    return _profile_with_layer_diagnostics(
        request_id=decision.request_id,
        decision_type=decision.decision_type,
        actor_id=decision.actor_id,
        selectable_layers=("unit",),
        requested_active_layer="unit",
        candidate_refs=tuple(refs),
        alias_rules=tuple(alias_rules),
        cardinality=SelectionCardinality(min_count=0, max_count=1),
        additive_allowed=False,
        subtractive_allowed=False,
        unsupported_reason=unsupported_reason,
        diagnostics=tuple(diagnostics),
    )


def unsupported_entity_selection_profile(
    *,
    decision: UiDecision,
    reason: str,
) -> EntitySelectionProfile:
    """Build a typed unsupported profile for a request family not implemented here."""

    return EntitySelectionProfile(
        request_id=decision.request_id,
        decision_type=decision.decision_type,
        actor_id=decision.actor_id,
        selectable_layers=(),
        active_layer=None,
        candidate_refs=(),
        alias_rules=(),
        cardinality=SelectionCardinality(max_count=0),
        additive_allowed=False,
        subtractive_allowed=False,
        unsupported_reason=reason,
        diagnostics=(
            _diagnostic(
                code="unsupported_request_profile",
                message=reason,
                field="decision_type",
                severity="error",
            ),
        ),
    )


def unit_entity_ref(unit: UnitView) -> EntityRef:
    """Build a unit entity ref with a safe projection anchor."""

    return EntityRef(
        kind="unit",
        entity_id=unit.unit_id,
        owner_player_id=unit.player_id,
        parent_refs=(),
        display_label=unit.label,
        visual_anchor_world=unit_center(unit),
    )


def model_entity_ref(*, unit: UnitView, model: ModelBaseView) -> EntityRef:
    """Build a model entity ref with its owning unit as parent metadata."""

    unit_ref = unit_entity_ref(unit)
    return EntityRef(
        kind="model",
        entity_id=model.model_id,
        owner_player_id=unit.player_id,
        parent_refs=(unit_ref,),
        display_label=f"{unit.label}: {model.label}",
        visual_anchor_world=model.position,
    )


def entity_ref_for_unit(
    *,
    view: BattlefieldView,
    unit_id: str,
) -> EntityRef | None:
    """Return a unit entity ref from the current projection."""

    unit = _unit_by_id(view, unit_id)
    return None if unit is None else unit_entity_ref(unit)


def entity_ref_for_model(
    *,
    view: BattlefieldView,
    unit_id: str,
    model_id: str,
) -> EntityRef | None:
    """Return a model entity ref from the current projection."""

    unit = _unit_by_id(view, unit_id)
    if unit is None:
        return None
    for model in unit.models:
        if model.model_id == model_id:
            return model_entity_ref(unit=unit, model=model)
    return None


def visual_anchor_diagnostics(
    refs: tuple[EntityRef, ...],
) -> tuple[EntitySelectionDiagnostic, ...]:
    """Return typed diagnostics for refs that cannot be safely drawn on the battlefield."""

    return tuple(
        _diagnostic(
            code="visual_anchor_unavailable",
            message=f"Entity has no safe visual anchor: {ref.selection_key}.",
            field="visual_anchor_world",
            entity_ref_key=ref.selection_key,
        )
        for ref in refs
        if ref.visual_anchor_world is None
    )


def _profile_with_layer_diagnostics(
    *,
    request_id: str | None,
    decision_type: str,
    actor_id: str | None,
    selectable_layers: tuple[EntityLayer, ...],
    requested_active_layer: EntityLayer | None,
    candidate_refs: tuple[EntityRef, ...],
    alias_rules: tuple[EntityAliasRule, ...],
    cardinality: SelectionCardinality,
    additive_allowed: bool,
    subtractive_allowed: bool,
    unsupported_reason: str | None,
    diagnostics: tuple[EntitySelectionDiagnostic, ...],
) -> EntitySelectionProfile:
    available_layer_list: list[EntityLayer] = []
    for layer in selectable_layers:
        if any(candidate.kind == layer for candidate in candidate_refs):
            available_layer_list.append(layer)
    available_layers = tuple(available_layer_list)
    layer_diagnostics = tuple(
        _diagnostic(
            code="entity_layer_unavailable",
            message=f"Layer has no candidates in the current profile: {layer}.",
            field="selectable_layers",
            severity="warning",
        )
        for layer in selectable_layers
        if layer not in available_layers
    )
    active_layer: EntityLayer | None
    if requested_active_layer is not None and requested_active_layer in available_layers:
        active_layer = requested_active_layer
    elif available_layers:
        active_layer = available_layers[0]
    else:
        active_layer = None
    return EntitySelectionProfile(
        request_id=request_id,
        decision_type=decision_type,
        actor_id=actor_id,
        selectable_layers=selectable_layers,
        active_layer=active_layer,
        candidate_refs=candidate_refs,
        alias_rules=alias_rules,
        cardinality=cardinality,
        additive_allowed=additive_allowed,
        subtractive_allowed=subtractive_allowed,
        unsupported_reason=unsupported_reason,
        diagnostics=(*diagnostics, *layer_diagnostics),
    )


def _model_to_unit_aliases(
    *,
    model_refs: tuple[EntityRef, ...],
    unit_ref: EntityRef,
) -> tuple[EntityAliasRule, ...]:
    return tuple(
        EntityAliasRule(
            source_layer="model",
            target_layer="unit",
            source_ref=model_ref,
            target_refs=(unit_ref,),
            label="Alias model to owning unit",
        )
        for model_ref in model_refs
    )


def _finite_unit_candidate_ids(decision: UiDecision) -> tuple[str, ...]:
    ids: list[str] = []
    for option in decision.options:
        if type(option.payload) is not dict:
            continue
        payload = option.payload
        for key in _FINITE_UNIT_ID_KEYS:
            value = payload.get(key)
            if type(value) is str and value and value not in ids:
                ids.append(value)
    return tuple(ids)


def _alias_targets_for_layer(
    *,
    rules: tuple[EntityAliasRule, ...],
    source_ref: EntityRef,
    target_layer: EntityLayer,
) -> tuple[EntityRef, ...]:
    targets: list[EntityRef] = []
    for rule in rules:
        if (
            rule.source_ref.selection_key == source_ref.selection_key
            and rule.target_layer == target_layer
        ):
            targets.extend(rule.target_refs)
    return tuple(targets)


def _ordered_candidates(
    *,
    profile: EntitySelectionProfile,
    refs: tuple[EntityRef, ...],
) -> tuple[EntityRef, ...]:
    keys = {ref.selection_key for ref in refs}
    return tuple(
        candidate for candidate in profile.candidate_refs if candidate.selection_key in keys
    )


def _first_candidate_for_layer(
    profile: EntitySelectionProfile,
    layer: EntityLayer | None,
) -> EntityRef | None:
    if layer is None:
        return None
    candidates = profile.candidates_for_layer(layer)
    return candidates[0] if candidates else None


def _candidate_index(candidates: tuple[EntityRef, ...], ref: EntityRef | None) -> int:
    if ref is None:
        return -1
    for index, candidate in enumerate(candidates):
        if candidate.selection_key == ref.selection_key:
            return index
    return -1


def _unit_by_id(view: BattlefieldView, unit_id: str) -> UnitView | None:
    for unit in view.units:
        if unit.unit_id == unit_id:
            return unit
    return None


def _validate_unique_ref_keys(field_name: str, refs: tuple[EntityRef, ...]) -> None:
    seen: set[str] = set()
    for ref in refs:
        if ref.selection_key in seen:
            raise EntitySelectionError(f"{field_name} must not contain duplicate entity refs.")
        seen.add(ref.selection_key)


def _validate_entity_layer(layer: str) -> None:
    if layer not in _ENTITY_LAYERS:
        raise EntitySelectionError(f"Unsupported entity layer: {layer}.")


def _optional_world_point(field_name: str, value: WorldPoint | None) -> WorldPoint | None:
    if value is None:
        return None
    return _validate_world_point(field_name, value)


def _validate_world_point(field_name: str, value: object) -> WorldPoint:
    if type(value) is not tuple:
        raise EntitySelectionError(f"{field_name} must be a 2D world point.")
    point = cast(tuple[object, ...], value)
    if len(point) != 2:
        raise EntitySelectionError(f"{field_name} must be a 2D world point.")
    x = _validated_finite_float(f"{field_name}.x", point[0])
    y = _validated_finite_float(f"{field_name}.y", point[1])
    return (x, y)


def _validated_finite_float(field_name: str, value: object) -> float:
    if type(value) is not float and type(value) is not int:
        raise EntitySelectionError(f"{field_name} must be a number.")
    float_value = float(value)
    if not math.isfinite(float_value):
        raise EntitySelectionError(f"{field_name} must be finite.")
    return float_value


def _non_empty_string(field_name: str, value: object) -> str:
    if type(value) is not str:
        raise EntitySelectionError(f"{field_name} must be a string.")
    stripped = value.strip()
    if not stripped:
        raise EntitySelectionError(f"{field_name} must not be empty.")
    return stripped


def _optional_string(field_name: str, value: object | None) -> str | None:
    if value is None:
        return None
    return _non_empty_string(field_name, value)


def _diagnostic(
    *,
    code: str,
    message: str,
    field: str | None = None,
    entity_ref_key: str | None = None,
    severity: EntitySelectionSeverity = "warning",
) -> EntitySelectionDiagnostic:
    return EntitySelectionDiagnostic(
        code=code,
        message=message,
        field=field,
        entity_ref_key=entity_ref_key,
        severity=severity,
    )
