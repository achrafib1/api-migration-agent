"""Create a schema-validated plan from sanitized deterministic evidence."""

from __future__ import annotations

from api_migration_agent.agents.migration_agent.dependencies import MigrationGraphDependencies
from api_migration_agent.agents.migration_agent.nodes._logging import log_node_event
from api_migration_agent.agents.migration_agent.state import MigrationAgentState
from api_migration_agent.domain.enums import WorkflowStatus


def create_plan(
    state: MigrationAgentState,
    dependencies: MigrationGraphDependencies,
) -> dict[str, object]:
    """Request a structured proposal and validate it through the planner service."""

    plan = dependencies.planner.create_plan(
        state["api_changes"],
        state["repository_impacts"],
    )
    log_node_event(dependencies, state, "migration_plan_created", "create_plan")
    return {"migration_plan": plan, "status": WorkflowStatus.AWAITING_REVIEW}
