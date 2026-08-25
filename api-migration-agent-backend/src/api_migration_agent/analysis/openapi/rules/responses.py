"""Deterministic compatibility rules for JSON OpenAPI responses.

Every response key on operations shared by both contracts is considered,
including ``default`` and patterned status keys. Schema details are compared only
for the explicitly supported ``application/json`` media type.
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
class _ResponsePropertyFact:
    """Normalized evidence for one JSON response property."""

    name: str
    required: bool
    schema_type: str | None

    def as_json(self) -> dict[str, str | bool | None]:
        """Return the minimal property representation stored in evidence."""

        return {"name": self.name, "required": self.required, "type": self.schema_type}


@dataclass(frozen=True, slots=True)
class _ResponseFact:
    """Normalized response status and optional JSON schema facts."""

    status: str
    pointer: str
    schema_reference: str | None
    properties: Mapping[str, _ResponsePropertyFact]


def compare_responses(
    old_document: OpenApiDocument,
    new_document: OpenApiDocument,
) -> tuple[ApiChange, ...]:
    """Compare response contracts on operations present in both documents.

    Args:
        old_document: Validated baseline OpenAPI contract.
        new_document: Validated revision OpenAPI contract.

    Returns:
        Stable removed-status, schema-reference, and property changes.
    """

    old_resolver = LocalSchemaResolver(old_document)
    new_resolver = LocalSchemaResolver(new_document)
    changes: list[ApiChange] = []

    for pair in match_operations(old_document, new_document):
        old_responses = _extract_responses(
            old_document, pair.old_path, pair.old_method, old_resolver
        )
        new_responses = _extract_responses(
            new_document, pair.new_path, pair.new_method, new_resolver
        )
        for status in sorted(old_responses.keys() - new_responses.keys()):
            changes.append(_status_removed(pair.new_path, pair.new_method, old_responses[status]))
        for status in sorted(old_responses.keys() & new_responses.keys()):
            changes.extend(
                _compare_response(
                    pair.new_path,
                    pair.new_method,
                    old_responses[status],
                    new_responses[status],
                )
            )
    return tuple(changes)


def _compare_response(
    path: str,
    method: HttpMethod,
    old_response: _ResponseFact,
    new_response: _ResponseFact,
) -> list[ApiChange]:
    """Compare schema identity and properties for a matched response status."""

    changes: list[ApiChange] = []
    if (
        old_response.schema_reference is not None
        and new_response.schema_reference is not None
        and old_response.schema_reference != new_response.schema_reference
    ):
        changes.append(_schema_reference_changed(path, method, old_response, new_response))

    old_names = set(old_response.properties)
    for name in sorted(old_names):
        old_property = old_response.properties[name]
        new_property = new_response.properties.get(name)
        if old_property.required and (new_property is None or not new_property.required):
            changes.append(
                _required_property_removed(
                    path,
                    method,
                    old_response,
                    new_response,
                    old_property,
                    new_property,
                )
            )
        if (
            new_property is not None
            and old_property.schema_type is not None
            and new_property.schema_type is not None
            and old_property.schema_type != new_property.schema_type
        ):
            changes.append(
                _property_type_changed(
                    path,
                    method,
                    old_response,
                    new_response,
                    old_property,
                    new_property,
                )
            )
    return changes


def _extract_responses(
    document: OpenApiDocument,
    path: str,
    method: HttpMethod,
    resolver: LocalSchemaResolver,
) -> dict[str, _ResponseFact]:
    """Normalize structurally valid Response Objects for one operation."""

    paths = document.get("paths")
    path_item = paths.get(path) if isinstance(paths, Mapping) else None
    operation = path_item.get(method.value) if isinstance(path_item, Mapping) else None
    raw_responses = operation.get("responses") if isinstance(operation, Mapping) else None
    if not isinstance(raw_responses, Mapping):
        return {}

    responses: dict[str, _ResponseFact] = {}
    for raw_status, raw_response in raw_responses.items():
        if not isinstance(raw_status, str) or not isinstance(raw_response, Mapping):
            continue
        pointer = (
            f"#/paths/{_escape_pointer(path)}/{method.value}/responses/"
            f"{_escape_pointer(raw_status)}"
        )
        responses[raw_status] = _normalize_response(
            raw_status,
            raw_response,
            pointer,
            resolver,
        )
    return responses


def _normalize_response(
    status: str,
    raw_response: Mapping[str, Any],
    pointer: str,
    resolver: LocalSchemaResolver,
) -> _ResponseFact:
    """Resolve one Response Object and extract its supported JSON schema."""

    response_reference = raw_response.get("$ref")
    response = (
        resolver.resolve_response(response_reference)
        if isinstance(response_reference, str)
        else raw_response
    )
    content = response.get("content")
    media = content.get("application/json") if isinstance(content, Mapping) else None
    raw_schema = media.get("schema") if isinstance(media, Mapping) else None
    if not isinstance(raw_schema, Mapping):
        return _ResponseFact(status, pointer, None, {})

    raw_schema_reference = raw_schema.get("$ref")
    schema_reference = raw_schema_reference if isinstance(raw_schema_reference, str) else None
    schema = resolver.resolve_schema_object(raw_schema)
    required_names = _required_property_names(schema.get("required"))
    raw_properties = schema.get("properties")
    properties = raw_properties if isinstance(raw_properties, Mapping) else {}
    property_facts: dict[str, _ResponsePropertyFact] = {}
    for name, raw_property in properties.items():
        if not isinstance(name, str) or not isinstance(raw_property, Mapping):
            continue
        property_schema = resolver.resolve_schema_object(raw_property)
        raw_type = property_schema.get("type")
        property_facts[name] = _ResponsePropertyFact(
            name=name,
            required=name in required_names,
            schema_type=raw_type if isinstance(raw_type, str) else None,
        )
    return _ResponseFact(status, pointer, schema_reference, property_facts)


def _required_property_names(raw_required: Any) -> frozenset[str]:
    """Return valid property names from a schema required array."""

    if not isinstance(raw_required, Sequence) or isinstance(raw_required, (str, bytes)):
        return frozenset()
    return frozenset(item for item in raw_required if isinstance(item, str))


def _status_removed(path: str, method: HttpMethod, old_response: _ResponseFact) -> ApiChange:
    """Build a removed response-status compatibility fact."""

    return _change(
        category=ChangeCategory.RESPONSE_STATUS_REMOVED,
        path=path,
        method=method,
        status=old_response.status,
        subject=old_response.status,
        old_value={"status": old_response.status},
        new_value=None,
        old_pointer=old_response.pointer,
        new_pointer=None,
        description=(
            f"Response status '{old_response.status}' was removed from "
            f"{method.value.upper()} {path}."
        ),
        summary="The response status exists in the baseline and not in the revision.",
    )


def _schema_reference_changed(
    path: str,
    method: HttpMethod,
    old_response: _ResponseFact,
    new_response: _ResponseFact,
) -> ApiChange:
    """Build an explicit response schema-reference change fact."""

    return _change(
        category=ChangeCategory.RESPONSE_SCHEMA_REFERENCE_CHANGED,
        path=path,
        method=method,
        status=new_response.status,
        subject=new_response.status,
        old_value={"$ref": old_response.schema_reference},
        new_value={"$ref": new_response.schema_reference},
        old_pointer=old_response.pointer,
        new_pointer=new_response.pointer,
        description=(
            f"Response schema reference changed for status '{new_response.status}' on "
            f"{method.value.upper()} {path}."
        ),
        summary="Both responses use explicit local schema references with different targets.",
    )


def _required_property_removed(
    path: str,
    method: HttpMethod,
    old_response: _ResponseFact,
    new_response: _ResponseFact,
    old_property: _ResponsePropertyFact,
    new_property: _ResponsePropertyFact | None,
) -> ApiChange:
    """Build a lost required-response-property guarantee fact."""

    return _change(
        category=ChangeCategory.RESPONSE_REQUIRED_PROPERTY_REMOVED,
        path=path,
        method=method,
        status=old_response.status,
        subject=old_property.name,
        old_value=old_property.as_json(),
        new_value=None if new_property is None else new_property.as_json(),
        old_pointer=old_response.pointer,
        new_pointer=new_response.pointer,
        description=(
            f"Response property '{old_property.name}' is no longer guaranteed for status "
            f"'{old_response.status}' on {method.value.upper()} {path}."
        ),
        summary="A baseline required property is absent or optional in the revision schema.",
    )


def _property_type_changed(
    path: str,
    method: HttpMethod,
    old_response: _ResponseFact,
    new_response: _ResponseFact,
    old_property: _ResponsePropertyFact,
    new_property: _ResponsePropertyFact,
) -> ApiChange:
    """Build an explicit response-property type-change fact."""

    return _change(
        category=ChangeCategory.RESPONSE_PROPERTY_TYPE_CHANGED,
        path=path,
        method=method,
        status=old_response.status,
        subject=old_property.name,
        old_value=old_property.as_json(),
        new_value=new_property.as_json(),
        old_pointer=old_response.pointer,
        new_pointer=new_response.pointer,
        description=(
            f"Response property '{old_property.name}' changed type from "
            f"'{old_property.schema_type}' to '{new_property.schema_type}' for status "
            f"'{old_response.status}'."
        ),
        summary="The matched response property has different explicit schema types.",
    )


def _change(
    *,
    category: ChangeCategory,
    path: str,
    method: HttpMethod,
    status: str,
    subject: str,
    old_value: dict[str, str | bool | None] | None,
    new_value: dict[str, str | bool | None] | None,
    old_pointer: str | None,
    new_pointer: str | None,
    description: str,
    summary: str,
) -> ApiChange:
    """Create a consistently structured breaking response change."""

    identity = f"{category.value}\x00{path}\x00{method.value}\x00{status}\x00{subject}".encode()
    return ApiChange(
        id=f"CHANGE-{hashlib.sha256(identity).hexdigest()[:12].upper()}",
        category=category,
        severity=ChangeSeverity.HIGH,
        breaking=True,
        path=path,
        method=method,
        location=f"response.{status}",
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
