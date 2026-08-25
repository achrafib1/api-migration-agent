"""Security-constrained logging shared by migration graph nodes."""

from __future__ import annotations

import logging

from api_migration_agent.agents.migration_agent.dependencies import MigrationGraphDependencies
from api_migration_agent.agents.migration_agent.state import MigrationAgentState
from api_migration_agent.core.logging import log_event


def log_node_event(
    dependencies: MigrationGraphDependencies,
    state: MigrationAgentState,
    event: str,
    stage: str,
    **fields: str | int,
) -> None:
    """Emit allowlisted metadata without serializing state or analyzed content."""

    log_event(
        dependencies.logger,
        logging.INFO,
        event,
        run_id=state["run_id"],
        stage=stage,
        **fields,
    )
