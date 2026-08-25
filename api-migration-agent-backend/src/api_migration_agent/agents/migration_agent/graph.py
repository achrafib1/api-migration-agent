"""Composition root for the complete MVP migration LangGraph workflow."""

from __future__ import annotations

from functools import partial
from typing import Any

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from api_migration_agent.agents.migration_agent.dependencies import MigrationGraphDependencies
from api_migration_agent.agents.migration_agent.edges import (
    ANALYZE_SPECS,
    APPLY_PATCH,
    CREATE_PLAN,
    CREATE_WORKSPACE,
    FINALIZE_REPORT,
    GENERATE_PATCH,
    INDEX_REPOSITORY,
    INVESTIGATE_FAILURE,
    MAP_IMPACT,
    REVIEW_PLAN,
    RUN_VALIDATION,
    VALIDATE_INPUTS,
    add_planning_edges,
)
from api_migration_agent.agents.migration_agent.nodes import (
    analyze_specs,
    apply_patch,
    create_plan,
    create_workspace,
    finalize_report,
    generate_patch,
    index_repository,
    investigate_failure,
    map_impact,
    review_plan,
    run_validation,
    validate_inputs,
)
from api_migration_agent.agents.migration_agent.state import MigrationAgentState


def build_planning_graph(
    *, dependencies: MigrationGraphDependencies, checkpointer: Any
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Build the deterministic planning graph with injected collaborators."""

    graph = StateGraph(MigrationAgentState)
    graph.add_node(VALIDATE_INPUTS, partial(validate_inputs, dependencies=dependencies))
    graph.add_node(ANALYZE_SPECS, partial(analyze_specs, dependencies=dependencies))
    graph.add_node(INDEX_REPOSITORY, partial(index_repository, dependencies=dependencies))
    graph.add_node(MAP_IMPACT, partial(map_impact, dependencies=dependencies))
    graph.add_node(CREATE_PLAN, partial(create_plan, dependencies=dependencies))
    graph.add_node(REVIEW_PLAN, partial(review_plan, dependencies=dependencies))
    graph.add_node(CREATE_WORKSPACE, partial(create_workspace, dependencies=dependencies))
    graph.add_node(GENERATE_PATCH, partial(generate_patch, dependencies=dependencies))
    graph.add_node(APPLY_PATCH, partial(apply_patch, dependencies=dependencies))
    graph.add_node(RUN_VALIDATION, partial(run_validation, dependencies=dependencies))
    graph.add_node(
        INVESTIGATE_FAILURE,
        partial(investigate_failure, dependencies=dependencies),
    )
    graph.add_node(FINALIZE_REPORT, partial(finalize_report, dependencies=dependencies))
    add_planning_edges(graph)
    return graph.compile(checkpointer=checkpointer, name="api-migration-planning")
