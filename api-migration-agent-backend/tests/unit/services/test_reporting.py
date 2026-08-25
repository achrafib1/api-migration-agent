"""Tests for deterministic content-safe final report rendering."""

from __future__ import annotations

from api_migration_agent.domain.enums import ReportOutcome, ValidationStatus
from api_migration_agent.services.reporting import ReportInput, ReportRenderer


def test_report_deduplicates_and_sorts_verified_identifiers() -> None:
    """Reports remain stable and contain metadata rather than generated prose."""

    report = ReportRenderer().render(
        ReportInput(
            run_id="report-run",
            outcome=ReportOutcome.FAILED,
            change_ids=("CHANGE-B", "CHANGE-A", "CHANGE-A"),
            evidence_ids=("IMPACT-B", "IMPACT-A"),
            proposed_action_ids=("ACTION-A",),
            approved_action_ids=("ACTION-A",),
            modified_files=("src/client.py",),
            validation_status=ValidationStatus.FAILED,
            human_decision="approve",
            repair_attempt_count=0,
            uncertainty_codes=("INSUFFICIENT_SANITIZED_FAILURE_EVIDENCE",),
            workspace_cleaned=True,
        )
    )

    assert report.confirmed_change_ids == ("CHANGE-A", "CHANGE-B")
    assert report.repair_attempt_count == 0
    assert report.remaining_uncertainty_codes == ("INSUFFICIENT_SANITIZED_FAILURE_EVIDENCE",)
