"""Protocol for deterministic application of validated exact replacements."""

from __future__ import annotations

from typing import Protocol

from api_migration_agent.domain.applied_patch import AppliedPatch
from api_migration_agent.domain.patch import PatchProposal
from api_migration_agent.domain.repository_impact import RepositoryFile
from api_migration_agent.domain.workspace import MigrationWorkspace


class PatchApplier(Protocol):
    """Apply validated operations only inside an approved workspace."""

    def apply(
        self,
        *,
        proposal: PatchProposal,
        workspace: MigrationWorkspace,
        manifest: tuple[RepositoryFile, ...],
    ) -> AppliedPatch:
        """Apply all operations or raise a sanitized domain exception."""

        ...
