"""Tests for production planning-graph composition."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from api_migration_agent.application.planning import build_production_planning_graph
from api_migration_agent.core.config import Settings
from api_migration_agent.domain.migration_plan import MigrationPlanProposal
from api_migration_agent.domain.patch import PatchProposal


class _StructuredRunnable:
    """Network-free runnable used only to verify composition."""

    def invoke(self, input: object) -> object:
        """Return a minimal structured proposal if the graph reaches planning."""

        return MigrationPlanProposal(actions=(), summary="No verified actions required.")


class _StructuredModel:
    """Record the output schema requested by the real planning adapter."""

    def __init__(self) -> None:
        self.schemas: list[type[Any]] = []

    def with_structured_output(self, schema: type[Any]) -> _StructuredRunnable:
        """Bind and record the Pydantic output schema without provider access."""

        self.schemas.append(schema)
        return _StructuredRunnable()


def test_composition_binds_real_adapter_to_migration_plan_schema() -> None:
    """Application wiring must connect LangChain output to the planning graph."""

    model = _StructuredModel()
    logger = logging.Logger("planning-composition-test")
    logger.addHandler(logging.NullHandler())

    graph = build_production_planning_graph(
        checkpointer=InMemorySaver(),
        settings=Settings(planning_api_key=None),
        logger=logger,
        model=model,
    )

    assert graph.name == "api-migration-planning"
    assert model.schemas == [MigrationPlanProposal, PatchProposal]
