"""Domain records for planning-run lifecycle tracking."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from api_migration_agent.domain.enums import MigrationOperationType, MigrationRisk, WorkflowStatus
from api_migration_agent.domain.migration_plan import HumanQuestion
from api_migration_agent.domain.report import MigrationReport
from api_migration_agent.domain.validation import ValidationResult


class ReviewActionSummary(BaseModel):
    """Expose one safe action summary for explicit human review."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    target_file: str
    risk: MigrationRisk
    requires_human_input: bool
    question_key: str | None


class PlanningReview(BaseModel):
    """Typed payload presented while a graph is awaiting human review."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    actions: tuple[ReviewActionSummary, ...]
    questions: tuple[HumanQuestion, ...]


class PatchOperationSummary(BaseModel):
    """Expose patch metadata without source or replacement content."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    migration_action_id: str
    api_change_id: str
    operation_type: MigrationOperationType
    target_file: str


class PatchSummary(BaseModel):
    """Safe collection of accepted patch-operation metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operations: tuple[PatchOperationSummary, ...]


class MigrationRunRecord(BaseModel):
    """Persist one content-safe process-local workflow snapshot.

    ``target_id`` is the stable public identifier selected when the run starts.
    It preserves audit context across review and finalization without exposing
    any server-side specification or repository path.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1, max_length=100)
    target_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,49}$")
    status: WorkflowStatus
    review: PlanningReview | None = None
    patch: PatchSummary | None = None
    validation: ValidationResult | None = None
    report: MigrationReport | None = None
