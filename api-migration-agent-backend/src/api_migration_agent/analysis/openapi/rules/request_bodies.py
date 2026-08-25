"""Deterministic compatibility rules for JSON request bodies.

Only operations present in both contracts are compared. The MVP inspects the
``application/json`` media type and ordinary object ``properties``. Composition
keywords are intentionally not interpreted because doing so incompletely could
turn inference into false compatibility facts.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from api_migration_agent.analysis.openapi.loader import OpenApiDocument
from api_migration_agent.analysis.openapi.ref_resolver import LocalSchemaResolver
from api_migration_agent.analysis.openapi.rules.operations import match_operations
from api_migration_agent.domain.api_change import ApiChange, ChangeEvidence
from api_migration_agent.domain.enums import ChangeCategory, ChangeSeverity, HttpMethod


@dataclass(frozen=True, slots=True)
class _PropertyFact:
    """Normalized evidence for one request schema property."""

    name: str
    required: bool
    schema_type: str | None
    schema: Mapping[str, Any]

    def as_json(self) -> dict[str, str | bool | None]:
        """Return the minimal property value suitable for change evidence."""

        return {"name": self.name, "required": self.required, "type": self.schema_type}


@dataclass(frozen=True, slots=True)
class _RequestBodyFact:
    """Normalized JSON request body for a single operation."""

    required: bool
    pointer: str
    properties: Mapping[str, _PropertyFact]


def compare_request_bodies(
    old_document: OpenApiDocument,
    new_document: OpenApiDocument,
) -> tuple[ApiChange, ...]:
    """Compare JSON request bodies on operations shared by both contracts.

    Args:
        old_document: Validated baseline OpenAPI contract.
        new_document: Validated revision OpenAPI contract.

    Returns:
        Stable request-body and property compatibility changes.
    """

    old_resolver = LocalSchemaResolver(old_document)
    new_resolver = LocalSchemaResolver(new_document)
    changes: list[ApiChange] = []

    for pair in match_operations(old_document, new_document):
        old_body = _extract_request_body(old_document, pair.old_path, pair.old_method, old_resolver)
        new_body = _extract_request_body(new_document, pair.new_path, pair.new_method, new_resolver)
        if (
            new_body is not None
            and new_body.required
            and (old_body is None or not old_body.required)
        ):
            changes.append(
                _body_became_required(pair.new_path, pair.new_method, old_body, new_body)
            )
        if old_body is not None and new_body is not None:
            changes.extend(_compare_properties(pair.new_path, pair.new_method, old_body, new_body))
    return tuple(changes)


def _compare_properties(
    path: str,
    method: HttpMethod,
    old_body: _RequestBodyFact,
    new_body: _RequestBodyFact,
) -> list[ApiChange]:
    """Compare properties and apply the bounded rename-candidate rule."""

    changes: list[ApiChange] = []
    old_names = set(old_body.properties)
    new_names = set(new_body.properties)

    for name in sorted(old_names & new_names):
        old_property = old_body.properties[name]
        new_property = new_body.properties[name]
        if (
            old_property.schema_type is not None
            and new_property.schema_type is not None
            and old_property.schema_type != new_property.schema_type
        ):
            changes.append(
                _property_type_changed(path, method, old_body, new_body, old_property, new_property)
            )
        if not old_property.required and new_property.required:
            changes.append(_required_property_added(path, method, old_body, new_body, new_property))

    removed_names = old_names - new_names
    added_names = new_names - old_names
    rename_pairs = _unique_rename_pairs(old_body, new_body, removed_names, added_names)
    for old_name, new_name in rename_pairs:
        changes.append(
            _property_renamed(
                path,
                method,
                old_body,
                new_body,
                old_body.properties[old_name],
                new_body.properties[new_name],
            )
        )
        removed_names.remove(old_name)
        added_names.remove(new_name)

    for name in sorted(removed_names):
        changes.append(_property_removed(path, method, old_body, old_body.properties[name]))
    for name in sorted(added_names):
        property_fact = new_body.properties[name]
        if property_fact.required:
            changes.append(
                _required_property_added(path, method, old_body, new_body, property_fact)
            )
    return changes


def _unique_rename_pairs(
    old_body: _RequestBodyFact,
    new_body: _RequestBodyFact,
    removed_names: set[str],
    added_names: set[str],
) -> tuple[tuple[str, str], ...]:
    """Return mutually unique structural matches between removed and added names."""

    old_candidates = {
        old_name: {
            new_name
            for new_name in added_names
            if _is_rename_candidate(
                old_body.properties[old_name],
                new_body.properties[new_name],
            )
        }
        for old_name in removed_names
    }
    new_candidates = {
        new_name: {
            old_name
            for old_name in removed_names
            if _is_rename_candidate(
                old_body.properties[old_name],
                new_body.properties[new_name],
            )
        }
        for new_name in added_names
    }
    pairs = [
        (old_name, next(iter(candidates)))
        for old_name, candidates in old_candidates.items()
        if len(candidates) == 1 and len(new_candidates[next(iter(candidates))]) == 1
    ]
    return tuple(sorted(pairs))


def _extract_request_body(
    document: OpenApiDocument,
    path: str,
    method: HttpMethod,
    resolver: LocalSchemaResolver,
) -> _RequestBodyFact | None:
    """Extract one supported application/json Request Body Object."""

    paths = document.get("paths")
    path_item = paths.get(path) if isinstance(paths, Mapping) else None
    operation = path_item.get(method.value) if isinstance(path_item, Mapping) else None
    if not isinstance(operation, Mapping):
        return None

    raw_body = operation.get("requestBody")
    if not isinstance(raw_body, Mapping):
        return None
    reference = raw_body.get("$ref")
    body = resolver.resolve_request_body(reference) if isinstance(reference, str) else raw_body
    content = body.get("content")
    media = content.get("application/json") if isinstance(content, Mapping) else None
    raw_schema = media.get("schema") if isinstance(media, Mapping) else None
    if not isinstance(raw_schema, Mapping):
        return None

    schema = resolver.resolve_schema_object(raw_schema)
    raw_properties = schema.get("properties")
    properties = raw_properties if isinstance(raw_properties, Mapping) else {}
    required_names = _required_property_names(schema.get("required"))
    property_facts: dict[str, _PropertyFact] = {}
    for name, raw_property in properties.items():
        if not isinstance(name, str) or not isinstance(raw_property, Mapping):
            continue
        property_schema = resolver.resolve_schema_object(raw_property)
        raw_type = property_schema.get("type")
        property_facts[name] = _PropertyFact(
            name=name,
            required=name in required_names,
            schema_type=raw_type if isinstance(raw_type, str) else None,
            schema=property_schema,
        )

    pointer = f"#/paths/{_escape_pointer(path)}/{method.value}/requestBody"
    return _RequestBodyFact(
        required=body.get("required") is True,
        pointer=pointer,
        properties=property_facts,
    )


def _required_property_names(raw_required: Any) -> frozenset[str]:
    """Return valid names from an OpenAPI schema's required array."""

    if not isinstance(raw_required, Sequence) or isinstance(raw_required, (str, bytes)):
        return frozenset()
    return frozenset(item for item in raw_required if isinstance(item, str))


