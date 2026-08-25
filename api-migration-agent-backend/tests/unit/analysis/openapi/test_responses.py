"""Tests for deterministic JSON response compatibility rules."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest
from pydantic import JsonValue

from api_migration_agent.analysis.openapi.comparator import compare_api_documents
from api_migration_agent.analysis.openapi.loader import OpenApiDocument
from api_migration_agent.analysis.openapi.rules.responses import compare_responses
from api_migration_agent.core.exceptions import ReferenceResolutionError, UnsupportedReferenceError
from api_migration_agent.domain.enums import ChangeCategory


def _property(schema_type: str | None = "string") -> dict[str, JsonValue]:
    """Build a synthetic response property schema."""

    return {} if schema_type is None else {"type": schema_type}


def _schema(
    properties: Mapping[str, JsonValue],
    *,
    required: list[str] | None = None,
) -> dict[str, JsonValue]:
    """Build a synthetic response object schema."""

    schema: dict[str, JsonValue] = {"type": "object", "properties": dict(properties)}
    if required is not None:
        schema["required"] = cast(JsonValue, required)
    return schema


def _response(schema: Mapping[str, JsonValue] | None) -> dict[str, JsonValue]:
    """Build a Response Object with optional JSON schema content."""

    response: dict[str, JsonValue] = {"description": "Synthetic response"}
    if schema is not None:
        response["content"] = {"application/json": {"schema": dict(schema)}}
    return response


def _document(
    responses: Mapping[str, JsonValue],
    *,
    components: Mapping[str, JsonValue] | None = None,
) -> OpenApiDocument:
    """Build a GET operation containing the supplied response mapping."""

    document: OpenApiDocument = {
        "openapi": "3.1.0",
        "paths": {"/customers/{id}": {"get": {"responses": dict(responses)}}},
    }
    if components is not None:
        document["components"] = dict(components)
    return document


def test_detects_removed_response_status() -> None:
    """Any removed response key creates a breaking compatibility fact."""

    changes = compare_responses(
        _document({"200": _response(_schema({})), "404": _response(None)}),
        _document({"200": _response(_schema({}))}),
    )

    assert [change.category for change in changes] == [ChangeCategory.RESPONSE_STATUS_REMOVED]
    assert changes[0].old_value == {"status": "404"}
    assert changes[0].evidence[0].old_document_pointer == (
        "#/paths/~1customers~1{id}/get/responses/404"
    )


def test_detects_removed_default_response() -> None:
    """The special default response key is compared like status-code keys."""

    changes = compare_responses(
        _document({"200": _response(None), "default": _response(None)}),
        _document({"200": _response(None)}),
    )

    assert [change.location for change in changes] == ["response.default"]


def test_added_response_status_is_non_breaking_and_omitted() -> None:
    """A newly documented response does not remove existing guarantees."""

    changes = compare_responses(
        _document({"200": _response(None)}),
        _document({"200": _response(None), "404": _response(None)}),
    )

    assert changes == ()


def test_detects_required_response_property_removal() -> None:
    """A required property disappearing breaks consumers relying on it."""

    changes = compare_responses(
        _document({"200": _response(_schema({"id": _property()}, required=["id"]))}),
        _document({"200": _response(_schema({}))}),
    )

    assert [change.category for change in changes] == [
        ChangeCategory.RESPONSE_REQUIRED_PROPERTY_REMOVED
    ]
    assert changes[0].new_value is None


def test_detects_required_property_becoming_optional() -> None:
    """Relaxing the server guarantee is breaking even if the property remains."""

    properties = {"id": _property()}
    changes = compare_responses(
        _document({"200": _response(_schema(properties, required=["id"]))}),
        _document({"200": _response(_schema(properties))}),
    )

    assert [change.category for change in changes] == [
        ChangeCategory.RESPONSE_REQUIRED_PROPERTY_REMOVED
    ]
    assert changes[0].new_value == {"name": "id", "required": False, "type": "string"}


def test_optional_property_removal_is_not_reported_by_supported_rule() -> None:
    """The MVP rule is deliberately limited to required response properties."""

    changes = compare_responses(
        _document({"200": _response(_schema({"note": _property()}))}),
        _document({"200": _response(_schema({}))}),
    )

    assert changes == ()


def test_detects_explicit_response_property_type_change() -> None:
    """Different explicit types on a matched property are breaking."""

    changes = compare_responses(
        _document({"200": _response(_schema({"id": _property("integer")}))}),
        _document({"200": _response(_schema({"id": _property("string")}))}),
    )

    assert [change.category for change in changes] == [
        ChangeCategory.RESPONSE_PROPERTY_TYPE_CHANGED
    ]


def test_missing_type_does_not_invent_response_type_change() -> None:
    """Both sides need explicit type evidence before reporting a type change."""

    changes = compare_responses(
        _document({"200": _response(_schema({"id": _property(None)}))}),
        _document({"200": _response(_schema({"id": _property("string")}))}),
    )

    assert changes == ()


def test_detects_explicit_schema_reference_change() -> None:
    """Different local response schema targets create an explicit fact."""

    old_components: dict[str, JsonValue] = {"schemas": {"CustomerV1": _schema({"id": _property()})}}
    new_components: dict[str, JsonValue] = {"schemas": {"CustomerV2": _schema({"id": _property()})}}
    changes = compare_responses(
        _document(
            {"200": _response({"$ref": "#/components/schemas/CustomerV1"})},
            components=old_components,
        ),
        _document(
            {"200": _response({"$ref": "#/components/schemas/CustomerV2"})},
            components=new_components,
        ),
    )

    assert [change.category for change in changes] == [
        ChangeCategory.RESPONSE_SCHEMA_REFERENCE_CHANGED
    ]


def test_same_schema_reference_produces_no_change() -> None:
    """Stable local schema identity and shape produce no compatibility fact."""

    components: dict[str, JsonValue] = {"schemas": {"Customer": _schema({})}}
    document = _document(
        {"200": _response({"$ref": "#/components/schemas/Customer"})},
        components=components,
    )

    assert compare_responses(document, document) == ()


def test_resolves_reusable_response_component() -> None:
    """Approved local Response Object references participate in comparison."""

    components: dict[str, JsonValue] = {
        "responses": {"Customer": _response(_schema({"id": _property()}, required=["id"]))}
    }
    old = _document(
        {"200": {"$ref": "#/components/responses/Customer"}},
        components=components,
    )
    new = _document({"200": _response(_schema({}))})

    changes = compare_responses(old, new)

    assert [change.category for change in changes] == [
        ChangeCategory.RESPONSE_REQUIRED_PROPERTY_REMOVED
    ]


def test_missing_json_schema_produces_no_property_fact() -> None:
    """A missing supported media schema is insufficient property evidence."""

    changes = compare_responses(
        _document({"200": _response(None)}),
        _document({"200": _response(_schema({"id": _property()}))}),
    )

    assert changes == ()


def test_rejects_external_response_reference() -> None:
    """Response analysis never follows remote Response Objects."""

    new = _document({"200": {"$ref": "https://example.invalid/response.json"}})

    with pytest.raises(UnsupportedReferenceError):
        compare_responses(_document({"200": _response(None)}), new)


def test_rejects_cyclic_response_schema_reference() -> None:
    """Existing schema cycle protection also applies to response analysis."""

    components: dict[str, JsonValue] = {"schemas": {"Loop": {"$ref": "#/components/schemas/Loop"}}}
    new = _document(
        {"200": _response({"$ref": "#/components/schemas/Loop"})},
        components=components,
    )

    with pytest.raises(ReferenceResolutionError):
        compare_responses(_document({"200": _response(_schema({}))}), new)


def test_removed_operation_does_not_emit_response_changes() -> None:
    """Aggregate analysis avoids redundant facts below a removed operation."""

    old = _document({"200": _response(_schema({"id": _property()}, required=["id"]))})
    new: OpenApiDocument = {"openapi": "3.1.0", "paths": {}}

    changes = compare_api_documents(old, new)

    assert [change.category for change in changes] == [ChangeCategory.OPERATION_REMOVED]
