"""Tests for the model-agnostic structured planning adapter."""

from __future__ import annotations

from typing import Any

import pytest

from api_migration_agent.core.config import Settings
from api_migration_agent.core.exceptions import ModelConfigurationError, PlanningValidationError
from api_migration_agent.domain.enums import (
    ChangeCategory,
    HttpMethod,
    MigrationOperationType,
    MigrationRisk,
)
from api_migration_agent.domain.migration_plan import MigrationAction, MigrationPlanProposal
from api_migration_agent.infrastructure.llm.client import (
    LangChainPlanningClient,
    StructuredPlanRunnable,
)
from api_migration_agent.infrastructure.llm.factory import create_planning_model
from api_migration_agent.services.planning_models import (
    PlanningChangeEvidence,
    PlanningRepositoryEvidence,
    PlanningRequest,
)


class _Runnable:
    """Return one injected result without contacting a provider."""

    def __init__(self, result: object) -> None:
        self.result = result
        self.input: object | None = None

    def invoke(self, input: object) -> object:
        """Record the message input and return the configured result."""

        self.input = input
        return self.result


class _FailingRunnable:
    """Simulate an unsafe provider exception without network access."""

    def invoke(self, input: object) -> object:
        """Raise content that must never escape the infrastructure boundary."""

        raise RuntimeError("unsafe-provider-detail")


class _Model:
    """Expose only the structured-output capability used by the adapter."""

    def __init__(self, runnable: StructuredPlanRunnable) -> None:
        self.runnable = runnable
        self.schema: type[Any] | None = None

    def with_structured_output(self, schema: type[Any]) -> StructuredPlanRunnable:
        """Record the requested schema and return the deterministic runnable."""

        self.schema = schema
        return self.runnable


def _request() -> PlanningRequest:
    return PlanningRequest(
        changes=(
            PlanningChangeEvidence(
                id="CHANGE-AAAAAAAAAAAA",
                category=ChangeCategory.OPERATION_REMOVED,
                path="/customers",
                method=HttpMethod.POST,
                old_value={"path": "/customers"},
                new_value=None,
                description="Verified change.",
            ),
        ),
        repository_evidence=(
            PlanningRepositoryEvidence(
                id="IMPACT-BBBBBBBBBBBB",
                api_change_id="CHANGE-AAAAAAAAAAAA",
                file_path="src/client.py",
                symbol_name="Client.create",
                line_number=12,
                matched_text="/customers",
                reason="Exact deterministic match.",
            ),
        ),
    )


def _proposal() -> MigrationPlanProposal:
    return MigrationPlanProposal(
        actions=(
            MigrationAction(
                id="ACTION-CCCCCCCCCCCC",
                api_change_id="CHANGE-AAAAAAAAAAAA",
                title="Update endpoint",
                description="Replace the verified endpoint occurrence.",
                target_file="src/client.py",
                operation_type=MigrationOperationType.REPLACE_ENDPOINT,
                risk=MigrationRisk.LOW,
                evidence_ids=("IMPACT-BBBBBBBBBBBB",),
            ),
        ),
        summary="Update verified client usage.",
    )


def test_adapter_requests_and_validates_structured_output() -> None:
    """The LangChain boundary must use the exact proposal schema."""

    runnable = _Runnable(_proposal())
    model = _Model(runnable)
    client = LangChainPlanningClient(model)

    result = client.create_migration_plan(_request())

    assert model.schema is MigrationPlanProposal
    assert runnable.input is not None
    assert result == _proposal()


def test_adapter_sanitizes_invalid_model_output() -> None:
    """Malformed provider output must become a constant domain exception."""

    client = LangChainPlanningClient(_Model(_Runnable({"unexpected": "value"})))

    with pytest.raises(PlanningValidationError):
        client.create_migration_plan(_request())


def test_factory_requires_provider_credential() -> None:
    """Production model construction stops safely when no key is configured."""

    with pytest.raises(ModelConfigurationError):
        create_planning_model(Settings(planning_api_key=None))


def test_adapter_sanitizes_provider_exception() -> None:
    """External exception text must not propagate into application errors."""

    client = LangChainPlanningClient(_Model(_FailingRunnable()))

    with pytest.raises(PlanningValidationError) as captured:
        client.create_migration_plan(_request())

    assert str(captured.value) == PlanningValidationError.public_message
