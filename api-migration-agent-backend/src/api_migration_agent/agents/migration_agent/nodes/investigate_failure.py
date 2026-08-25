"""Decide whether sanitized validation evidence supports one repair attempt."""

from __future__ import annotations

from api_migration_agent.agents.migration_agent.dependencies import MigrationGraphDependencies
from api_migration_agent.agents.migration_agent.nodes._logging import log_node_event
from api_migration_agent.agents.migration_agent.state import MigrationAgentState
from api_migration_agent.domain.investigation import FailureInvestigation


def investigate_failure(
    state: MigrationAgentState,
    dependencies: MigrationGraphDependencies,
) -> dict[str, object]:
    """Stop automated repair when no content-safe failure evidence exists."""

    investigation = FailureInvestigation(
        can_repair=False,
        reason_code="INSUFFICIENT_SANITIZED_FAILURE_EVIDENCE",
        retry_count=0,
    )
    log_node_event(
        dependencies,
        state,
        "validation_failure_investigated",
        "investigate_failure",
        retry_count=0,
    )
    return {"failure_investigation": investigation}
