"""Canonical stage names and linear planning-edge registration."""

from __future__ import annotations

from typing import Final

from langgraph.graph import END, START, StateGraph

from api_migration_agent.agents.migration_agent.state import MigrationAgentState
from api_migration_agent.domain.enums import WorkflowStatus

VALIDATE_INPUTS: Final = "validate_inputs"
ANALYZE_SPECS: Final = "analyze_specs"
INDEX_REPOSITORY: Final = "index_repository"
MAP_IMPACT: Final = "map_impact"
CREATE_PLAN: Final = "create_plan"
REVIEW_PLAN: Final = "review_plan"
CREATE_WORKSPACE: Final = "create_workspace"
GENERATE_PATCH: Final = "generate_patch"
APPLY_PATCH: Final = "apply_patch"
RUN_VALIDATION: Final = "run_validation"
INVESTIGATE_FAILURE: Final = "investigate_failure"
FINALIZE_REPORT: Final = "finalize_report"


def route_after_review(state: MigrationAgentState) -> str:
    """Continue only after approval; rejected plans terminate without copying."""

    return "create_workspace" if state["status"] is WorkflowStatus.APPROVED else "finalize_report"


def route_after_validation(state: MigrationAgentState) -> str:
    """Investigate failures; successful validation proceeds directly to reporting."""

    return (
        "finalize_report"
        if state["status"] is WorkflowStatus.VALIDATION_PASSED
        else "investigate_failure"
    )


def add_planning_edges(graph: StateGraph[MigrationAgentState]) -> None:
    """Connect the planning stages in their required deterministic order."""

    graph.add_edge(START, VALIDATE_INPUTS)
    graph.add_edge(VALIDATE_INPUTS, ANALYZE_SPECS)
    graph.add_edge(ANALYZE_SPECS, INDEX_REPOSITORY)
    graph.add_edge(INDEX_REPOSITORY, MAP_IMPACT)
    graph.add_edge(MAP_IMPACT, CREATE_PLAN)
    graph.add_edge(CREATE_PLAN, REVIEW_PLAN)
    graph.add_conditional_edges(
        REVIEW_PLAN,
        route_after_review,
        {"create_workspace": CREATE_WORKSPACE, "finalize_report": FINALIZE_REPORT},
    )
    graph.add_edge(CREATE_WORKSPACE, GENERATE_PATCH)
    graph.add_edge(GENERATE_PATCH, APPLY_PATCH)
    graph.add_edge(APPLY_PATCH, RUN_VALIDATION)
    graph.add_conditional_edges(
        RUN_VALIDATION,
        route_after_validation,
        {"finalize_report": FINALIZE_REPORT, "investigate_failure": INVESTIGATE_FAILURE},
    )
    graph.add_edge(INVESTIGATE_FAILURE, FINALIZE_REPORT)
    graph.add_edge(FINALIZE_REPORT, END)
