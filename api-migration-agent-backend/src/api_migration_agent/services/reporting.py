"""Deterministic final report construction from verified workflow metadata."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from api_migration_agent.domain.enums import ReportOutcome, ValidationStatus
from api_migration_agent.domain.report import MigrationReport


class ReportInput(BaseModel):
    """Internal content-free metadata supplied to the report renderer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    outcome: ReportOutcome
    change_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    proposed_action_ids: tuple[str, ...]
    approved_action_ids: tuple[str, ...]
    modified_files: tuple[str, ...]
    validation_status: ValidationStatus | None
    human_decision: str | None
    repair_attempt_count: int
    uncertainty_codes: tuple[str, ...]
    workspace_cleaned: bool


class ReportRenderer:
    """Render a structured report using verified metadata only."""

    def render(self, report_input: ReportInput) -> MigrationReport:
        """Return an immutable report without free-form model content."""

        return MigrationReport(
            run_id=report_input.run_id,
            outcome=report_input.outcome,
            confirmed_change_ids=tuple(sorted(set(report_input.change_ids))),
            repository_evidence_ids=tuple(sorted(set(report_input.evidence_ids))),
            proposed_action_ids=tuple(sorted(set(report_input.proposed_action_ids))),
            approved_action_ids=tuple(sorted(set(report_input.approved_action_ids))),
            modified_files=tuple(sorted(set(report_input.modified_files))),
            validation_status=report_input.validation_status,
            human_decision=report_input.human_decision,
            repair_attempt_count=report_input.repair_attempt_count,
            remaining_uncertainty_codes=tuple(sorted(set(report_input.uncertainty_codes))),
            workspace_cleaned=report_input.workspace_cleaned,
        )
