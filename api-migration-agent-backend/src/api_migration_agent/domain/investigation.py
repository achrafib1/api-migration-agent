"""Sanitized failure-investigation results for bounded repair routing."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FailureInvestigation(BaseModel):
    """Record whether deterministic evidence supports an automated repair."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    can_repair: bool
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    retry_count: int = Field(ge=0, le=1)
