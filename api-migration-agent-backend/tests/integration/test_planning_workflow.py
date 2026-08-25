"""Integration test for AtlasPay planning and the LangGraph human interrupt."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from api_migration_agent.agents.migration_agent.dependencies import MigrationGraphDependencies
from api_migration_agent.agents.migration_agent.graph import build_planning_graph
from api_migration_agent.agents.migration_agent.state import PlanningWorkflowRequest, initial_state
from api_migration_agent.api.main import create_app
from api_migration_agent.domain.enums import (
    ChangeCategory,
    MigrationOperationType,
    MigrationRisk,
    ValidationStatus,
    WorkflowStatus,
)
from api_migration_agent.domain.migration_plan import (
    MigrationAction,
    MigrationPlanProposal,
)
from api_migration_agent.domain.migration_target import MigrationTargetSummary
from api_migration_agent.domain.patch import PatchOperation, PatchProposal
from api_migration_agent.domain.validation import ValidationResult
from api_migration_agent.infrastructure.patch_applier import ExactPatchApplier
from api_migration_agent.infrastructure.run_store import MemoryMigrationRunStore
from api_migration_agent.infrastructure.target_registry import StaticMigrationTargetRegistry
from api_migration_agent.infrastructure.workspace import TemporaryWorkspaceCreator
from api_migration_agent.services.migration_planner import MigrationPlanner
from api_migration_agent.services.patch_generator import PatchGenerator
from api_migration_agent.services.patch_models import PatchGenerationRequest
from api_migration_agent.services.patch_proposal import PatchProposalValidator
from api_migration_agent.services.planning_models import PlanningRequest
from api_migration_agent.services.planning_workflow import PlanningWorkflowService
from api_migration_agent.services.reporting import ReportRenderer
from api_migration_agent.services.target_registry import TrustedMigrationTarget

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ATLASPAY_ROOT = _PROJECT_ROOT / "examples" / "atlaspay"


class _AtlasPayPlanningClient:
    """Build a fixed structured plan from verified AtlasPay evidence only."""

    def create_migration_plan(self, request: PlanningRequest) -> MigrationPlanProposal:
        """Return endpoint and currency actions without external provider access."""

        endpoint_change = next(
            change
            for change in request.changes
            if change.category is ChangeCategory.OPERATION_REMOVED
        )
        endpoint_evidence = next(
            evidence
            for evidence in request.repository_evidence
            if evidence.api_change_id == endpoint_change.id
            and evidence.file_path == "src/atlaspay_client/client.py"
        )
        return MigrationPlanProposal(
            actions=(
                MigrationAction(
                    id="ACTION-AAAAAAAAAAAA",
                    api_change_id=endpoint_change.id,
                    title="Replace the customer endpoint",
                    description="Update the verified endpoint occurrence in the HTTP client.",
                    target_file=endpoint_evidence.file_path,
                    operation_type=MigrationOperationType.REPLACE_ENDPOINT,
                    risk=MigrationRisk.LOW,
                    evidence_ids=(endpoint_evidence.id,),
                ),
            ),
            summary="Migrate the evidence-backed AtlasPay endpoint occurrence.",
        )


class _AtlasPayPatchClient:
    """Return one exact endpoint replacement from approved bounded evidence."""

    def create_patch_proposal(self, request: PatchGenerationRequest) -> PatchProposal:
        """Build a deterministic proposal without provider or network access."""

        action = request.actions[0]
        evidence = request.evidence[0]
        return PatchProposal(
            operations=(
                PatchOperation(
                    id="PATCH-DDDDDDDDDDDD",
                    migration_action_id=action.id,
                    api_change_id=action.api_change_id,
                    operation_type=action.operation_type,
                    target_file=action.target_file,
                    expected_original_text="/customers/create",
                    replacement_text="/customers",
                    evidence_ids=(evidence.id,),
                    human_approved=True,
                    explanation="Replace the single approved endpoint literal.",
                ),
            ),
            summary="Replace the approved AtlasPay endpoint literal.",
        )


class _PassingValidationRunner:
    """Return deterministic success without starting a nested test process."""

    def __init__(self, status: ValidationStatus = ValidationStatus.PASSED) -> None:
        self._status = status

    def run(self, workspace_root: Path) -> ValidationResult:
        """Confirm the workspace exists and return sanitized passing metadata."""

        assert workspace_root.is_dir()
        return ValidationResult(
            status=self._status,
            duration_ms=1,
            exit_code=0 if self._status is ValidationStatus.PASSED else 1,
            timed_out=False,
        )


def _dependencies(
    tmp_path: Path,
    validation_status: ValidationStatus = ValidationStatus.PASSED,
) -> MigrationGraphDependencies:
    """Build the complete workflow using deterministic external-boundary fakes."""

    logger = logging.Logger("planning-workflow-test")
    logger.addHandler(logging.NullHandler())
    return MigrationGraphDependencies(
        planner=MigrationPlanner(_AtlasPayPlanningClient()),
        logger=logger,
        workspace_creator=TemporaryWorkspaceCreator(temporary_parent=tmp_path),
        patch_generator=PatchGenerator(
            client=_AtlasPayPatchClient(),
            validator=PatchProposalValidator(),
        ),
        patch_applier=ExactPatchApplier(),
        validation_runner=_PassingValidationRunner(validation_status),
        report_renderer=ReportRenderer(),
    )


def test_planning_graph_pauses_and_resumes_with_currency_decision(tmp_path: Path) -> None:
    """The graph must not approve a plan before an explicit valid resume."""

    dependencies = _dependencies(tmp_path)
    graph = build_planning_graph(dependencies=dependencies, checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "atlaspay-planning-test"}}
    request = PlanningWorkflowRequest(
        run_id="atlaspay-run",
        old_spec_path=str(_ATLASPAY_ROOT / "specs" / "atlaspay-v1.json"),
        new_spec_path=str(_ATLASPAY_ROOT / "specs" / "atlaspay-v2.json"),
        repository_path=str(_ATLASPAY_ROOT / "client-repository"),
    )

    interrupted = cast(Mapping[str, Any], graph.invoke(initial_state(request), config=config))

    assert interrupted["status"] is WorkflowStatus.AWAITING_REVIEW
    assert "reviewed_plan" not in interrupted
    assert len(interrupted["__interrupt__"]) == 1

    completed = cast(
        Mapping[str, Any],
        graph.invoke(
            Command[Any](
                resume={
                    "decision": "approve",
                }
            ),
            config=config,
        ),
    )

    assert completed["status"] is WorkflowStatus.FINALIZED
    assert all(action.status.value == "approved" for action in completed["reviewed_plan"].actions)
    workspace_root = Path(completed["workspace"].root_path)
    assert not workspace_root.exists()
    assert completed["patch_proposal"].operations[0].replacement_text == "/customers"
    assert completed["final_report"].outcome.value == "succeeded"
    assert completed["final_report"].workspace_cleaned is True
    assert completed["final_report"].modified_files == ("src/atlaspay_client/client.py",)
    assert '"/customers/create"' in (
        _ATLASPAY_ROOT / "client-repository/src/atlaspay_client/client.py"
    ).read_text(encoding="utf-8")


def _api_client(
    tmp_path: Path,
    validation_status: ValidationStatus = ValidationStatus.PASSED,
) -> TestClient:
    """Create an API client backed by the complete real application service."""

    graph = build_planning_graph(
        dependencies=_dependencies(tmp_path, validation_status),
        checkpointer=InMemorySaver(),
    )
    service = PlanningWorkflowService(
        graph=graph,
        store=MemoryMigrationRunStore(),
        target_registry=StaticMigrationTargetRegistry(
            (
                TrustedMigrationTarget(
                    summary=MigrationTargetSummary(
                        id="atlaspay",
                        name="AtlasPay Python client",
                        description="Bundled trusted integration fixture.",
                    ),
                    root=_ATLASPAY_ROOT,
                    old_spec_path=_ATLASPAY_ROOT / "specs" / "atlaspay-v1.json",
                    new_spec_path=_ATLASPAY_ROOT / "specs" / "atlaspay-v2.json",
                    repository_path=_ATLASPAY_ROOT / "client-repository",
                ),
            )
        ),
    )
    return TestClient(create_app(planning_service=service))


def test_api_completes_successful_atlaspay_workflow(tmp_path: Path) -> None:
    """The public API completes approval, patching, validation, reporting, and polling."""

    with _api_client(tmp_path) as client:
        started = client.post("/api/v1/migrations", json={"target_id": "atlaspay"})
        run_id = started.json()["run_id"]
        completed = client.post(
            f"/api/v1/migrations/{run_id}/review",
            json={"decision": "approve", "answers": {}},
        )
        polled = client.get(f"/api/v1/migrations/{run_id}")

    assert started.status_code == 201
    assert started.json()["status"] == "awaiting_review"
    assert started.json()["target_id"] == "atlaspay"
    assert completed.status_code == 200
    assert completed.json()["target_id"] == "atlaspay"
    assert completed.json()["report"]["outcome"] == "succeeded"
    assert completed.json()["validation"]["status"] == "passed"
    assert completed.json()["patch"]["operations"][0]["target_file"] == (
        "src/atlaspay_client/client.py"
    )
    assert polled.json() == completed.json()


def test_api_finalizes_rejected_atlaspay_workflow(tmp_path: Path) -> None:
    """Human rejection produces a report without workspace, patch, or validation."""

    with _api_client(tmp_path) as client:
        run_id = client.post("/api/v1/migrations", json={"target_id": "atlaspay"}).json()["run_id"]
        completed = client.post(
            f"/api/v1/migrations/{run_id}/review",
            json={"decision": "reject", "answers": {}},
        )

    payload = completed.json()
    assert payload["report"]["outcome"] == "rejected"
    assert payload["report"]["workspace_cleaned"] is False
    assert payload["patch"] is None
    assert payload["validation"] is None


def test_api_finalizes_failed_validation_without_guessing_repair(tmp_path: Path) -> None:
    """Failed validation reports uncertainty and performs zero repair attempts."""

    with _api_client(tmp_path, ValidationStatus.FAILED) as client:
        run_id = client.post("/api/v1/migrations", json={"target_id": "atlaspay"}).json()["run_id"]
        completed = client.post(
            f"/api/v1/migrations/{run_id}/review",
            json={"decision": "approve", "answers": {}},
        )

    report = completed.json()["report"]
    assert report["outcome"] == "failed"
    assert report["repair_attempt_count"] == 0
    assert report["remaining_uncertainty_codes"] == ["INSUFFICIENT_SANITIZED_FAILURE_EVIDENCE"]
    assert report["workspace_cleaned"] is True
