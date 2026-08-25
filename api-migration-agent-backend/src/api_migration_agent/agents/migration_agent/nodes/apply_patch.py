"""Apply validated exact operations inside the isolated workspace."""

from __future__ import annotations

from api_migration_agent.agents.migration_agent.dependencies import MigrationGraphDependencies
from api_migration_agent.agents.migration_agent.nodes._logging import log_node_event
from api_migration_agent.agents.migration_agent.state import MigrationAgentState
from api_migration_agent.domain.enums import WorkflowStatus


def apply_patch(
    state: MigrationAgentState,
    dependencies: MigrationGraphDependencies,
) -> dict[str, object]:
    """Apply the accepted proposal and record only non-content file metadata."""

    applied = dependencies.patch_applier.apply(
        proposal=state["patch_proposal"],
        workspace=state["workspace"],
        manifest=state["repository_manifest"],
    )
    log_node_event(
        dependencies,
        state,
        "patch_applied",
        "apply_patch",
        modified_file_count=len(applied.modified_files),
    )
    return {"applied_patch": applied, "status": WorkflowStatus.PATCH_APPLIED}
