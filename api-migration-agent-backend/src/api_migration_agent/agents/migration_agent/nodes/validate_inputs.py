"""Validate trusted workflow inputs before analysis begins."""

from __future__ import annotations

from pathlib import Path

from api_migration_agent.agents.migration_agent.dependencies import MigrationGraphDependencies
from api_migration_agent.agents.migration_agent.nodes._logging import log_node_event
from api_migration_agent.agents.migration_agent.state import MigrationAgentState
from api_migration_agent.core.exceptions import OpenApiInputError
from api_migration_agent.domain.enums import WorkflowStatus


def validate_inputs(
    state: MigrationAgentState,
    dependencies: MigrationGraphDependencies,
) -> dict[str, object]:
    """Confirm all required trusted paths exist before reading their contents.

    Raises:
        OpenApiInputError: If a specification or repository path is absent.
    """

    required_paths = (
        Path(state["old_spec_path"]),
        Path(state["new_spec_path"]),
        Path(state["repository_path"]),
    )
    if not all(path.exists() for path in required_paths):
        raise OpenApiInputError
    log_node_event(dependencies, state, "workflow_inputs_validated", "validate_inputs")
    return {"status": WorkflowStatus.ANALYZING}
