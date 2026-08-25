"""Tests for exact text and AST-backed repository impact mapping."""

from __future__ import annotations

from pathlib import Path

import pytest

from api_migration_agent.analysis.repository.impact_mapper import map_repository_impacts
from api_migration_agent.analysis.repository.manifest import build_repository_manifest
from api_migration_agent.core.exceptions import RepositorySourceError
from api_migration_agent.domain.api_change import ApiChange, ChangeEvidence
from api_migration_agent.domain.enums import (
    ChangeCategory,
    ChangeSeverity,
    HttpMethod,
    ImpactConfidence,
    SourceContext,
)


def _change() -> ApiChange:
    """Build one deterministic endpoint change for repository tests."""

    return ApiChange(
        id="CHANGE-AAAAAAAAAAAA",
        category=ChangeCategory.OPERATION_REMOVED,
        severity=ChangeSeverity.HIGH,
        breaking=True,
        path="/customers/create",
        method=HttpMethod.POST,
        old_value={"path": "/customers/create"},
        description="Synthetic endpoint removal.",
        evidence=(ChangeEvidence(summary="Synthetic deterministic evidence."),),
    )


def test_maps_executable_match_to_qualified_symbol(tmp_path: Path) -> None:
    """An exact executable string receives high confidence and its method name."""

    (tmp_path / "src" / "package").mkdir(parents=True)
    (tmp_path / "src" / "package" / "client.py").write_text(
        "class Client:\n    def create(self) -> str:\n        return '/customers/create'\n",
        encoding="utf-8",
    )

    impacts = map_repository_impacts(tmp_path, build_repository_manifest(tmp_path), (_change(),))

    assert len(impacts) == 1
    assert impacts[0].symbol_name == "Client.create"
    assert impacts[0].context is SourceContext.EXECUTABLE
    assert impacts[0].confidence is ImpactConfidence.HIGH


def test_comments_and_docstrings_receive_low_confidence(tmp_path: Path) -> None:
    """Non-executable occurrences remain evidence but cannot outrank code."""

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "notes.py").write_text(
        '"""Mentions /customers/create for historical context."""\n'
        "# /customers/create must not be treated as executable\n",
        encoding="utf-8",
    )

    impacts = map_repository_impacts(tmp_path, build_repository_manifest(tmp_path), (_change(),))

    assert {impact.context for impact in impacts} == {
        SourceContext.COMMENT,
        SourceContext.DOCSTRING,
    }
    assert all(impact.confidence is ImpactConfidence.LOW for impact in impacts)


def test_unrelated_source_produces_no_impact(tmp_path: Path) -> None:
    """Files without exact structured evidence are not marked as affected."""

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "unrelated.py").write_text("VALUE = 'unrelated'\n", encoding="utf-8")

    assert map_repository_impacts(tmp_path, build_repository_manifest(tmp_path), (_change(),)) == ()


def test_lowercase_field_does_not_match_inside_larger_identifier(tmp_path: Path) -> None:
    """A field such as status must not match a method like raise_for_status."""

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "client.py").write_text(
        "def validate(response):\n    response.raise_for_status()\n",
        encoding="utf-8",
    )
    change = _change().model_copy(update={"old_value": {"name": "status"}})

    assert (
        map_repository_impacts(
            tmp_path,
            build_repository_manifest(tmp_path),
            (change,),
        )
        == ()
    )


def test_rejects_source_changed_after_manifest(tmp_path: Path) -> None:
    """The manifest digest is a precondition for later source analysis."""

    (tmp_path / "src").mkdir()
    source = tmp_path / "src" / "client.py"
    source.write_text("PATH = '/customers/create'\n", encoding="utf-8")
    manifest = build_repository_manifest(tmp_path)
    source.write_text("PATH = '/changed'\n", encoding="utf-8")

    with pytest.raises(RepositorySourceError):
        map_repository_impacts(tmp_path, manifest, (_change(),))


def test_rejects_invalid_python_without_executing_it(tmp_path: Path) -> None:
    """Syntax-invalid source fails safely through the parser boundary."""

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "invalid.py").write_text("def broken(:\n", encoding="utf-8")

    with pytest.raises(RepositorySourceError):
        map_repository_impacts(tmp_path, build_repository_manifest(tmp_path), (_change(),))
