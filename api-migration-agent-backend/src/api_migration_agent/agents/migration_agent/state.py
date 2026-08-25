"""Typed state models for the evidence-backed migration graph."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field

from api_migration_agent.domain.api_change import ApiChange
from api_migration_agent.domain.applied_patch import AppliedPatch
from api_migration_agent.domain.enums import WorkflowStatus
from api_migration_agent.domain.investigation import FailureInvestigation
from api_migration_agent.domain.migration_plan import MigrationPlanProposal, ReviewedMigrationPlan
from api_migration_agent.domain.patch import PatchProposal
from api_migration_agent.domain.report import MigrationReport
from api_migration_agent.domain.repository_impact import RepositoryFile, RepositoryImpact
from api_migration_agent.domain.validation import ValidationResult
from api_migration_agent.domain.workspace import MigrationWorkspace


class PlanningWorkflowRequest(BaseModel):
    """Validated trusted paths used to initialize one planning run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1, max_length=100)
    old_spec_path: str = Field(min_length=1)
    new_spec_path: str = Field(min_length=1)
    repository_path: str = Field(min_length=1)


class MigrationAgentState(TypedDict, total=False):
    """State carrying deterministic evidence and reviewed planning output."""

    run_id: str
    status: WorkflowStatus
    old_spec_path: str
    new_spec_path: str
    repository_path: str
    api_changes: tuple[ApiChange, ...]
    repository_manifest: tuple[RepositoryFile, ...]
    repository_impacts: tuple[RepositoryImpact, ...]
    migration_plan: MigrationPlanProposal
    reviewed_plan: ReviewedMigrationPlan
    workspace: MigrationWorkspace
    patch_proposal: PatchProposal
    applied_patch: AppliedPatch
    validation_result: ValidationResult
    failure_investigation: FailureInvestigation
    final_report: MigrationReport


def initial_state(request: PlanningWorkflowRequest) -> MigrationAgentState:
    """Convert validated workflow input into minimal, secret-free graph state."""

    return MigrationAgentState(
        run_id=request.run_id,
        status=WorkflowStatus.PENDING,
        old_spec_path=request.old_spec_path,
        new_spec_path=request.new_spec_path,
        repository_path=request.repository_path,
    )
