"""Finalize a content-safe report and clean any temporary workspace."""

from __future__ import annotations

from api_migration_agent.agents.migration_agent.dependencies import MigrationGraphDependencies
from api_migration_agent.agents.migration_agent.nodes._logging import log_node_event
from api_migration_agent.agents.migration_agent.state import MigrationAgentState
from api_migration_agent.domain.enums import (
    ActionStatus,
    PlanDecision,
    ReportOutcome,
    ValidationStatus,
    WorkflowStatus,
)
from api_migration_agent.services.reporting import ReportInput


def finalize_report(
    state: MigrationAgentState,
    dependencies: MigrationGraphDependencies,
) -> dict[str, object]:
    """Create the terminal report and remove an owned temporary workspace."""

    reviewed = state.get("reviewed_plan")
    validation = state.get("validation_result")
    investigation = state.get("failure_investigation")
    workspace = state.get("workspace")
    modified = state.get("applied_patch")
    if reviewed is not None and reviewed.decision.decision is PlanDecision.REJECT:
        outcome = ReportOutcome.REJECTED
    elif validation is not None and validation.status is ValidationStatus.PASSED:
        outcome = ReportOutcome.SUCCEEDED
    else:
        outcome = ReportOutcome.FAILED

    workspace_cleaned = False
    if workspace is not None:
        dependencies.workspace_creator.cleanup(workspace)
        workspace_cleaned = True
    uncertainties = (
        (investigation.reason_code,)
        if investigation is not None and not investigation.can_repair
        else ()
    )
    report = dependencies.report_renderer.render(
        ReportInput(
            run_id=state["run_id"],
            outcome=outcome,
            change_ids=tuple(change.id for change in state.get("api_changes", ())),
            evidence_ids=tuple(impact.id for impact in state.get("repository_impacts", ())),
            proposed_action_ids=(
                tuple(action.id for action in state["migration_plan"].actions)
                if "migration_plan" in state
                else ()
            ),
            approved_action_ids=(
                tuple(
                    action.id
                    for action in reviewed.actions
                    if action.status is ActionStatus.APPROVED
                )
                if reviewed is not None
                else ()
            ),
            modified_files=(
                tuple(item.relative_path for item in modified.modified_files)
                if modified is not None
                else ()
            ),
            validation_status=validation.status if validation is not None else None,
            human_decision=(reviewed.decision.decision.value if reviewed is not None else None),
            repair_attempt_count=investigation.retry_count if investigation is not None else 0,
            uncertainty_codes=uncertainties,
            workspace_cleaned=workspace_cleaned,
        )
    )
    log_node_event(
        dependencies,
        state,
        "migration_report_finalized",
        "finalize_report",
        status=outcome.value,
    )
    return {"final_report": report, "status": WorkflowStatus.FINALIZED}
