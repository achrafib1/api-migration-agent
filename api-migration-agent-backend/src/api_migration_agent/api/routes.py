"""Thin FastAPI routes for starting and reviewing migration plans."""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from api_migration_agent.api.dependencies import PlanningServiceDependency
from api_migration_agent.domain.migration_plan import HumanPlanDecision
from api_migration_agent.domain.migration_run import MigrationRunRecord
from api_migration_agent.domain.migration_target import MigrationTargetCatalog

router = APIRouter(prefix="/api/v1/migrations", tags=["migrations"])


class StartMigrationRequest(BaseModel):
    """Select one server-approved target by stable identifier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,49}$")


@router.get("/targets", response_model=MigrationTargetCatalog)
def list_migration_targets(service: PlanningServiceDependency) -> MigrationTargetCatalog:
    """List content-safe targets selectable by the current user interface."""

    return service.list_targets()


@router.post("", response_model=MigrationRunRecord, status_code=status.HTTP_201_CREATED)
def start_migration(
    payload: StartMigrationRequest,
    service: PlanningServiceDependency,
) -> MigrationRunRecord:
    """Start one approved target analysis and pause for plan approval."""

    return service.start(payload.target_id)


@router.post("/{run_id}/review", response_model=MigrationRunRecord)
def review_migration(
    run_id: str,
    decision: HumanPlanDecision,
    service: PlanningServiceDependency,
) -> MigrationRunRecord:
    """Resume a paused planning run with an explicit human decision."""

    return service.review(run_id, decision)


@router.get("/{run_id}", response_model=MigrationRunRecord)
def get_migration(run_id: str, service: PlanningServiceDependency) -> MigrationRunRecord:
    """Return a content-safe process-local migration snapshot."""

    return service.get(run_id)
