"""Tests for deterministic operation compatibility rules."""

from __future__ import annotations

from pydantic import JsonValue

from api_migration_agent.analysis.openapi.comparator import compare_operations
from api_migration_agent.analysis.openapi.loader import OpenApiDocument
from api_migration_agent.analysis.openapi.rules.operations import match_operations
from api_migration_agent.domain.enums import ChangeCategory, ChangeSeverity, HttpMethod


def _document(paths: dict[str, JsonValue]) -> OpenApiDocument:
    """Build a minimal synthetic OpenAPI document for rule tests."""

    return {"openapi": "3.1.0", "paths": paths}


def test_detects_removed_operation_as_breaking() -> None:
    """An operation absent from the revision produces high-severity evidence."""

    changes = compare_operations(
        _document({"/customers/create": {"post": {"responses": {}}}}),
        _document({}),
    )

    assert len(changes) == 1
    change = changes[0]
    assert change.category is ChangeCategory.OPERATION_REMOVED
    assert change.severity is ChangeSeverity.HIGH
    assert change.breaking is True
    assert change.path == "/customers/create"
    assert change.method is HttpMethod.POST
    assert change.evidence[0].old_document_pointer == "#/paths/~1customers~1create/post"
    assert change.evidence[0].new_document_pointer is None


def test_detects_added_operation_as_non_breaking() -> None:
    """A new operation is recorded as useful non-breaking context."""

    changes = compare_operations(_document({}), _document({"/customers": {"post": {}}}))

    assert len(changes) == 1
    change = changes[0]
    assert change.category is ChangeCategory.OPERATION_ADDED
    assert change.severity is ChangeSeverity.INFO
    assert change.breaking is False
    assert change.evidence[0].new_document_pointer == "#/paths/~1customers/post"


def test_unchanged_operation_produces_no_change() -> None:
    """Equivalent operation sets do not create false positives."""

    document = _document({"/customers": {"get": {"responses": {}}}})

    assert compare_operations(document, document) == ()


def test_ignores_path_item_metadata_and_malformed_operations() -> None:
    """Parameters, extensions, and scalar method values are not operations."""

    old = _document(
        {
            "/customers": {
                "parameters": [],
                "summary": "Customers",
                "x-untrusted": "data",
                "post": "not-an-operation-object",
            }
        }
    )

    assert compare_operations(old, _document({})) == ()


def test_change_identifiers_and_order_are_stable() -> None:
    """Repeated comparisons produce identical sorted facts and identifiers."""

    old = _document({"/z": {"get": {}}, "/a": {"post": {}}})
    new = _document({"/b": {"get": {}}})

    first = compare_operations(old, new)
    second = compare_operations(old, new)

    assert first == second
    assert [(item.path, item.method) for item in first] == [
        ("/a", HttpMethod.POST),
        ("/z", HttpMethod.GET),
        ("/b", HttpMethod.GET),
    ]
    assert all(item.id.startswith("CHANGE-") for item in first)


def test_pairs_moved_operation_by_unique_operation_id() -> None:
    """A unique shared operationId safely links nested contracts across paths."""

    old = _document({"/customers/create": {"post": {"operationId": "createCustomer"}}})
    new = _document({"/customers": {"post": {"operationId": "createCustomer"}}})

    pairs = match_operations(old, new)

    assert len(pairs) == 1
    assert pairs[0].old_path == "/customers/create"
    assert pairs[0].new_path == "/customers"


def test_does_not_pair_ambiguous_duplicate_operation_ids() -> None:
    """Duplicate operationIds provide insufficient evidence for moved matching."""

    old = _document(
        {
            "/first": {"post": {"operationId": "duplicate"}},
            "/second": {"post": {"operationId": "duplicate"}},
        }
    )
    new = _document({"/replacement": {"post": {"operationId": "duplicate"}}})

    assert match_operations(old, new) == ()
