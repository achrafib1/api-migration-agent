"""Immutable metadata for an isolated migration workspace."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MigrationWorkspace(BaseModel):
    """Describe a temporary trusted copy and its approved modification scope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    root_path: str = Field(min_length=1)
    approved_files: tuple[str, ...] = Field(min_length=1)
