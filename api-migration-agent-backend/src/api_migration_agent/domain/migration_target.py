"""Public metadata for server-approved migration targets."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MigrationTargetSummary(BaseModel):
    """Describe a selectable target without exposing server filesystem paths."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,49}$")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=300)


class MigrationTargetCatalog(BaseModel):
    """Return the complete process-local catalog of approved targets."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    targets: tuple[MigrationTargetSummary, ...]