def _is_rename_candidate(old_property: _PropertyFact, new_property: _PropertyFact) -> bool:
    """Return whether a one-to-one rename candidate has identical structure."""

    return (
        old_property.required == new_property.required
        and old_property.schema == new_property.schema
    )


def _body_became_required(
    path: str,
    method: HttpMethod,
    old_body: _RequestBodyFact | None,
    new_body: _RequestBodyFact,
) -> ApiChange:
    """Build a required request-body compatibility fact."""

    return _change(
        category=ChangeCategory.REQUEST_BODY_BECAME_REQUIRED,
        path=path,
        method=method,
        subject="request_body",
        old_value=None if old_body is None else {"required": old_body.required},
        new_value={"required": True},
        old_pointer=None if old_body is None else old_body.pointer,
        new_pointer=new_body.pointer,
        description=f"The request body became required for {method.value.upper()} {path}.",
        summary="The revision requires a body where the baseline did not.",
    )


def _required_property_added(
    path: str,
    method: HttpMethod,
    old_body: _RequestBodyFact,
    new_body: _RequestBodyFact,
    new_property: _PropertyFact,
) -> ApiChange:
    """Build a newly required request-property fact."""

    old_property = old_body.properties.get(new_property.name)
    return _change(
        category=ChangeCategory.REQUEST_PROPERTY_ADDED_REQUIRED,
        path=path,
        method=method,
        subject=new_property.name,
        old_value=None if old_property is None else old_property.as_json(),
        new_value=new_property.as_json(),
        old_pointer=old_body.pointer,
        new_pointer=new_body.pointer,
        description=(
            f"Request property '{new_property.name}' became required for "
            f"{method.value.upper()} {path}."
        ),
        summary="The property is newly required in the revision request schema.",
    )


