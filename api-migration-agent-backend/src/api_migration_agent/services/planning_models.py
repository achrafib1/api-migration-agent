"""Sanitized planning-boundary models supplied to an LLM client."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from api_migration_agent.domain.enums import ChangeCategory, HttpMethod


class PlanningChangeEvidence(BaseModel):
    """Expose verified API facts without entire OpenAPI documents."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    category: ChangeCategory
    path: str | None
    method: HttpMethod | None
    old_value: JsonValue
    new_value: JsonValue
    description: str


class PlanningRepositoryEvidence(BaseModel):
    """Expose repository coordinates without source excerpts or file content."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    api_change_id: str
    file_path: str
    symbol_name: str | None
    line_number: int = Field(ge=1)
    matched_text: str
    reason: str


class PlanningRequest(BaseModel):
    """Complete sanitized input for structured migration planning."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    changes: tuple[PlanningChangeEvidence, ...]
    repository_evidence: tuple[PlanningRepositoryEvidence, ...]
