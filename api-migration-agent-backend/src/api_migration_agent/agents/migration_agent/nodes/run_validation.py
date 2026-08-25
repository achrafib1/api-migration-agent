"""Run the fixed validation command inside the isolated workspace."""

from __future__ import annotations

from pathlib import Path

from api_migration_agent.agents.migration_agent.dependencies import MigrationGraphDependencies
from api_migration_agent.agents.migration_agent.nodes._logging import log_node_event
from api_migration_agent.agents.migration_agent.state import MigrationAgentState
from api_migration_agent.domain.enums import ValidationStatus, WorkflowStatus


def run_validation(
    state: MigrationAgentState,
    dependencies: MigrationGraphDependencies,
) -> dict[str, object]:
    """Execute fixed pytest validation and retain only sanitized metadata."""

    result = dependencies.validation_runner.run(Path(state["workspace"].root_path))
    status = (
        WorkflowStatus.VALIDATION_PASSED
        if result.status is ValidationStatus.PASSED
        else WorkflowStatus.VALIDATION_FAILED
    )
    log_node_event(
        dependencies,
        state,
        "validation_completed",
        "run_validation",
        status=result.status.value,
        duration_ms=result.duration_ms,
    )
    return {"validation_result": result, "status": status}
