"""End-to-end deterministic analysis test for the trusted AtlasPay contracts."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from api_migration_agent.analysis.openapi.comparator import compare_api_documents
from api_migration_agent.analysis.openapi.loader import load_openapi_document
from api_migration_agent.domain.api_change import ApiChange
from api_migration_agent.domain.enums import ChangeCategory

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ATLASPAY_ROOT = _PROJECT_ROOT / "examples" / "atlaspay"
_CHANGE_LIST_ADAPTER = TypeAdapter(list[ApiChange])


def test_atlaspay_contracts_match_locked_expected_changes() -> None:
    """Compare AtlasPay v1 and v2 and require the complete reviewed result.

    This test intentionally compares full domain models rather than category
    counts. Evidence pointers, old/new values, descriptions, ordering, and stable
    identifiers are part of the deterministic analyzer contract.
    """

    old_document = load_openapi_document(_ATLASPAY_ROOT / "specs" / "atlaspay-v1.json")
    new_document = load_openapi_document(_ATLASPAY_ROOT / "specs" / "atlaspay-v2.json")
    expected_data = json.loads(
        (_ATLASPAY_ROOT / "expected" / "api-changes.json").read_text(encoding="utf-8")
    )
    expected_changes = tuple(_CHANGE_LIST_ADAPTER.validate_python(expected_data))

    actual_changes = compare_api_documents(old_document, new_document)

    assert actual_changes == expected_changes
    assert len(actual_changes) == 9
    assert sum(change.breaking for change in actual_changes) == 8
    assert ChangeCategory.REQUEST_PROPERTY_RENAMED in {change.category for change in actual_changes}


def test_atlaspay_moved_operation_uses_cross_path_evidence() -> None:
    """Nested changes retain both old and new pointers across the endpoint move."""

    old_document = load_openapi_document(_ATLASPAY_ROOT / "specs" / "atlaspay-v1.json")
    new_document = load_openapi_document(_ATLASPAY_ROOT / "specs" / "atlaspay-v2.json")

    rename = next(
        change
        for change in compare_api_documents(old_document, new_document)
        if change.category is ChangeCategory.REQUEST_PROPERTY_RENAMED
    )

    evidence = rename.evidence[0]
    assert evidence.old_document_pointer == "#/paths/~1customers~1create/post/requestBody"
    assert evidence.new_document_pointer == "#/paths/~1customers/post/requestBody"
