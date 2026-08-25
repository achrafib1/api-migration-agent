"""Bounded structured input supplied to the patch-generation LLM."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from api_migration_agent.domain.enums import MigrationOperationType


class PatchActionInput(BaseModel):
    """Represent one explicitly approved migration action."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    api_change_id: str
    operation_type: MigrationOperationType
    target_file: str
    title: str
    description: str
    evidence_ids: tuple[str, ...]
    approved_answer: str | None = None


class PatchEvidenceInput(BaseModel):
    """Expose one bounded deterministic source location for patch planning."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    api_change_id: str
    target_file: str
    line_number: int = Field(ge=1)
    matched_text: str = Field(min_length=1, max_length=200)
    source_excerpt: str = Field(min_length=1, max_length=300)


class PatchGenerationRequest(BaseModel):
    """Complete approved and bounded input for structured patch generation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    actions: tuple[PatchActionInput, ...] = Field(min_length=1)
    evidence: tuple[PatchEvidenceInput, ...] = Field(min_length=1)
