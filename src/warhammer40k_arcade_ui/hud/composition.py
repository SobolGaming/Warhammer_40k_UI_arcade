"""Validated YAML composition profiles for the HUD widget toolkit."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import yaml

from warhammer40k_arcade_ui.hud.toolkit import (
    HudComponentNode,
    HudLayoutSpec,
    HudWidgetType,
    component_allowed_attributes,
    known_data_refs,
    known_icon_ids,
    parse_overflow_policy,
    parse_scroll_config,
    parse_size_spec,
    parse_status_chip_shape,
    widget_type_from_string,
)
from warhammer40k_arcade_ui.preferences.schema import JsonObject, JsonValue, UiPreferences
from warhammer40k_arcade_ui.resources.source import (
    GenericSource,
    ResourceSource,
    read_builtin_text,
    resolve_resource_reference,
)

type HudCompositionSeverity = Literal["error", "warning"]
type HudCompositionLayoutPreset = Literal["compass_ring", "command_bench"]

_SCHEMA_VERSION = "1"
_TOP_LEVEL_KEYS = frozenset(("schema_version", "profile_id", "layout_preset", "theme", "regions"))
_PREVIEW_TOP_LEVEL_KEYS = _TOP_LEVEL_KEYS | frozenset(("sample_data",))
_REGION_KEYS = frozenset(("widget",))
_WIDGET_RESERVED_KEYS = frozenset(("type", "id", "layout", "children", "icon_id", "data_ref"))
_LAYOUT_KEYS = frozenset(("kind", "orientation", "columns", "gap_px", "padding_px", "alignment"))
_VALID_LAYOUT_KINDS = frozenset(("stack", "grid", "anchor", "overlay"))
_VALID_ORIENTATIONS = frozenset(("vertical", "horizontal"))
_VALID_ALIGNMENTS = frozenset(("start", "center", "end", "stretch"))
_VALID_LAYOUT_PRESETS = frozenset(("compass_ring", "command_bench"))
_FORBIDDEN_INCLUDE_KEYS = frozenset(("include", "includes", "template", "templates"))
_SIZE_ATTRIBUTES = frozenset(
    ("width", "height", "min_width", "max_width", "min_height", "max_height")
)
_BUILTIN_COMPOSITION_PROFILES = {
    "default-hud": "hud/default-hud.yaml",
    "command-bench-hud": "hud/command-bench-hud.yaml",
}


@dataclass(frozen=True, slots=True)
class HudCompositionDiagnostic:
    """Typed diagnostic emitted while loading a HUD composition profile."""

    severity: HudCompositionSeverity
    code: str
    field: str
    message: str
    value: str | None = None


@dataclass(frozen=True, slots=True)
class HudCompositionRegion:
    """One HUD region mapped to a widget tree."""

    region_id: str
    widget: HudComponentNode


@dataclass(frozen=True, slots=True)
class HudCompositionProfile:
    """Validated HUD composition profile."""

    schema_version: str
    profile_id: str
    layout_preset: HudCompositionLayoutPreset
    theme: str
    regions: tuple[HudCompositionRegion, ...]
    sample_data: JsonObject
    source_path: Path | None = None
    source: ResourceSource | None = None

    def region(self, region_id: str) -> HudCompositionRegion | None:
        """Return a region by ID if present."""

        for region in self.regions:
            if region.region_id == region_id:
                return region
        return None


@dataclass(frozen=True, slots=True)
class HudCompositionValidationResult:
    """Composition load result plus typed diagnostics."""

    profile: HudCompositionProfile | None
    diagnostics: tuple[HudCompositionDiagnostic, ...]

    @property
    def has_errors(self) -> bool:
        """Return whether validation produced error diagnostics."""

        return any(diagnostic.severity == "error" for diagnostic in self.diagnostics)


def load_hud_composition(
    path: Path,
    *,
    preview: bool = False,
) -> HudCompositionValidationResult:
    """Load and validate a HUD composition YAML file."""

    return _load_hud_composition_file(
        path,
        source=ResourceSource(kind="explicit_path", name=str(path), path=path),
        preview=preview,
    )


def _load_hud_composition_file(
    path: Path,
    *,
    source: ResourceSource,
    preview: bool,
) -> HudCompositionValidationResult:
    """Load and validate a HUD composition YAML file from a resolved filesystem source."""

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return HudCompositionValidationResult(
            profile=None,
            diagnostics=(
                _diagnostic(
                    severity="error",
                    code="composition_file_error",
                    field="$",
                    message=f"Could not read HUD composition file: {exc}.",
                    value=str(path),
                ),
            ),
        )
    try:
        payload = cast(object, yaml.safe_load(raw_text))
    except yaml.YAMLError as exc:
        return HudCompositionValidationResult(
            profile=None,
            diagnostics=(
                _diagnostic(
                    severity="error",
                    code="composition_yaml_error",
                    field="$",
                    message=f"Could not parse HUD composition YAML: {exc}.",
                    value=str(path),
                ),
            ),
        )
    return parse_hud_composition_payload(
        payload,
        source_path=path,
        source=source,
        preview=preview,
    )


def load_hud_composition_reference(
    reference: str,
    *,
    relative_to: GenericSource | None = None,
    preview: bool = False,
) -> HudCompositionValidationResult:
    """Load a HUD composition by built-in name, source-relative path, or explicit path."""

    try:
        source = resolve_resource_reference(
            reference,
            relative_to=relative_to,
            known_builtins=_BUILTIN_COMPOSITION_PROFILES,
        )
    except ValueError as exc:
        return HudCompositionValidationResult(
            profile=None,
            diagnostics=(
                _diagnostic(
                    severity="error",
                    code="composition_source_error",
                    field="$",
                    message=f"Could not resolve HUD composition source: {exc}.",
                    value=reference,
                ),
            ),
        )
    if source.kind == "builtin":
        return _load_builtin_hud_composition(source.name, preview=preview)
    if source.path is None:
        return HudCompositionValidationResult(
            profile=None,
            diagnostics=(
                _diagnostic(
                    severity="error",
                    code="composition_source_error",
                    field="$",
                    message="Resolved HUD composition source did not include a filesystem path.",
                    value=source.display_name,
                ),
            ),
        )
    return _load_hud_composition_file(source.path, source=source, preview=preview)


def load_hud_composition_for_preferences(
    preferences: UiPreferences,
    *,
    source: GenericSource | None = None,
    preview: bool = False,
) -> HudCompositionValidationResult:
    """Load the composition profile referenced by validated UI preferences."""

    profile_path = preferences.hud.composition_profile
    if profile_path is None:
        if source is not None and source.kind in ("user_default", "explicit_path"):
            return HudCompositionValidationResult(
                profile=None,
                diagnostics=(_missing_composition_profile_diagnostic(source),),
            )
        return HudCompositionValidationResult(profile=None, diagnostics=())
    return load_hud_composition_reference(profile_path, relative_to=source, preview=preview)


def parse_hud_composition_payload(
    payload: object,
    *,
    source_path: Path | None = None,
    source: ResourceSource | None = None,
    preview: bool = False,
) -> HudCompositionValidationResult:
    """Parse a JSON/YAML payload into a validated HUD composition profile."""

    diagnostics: list[HudCompositionDiagnostic] = []
    if type(payload) is not dict:
        return HudCompositionValidationResult(
            profile=None,
            diagnostics=(
                _diagnostic(
                    severity="error",
                    code="invalid_document",
                    field="$",
                    message="HUD composition document must be an object.",
                ),
            ),
        )
    document = cast(dict[object, object], payload)
    section = _string_key_object(document, "$", diagnostics)
    allowed_keys = _PREVIEW_TOP_LEVEL_KEYS if preview else _TOP_LEVEL_KEYS
    _diagnose_forbidden_include_keys(section, "$", diagnostics)
    _diagnose_unknown_keys(section, allowed_keys, "$", diagnostics)
    schema_version = _schema_version(section, diagnostics)
    profile_id = _required_string(section, "profile_id", diagnostics, "$")
    layout_preset = _layout_preset(section, diagnostics)
    theme = _optional_string(section, "theme", default="default") or "default"
    sample_data = _sample_data(section, diagnostics, preview=preview)
    regions = _parse_regions(
        section.get("regions"),
        diagnostics,
        sample_data=sample_data,
        preview=preview,
    )
    if schema_version != _SCHEMA_VERSION or any(
        diagnostic.severity == "error" for diagnostic in diagnostics
    ):
        return HudCompositionValidationResult(profile=None, diagnostics=tuple(diagnostics))
    return HudCompositionValidationResult(
        profile=HudCompositionProfile(
            schema_version=schema_version,
            profile_id=profile_id,
            layout_preset=layout_preset,
            theme=theme,
            regions=regions,
            sample_data=sample_data,
            source_path=source_path,
            source=source,
        ),
        diagnostics=tuple(diagnostics),
    )


def _load_builtin_hud_composition(
    relative_resource: str,
    *,
    preview: bool,
) -> HudCompositionValidationResult:
    source = ResourceSource(kind="builtin", name=relative_resource)
    try:
        raw_text = read_builtin_text(relative_resource)
    except (OSError, ValueError) as exc:
        return HudCompositionValidationResult(
            profile=None,
            diagnostics=(
                _diagnostic(
                    severity="error",
                    code="composition_builtin_error",
                    field="$",
                    message=f"Could not read built-in HUD composition resource: {exc}.",
                    value=relative_resource,
                ),
            ),
        )
    try:
        payload = cast(object, yaml.safe_load(raw_text))
    except yaml.YAMLError as exc:
        return HudCompositionValidationResult(
            profile=None,
            diagnostics=(
                _diagnostic(
                    severity="error",
                    code="composition_yaml_error",
                    field="$",
                    message=f"Could not parse built-in HUD composition YAML: {exc}.",
                    value=relative_resource,
                ),
            ),
        )
    return parse_hud_composition_payload(payload, source=source, preview=preview)


def _missing_composition_profile_diagnostic(source: GenericSource) -> HudCompositionDiagnostic:
    if source.kind == "user_default":
        return _diagnostic(
            severity="error",
            code="platform_preferences_missing_hud_composition",
            field="hud.composition_profile",
            message=(
                f"Platform default preferences at {source.display_name} are missing "
                "hud.composition_profile, so the current HUD cannot render. Move that file out "
                "of the way or update it manually. Generate a fresh default with: "
                "warhammer40k-export-preferences --profile default --format yaml --output "
                f"{source.display_name}"
            ),
            value=source.display_name,
        )
    return _diagnostic(
        severity="error",
        code="preferences_missing_hud_composition",
        field="hud.composition_profile",
        message=(
            f"Preferences at {source.display_name} are missing hud.composition_profile, so the "
            "current HUD cannot render. Update the file manually or export a fresh default with: "
            "warhammer40k-export-preferences --profile default --format yaml --output <path>"
        ),
        value=source.display_name,
    )


def find_component(
    profile: HudCompositionProfile,
    component_id: str,
) -> HudComponentNode | None:
    """Find a component node by stable component ID."""

    for region in profile.regions:
        found = _find_component_in_tree(region.widget, component_id)
        if found is not None:
            return found
    return None


def _find_component_in_tree(
    node: HudComponentNode,
    component_id: str,
) -> HudComponentNode | None:
    if node.widget_id == component_id:
        return node
    for child in node.children:
        found = _find_component_in_tree(child, component_id)
        if found is not None:
            return found
    return None


def _parse_regions(
    payload: object,
    diagnostics: list[HudCompositionDiagnostic],
    *,
    sample_data: JsonObject,
    preview: bool,
) -> tuple[HudCompositionRegion, ...]:
    if type(payload) is not dict:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_regions",
                field="regions",
                message="regions must be an object mapping region IDs to widget roots.",
            )
        )
        return ()
    regions: list[HudCompositionRegion] = []
    for raw_region_id, raw_region in cast(dict[object, object], payload).items():
        if type(raw_region_id) is not str or not raw_region_id:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="invalid_key",
                    field="regions",
                    message="Region IDs must be non-empty strings.",
                    value=repr(raw_region_id),
                )
            )
            continue
        field = f"regions.{raw_region_id}"
        region_payload = _object_section(raw_region, field, diagnostics)
        _diagnose_unknown_keys(region_payload, _REGION_KEYS, field, diagnostics)
        widget = _parse_widget(
            region_payload.get("widget"),
            f"{field}.widget",
            diagnostics,
            sample_data=sample_data,
            preview=preview,
        )
        if widget is not None:
            regions.append(HudCompositionRegion(region_id=raw_region_id, widget=widget))
    return tuple(regions)


def _parse_widget(
    payload: object,
    field: str,
    diagnostics: list[HudCompositionDiagnostic],
    *,
    sample_data: JsonObject,
    preview: bool,
) -> HudComponentNode | None:
    section = _object_section(payload, field, diagnostics)
    _diagnose_forbidden_include_keys(section, field, diagnostics)
    raw_type = _required_string(section, "type", diagnostics, field)
    widget_type = widget_type_from_string(raw_type)
    if widget_type is None:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="unknown_widget_type",
                field=f"{field}.type",
                message=f"Unknown HUD widget type: {raw_type}.",
                value=raw_type,
            )
        )
        widget_type = "HudContainer"
    widget_id = _required_string(section, "id", diagnostics, field)
    icon_id = _optional_string(section, "icon_id", default=None)
    if icon_id is not None and icon_id not in known_icon_ids():
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="unknown_icon_id",
                field=f"{field}.icon_id",
                message=f"Unknown HUD icon id: {icon_id}.",
                value=icon_id,
            )
        )
    data_ref = _optional_string(section, "data_ref", default=None)
    if data_ref is not None:
        _validate_data_ref(
            data_ref=data_ref,
            field=f"{field}.data_ref",
            diagnostics=diagnostics,
            sample_data=sample_data,
            preview=preview,
        )
    layout = _parse_layout(section.get("layout"), f"{field}.layout", diagnostics)
    children = _parse_children(
        section.get("children"),
        f"{field}.children",
        diagnostics,
        sample_data=sample_data,
        preview=preview,
    )
    attributes = _parse_attributes(
        section,
        field,
        diagnostics,
        widget_type=widget_type,
    )
    return HudComponentNode(
        widget_type=widget_type,
        widget_id=widget_id,
        attributes=attributes,
        layout=layout,
        children=children,
        icon_id=icon_id,
        data_ref=data_ref,
    )


def _parse_children(
    payload: object,
    field: str,
    diagnostics: list[HudCompositionDiagnostic],
    *,
    sample_data: JsonObject,
    preview: bool,
) -> tuple[HudComponentNode, ...]:
    if payload is None:
        return ()
    if type(payload) is not list:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_children",
                field=field,
                message="children must be a list of widget objects.",
            )
        )
        return ()
    children: list[HudComponentNode] = []
    for index, child_payload in enumerate(cast(list[object], payload)):
        child = _parse_widget(
            child_payload,
            f"{field}[{index}]",
            diagnostics,
            sample_data=sample_data,
            preview=preview,
        )
        if child is not None:
            children.append(child)
    return tuple(children)


def _parse_attributes(
    section: dict[str, object],
    field: str,
    diagnostics: list[HudCompositionDiagnostic],
    *,
    widget_type: HudWidgetType,
) -> JsonObject:
    allowed = component_allowed_attributes(widget_type)
    attributes: JsonObject = {}
    for key, value in section.items():
        if key in _WIDGET_RESERVED_KEYS:
            continue
        if key not in allowed:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="unknown_widget_attribute",
                    field=f"{field}.{key}",
                    message=f"{widget_type} does not support attribute {key}.",
                    value=key,
                )
            )
            continue
        safe_value = _json_safe_value(value, f"{field}.{key}", diagnostics)
        _validate_attribute_value(
            key=key,
            value=safe_value,
            field=f"{field}.{key}",
            widget_type=widget_type,
            diagnostics=diagnostics,
        )
        attributes[key] = safe_value
    _validate_size_constraints(attributes, field, diagnostics)
    return attributes


def _parse_layout(
    payload: object,
    field: str,
    diagnostics: list[HudCompositionDiagnostic],
) -> HudLayoutSpec:
    if payload is None:
        return HudLayoutSpec(kind="stack")
    section = _object_section(payload, field, diagnostics)
    _diagnose_unknown_keys(section, _LAYOUT_KEYS, field, diagnostics)
    raw_kind = _optional_string(section, "kind", default="stack")
    layout_kind: Literal["stack", "grid", "anchor", "overlay"] = "stack"
    if raw_kind == "grid":
        layout_kind = "grid"
    elif raw_kind == "anchor":
        layout_kind = "anchor"
    elif raw_kind == "overlay":
        layout_kind = "overlay"
    elif raw_kind != "stack":
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_layout_kind",
                field=f"{field}.kind",
                message="layout.kind must be stack, grid, anchor, or overlay.",
                value=raw_kind,
            )
        )
    raw_orientation = _optional_string(section, "orientation", default="vertical")
    layout_orientation: Literal["vertical", "horizontal"] = "vertical"
    if raw_orientation == "horizontal":
        layout_orientation = "horizontal"
    elif raw_orientation != "vertical":
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_layout_orientation",
                field=f"{field}.orientation",
                message="layout.orientation must be vertical or horizontal.",
                value=raw_orientation,
            )
        )
    raw_alignment = _optional_string(section, "alignment", default="stretch")
    layout_alignment: Literal["start", "center", "end", "stretch"] = "stretch"
    if raw_alignment == "start":
        layout_alignment = "start"
    elif raw_alignment == "center":
        layout_alignment = "center"
    elif raw_alignment == "end":
        layout_alignment = "end"
    elif raw_alignment != "stretch":
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_layout_alignment",
                field=f"{field}.alignment",
                message="layout.alignment must be start, center, end, or stretch.",
                value=raw_alignment,
            )
        )
    columns = _optional_int(section, "columns", default=1)
    if columns < 1 or columns > 12:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_layout_columns",
                field=f"{field}.columns",
                message="layout.columns must be between 1 and 12.",
                value=str(columns),
            )
        )
        columns = 1
    return HudLayoutSpec(
        kind=layout_kind,
        orientation=layout_orientation,
        columns=columns,
        gap_px=_optional_float(section, "gap_px", default=8.0),
        padding_px=_optional_float(section, "padding_px", default=8.0),
        alignment=layout_alignment,
    )


def _validate_attribute_value(
    *,
    key: str,
    value: JsonValue,
    field: str,
    widget_type: HudWidgetType,
    diagnostics: list[HudCompositionDiagnostic],
) -> None:
    if key in _SIZE_ATTRIBUTES:
        try:
            parse_size_spec(value)
        except ValueError as exc:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="invalid_size_spec",
                    field=field,
                    message=str(exc),
                    value=repr(value),
                )
            )
    elif key == "aspect_ratio":
        _validate_aspect_ratio(value=value, field=field, diagnostics=diagnostics)
    elif key == "overflow":
        try:
            parse_overflow_policy(value)
        except ValueError as exc:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="invalid_overflow_policy",
                    field=field,
                    message=str(exc),
                    value=repr(value),
                )
            )
    elif key == "scroll":
        try:
            parse_scroll_config(value)
        except ValueError as exc:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="invalid_scroll_config",
                    field=field,
                    message=str(exc),
                    value=repr(value),
                )
            )
    elif key == "shape" and widget_type == "StatusChip":
        try:
            parse_status_chip_shape(value)
        except ValueError as exc:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="invalid_status_chip_shape",
                    field=field,
                    message=str(exc),
                    value=repr(value),
                )
            )
    elif key in ("text", "icons", "slots") and type(value) is not dict:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_widget_mapping",
                field=field,
                message=f"{key} must be an object.",
                value=repr(value),
            )
        )


def _validate_size_constraints(
    attributes: JsonObject,
    field: str,
    diagnostics: list[HudCompositionDiagnostic],
) -> None:
    _validate_size_constraint_pair(
        attributes,
        min_key="min_width",
        max_key="max_width",
        field=field,
        diagnostics=diagnostics,
    )
    _validate_size_constraint_pair(
        attributes,
        min_key="min_height",
        max_key="max_height",
        field=field,
        diagnostics=diagnostics,
    )


def _validate_size_constraint_pair(
    attributes: JsonObject,
    *,
    min_key: str,
    max_key: str,
    field: str,
    diagnostics: list[HudCompositionDiagnostic],
) -> None:
    min_value = _pixel_size_value(attributes.get(min_key))
    max_value = _pixel_size_value(attributes.get(max_key))
    if min_value is None or max_value is None or min_value <= max_value:
        return
    diagnostics.append(
        _diagnostic(
            severity="error",
            code="invalid_size_constraint",
            field=field,
            message=f"{min_key} must not be greater than {max_key}.",
            value=f"{min_value} > {max_value}",
        )
    )


def _pixel_size_value(value: JsonValue | None) -> float | None:
    if value is None:
        return None
    try:
        spec = parse_size_spec(value)
    except ValueError:
        return None
    if spec.unit != "px":
        return None
    return spec.value


def _validate_aspect_ratio(
    *,
    value: JsonValue,
    field: str,
    diagnostics: list[HudCompositionDiagnostic],
) -> None:
    if (type(value) is int or type(value) is float) and float(value) > 0.0:
        return
    if type(value) is str:
        parts = value.split(":", maxsplit=1)
        if len(parts) == 2:
            try:
                first = float(parts[0])
                second = float(parts[1])
            except ValueError:
                first = 0.0
                second = 0.0
            if first > 0.0 and second > 0.0:
                return
    diagnostics.append(
        _diagnostic(
            severity="error",
            code="invalid_aspect_ratio",
            field=field,
            message="aspect_ratio must be a positive number or ratio string like 1:1.",
            value=repr(value),
        )
    )


def _sample_data(
    section: dict[str, object],
    diagnostics: list[HudCompositionDiagnostic],
    *,
    preview: bool,
) -> JsonObject:
    if "sample_data" not in section:
        return {}
    if not preview:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="production_sample_data_not_allowed",
                field="sample_data",
                message="Runtime HUD composition files must not contain preview sample_data.",
            )
        )
        return {}
    return _json_object_section(section["sample_data"], "sample_data", diagnostics)


def _validate_data_ref(
    *,
    data_ref: str,
    field: str,
    diagnostics: list[HudCompositionDiagnostic],
    sample_data: JsonObject,
    preview: bool,
) -> None:
    if data_ref not in known_data_refs():
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="unknown_data_ref",
                field=field,
                message=f"Unknown HUD data_ref: {data_ref}.",
                value=data_ref,
            )
        )
    if preview and data_ref not in sample_data:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="missing_sample_data",
                field=field,
                message=f"Preview HUD data_ref {data_ref} is missing from sample_data.",
                value=data_ref,
            )
        )


def _schema_version(
    section: dict[str, object],
    diagnostics: list[HudCompositionDiagnostic],
) -> str:
    value = section.get("schema_version")
    if type(value) is int:
        normalized = str(value)
    elif type(value) is str:
        normalized = value
    else:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_schema_version",
                field="schema_version",
                message="schema_version must be 1.",
                value=repr(value),
            )
        )
        return ""
    if normalized != _SCHEMA_VERSION:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="unsupported_schema_version",
                field="schema_version",
                message=f"Unsupported HUD composition schema version: {normalized}.",
                value=normalized,
            )
        )
    return normalized


def _layout_preset(
    section: dict[str, object],
    diagnostics: list[HudCompositionDiagnostic],
) -> HudCompositionLayoutPreset:
    raw_preset = _required_string(section, "layout_preset", diagnostics, "$")
    if raw_preset == "compass_ring":
        return "compass_ring"
    if raw_preset == "command_bench":
        return "command_bench"
    diagnostics.append(
        _diagnostic(
            severity="error",
            code="invalid_layout_preset",
            field="layout_preset",
            message="layout_preset must be compass_ring or command_bench.",
            value=raw_preset,
        )
    )
    return "compass_ring"


def _json_object_section(
    payload: object,
    field: str,
    diagnostics: list[HudCompositionDiagnostic],
) -> JsonObject:
    if type(payload) is not dict:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_section",
                field=field,
                message=f"{field} must be an object.",
            )
        )
        return {}
    result: JsonObject = {}
    for key, value in cast(dict[object, object], payload).items():
        if type(key) is not str or not key:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="invalid_key",
                    field=field,
                    message=f"{field} keys must be non-empty strings.",
                    value=repr(key),
                )
            )
            continue
        result[key] = _json_safe_value(value, f"{field}.{key}", diagnostics)
    return result


def _json_safe_value(
    value: object,
    field: str,
    diagnostics: list[HudCompositionDiagnostic],
) -> JsonValue:
    if value is None or type(value) in (bool, int, float, str):
        return cast(JsonValue, value)
    if type(value) is list:
        return [
            _json_safe_value(item, f"{field}[{index}]", diagnostics)
            for index, item in enumerate(cast(list[object], value))
        ]
    if type(value) is dict:
        result: JsonObject = {}
        for key, raw_value in cast(dict[object, object], value).items():
            if type(key) is not str or not key:
                diagnostics.append(
                    _diagnostic(
                        severity="error",
                        code="invalid_key",
                        field=field,
                        message="YAML object keys must be non-empty strings.",
                        value=repr(key),
                    )
                )
                continue
            result[key] = _json_safe_value(raw_value, f"{field}.{key}", diagnostics)
        return result
    diagnostics.append(
        _diagnostic(
            severity="error",
            code="invalid_json_value",
            field=field,
            message="HUD composition values must be JSON-safe scalars, lists, or objects.",
            value=repr(value),
        )
    )
    return None


def _string_key_object(
    mapping: Mapping[object, object],
    field: str,
    diagnostics: list[HudCompositionDiagnostic],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in mapping.items():
        if type(key) is not str or not key:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="invalid_key",
                    field=field,
                    message="HUD composition keys must be non-empty strings.",
                    value=repr(key),
                )
            )
            continue
        result[key] = value
    return result


def _object_section(
    payload: object,
    field: str,
    diagnostics: list[HudCompositionDiagnostic],
) -> dict[str, object]:
    if type(payload) is not dict:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="invalid_section",
                field=field,
                message=f"{field} must be an object.",
            )
        )
        return {}
    return _string_key_object(cast(dict[object, object], payload), field, diagnostics)


def _required_string(
    section: dict[str, object],
    key: str,
    diagnostics: list[HudCompositionDiagnostic],
    prefix: str,
) -> str:
    value = section.get(key)
    field = key if prefix == "$" else f"{prefix}.{key}"
    if type(value) is str and value:
        return value
    diagnostics.append(
        _diagnostic(
            severity="error",
            code="invalid_string",
            field=field,
            message=f"{field} must be a non-empty string.",
            value=repr(value),
        )
    )
    return ""


def _optional_string(
    section: dict[str, object],
    key: str,
    *,
    default: str | None,
) -> str | None:
    value = section.get(key, default)
    if type(value) is str and value:
        return value
    return default


def _optional_int(section: dict[str, object], key: str, *, default: int) -> int:
    value = section.get(key, default)
    if type(value) is int:
        return value
    return default


def _optional_float(section: dict[str, object], key: str, *, default: float) -> float:
    value = section.get(key, default)
    if type(value) is int:
        return float(value)
    if type(value) is float:
        return value
    return default


def _diagnose_unknown_keys(
    section: dict[str, object],
    allowed_keys: frozenset[str],
    field: str,
    diagnostics: list[HudCompositionDiagnostic],
) -> None:
    for key in sorted(section):
        if key in _FORBIDDEN_INCLUDE_KEYS:
            continue
        if key not in allowed_keys:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="unknown_key",
                    field=f"{field}.{key}" if field != "$" else key,
                    message=f"Unknown HUD composition key: {key}.",
                    value=key,
                )
            )


def _diagnose_forbidden_include_keys(
    section: dict[str, object],
    field: str,
    diagnostics: list[HudCompositionDiagnostic],
) -> None:
    for key in sorted(section):
        if key in _FORBIDDEN_INCLUDE_KEYS:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="unsafe_include",
                    field=f"{field}.{key}" if field != "$" else key,
                    message="HUD composition includes/templates are not supported yet.",
                    value=key,
                )
            )


def _diagnostic(
    *,
    severity: HudCompositionSeverity,
    code: str,
    field: str,
    message: str,
    value: str | None = None,
) -> HudCompositionDiagnostic:
    return HudCompositionDiagnostic(
        severity=severity,
        code=code,
        field=field,
        message=message,
        value=value,
    )
