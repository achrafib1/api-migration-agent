"""Run authoritative deterministic OpenAPI comparison."""

from __future__ import annotations

from pathlib import Path

from api_migration_agent.agents.migration_agent.dependencies import MigrationGraphDependencies
from api_migration_agent.agents.migration_agent.nodes._logging import log_node_event
from api_migration_agent.agents.migration_agent.state import MigrationAgentState
from api_migration_agent.analysis.openapi.comparator import compare_api_documents
from api_migration_agent.analysis.openapi.loader import load_openapi_document


def analyze_specs(
    state: MigrationAgentState,
    dependencies: MigrationGraphDependencies,
) -> dict[str, object]:
    """Compare validated specifications and return verified change facts."""

    changes = compare_api_documents(
        load_openapi_document(Path(state["old_spec_path"])),
        load_openapi_document(Path(state["new_spec_path"])),
    )
    log_node_event(
        dependencies,
        state,
        "spec_analysis_completed",
        "analyze_specs",
        change_count=len(changes),
    )
    return {"api_changes": changes}
