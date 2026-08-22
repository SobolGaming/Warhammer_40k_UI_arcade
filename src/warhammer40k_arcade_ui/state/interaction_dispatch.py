"""Descriptor-driven selection of the UI editor for an engine interaction."""

from __future__ import annotations

from dataclasses import dataclass

from warhammer40k_arcade_ui.core_client.protocol import UiDecision, UiInteractionDescriptor

FINITE_EDITOR = "generic_finite"
DICE_EDITOR = "dice_tray"
MOVEMENT_EDITOR = "movement"
PLACEMENT_EDITOR = "placement"
ASSIGNMENT_EDITOR = "assignment"
ROSTER_EDITOR = "roster"

_EDITOR_BY_INTERACTION_KIND = {
    "finite_option_list": FINITE_EDITOR,
    "entity_selection": FINITE_EDITOR,
    "ordered_sequencing": FINITE_EDITOR,
    "confirmation": FINITE_EDITOR,
    "quantity_selection": FINITE_EDITOR,
    "opportunity_window": FINITE_EDITOR,
    "dice_selection": DICE_EDITOR,
    "path_editor": MOVEMENT_EDITOR,
    "battlefield_point_placement": PLACEMENT_EDITOR,
    "model_pose_placement": PLACEMENT_EDITOR,
    "multi_model_placement": PLACEMENT_EDITOR,
    "weapon_allocation_matrix": ASSIGNMENT_EDITOR,
    "roster_construction": ROSTER_EDITOR,
}


@dataclass(frozen=True, slots=True)
class UiInteractionRoute:
    """Resolved editor and explicit engine-published submission variant."""

    editor_id: str
    interaction_kind: str
    submission_variant_id: str
    required_inputs: tuple[str, ...]
    supported: bool
    diagnostic: str | None = None


def interaction_route_for_decision(decision: UiDecision) -> UiInteractionRoute:
    """Resolve a visible request exclusively from its interaction descriptor."""

    interaction = decision.interaction
    if interaction is None:
        return UiInteractionRoute(
            editor_id="hidden",
            interaction_kind="hidden",
            submission_variant_id="none",
            required_inputs=(),
            supported=False,
            diagnostic="The current decision is hidden from this viewer.",
        )
    return interaction_route(interaction)


def interaction_route(interaction: UiInteractionDescriptor) -> UiInteractionRoute:
    """Resolve one validated interaction descriptor."""

    editor_id = _EDITOR_BY_INTERACTION_KIND[interaction.interaction_kind]
    if interaction.interaction_kind == "entity_selection" and interaction.submission_kind == (
        "parameterized"
    ):
        editor_id = ASSIGNMENT_EDITOR
    if len(interaction.submission_variants) != 1:
        required_inputs = tuple(
            dict.fromkeys(
                required_input
                for variant in interaction.submission_variants
                for required_input in variant.required_inputs
            )
        )
        return UiInteractionRoute(
            editor_id=editor_id,
            interaction_kind=interaction.interaction_kind,
            submission_variant_id="unselected",
            required_inputs=required_inputs,
            supported=False,
            diagnostic=(
                f"Interaction {interaction.interaction_kind!r} publishes multiple submission "
                "variants; explicit variant selection is not implemented yet."
            ),
        )
    variant = interaction.submission_variants[0]
    supported = not (
        editor_id == ROSTER_EDITOR
        or (
            editor_id == PLACEMENT_EDITOR
            and interaction.interaction_kind == "battlefield_point_placement"
        )
    )
    diagnostic = None
    if not supported:
        diagnostic = (
            f"Interaction {interaction.interaction_kind!r} requires "
            f"{', '.join(variant.required_inputs) or 'specialized input'}; "
            "this editor is not implemented yet."
        )
    return UiInteractionRoute(
        editor_id=editor_id,
        interaction_kind=interaction.interaction_kind,
        submission_variant_id=variant.variant_id,
        required_inputs=variant.required_inputs,
        supported=supported,
        diagnostic=diagnostic,
    )


def editor_matches(decision: UiDecision | None, editor_id: str) -> bool:
    """Return whether a visible current request belongs to an editor family."""

    if decision is None or decision.interaction is None:
        return False
    return interaction_route_for_decision(decision).editor_id == editor_id
