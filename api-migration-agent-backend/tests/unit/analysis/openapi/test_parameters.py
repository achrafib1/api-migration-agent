"""Tests for deterministic OpenAPI parameter compatibility rules."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest
from pydantic import JsonValue

from api_migration_agent.analysis.openapi.comparator import compare_api_documents
from api_migration_agent.analysis.openapi.loader import OpenApiDocument
from api_migration_agent.analysis.openapi.rules.parameters import compare_parameters
from api_migration_agent.core.exceptions import OpenApiDocumentError
from api_migration_agent.domain.enums import ChangeCategory, ChangeSeverity


def _parameter(
    name: str,
    location: str = "query",
    *,
    required: bool = False,
    schema_type: str | None = "string",
) -> dict[str, JsonValue]:
    """Build a synthetic inline Parameter Object."""

    parameter: dict[str, JsonValue] = {
        "name": name,
        "in": location,
        "required": required,
    }
    if schema_type is not None:
        parameter["schema"] = {"type": schema_type}
    return parameter


def _document(
    parameters: Sequence[JsonValue],
    *,
    path_parameters: Sequence[JsonValue] | None = None,
    components: Mapping[str, JsonValue] | None = None,
    additional_paths: Mapping[str, JsonValue] | None = None,
) -> OpenApiDocument:
    """Build one operation with optional inherited and reusable parameters."""

    path_item: dict[str, JsonValue] = {"get": {"parameters": list(parameters)}}
    if path_parameters is not None:
        path_item["parameters"] = list(path_parameters)
    paths: dict[str, JsonValue] = {"/customers": path_item}
    if additional_paths is not None:
        paths.update(additional_paths)
    document: OpenApiDocument = {
        "openapi": "3.1.0",
        "paths": paths,
    }
    if components is not None:
        document["components"] = dict(components)
    return document


def test_detects_added_required_parameter_as_breaking() -> None:
    """A newly required input creates a high-severity compatibility fact."""

    changes = compare_parameters(
        _document([]),
        _document([_parameter("currency", required=True)]),
    )

    assert len(changes) == 1
    change = changes[0]
    assert change.category is ChangeCategory.PARAMETER_ADDED_REQUIRED
    assert change.severity is ChangeSeverity.HIGH
    assert change.breaking is True
    assert change.new_value == {
        "name": "currency",
        "in": "query",
        "required": True,
        "type": "string",
    }
    assert change.evidence[0].new_document_pointer == ("#/paths/~1customers/get/parameters/0")


def test_records_added_optional_parameter_as_non_breaking() -> None:
    """An optional addition is useful context but not a breaking change."""

    changes = compare_parameters(_document([]), _document([_parameter("locale")]))

    assert len(changes) == 1
    assert changes[0].category is ChangeCategory.PARAMETER_ADDED_OPTIONAL
    assert changes[0].severity is ChangeSeverity.INFO
    assert changes[0].breaking is False


def test_detects_optional_parameter_becoming_required() -> None:
    """A matched optional parameter becoming required is breaking."""

    changes = compare_parameters(
        _document([_parameter("currency")]),
        _document([_parameter("currency", required=True)]),
    )

    assert [change.category for change in changes] == [ChangeCategory.PARAMETER_BECAME_REQUIRED]


def test_required_parameter_becoming_optional_is_not_reported_as_breaking() -> None:
    """Relaxing a requirement does not create a compatibility warning."""

    changes = compare_parameters(
        _document([_parameter("currency", required=True)]),
        _document([_parameter("currency")]),
    )

    assert changes == ()


def test_detects_removed_parameter() -> None:
    """Removing an accepted input is reported for existing client compatibility."""

    changes = compare_parameters(_document([_parameter("expand")]), _document([]))

    assert len(changes) == 1
    assert changes[0].category is ChangeCategory.PARAMETER_REMOVED
    assert changes[0].breaking is True


def test_detects_explicit_parameter_type_change() -> None:
    """Different explicit schema types produce one deterministic change."""

    changes = compare_parameters(
        _document([_parameter("limit", schema_type="integer")]),
        _document([_parameter("limit", schema_type="string")]),
    )

    assert [change.category for change in changes] == [ChangeCategory.PARAMETER_TYPE_CHANGED]
    assert changes[0].old_value is not None
    assert changes[0].new_value is not None


def test_missing_schema_type_does_not_invent_type_change() -> None:
    """Incomplete type evidence is ignored instead of guessed."""

    changes = compare_parameters(
        _document([_parameter("limit", schema_type=None)]),
        _document([_parameter("limit", schema_type="integer")]),
    )

    assert changes == ()


def test_detects_unambiguous_parameter_location_change() -> None:
    """One old and one new location for a name are safely matched as a move."""

    changes = compare_parameters(
        _document([_parameter("trace_id", "query")]),
        _document([_parameter("trace_id", "header")]),
    )

    assert [change.category for change in changes] == [ChangeCategory.PARAMETER_LOCATION_CHANGED]
    assert changes[0].old_value is not None
    assert changes[0].new_value is not None


def test_ambiguous_locations_are_not_guessed_as_moves() -> None:
    """Multiple candidates remain explicit removals and additions."""

    changes = compare_parameters(
        _document([_parameter("id", "query"), _parameter("id", "header")]),
        _document([_parameter("id", "path"), _parameter("id", "cookie")]),
    )

    assert [change.category for change in changes].count(ChangeCategory.PARAMETER_REMOVED) == 2
    assert [change.category for change in changes].count(
        ChangeCategory.PARAMETER_ADDED_OPTIONAL
    ) == 2
    assert all(
        change.category is not ChangeCategory.PARAMETER_LOCATION_CHANGED for change in changes
    )


def test_operation_parameter_overrides_path_parameter() -> None:
    """Operation-level identity overrides inherited path-level configuration."""

    old = _document([], path_parameters=[_parameter("locale")])
    new = _document(
        [_parameter("locale", required=True)],
        path_parameters=[_parameter("locale")],
    )

    changes = compare_parameters(old, new)

    assert [change.category for change in changes] == [ChangeCategory.PARAMETER_BECAME_REQUIRED]
    assert changes[0].evidence[0].old_document_pointer == "#/paths/~1customers/parameters/0"
    assert changes[0].evidence[0].new_document_pointer == ("#/paths/~1customers/get/parameters/0")


def test_resolves_local_reusable_parameter() -> None:
    """Local component parameters participate in deterministic comparison."""

    components: dict[str, JsonValue] = {
        "parameters": {
            "Currency": _parameter("currency", required=True),
        }
    }
    reference: dict[str, JsonValue] = {"$ref": "#/components/parameters/Currency"}

    changes = compare_parameters(_document([]), _document([reference], components=components))

    assert [change.category for change in changes] == [ChangeCategory.PARAMETER_ADDED_REQUIRED]


def test_missing_parameter_identity_is_not_evidence() -> None:
    """A malformed object without name or location cannot establish a change."""

    assert compare_parameters(_document([]), _document([{"required": True}])) == ()


def test_duplicate_parameter_identity_is_rejected() -> None:
    """Duplicate identities stop analysis because matching would be ambiguous."""

    duplicate = [_parameter("locale"), _parameter("locale")]

    with pytest.raises(OpenApiDocumentError):
        compare_parameters(_document([]), _document(duplicate))


def test_only_compares_parameters_on_shared_operations() -> None:
    """Removed operations do not create redundant per-parameter changes."""

    old = _document([_parameter("currency", required=True)])
    new: OpenApiDocument = {"openapi": "3.1.0", "paths": {}}

    changes = compare_api_documents(old, new)

    assert [change.category for change in changes] == [ChangeCategory.OPERATION_REMOVED]


def test_full_comparator_includes_operation_and_parameter_rules() -> None:
    """The public comparator aggregates every implemented rule family."""

    old = _document([])
    new = _document(
        [_parameter("currency", required=True)],
        additional_paths={"/health": {"get": {}}},
    )

    changes = compare_api_documents(old, new)

    assert [change.category for change in changes] == [
        ChangeCategory.OPERATION_ADDED,
        ChangeCategory.PARAMETER_ADDED_REQUIRED,
    ]
