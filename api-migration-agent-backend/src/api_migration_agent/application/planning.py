"""Production composition root for Gemini-backed migration planning."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from api_migration_agent.agents.migration_agent.dependencies import MigrationGraphDependencies
from api_migration_agent.agents.migration_agent.graph import build_planning_graph
from api_migration_agent.core.config import Settings, get_settings
from api_migration_agent.core.logging import configure_logging
from api_migration_agent.infrastructure.llm.client import LangChainPlanningClient
from api_migration_agent.infrastructure.llm.factory import (
    StructuredChatModel,
    create_planning_model,
)
from api_migration_agent.infrastructure.llm.patch_client import LangChainPatchClient
from api_migration_agent.infrastructure.patch_applier import ExactPatchApplier
from api_migration_agent.infrastructure.validation import PytestValidationRunner
from api_migration_agent.infrastructure.workspace import TemporaryWorkspaceCreator
from api_migration_agent.services.migration_planner import MigrationPlanner
from api_migration_agent.services.patch_generator import PatchGenerator
from api_migration_agent.services.patch_proposal import PatchProposalValidator
from api_migration_agent.services.reporting import ReportRenderer


def build_production_planning_graph(
    *,
    checkpointer: Any,
    settings: Settings | None = None,
    logger: logging.Logger | None = None,
    model: StructuredChatModel | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Build the runnable graph with the real LangChain/LiteLLM client.

    Normal application wiring omits ``model`` and constructs ``ChatLiteLLM``
    from centralized settings. Tests inject a deterministic structured model,
    ensuring no provider or network access occurs.

    Args:
        checkpointer: Process-local LangGraph persistence boundary for the MVP.
        settings: Optional immutable configuration override.
        logger: Optional allowlisted local logger override.
        model: Optional structured chat model used for isolated tests.

    Returns:
        A compiled planning graph whose ``create_plan`` node invokes the
        LangChain structured-output adapter.

    Raises:
        ModelConfigurationError: If normal production construction is requested
            without a configured provider credential.
    """

    resolved_settings = settings or get_settings()
    resolved_model = model or create_planning_model(resolved_settings)
    planning_client = LangChainPlanningClient(resolved_model)
    planner = MigrationPlanner(planning_client)
    patch_generator = PatchGenerator(
        client=LangChainPatchClient(resolved_model),
        validator=PatchProposalValidator(),
    )
    dependencies = MigrationGraphDependencies(
        planner=planner,
        logger=logger or configure_logging(),
        workspace_creator=TemporaryWorkspaceCreator(),
        patch_generator=patch_generator,
        patch_applier=ExactPatchApplier(),
        validation_runner=PytestValidationRunner(),
        report_renderer=ReportRenderer(),
    )
    return build_planning_graph(
        dependencies=dependencies,
        checkpointer=checkpointer,
    )
