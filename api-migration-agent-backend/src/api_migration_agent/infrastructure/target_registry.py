"""Confining in-memory registry for trusted local migration targets."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from api_migration_agent.core.exceptions import MigrationTargetConfigurationError
from api_migration_agent.domain.migration_target import MigrationTargetSummary
from api_migration_agent.services.target_registry import TrustedMigrationTarget


class StaticMigrationTargetRegistry:
    """Store a fixed set of startup-validated, server-approved targets."""

    def __init__(self, targets: Iterable[TrustedMigrationTarget]) -> None:
        """Validate and index targets before the application begins serving."""

        indexed: dict[str, TrustedMigrationTarget] = {}
        for target in targets:
            validated = _validate_target(target)
            if validated.summary.id in indexed:
                raise MigrationTargetConfigurationError
            indexed[validated.summary.id] = validated
        if not indexed:
            raise MigrationTargetConfigurationError
        self._targets = indexed

    def list_summaries(self) -> tuple[MigrationTargetSummary, ...]:
        """Return summaries sorted by stable target identifier."""

        return tuple(self._targets[key].summary for key in sorted(self._targets))

    def get(self, target_id: str) -> TrustedMigrationTarget | None:
        """Resolve an exact identifier; user-controlled paths are never accepted."""

        return self._targets.get(target_id)


def _validate_target(target: TrustedMigrationTarget) -> TrustedMigrationTarget:
    """Resolve one target and enforce root confinement without reading its contents."""

    try:
        root = target.root.resolve(strict=True)
        old_spec = _confined_file(target.old_spec_path, root)
        new_spec = _confined_file(target.new_spec_path, root)
        repository = _confined_directory(target.repository_path, root)
    except (OSError, RuntimeError):
        raise MigrationTargetConfigurationError from None
    return target.model_copy(
        update={
            "root": root,
            "old_spec_path": old_spec,
            "new_spec_path": new_spec,
            "repository_path": repository,
        }
    )


def _confined_file(path: Path, root: Path) -> Path:
    """Resolve a regular non-symlink file contained by ``root``."""

    if path.is_symlink():
        raise MigrationTargetConfigurationError
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or not resolved.is_relative_to(root):
        raise MigrationTargetConfigurationError
    return resolved


def _confined_directory(path: Path, root: Path) -> Path:
    """Resolve a non-symlink directory contained by ``root``."""

    if path.is_symlink():
        raise MigrationTargetConfigurationError
    resolved = path.resolve(strict=True)
    if not resolved.is_dir() or not resolved.is_relative_to(root):
        raise MigrationTargetConfigurationError
    return resolved
