"""Structured final migration report with explicit evidence categories."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from api_migration_agent.domain.enums import ReportOutcome, ValidationStatus


class MigrationReport(BaseModel):
    """Summarize a run without source content, patches, or model responses."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1, max_length=100)
    outcome: ReportOutcome
    confirmed_change_ids: tuple[str, ...]
    repository_evidence_ids: tuple[str, ...]
    proposed_action_ids: tuple[str, ...]
    approved_action_ids: tuple[str, ...]
    modified_files: tuple[str, ...]
    validation_status: ValidationStatus | None
    human_decision: str | None
    repair_attempt_count: int = Field(ge=0, le=1)
    remaining_uncertainty_codes: tuple[str, ...]
    workspace_cleaned: bool