def _property_removed(
    path: str,
    method: HttpMethod,
    old_body: _RequestBodyFact,
    old_property: _PropertyFact,
) -> ApiChange:
    """Build a removed request-property fact."""

    return _change(
        category=ChangeCategory.REQUEST_PROPERTY_REMOVED,
        path=path,
        method=method,
        subject=old_property.name,
        old_value=old_property.as_json(),
        new_value=None,
        old_pointer=old_body.pointer,
        new_pointer=None,
        description=(
            f"Request property '{old_property.name}' was removed from "
            f"{method.value.upper()} {path}."
        ),
        summary="The property exists in the baseline schema and not in the revision schema.",
    )


def _property_type_changed(
    path: str,
    method: HttpMethod,
    old_body: _RequestBodyFact,
    new_body: _RequestBodyFact,
    old_property: _PropertyFact,
    new_property: _PropertyFact,
) -> ApiChange:
    """Build an explicit request-property type-change fact."""

    return _change(
        category=ChangeCategory.REQUEST_PROPERTY_TYPE_CHANGED,
        path=path,
        method=method,
        subject=new_property.name,
        old_value=old_property.as_json(),
        new_value=new_property.as_json(),
        old_pointer=old_body.pointer,
        new_pointer=new_body.pointer,
        description=(
            f"Request property '{new_property.name}' changed type from "
            f"'{old_property.schema_type}' to '{new_property.schema_type}'."
        ),
        summary="The matched property has different explicit schema types.",
    )


def _property_renamed(
    path: str,
    method: HttpMethod,
    old_body: _RequestBodyFact,
    new_body: _RequestBodyFact,
    old_property: _PropertyFact,
    new_property: _PropertyFact,
) -> ApiChange:
    """Build a conservative structurally identical rename-candidate fact."""

    return _change(
        category=ChangeCategory.REQUEST_PROPERTY_RENAMED,
        path=path,
        method=method,
        subject=f"{old_property.name}->{new_property.name}",
        old_value=old_property.as_json(),
        new_value=new_property.as_json(),
        old_pointer=old_body.pointer,
        new_pointer=new_body.pointer,
        description=(
            f"Request property '{old_property.name}' is a deterministic rename candidate for "
            f"'{new_property.name}' on {method.value.upper()} {path}."
        ),
        summary=("The removed and added properties are a mutually unique structural match."),
    )


def _change(
    *,
    category: ChangeCategory,
    path: str,
    method: HttpMethod,
    subject: str,
    old_value: dict[str, str | bool | None] | None,
    new_value: dict[str, str | bool | None] | None,
    old_pointer: str | None,
    new_pointer: str | None,
    description: str,
    summary: str,
) -> ApiChange:
    """Create a consistently structured breaking request-body change."""

    identity = f"{category.value}\x00{path}\x00{method.value}\x00{subject}".encode()
    return ApiChange(
        id=f"CHANGE-{hashlib.sha256(identity).hexdigest()[:12].upper()}",
        category=category,
        severity=ChangeSeverity.HIGH,
        breaking=True,
        path=path,
        method=method,
        location="request.body",
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
