"""Build a confined manifest for the trusted client repository."""

from __future__ import annotations

from pathlib import Path

from api_migration_agent.agents.migration_agent.dependencies import MigrationGraphDependencies
from api_migration_agent.agents.migration_agent.nodes._logging import log_node_event
from api_migration_agent.agents.migration_agent.state import MigrationAgentState
from api_migration_agent.analysis.repository.manifest import build_repository_manifest


def index_repository(
    state: MigrationAgentState,
    dependencies: MigrationGraphDependencies,
) -> dict[str, object]:
    """Create the deterministic, hash-bearing repository manifest."""

    manifest = build_repository_manifest(Path(state["repository_path"]))
    log_node_event(dependencies, state, "repository_index_completed", "index_repository")
    return {"repository_manifest": manifest}
