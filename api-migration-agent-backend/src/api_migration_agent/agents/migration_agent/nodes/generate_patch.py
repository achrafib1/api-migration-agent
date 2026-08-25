"""Generate and validate exact patch operations without applying them."""

from __future__ import annotations

from api_migration_agent.agents.migration_agent.dependencies import MigrationGraphDependencies
from api_migration_agent.agents.migration_agent.nodes._logging import log_node_event
from api_migration_agent.agents.migration_agent.state import MigrationAgentState
from api_migration_agent.domain.enums import WorkflowStatus


def generate_patch(
    state: MigrationAgentState,
    dependencies: MigrationGraphDependencies,
) -> dict[str, object]:
    """Call Gemini through the injected generator and validate every operation."""

    proposal = dependencies.patch_generator.generate(
        reviewed_plan=state["reviewed_plan"],
        repository_impacts=state["repository_impacts"],
        workspace=state["workspace"],
    )
    log_node_event(dependencies, state, "patch_proposal_created", "generate_patch")
    return {"patch_proposal": proposal, "status": WorkflowStatus.PATCH_PROPOSED}
