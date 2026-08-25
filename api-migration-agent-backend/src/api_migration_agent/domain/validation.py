"""Sanitized deterministic validation result models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from api_migration_agent.domain.enums import ValidationStatus


class ValidationResult(BaseModel):
    """Record non-content metadata from the fixed pytest invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ValidationStatus
    duration_ms: int = Field(ge=0)
    exit_code: int | None = None
    timed_out: bool
