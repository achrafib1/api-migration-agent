"""Deterministic compatibility rules for OpenAPI Parameter Objects.

The rule engine computes the effective parameters of every operation shared by
both documents. Path-level parameters are inherited, while operation-level
parameters override an inherited parameter with the same ``(name, in)`` key as
required by OpenAPI.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from api_migration_agent.analysis.openapi.loader import OpenApiDocument
from api_migration_agent.analysis.openapi.ref_resolver import LocalSchemaResolver
from api_migration_agent.analysis.openapi.rules.operations import match_operations
from api_migration_agent.core.exceptions import OpenApiDocumentError
from api_migration_agent.domain.api_change import ApiChange, ChangeEvidence
from api_migration_agent.domain.enums import (
    ChangeCategory,
    ChangeSeverity,
    HttpMethod,
    ParameterLocation,
)

type ParameterKey = tuple[str, ParameterLocation]


@dataclass(frozen=True, slots=True)
class _ParameterFact:
    """Normalized parameter data used only inside deterministic comparison."""

    name: str
    location: ParameterLocation
    required: bool
    schema_type: str | None
    pointer: str

    @property
    def key(self) -> ParameterKey:
        """Return the OpenAPI identity key for this parameter."""

        return self.name, self.location

    def as_json(self) -> dict[str, str | bool | None]:
        """Return the minimal evidence value stored in an API change."""

        return {
            "name": self.name,
            "in": self.location.value,
            "required": self.required,
            "type": self.schema_type,
        }


def compare_parameters(
    old_document: OpenApiDocument,
    new_document: OpenApiDocument,
) -> tuple[ApiChange, ...]:
    """Compare effective parameters on operations present in both documents.

    Args:
        old_document: Validated baseline OpenAPI contract.
        new_document: Validated revision OpenAPI contract.

    Returns:
        Stable parameter changes ordered by operation and parameter identity.

    Raises:
        OpenApiDocumentError: If a parameter list contains duplicate identities,
            which would make deterministic matching ambiguous.
    """

    old_resolver = LocalSchemaResolver(old_document)
    new_resolver = LocalSchemaResolver(new_document)
    changes: list[ApiChange] = []

    for pair in match_operations(old_document, new_document):
        old_parameters = _effective_parameters(
            old_document, pair.old_path, pair.old_method, old_resolver
        )
        new_parameters = _effective_parameters(
            new_document, pair.new_path, pair.new_method, new_resolver
        )
        changes.extend(
            _compare_operation_parameters(
                pair.new_path, pair.new_method, old_parameters, new_parameters
            )
        )

    return tuple(changes)


def _compare_operation_parameters(
    path: str,
    method: HttpMethod,
    old_parameters: Mapping[ParameterKey, _ParameterFact],
    new_parameters: Mapping[ParameterKey, _ParameterFact],
) -> list[ApiChange]:
    """Compare one operation while conservatively identifying location moves."""

    changes: list[ApiChange] = []
    old_unmatched = dict(old_parameters)
    new_unmatched = dict(new_parameters)

    for key in sorted(old_parameters.keys() & new_parameters.keys()):
        old_parameter = old_unmatched.pop(key)
        new_parameter = new_unmatched.pop(key)
        changes.extend(_compare_matched_parameter(path, method, old_parameter, new_parameter))

    # A location change is certain only with one unmatched old and one unmatched
    # new parameter sharing a name. Multiple candidates are intentionally left
    # as removals and additions because choosing a pairing would be inference.
    old_by_name = _group_by_name(old_unmatched.values())
    new_by_name = _group_by_name(new_unmatched.values())
    for name in sorted(old_by_name.keys() & new_by_name.keys()):
        old_candidates = old_by_name[name]
        new_candidates = new_by_name[name]
        if len(old_candidates) != 1 or len(new_candidates) != 1:
            continue
        old_parameter = old_candidates[0]
        new_parameter = new_candidates[0]
        old_unmatched.pop(old_parameter.key)
        new_unmatched.pop(new_parameter.key)
        changes.append(_location_changed(path, method, old_parameter, new_parameter))
        changes.extend(_compare_matched_parameter(path, method, old_parameter, new_parameter))

    for key in sorted(old_unmatched):
        changes.append(_parameter_removed(path, method, old_unmatched[key]))
    for key in sorted(new_unmatched):
        changes.append(_parameter_added(path, method, new_unmatched[key]))
    return changes


def _compare_matched_parameter(
    path: str,
    method: HttpMethod,
    old_parameter: _ParameterFact,
    new_parameter: _ParameterFact,
) -> list[ApiChange]:
    """Detect requirement and schema-type changes for a matched parameter."""

    changes: list[ApiChange] = []
    if not old_parameter.required and new_parameter.required:
        changes.append(_parameter_became_required(path, method, old_parameter, new_parameter))
    if (
        old_parameter.schema_type is not None
        and new_parameter.schema_type is not None
        and old_parameter.schema_type != new_parameter.schema_type
    ):
        changes.append(_parameter_type_changed(path, method, old_parameter, new_parameter))
    return changes


def _effective_parameters(
    document: OpenApiDocument,
    path: str,
    method: HttpMethod,
    resolver: LocalSchemaResolver,
) -> dict[ParameterKey, _ParameterFact]:
    """Merge inherited and operation-specific parameters for one operation."""

    paths = document.get("paths")
    path_item = paths.get(path) if isinstance(paths, Mapping) else None
    operation = path_item.get(method.value) if isinstance(path_item, Mapping) else None
    if not isinstance(path_item, Mapping) or not isinstance(operation, Mapping):
        return {}

    path_pointer = f"#/paths/{_escape_pointer(path)}"
    inherited = _parameter_map(path_item.get("parameters"), f"{path_pointer}/parameters", resolver)
    specific = _parameter_map(
        operation.get("parameters"),
        f"{path_pointer}/{method.value}/parameters",
        resolver,
    )
    return inherited | specific


def _parameter_map(
    raw_parameters: Any,
    pointer: str,
    resolver: LocalSchemaResolver,
) -> dict[ParameterKey, _ParameterFact]:
    """Normalize one Parameter Object list and reject duplicate identities."""

    if raw_parameters is None:
        return {}
    if not isinstance(raw_parameters, Sequence) or isinstance(raw_parameters, (str, bytes)):
        raise OpenApiDocumentError

    parameters: dict[ParameterKey, _ParameterFact] = {}
    for index, item in enumerate(raw_parameters):
        parameter = _normalize_parameter(item, f"{pointer}/{index}", resolver)
        if parameter is None:
            continue
        if parameter.key in parameters:
            raise OpenApiDocumentError
        parameters[parameter.key] = parameter
    return parameters


def _normalize_parameter(
    item: Any,
    pointer: str,
    resolver: LocalSchemaResolver,
) -> _ParameterFact | None:
    """Convert a supported inline or referenced Parameter Object to a fact."""

    if not isinstance(item, Mapping):
        return None

    reference = item.get("$ref")
    parameter = resolver.resolve_parameter(reference) if isinstance(reference, str) else item
    name = parameter.get("name")
    raw_location = parameter.get("in")
    if not isinstance(name, str) or not name or not isinstance(raw_location, str):
        return None
    try:
        location = ParameterLocation(raw_location)
    except ValueError:
        return None

    schema = parameter.get("schema")
    raw_type = schema.get("type") if isinstance(schema, Mapping) else None
    schema_type = raw_type if isinstance(raw_type, str) else None
    return _ParameterFact(
        name=name,
        location=location,
        required=parameter.get("required") is True,
        schema_type=schema_type,
        pointer=pointer,
    )


def _group_by_name(parameters: Any) -> dict[str, list[_ParameterFact]]:
    """Group unmatched parameters by name for conservative move detection."""

    grouped: dict[str, list[_ParameterFact]] = defaultdict(list)
    for parameter in parameters:
        grouped[parameter.name].append(parameter)
    return grouped


def _parameter_added(path: str, method: HttpMethod, parameter: _ParameterFact) -> ApiChange:
    """Build a required or optional parameter-addition fact."""

    category = (
        ChangeCategory.PARAMETER_ADDED_REQUIRED
        if parameter.required
        else ChangeCategory.PARAMETER_ADDED_OPTIONAL
    )
    severity = ChangeSeverity.HIGH if parameter.required else ChangeSeverity.INFO
    qualifier = "required" if parameter.required else "optional"
    return _change(
        category=category,
        severity=severity,
        breaking=parameter.required,
        path=path,
        method=method,
        parameter=parameter,
        old_value=None,
        new_value=parameter.as_json(),
        old_pointer=None,
        new_pointer=parameter.pointer,
        description=(
            f"{qualifier.capitalize()} {parameter.location.value} parameter "
            f"'{parameter.name}' was added to {method.value.upper()} {path}."
        ),
        summary="Parameter is absent from the baseline and present in the revision.",
    )


def _parameter_removed(path: str, method: HttpMethod, parameter: _ParameterFact) -> ApiChange:
    """Build a breaking removed-parameter fact."""

    return _change(
        category=ChangeCategory.PARAMETER_REMOVED,
        severity=ChangeSeverity.HIGH,
        breaking=True,
        path=path,
        method=method,
        parameter=parameter,
        old_value=parameter.as_json(),
        new_value=None,
        old_pointer=parameter.pointer,
        new_pointer=None,
        description=(
            f"{parameter.location.value.capitalize()} parameter '{parameter.name}' was removed "
            f"from {method.value.upper()} {path}."
        ),
        summary="Parameter is present in the baseline and absent from the revision.",
    )


def _parameter_became_required(
    path: str,
    method: HttpMethod,
    old_parameter: _ParameterFact,
    new_parameter: _ParameterFact,
) -> ApiChange:
    """Build an optional-to-required parameter fact."""

    return _change(
        category=ChangeCategory.PARAMETER_BECAME_REQUIRED,
        severity=ChangeSeverity.HIGH,
        breaking=True,
        path=path,
        method=method,
        parameter=new_parameter,
        old_value=old_parameter.as_json(),
        new_value=new_parameter.as_json(),
        old_pointer=old_parameter.pointer,
        new_pointer=new_parameter.pointer,
        description=(
            f"{new_parameter.location.value.capitalize()} parameter '{new_parameter.name}' became "
            f"required for {method.value.upper()} {path}."
        ),
        summary="The matched parameter changed from optional to required.",
    )


def _parameter_type_changed(
    path: str,
    method: HttpMethod,
    old_parameter: _ParameterFact,
    new_parameter: _ParameterFact,
) -> ApiChange:
    """Build a parameter schema-type change fact."""

    return _change(
        category=ChangeCategory.PARAMETER_TYPE_CHANGED,
        severity=ChangeSeverity.HIGH,
        breaking=True,
        path=path,
        method=method,
        parameter=new_parameter,
        old_value=old_parameter.as_json(),
        new_value=new_parameter.as_json(),
        old_pointer=old_parameter.pointer,
        new_pointer=new_parameter.pointer,
        description=(
            f"{new_parameter.location.value.capitalize()} parameter '{new_parameter.name}' changed "
            f"type from '{old_parameter.schema_type}' to '{new_parameter.schema_type}'."
        ),
        summary="The matched parameter has different explicit schema types.",
    )


def _location_changed(
    path: str,
    method: HttpMethod,
    old_parameter: _ParameterFact,
    new_parameter: _ParameterFact,
) -> ApiChange:
    """Build a conservatively matched parameter-location change fact."""

    return _change(
        category=ChangeCategory.PARAMETER_LOCATION_CHANGED,
        severity=ChangeSeverity.HIGH,
        breaking=True,
        path=path,
        method=method,
        parameter=new_parameter,
        old_value=old_parameter.as_json(),
        new_value=new_parameter.as_json(),
        old_pointer=old_parameter.pointer,
        new_pointer=new_parameter.pointer,
        description=(
            f"Parameter '{new_parameter.name}' moved from {old_parameter.location.value} to "
            f"{new_parameter.location.value} for {method.value.upper()} {path}."
        ),
        summary="Exactly one unmatched parameter with this name exists in each document.",
    )


def _change(
    *,
    category: ChangeCategory,
    severity: ChangeSeverity,
    breaking: bool,
    path: str,
    method: HttpMethod,
    parameter: _ParameterFact,
    old_value: dict[str, str | bool | None] | None,
    new_value: dict[str, str | bool | None] | None,
    old_pointer: str | None,
    new_pointer: str | None,
    description: str,
    summary: str,
) -> ApiChange:
    """Create a consistently structured evidence-backed parameter change."""

    identity = (
        f"{category.value}\x00{path}\x00{method.value}\x00"
        f"{parameter.name}\x00{parameter.location.value}"
    ).encode()
    return ApiChange(
        id=f"CHANGE-{hashlib.sha256(identity).hexdigest()[:12].upper()}",
        category=category,
        severity=severity,
        breaking=breaking,
        path=path,
        method=method,
        location=f"parameter.{parameter.location.value}",
        old_value=old_value,
        new_value=new_value,
        description=description,
        evidence=(
            ChangeEvidence(
                old_document_pointer=old_pointer,
                new_document_pointer=new_pointer,
                summary=summary,
            ),
        ),
    )


def _escape_pointer(value: str) -> str:
    """Escape one JSON Pointer token according to RFC 6901."""

    return value.replace("~", "~0").replace("/", "~1")
