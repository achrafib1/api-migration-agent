"""Security tests for server-approved migration target registration."""

from __future__ import annotations

from pathlib import Path

import pytest

from api_migration_agent.core.exceptions import MigrationTargetConfigurationError
from api_migration_agent.domain.migration_target import MigrationTargetSummary
from api_migration_agent.infrastructure.target_registry import StaticMigrationTargetRegistry
from api_migration_agent.services.target_registry import TrustedMigrationTarget


def _target(root: Path, *, target_id: str = "sample") -> TrustedMigrationTarget:
    """Create a complete synthetic target rooted under ``tmp_path``."""

    specs = root / "specs"
    repository = root / "repository"
    specs.mkdir(parents=True)
    repository.mkdir()
    old_spec = specs / "old.json"
    new_spec = specs / "new.json"
    old_spec.write_text("{}", encoding="utf-8")
    new_spec.write_text("{}", encoding="utf-8")
    return TrustedMigrationTarget(
        summary=MigrationTargetSummary(
            id=target_id,
            name="Synthetic target",
            description="Synthetic trusted target used only by tests.",
        ),
        root=root,
        old_spec_path=old_spec,
        new_spec_path=new_spec,
        repository_path=repository,
    )


def test_registry_exposes_only_content_safe_metadata(tmp_path: Path) -> None:
    """Public discovery must never contain a filesystem path."""

    registry = StaticMigrationTargetRegistry((_target(tmp_path / "target"),))

    summaries = registry.list_summaries()

    assert [summary.id for summary in summaries] == ["sample"]
    assert "path" not in summaries[0].model_dump()
    assert registry.get("unknown") is None


def test_registry_rejects_component_outside_declared_root(tmp_path: Path) -> None:
    """A registered target cannot borrow a specification from another root."""

    target = _target(tmp_path / "target")
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(MigrationTargetConfigurationError):
        StaticMigrationTargetRegistry((target.model_copy(update={"new_spec_path": outside}),))


def test_registry_rejects_duplicate_stable_identifiers(tmp_path: Path) -> None:
    """An identifier must resolve to exactly one target."""

    first = _target(tmp_path / "first")
    second = _target(tmp_path / "second")

    with pytest.raises(MigrationTargetConfigurationError):
        StaticMigrationTargetRegistry((first, second))
