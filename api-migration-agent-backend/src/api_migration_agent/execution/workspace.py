"""Protocols for creating isolated trusted migration workspaces."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from api_migration_agent.domain.migration_plan import ReviewedMigrationPlan
from api_migration_agent.domain.repository_impact import RepositoryFile
from api_migration_agent.domain.workspace import MigrationWorkspace


class WorkspaceCreator(Protocol):
    """Create a confined temporary copy for approved migration actions."""

    def create(
        self,
        *,
        source_root: Path,
        manifest: tuple[RepositoryFile, ...],
        reviewed_plan: ReviewedMigrationPlan,
    ) -> MigrationWorkspace:
        """Copy approved trusted inputs into an isolated workspace."""

        ...

    def cleanup(self, workspace: MigrationWorkspace) -> None:
        """Remove a workspace previously created by this exact instance."""

        ...
