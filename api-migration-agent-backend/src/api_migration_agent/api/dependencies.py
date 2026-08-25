"""FastAPI dependency providers for application services."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request

from api_migration_agent.services.planning_workflow import PlanningWorkflowService


def get_planning_workflow_service(request: Request) -> PlanningWorkflowService:
    """Return the lifespan-owned planning service without constructing dependencies."""

    return cast(PlanningWorkflowService, request.app.state.planning_workflow_service)


PlanningServiceDependency = Annotated[
    PlanningWorkflowService,
    Depends(get_planning_workflow_service),
]
