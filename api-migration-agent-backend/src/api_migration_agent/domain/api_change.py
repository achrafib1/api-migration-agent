"""Validated value objects describing confirmed OpenAPI changes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from api_migration_agent.domain.enums import ChangeCategory, ChangeSeverity, HttpMethod


class ChangeEvidence(BaseModel):
    """Point to deterministic source locations supporting an API change."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    old_document_pointer: str | None = None
    new_document_pointer: str | None = None
    summary: str = Field(min_length=1, max_length=500)


class ApiChange(BaseModel):
    """Represent one deterministic difference between two API contracts.

    The immutable model prevents downstream agent reasoning from rewriting facts
    established by the analyzer.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^CHANGE-[0-9A-F]{12}$")
    category: ChangeCategory
    severity: ChangeSeverity
    breaking: bool
    path: str | None = Field(default=None, min_length=1)
    method: HttpMethod | None = None
    location: str = "operation"
    old_value: JsonValue = None
    new_value: JsonValue = None
    description: str = Field(min_length=1, max_length=500)
    evidence: tuple[ChangeEvidence, ...] = Field(min_length=1)
