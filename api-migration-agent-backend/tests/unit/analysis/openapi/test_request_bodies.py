"""Tests for deterministic JSON request-body compatibility rules."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest
from pydantic import JsonValue

from api_migration_agent.analysis.openapi.comparator import compare_api_documents
from api_migration_agent.analysis.openapi.loader import OpenApiDocument
from api_migration_agent.analysis.openapi.rules.request_bodies import compare_request_bodies
from api_migration_agent.core.exceptions import ReferenceResolutionError, UnsupportedReferenceError
from api_migration_agent.domain.enums import ChangeCategory


def _schema(
    properties: Mapping[str, JsonValue],
    *,
    required: list[str] | None = None,
) -> dict[str, JsonValue]:
    """Build a synthetic object schema."""

    schema: dict[str, JsonValue] = {"type": "object", "properties": dict(properties)}
    if required is not None:
        schema["required"] = cast(JsonValue, required)
    return schema


def _property(schema_type: str | None = "string", **extra: JsonValue) -> dict[str, JsonValue]:
    """Build a synthetic property schema with optional extra constraints."""

    schema: dict[str, JsonValue] = dict(extra)
    if schema_type is not None:
        schema["type"] = schema_type
    return schema


def _document(
    schema: Mapping[str, JsonValue] | None,
    *,
    body_required: bool = False,
    request_body_reference: str | None = None,
    components: Mapping[str, JsonValue] | None = None,
) -> OpenApiDocument:
    """Build one POST operation with an optional JSON request body."""

    operation: dict[str, JsonValue] = {}
    if request_body_reference is not None:
        operation["requestBody"] = {"$ref": request_body_reference}
    elif schema is not None:
        operation["requestBody"] = {
            "required": body_required,
            "content": {"application/json": {"schema": dict(schema)}},
        }
    document: OpenApiDocument = {
        "openapi": "3.1.0",
        "paths": {"/customers": {"post": operation}},
    }
    if components is not None:
        document["components"] = dict(components)
    return document


def test_detects_newly_required_request_body() -> None:
    """Adding a required body to an existing operation is breaking."""

    changes = compare_request_bodies(
        _document(None),
        _document(_schema({}), body_required=True),
    )

    assert [change.category for change in changes] == [ChangeCategory.REQUEST_BODY_BECAME_REQUIRED]
    assert changes[0].breaking is True
    assert changes[0].evidence[0].new_document_pointer == ("#/paths/~1customers/post/requestBody")


def test_detects_optional_request_body_becoming_required() -> None:
    """Changing an existing body from optional to required is breaking."""

    schema = _schema({"name": _property()})
    changes = compare_request_bodies(
        _document(schema),
        _document(schema, body_required=True),
    )

    assert [change.category for change in changes] == [ChangeCategory.REQUEST_BODY_BECAME_REQUIRED]


def test_optional_body_addition_is_not_reported() -> None:
    """A newly optional body does not force existing clients to change."""

    assert compare_request_bodies(_document(None), _document(_schema({}))) == ()


def test_detects_required_property_addition() -> None:
    """A new required property produces structured old and new evidence."""

    changes = compare_request_bodies(
        _document(_schema({"name": _property()}, required=["name"])),
        _document(
            _schema(
                {"name": _property(), "currency": _property()},
                required=["name", "currency"],
            )
        ),
    )

    assert [change.category for change in changes] == [
        ChangeCategory.REQUEST_PROPERTY_ADDED_REQUIRED
    ]
    assert changes[0].new_value == {"name": "currency", "required": True, "type": "string"}


def test_optional_property_addition_is_non_breaking_and_omitted() -> None:
    """Adding an optional property does not create a breaking fact."""

    changes = compare_request_bodies(
        _document(_schema({"name": _property()})),
        _document(_schema({"name": _property(), "note": _property()})),
    )

    assert changes == ()


def test_detects_existing_property_becoming_required() -> None:
    """Required-list changes are detected even when the property already exists."""

    properties = {"currency": _property()}
    changes = compare_request_bodies(
        _document(_schema(properties)),
        _document(_schema(properties, required=["currency"])),
    )

    assert [change.category for change in changes] == [
        ChangeCategory.REQUEST_PROPERTY_ADDED_REQUIRED
    ]


def test_detects_removed_property() -> None:
    """A baseline request property absent from the revision is breaking."""

    changes = compare_request_bodies(
        _document(_schema({"legacy_name": _property(schema_type="integer")})),
        _document(_schema({})),
    )

    assert [change.category for change in changes] == [ChangeCategory.REQUEST_PROPERTY_REMOVED]


def test_detects_explicit_property_type_change() -> None:
    """Different explicit property types produce deterministic evidence."""

    changes = compare_request_bodies(
        _document(_schema({"count": _property("integer")})),
        _document(_schema({"count": _property("string")})),
    )

    assert [change.category for change in changes] == [ChangeCategory.REQUEST_PROPERTY_TYPE_CHANGED]


def test_missing_property_type_does_not_invent_change() -> None:
    """Incomplete property schemas do not support a type-change conclusion."""

    changes = compare_request_bodies(
        _document(_schema({"count": _property(None)})),
        _document(_schema({"count": _property("integer")})),
    )

    assert changes == ()


def test_detects_one_to_one_structurally_identical_rename_candidate() -> None:
    """Exactly one structurally identical replacement is a bounded candidate."""

    changes = compare_request_bodies(
        _document(_schema({"customer_name": _property(minLength=1)}, required=["customer_name"])),
        _document(_schema({"full_name": _property(minLength=1)}, required=["full_name"])),
    )

    assert [change.category for change in changes] == [ChangeCategory.REQUEST_PROPERTY_RENAMED]
    assert "candidate" in changes[0].description


def test_different_schema_is_not_guessed_as_rename() -> None:
    """Non-identical schemas remain removal and required addition facts."""

    changes = compare_request_bodies(
        _document(_schema({"old": _property("string")}, required=["old"])),
        _document(_schema({"new": _property("integer")}, required=["new"])),
    )

    assert [change.category for change in changes] == [
        ChangeCategory.REQUEST_PROPERTY_REMOVED,
        ChangeCategory.REQUEST_PROPERTY_ADDED_REQUIRED,
    ]


def test_multiple_candidates_are_not_guessed_as_renames() -> None:
    """Several additions prevent a one-to-one rename conclusion."""

    changes = compare_request_bodies(
        _document(_schema({"old": _property()}, required=["old"])),
        _document(
            _schema(
                {"first": _property(), "second": _property()},
                required=["first", "second"],
            )
        ),
    )

    assert all(change.category is not ChangeCategory.REQUEST_PROPERTY_RENAMED for change in changes)
    assert [change.category for change in changes].count(
        ChangeCategory.REQUEST_PROPERTY_ADDED_REQUIRED
    ) == 2


def test_resolves_local_request_body_and_schema_references() -> None:
    """Approved local component chains participate in request comparison."""

    components: dict[str, JsonValue] = {
        "requestBodies": {
            "CreateCustomer": {
                "required": True,
                "content": {
                    "application/json": {"schema": {"$ref": "#/components/schemas/Customer"}}
                },
            }
        },
        "schemas": {
            "Customer": _schema({"currency": _property()}, required=["currency"]),
        },
    }
    changes = compare_request_bodies(
        _document(None),
        _document(
            None,
            request_body_reference="#/components/requestBodies/CreateCustomer",
            components=components,
        ),
    )

    assert [change.category for change in changes] == [ChangeCategory.REQUEST_BODY_BECAME_REQUIRED]


def test_rejects_cyclic_schema_reference() -> None:
    """Reference cycles stop analysis instead of exhausting recursion."""

    components: dict[str, JsonValue] = {"schemas": {"Loop": {"$ref": "#/components/schemas/Loop"}}}
    new = _document({"$ref": "#/components/schemas/Loop"}, components=components)

    with pytest.raises(ReferenceResolutionError):
        compare_request_bodies(_document(_schema({})), new)


def test_rejects_external_schema_reference() -> None:
    """Request analysis never follows a remote schema URL."""

    new = _document({"$ref": "https://example.invalid/customer.json"})

    with pytest.raises(UnsupportedReferenceError):
        compare_request_bodies(_document(_schema({})), new)


def test_removed_operation_does_not_emit_request_property_changes() -> None:
    """The aggregate comparator avoids redundant facts for removed operations."""

    old = _document(_schema({"name": _property()}, required=["name"]))
    new: OpenApiDocument = {"openapi": "3.1.0", "paths": {}}

    changes = compare_api_documents(old, new)

    assert [change.category for change in changes] == [ChangeCategory.OPERATION_REMOVED]
