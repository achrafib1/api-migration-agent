"""Replaceable boundary for server-approved migration targets."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from api_migration_agent.domain.migration_target import MigrationTargetSummary


class TrustedMigrationTarget(BaseModel):
    """Hold private, pre-approved paths for one trusted local project.

    Instances are created only by server-side infrastructure. They must never be
    accepted from an API request or serialized into a response or agent state.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True, extra="forbid")

    summary: MigrationTargetSummary
    root: Path
    old_spec_path: Path
    new_spec_path: Path
    repository_path: Path


class MigrationTargetRegistry(Protocol):
    """Resolve stable public identifiers to private trusted target paths."""

    def list_summaries(self) -> tuple[MigrationTargetSummary, ...]:
        """Return content-safe target metadata in deterministic display order."""

        ...

    def get(self, target_id: str) -> TrustedMigrationTarget | None:
        """Return one approved target without accepting a filesystem path."""

        ...
