"""Tests for FastAPI dependency wiring and sanitized responses."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api_migration_agent.api.main import bundled_atlaspay_root, create_app
from api_migration_agent.core.config import Settings
from api_migration_agent.core.exceptions import (
    HumanDecisionError,
    MigrationRunNotFoundError,
    ModelConfigurationError,
)
from api_migration_agent.domain.enums import ReportOutcome, WorkflowStatus
from api_migration_agent.domain.migration_plan import HumanPlanDecision
from api_migration_agent.domain.migration_run import MigrationRunRecord, PlanningReview
from api_migration_agent.domain.migration_target import (
    MigrationTargetCatalog,
    MigrationTargetSummary,
)
from api_migration_agent.domain.report import MigrationReport
from api_migration_agent.services.planning_workflow import PlanningWorkflowService


class _PlanningService(PlanningWorkflowService):
    """Deterministic API fake that never constructs a provider client."""

    def __init__(self) -> None:
        """Avoid production dependencies while preserving the service contract."""

    def list_targets(self) -> MigrationTargetCatalog:
        """Return the single safe target exposed by this API fake."""

        return MigrationTargetCatalog(
            targets=(
                MigrationTargetSummary(
                    id="atlaspay",
                    name="AtlasPay Python client",
                    description="Safe synthetic target.",
                ),
            )
        )

    def start(self, target_id: str) -> MigrationRunRecord:
        """Return a safe awaiting-review result."""

        assert target_id == "atlaspay"
        return MigrationRunRecord(
            run_id="run-api-test",
            target_id="atlaspay",
            status=WorkflowStatus.AWAITING_REVIEW,
            review=PlanningReview(run_id="run-api-test", actions=(), questions=()),
        )

    def review(self, run_id: str, decision: HumanPlanDecision) -> MigrationRunRecord:
        """Return a final rejected snapshot or reject an unknown run."""

        if run_id == "unknown":
            raise HumanDecisionError
        return MigrationRunRecord(
            run_id=run_id,
            target_id="atlaspay",
            status=WorkflowStatus.FINALIZED,
            report=MigrationReport(
                run_id=run_id,
                outcome=ReportOutcome.REJECTED,
                confirmed_change_ids=(),
                repository_evidence_ids=(),
                proposed_action_ids=(),
                approved_action_ids=(),
                modified_files=(),
                validation_status=None,
                human_decision="reject",
                repair_attempt_count=0,
                remaining_uncertainty_codes=(),
                workspace_cleaned=False,
            ),
        )

    def get(self, run_id: str) -> MigrationRunRecord:
        """Return the awaiting snapshot or report a missing process-local run."""

        if run_id == "unknown":
            raise MigrationRunNotFoundError
        return self.start("atlaspay")


def test_bundled_atlaspay_root_resolves_to_trusted_fixture() -> None:
    """Production wiring must locate the repository-owned fixture exactly."""

    root = bundled_atlaspay_root()

    assert root.is_dir()
    assert (root / "specs" / "atlaspay-v1.json").is_file()
    assert (root / "client-repository").is_dir()


def test_health_exposes_only_operational_status() -> None:
    """Health responses must not reveal model or provider configuration."""

    with TestClient(create_app(planning_service=_PlanningService())) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_start_uses_injected_service() -> None:
    """The route delegates workflow behavior to its injected service."""

    with TestClient(create_app(planning_service=_PlanningService())) as client:
        response = client.post("/api/v1/migrations", json={"target_id": "atlaspay"})

    assert response.status_code == 201
    assert response.json()["status"] == "awaiting_review"
    assert response.json()["target_id"] == "atlaspay"


def test_target_catalog_exposes_metadata_without_paths() -> None:
    """Target discovery returns identifiers and labels but never private paths."""

    with TestClient(create_app(planning_service=_PlanningService())) as client:
        response = client.get("/api/v1/migrations/targets")

    assert response.status_code == 200
    assert response.json() == {
        "targets": [
            {
                "id": "atlaspay",
                "name": "AtlasPay Python client",
                "description": "Safe synthetic target.",
            }
        ]
    }
    assert "path" not in response.text.lower()


def test_domain_exception_response_is_sanitized() -> None:
    """API errors expose stable metadata without internal exception details."""

    with TestClient(create_app(planning_service=_PlanningService())) as client:
        response = client.post(
            "/api/v1/migrations/unknown/review",
            json={"decision": "reject", "answers": {}},
        )

    assert response.status_code == 400
    assert response.json() == {
        "error_code": HumanDecisionError.error_code,
        "message": HumanDecisionError.public_message,
    }


def test_get_run_returns_typed_snapshot() -> None:
    """Frontend polling receives the stable content-safe run contract."""

    with TestClient(create_app(planning_service=_PlanningService())) as client:
        response = client.get("/api/v1/migrations/run-api-test")

    assert response.status_code == 200
    assert response.json()["review"]["run_id"] == "run-api-test"
    assert response.json()["target_id"] == "atlaspay"
    assert response.json()["patch"] is None


def test_unknown_run_returns_sanitized_not_found() -> None:
    """Missing in-memory state uses a stable 404 without internal details."""

    with TestClient(create_app(planning_service=_PlanningService())) as client:
        response = client.get("/api/v1/migrations/unknown")

    assert response.status_code == 404
    assert response.json() == {
        "error_code": MigrationRunNotFoundError.error_code,
        "message": MigrationRunNotFoundError.public_message,
    }


def test_rejected_review_returns_final_report() -> None:
    """Terminal review responses expose the structured final report."""

    with TestClient(create_app(planning_service=_PlanningService())) as client:
        response = client.post(
            "/api/v1/migrations/run-api-test/review",
            json={"decision": "reject", "answers": {}},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "finalized"
    assert response.json()["target_id"] == "atlaspay"
    assert response.json()["report"]["outcome"] == "rejected"


def test_cors_allows_only_configured_nextjs_origin() -> None:
    """CORS is explicit and does not use credentialed wildcard access."""

    app = create_app(
        planning_service=_PlanningService(),
        settings=Settings(allowed_origins=("http://localhost:3000",)),
    )
    with TestClient(app) as client:
        allowed = client.options(
            "/api/v1/migrations",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        rejected = client.options(
            "/api/v1/migrations",
            headers={
                "Origin": "https://unapproved.example",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in rejected.headers


def test_openapi_exposes_stable_frontend_contract_without_secrets() -> None:
    """Generated schemas include run lifecycle models and no provider settings."""

    schema = create_app(planning_service=_PlanningService()).openapi()
    paths = schema["paths"]
    components = schema["components"]["schemas"]

    assert "/api/v1/migrations" in paths
    assert "/api/v1/migrations/targets" in paths
    assert "/api/v1/migrations/{run_id}" in paths
    assert "/api/v1/migrations/{run_id}/review" in paths
    assert "MigrationRunRecord" in components
    assert "PlanningReview" in components
    assert "PatchSummary" in components
    assert "MigrationReport" in components
    serialized = str(schema).lower()
    assert "planning_api_key" not in serialized
    assert "workspace_root" not in serialized
    assert "expected_original_text" not in serialized


def test_production_startup_fails_safely_without_provider_credential() -> None:
    """Production wiring fails before serving requests when Gemini is unconfigured."""

    app = create_app(settings=Settings(planning_api_key=None))

    with pytest.raises(ModelConfigurationError) as captured, TestClient(app):
        pass

    assert str(captured.value) == ModelConfigurationError.public_message
