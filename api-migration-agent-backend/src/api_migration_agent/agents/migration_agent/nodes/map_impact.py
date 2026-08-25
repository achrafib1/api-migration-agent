"""Map verified API changes to deterministic repository evidence."""

from __future__ import annotations

from pathlib import Path

from api_migration_agent.agents.migration_agent.dependencies import MigrationGraphDependencies
from api_migration_agent.agents.migration_agent.nodes._logging import log_node_event
from api_migration_agent.agents.migration_agent.state import MigrationAgentState
from api_migration_agent.analysis.repository.impact_mapper import map_repository_impacts


def map_impact(
    state: MigrationAgentState,
    dependencies: MigrationGraphDependencies,
) -> dict[str, object]:
    """Return exact source coordinates associated with known contract facts."""

    impacts = map_repository_impacts(
        Path(state["repository_path"]),
        state["repository_manifest"],
        state["api_changes"],
    )
    log_node_event(
        dependencies,
        state,
        "repository_impact_completed",
        "map_impact",
        affected_file_count=len({impact.file_path for impact in impacts}),
    )
    return {"repository_impacts": impacts}
