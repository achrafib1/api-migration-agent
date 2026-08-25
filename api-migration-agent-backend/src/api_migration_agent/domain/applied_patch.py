"""Immutable results from deterministic workspace patch application."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModifiedFile(BaseModel):
    """Record non-content metadata for one successfully modified file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    relative_path: str = Field(min_length=1)
    original_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    modified_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    operation_count: int = Field(ge=1)


class AppliedPatch(BaseModel):
    """Describe the exact files changed inside an isolated workspace."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    modified_files: tuple[ModifiedFile, ...] = Field(min_length=1)
