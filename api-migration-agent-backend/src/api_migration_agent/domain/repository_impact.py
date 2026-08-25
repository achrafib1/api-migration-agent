"""Immutable models for trusted repository manifests and impact evidence."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from api_migration_agent.domain.enums import ImpactConfidence, SourceContext


class RepositoryFile(BaseModel):
    """Describe one approved Python file without exposing its contents."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    relative_path: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RepositoryImpact(BaseModel):
    """Link one API change to an exact, deterministic source occurrence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^IMPACT-[0-9A-F]{12}$")
    api_change_id: str = Field(pattern=r"^CHANGE-[0-9A-F]{12}$")
    file_path: str = Field(min_length=1)
    symbol_name: str | None = None
    line_number: int = Field(ge=1)
    source_excerpt: str = Field(min_length=1, max_length=300)
    matched_text: str = Field(min_length=1, max_length=200)
    context: SourceContext
    confidence: ImpactConfidence
    reason: str = Field(min_length=1, max_length=500)
