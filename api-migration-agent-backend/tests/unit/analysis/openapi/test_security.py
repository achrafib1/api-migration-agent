"""Tests for deterministic OpenAPI security compatibility rules."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest
from pydantic import JsonValue

from api_migration_agent.analysis.openapi.loader import OpenApiDocument
from api_migration_agent.analysis.openapi.rules.security import compare_security
from api_migration_agent.core.exceptions import OpenApiDocumentError
from api_migration_agent.domain.enums import ChangeCategory


def _document(
    *,
    root_security: JsonValue | None = None,
    operation_security: JsonValue | None = None,
    operation_has_override: bool = False,
    schemes: Mapping[str, JsonValue] | None = None,
) -> OpenApiDocument:
    """Build one operation with independently configurable security sources."""

    operation: dict[str, JsonValue] = {"responses": {}}
    if operation_has_override:
        operation["security"] = operation_security
    document: OpenApiDocument = {
        "openapi": "3.1.0",
        "paths": {"/customers": {"post": operation}},
    }
    if root_security is not None:
        document["security"] = root_security
    if schemes is not None:
        document["components"] = {"securitySchemes": dict(schemes)}
    return document


def _requirements(*alternatives: Mapping[str, list[str]]) -> JsonValue:
    """Convert synthetic requirement alternatives to recursive JSON typing."""

    return cast(JsonValue, [dict(alternative) for alternative in alternatives])


def test_detects_security_requirement_added_to_anonymous_operation() -> None:
    """Requiring authentication where none existed is breaking."""

    changes = compare_security(
        _document(),
        _document(root_security=_requirements({"ApiKey": []})),
    )

    assert [change.category for change in changes] == [ChangeCategory.SECURITY_REQUIREMENT_ADDED]
    assert changes[0].path == "/customers"
    assert changes[0].evidence[0].old_document_pointer == "#/security"


def test_operation_security_overrides_root_security() -> None:
    """An explicit operation requirement replaces the inherited root value."""

    old = _document(
        root_security=_requirements({"ApiKey": []}),
        operation_security=cast(JsonValue, []),
        operation_has_override=True,
    )
    new = _document(root_security=_requirements({"ApiKey": []}))

    changes = compare_security(old, new)

    assert [change.category for change in changes] == [ChangeCategory.SECURITY_REQUIREMENT_ADDED]
    assert changes[0].evidence[0].old_document_pointer == ("#/paths/~1customers/post/security")
    assert changes[0].evidence[0].new_document_pointer == "#/security"


def test_explicit_anonymous_override_is_not_reported_as_tightening() -> None:
    """Changing a secured operation to `security: []` permits anonymous access."""

    old = _document(root_security=_requirements({"ApiKey": []}))
    new = _document(
        root_security=_requirements({"ApiKey": []}),
        operation_security=cast(JsonValue, []),
        operation_has_override=True,
    )

    assert compare_security(old, new) == ()


def test_empty_requirement_object_permits_anonymous_access() -> None:
    """An empty requirement alternative means anonymous access remains possible."""

    old = _document()
    new = _document(root_security=_requirements({}, {"ApiKey": []}))

    assert compare_security(old, new) == ()


def test_canonical_scope_and_alternative_order_prevents_false_positive() -> None:
    """Equivalent requirement ordering has identical canonical form."""

    old = _document(root_security=_requirements({"OAuth": ["write", "read"]}, {"ApiKey": []}))
    new = _document(root_security=_requirements({"ApiKey": []}, {"OAuth": ["read", "write"]}))

    assert compare_security(old, new) == ()


def test_detects_removed_security_scheme_without_fake_operation_coordinates() -> None:
    """Component-level removal uses nullable path and method fields."""

    scheme: dict[str, JsonValue] = {"type": "apiKey", "in": "header", "name": "X-Key"}
    changes = compare_security(
        _document(schemes={"ApiKey": scheme}),
        _document(schemes={}),
    )

    assert [change.category for change in changes] == [ChangeCategory.SECURITY_SCHEME_REMOVED]
    assert changes[0].path is None
    assert changes[0].method is None
    assert changes[0].old_value == {"name": "ApiKey", "type": "apiKey", "in": "header"}


def test_detects_security_scheme_type_change() -> None:
    """Different explicit scheme types produce a breaking component fact."""

    changes = compare_security(
        _document(schemes={"Auth": {"type": "apiKey", "in": "header"}}),
        _document(schemes={"Auth": {"type": "http", "scheme": "bearer"}}),
    )

    assert [change.category for change in changes] == [ChangeCategory.SECURITY_SCHEME_TYPE_CHANGED]


def test_detects_api_key_location_change() -> None:
    """Moving an apiKey between supported locations is breaking."""

    changes = compare_security(
        _document(schemes={"Auth": {"type": "apiKey", "in": "header"}}),
        _document(schemes={"Auth": {"type": "apiKey", "in": "query"}}),
    )

    assert [change.category for change in changes] == [
        ChangeCategory.SECURITY_API_KEY_LOCATION_CHANGED
    ]


def test_missing_scheme_type_or_location_does_not_invent_change() -> None:
    """Both sides require explicit structural evidence for scheme-field changes."""

    assert (
        compare_security(
            _document(schemes={"Auth": {}}),
            _document(schemes={"Auth": {"type": "apiKey", "in": "header"}}),
        )
        == ()
    )


def test_resolves_local_security_scheme_reference() -> None:
    """Approved local scheme references are normalized before comparison."""

    old_schemes: dict[str, JsonValue] = {
        "Base": {"type": "apiKey", "in": "header"},
        "Auth": {"$ref": "#/components/securitySchemes/Base"},
    }
    new_schemes: dict[str, JsonValue] = {
        "Base": {"type": "apiKey", "in": "header"},
        "Auth": {"type": "apiKey", "in": "query"},
    }

    changes = compare_security(
        _document(schemes=old_schemes),
        _document(schemes=new_schemes),
    )

    assert [change.category for change in changes] == [
        ChangeCategory.SECURITY_API_KEY_LOCATION_CHANGED
    ]


@pytest.mark.parametrize(
    "malformed",
    [
        cast(JsonValue, {}),
        cast(JsonValue, ["ApiKey"]),
        cast(JsonValue, [{"ApiKey": "not-a-scope-list"}]),
        cast(JsonValue, [{"ApiKey": [1]}]),
    ],
)
def test_rejects_malformed_explicit_security_evidence(malformed: JsonValue) -> None:
    """Malformed requirements stop rather than becoming anonymous access."""

    with pytest.raises(OpenApiDocumentError):
        compare_security(_document(), _document(root_security=malformed))
