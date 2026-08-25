"""Application service for starting and reviewing trusted planning runs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, cast
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from api_migration_agent.agents.migration_agent.state import PlanningWorkflowRequest, initial_state
from api_migration_agent.core.exceptions import (
    HumanDecisionError,
    MigrationRunNotFoundError,
    MigrationTargetNotFoundError,
)
from api_migration_agent.domain.enums import WorkflowStatus
from api_migration_agent.domain.migration_plan import HumanPlanDecision
from api_migration_agent.domain.migration_run import (
    MigrationRunRecord,
    PatchOperationSummary,
    PatchSummary,
    PlanningReview,
)
from api_migration_agent.domain.migration_target import MigrationTargetCatalog
from api_migration_agent.services.target_registry import MigrationTargetRegistry


class PlanningGraph(Protocol):
    """Minimal compiled-graph boundary used by the application service."""

    def invoke(self, input: object, config: RunnableConfig) -> object:
        """Execute or resume one isolated LangGraph thread."""

        ...


class MigrationRunStore(Protocol):
    """Replaceable persistence boundary for process-local run metadata."""

    def save(self, record: MigrationRunRecord) -> None:
        """Insert or replace one run record."""

        ...

    def get(self, run_id: str) -> MigrationRunRecord | None:
        """Return a run record when it exists."""

        ...


class PlanningWorkflowService:
    """Coordinate approved-target planning and explicit human review."""

    def __init__(
        self,
        *,
        graph: PlanningGraph,
        store: MigrationRunStore,
        target_registry: MigrationTargetRegistry,
    ) -> None:
        """Inject the graph, run store, and private approved-target registry."""

        self._graph = graph
        self._store = store
        self._target_registry = target_registry

    def list_targets(self) -> MigrationTargetCatalog:
        """Return selectable target metadata without private filesystem paths."""

        return MigrationTargetCatalog(targets=self._target_registry.list_summaries())

    def start(self, target_id: str) -> MigrationRunRecord:
        """Start a planning run for one exact server-approved target identifier."""

        target = self._target_registry.get(target_id)
        if target is None:
            raise MigrationTargetNotFoundError

        run_id = str(uuid4())
        config: RunnableConfig = {"configurable": {"thread_id": run_id}}
        request = PlanningWorkflowRequest(
            run_id=run_id,
            old_spec_path=str(target.old_spec_path),
            new_spec_path=str(target.new_spec_path),
            repository_path=str(target.repository_path),
        )
        result = cast(Mapping[str, Any], self._graph.invoke(initial_state(request), config))
        status = cast(WorkflowStatus, result["status"])
        record = MigrationRunRecord(
            run_id=run_id,
            target_id=target.summary.id,
            status=status,
            review=_review_payload(result),
        )
        self._store.save(record)
        return record

    def review(self, run_id: str, decision: HumanPlanDecision) -> MigrationRunRecord:
        """Resume an awaiting graph thread with an explicit human decision.

        Raises:
            HumanDecisionError: If the run is unknown or is not awaiting review.
        """

        record = self._store.get(run_id)
        if record is None or record.status is not WorkflowStatus.AWAITING_REVIEW:
            raise HumanDecisionError
        config: RunnableConfig = {"configurable": {"thread_id": run_id}}
        result = cast(
            Mapping[str, Any],
            self._graph.invoke(Command(resume=decision.model_dump(mode="json")), config),
        )
        status = cast(WorkflowStatus, result["status"])
        record = MigrationRunRecord(
            run_id=run_id,
            target_id=record.target_id,
            status=status,
            patch=_patch_summary(result),
            validation=result.get("validation_result"),
            report=result.get("final_report"),
        )
        self._store.save(record)
        return record

    def get(self, run_id: str) -> MigrationRunRecord:
        """Return a safe process-local snapshot for frontend polling.

        Raises:
            MigrationRunNotFoundError: If the run does not exist or was lost
                after a backend restart.
        """

        record = self._store.get(run_id)
        if record is None:
            raise MigrationRunNotFoundError
        return record


def _review_payload(result: Mapping[str, Any]) -> PlanningReview | None:
    """Extract the structured LangGraph interrupt payload without reflection."""

    interrupts = result.get("__interrupt__")
    if not isinstance(interrupts, tuple) or len(interrupts) != 1:
        return None
    value = getattr(interrupts[0], "value", None)
    if not isinstance(value, dict):
        return None
    try:
        return PlanningReview.model_validate(value)
    except ValueError:
        raise HumanDecisionError from None


def _patch_summary(result: Mapping[str, Any]) -> PatchSummary | None:
    """Project accepted operations into content-free API metadata."""

    proposal = result.get("patch_proposal")
    if proposal is None:
        return None
    return PatchSummary(
        operations=tuple(
            PatchOperationSummary(
                id=operation.id,
                migration_action_id=operation.migration_action_id,
                api_change_id=operation.api_change_id,
                operation_type=operation.operation_type,
                target_file=operation.target_file,
            )
            for operation in proposal.operations
        )
    )
