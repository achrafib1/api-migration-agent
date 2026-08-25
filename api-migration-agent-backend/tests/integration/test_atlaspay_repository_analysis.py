"""Integration coverage for deterministic AtlasPay repository impact mapping."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from api_migration_agent.analysis.openapi.comparator import compare_api_documents
from api_migration_agent.analysis.openapi.loader import load_openapi_document
from api_migration_agent.analysis.repository.impact_mapper import map_repository_impacts
from api_migration_agent.analysis.repository.manifest import build_repository_manifest
from api_migration_agent.domain.enums import ImpactConfidence, SourceContext

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ATLASPAY_ROOT = _PROJECT_ROOT / "examples" / "atlaspay"
_CLIENT_ROOT = _ATLASPAY_ROOT / "client-repository"


def test_atlaspay_repository_impacts_match_reviewed_fixture() -> None:
    """Require exact affected files, terms, lines, and unresolved changes."""

    changes = compare_api_documents(
        load_openapi_document(_ATLASPAY_ROOT / "specs" / "atlaspay-v1.json"),
        load_openapi_document(_ATLASPAY_ROOT / "specs" / "atlaspay-v2.json"),
    )
    manifest = build_repository_manifest(_CLIENT_ROOT)
    impacts = map_repository_impacts(_CLIENT_ROOT, manifest, changes)
    expected = _load_expected_impacts()

    assert len(impacts) == expected["impact_count"]
    assert sorted({impact.file_path for impact in impacts}) == expected["affected_files"]
    assert _group_impacts(impacts) == expected["matches_by_change"]
    assert (
        sorted({change.id for change in changes} - {impact.api_change_id for impact in impacts})
        == (expected["unresolved_change_ids"])
    )
    assert all(impact.context is SourceContext.EXECUTABLE for impact in impacts)
    assert all(impact.confidence is ImpactConfidence.HIGH for impact in impacts)


def test_atlaspay_manifest_excludes_unapproved_and_unrelated_files() -> None:
    """Only approved Python source and test files enter repository analysis."""

    manifest = build_repository_manifest(_CLIENT_ROOT)

    assert [entry.relative_path for entry in manifest] == [
        "src/atlaspay_client/__init__.py",
        "src/atlaspay_client/auth.py",
        "src/atlaspay_client/client.py",
        "src/atlaspay_client/models.py",
        "src/atlaspay_client/service.py",
        "tests/__init__.py",
        "tests/fixtures.py",
        "tests/test_client.py",
    ]


def _load_expected_impacts() -> dict[str, Any]:
    """Load the reviewed compact impact fixture as untrusted JSON data."""

    value = json.loads(
        (_ATLASPAY_ROOT / "expected" / "repository-impacts.json").read_text(encoding="utf-8")
    )
    assert isinstance(value, dict)
    return value


def _group_impacts(impacts: tuple[Any, ...]) -> dict[str, Any]:
    """Project full impact models into the compact reviewed fixture shape."""

    grouped: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    matched_text: dict[str, str] = {}
    for impact in impacts:
        grouped[impact.api_change_id][impact.file_path].append(impact.line_number)
        matched_text[impact.api_change_id] = impact.matched_text
    return {
        change_id: {
            "matched_text": matched_text[change_id],
            "locations": {
                file_path: sorted(lines) for file_path, lines in sorted(locations.items())
            },
        }
        for change_id, locations in sorted(grouped.items())
    }
