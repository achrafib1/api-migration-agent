"""Create the isolated workspace after explicit plan approval."""

from __future__ import annotations

from pathlib import Path

from api_migration_agent.agents.migration_agent.dependencies import MigrationGraphDependencies
from api_migration_agent.agents.migration_agent.nodes._logging import log_node_event
from api_migration_agent.agents.migration_agent.state import MigrationAgentState
from api_migration_agent.domain.enums import WorkflowStatus


def create_workspace(
    state: MigrationAgentState,
    dependencies: MigrationGraphDependencies,
) -> dict[str, object]:
    """Copy verified repository files into a temporary confined workspace."""

    workspace = dependencies.workspace_creator.create(
        source_root=Path(state["repository_path"]),
        manifest=state["repository_manifest"],
        reviewed_plan=state["reviewed_plan"],
    )
    log_node_event(dependencies, state, "workspace_created", "create_workspace")
    return {"workspace": workspace, "status": WorkflowStatus.WORKSPACE_READY}
