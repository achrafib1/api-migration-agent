"""Tests for structured planner validation and human review."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from api_migration_agent.core.exceptions import HumanDecisionError, PlanningValidationError
from api_migration_agent.domain.api_change import ApiChange, ChangeEvidence
from api_migration_agent.domain.enums import (
    ChangeCategory,
    ChangeSeverity,
    HttpMethod,
    MigrationOperationType,
    MigrationRisk,
    PlanDecision,
)
from api_migration_agent.domain.migration_plan import (
    HumanPlanDecision,
    HumanQuestion,
    MigrationAction,
    MigrationPlanProposal,
)
from api_migration_agent.domain.repository_impact import RepositoryImpact
from api_migration_agent.services.migration_planner import MigrationPlanner
from api_migration_agent.services.planning_models import PlanningRequest


@dataclass
class _RecordingClient:
    """Return a fixed proposal and retain the sanitized request for assertions."""

    proposal: MigrationPlanProposal
    request: PlanningRequest | None = None

    def create_migration_plan(self, request: PlanningRequest) -> MigrationPlanProposal:
        """Record planner input without contacting any provider."""

        self.request = request
        return self.proposal


def _change() -> ApiChange:
    return ApiChange(
        id="CHANGE-AAAAAAAAAAAA",
        category=ChangeCategory.OPERATION_REMOVED,
        severity=ChangeSeverity.HIGH,
        breaking=True,
        path="/customers/create",
        method=HttpMethod.POST,
        old_value={"path": "/customers/create"},
        description="Endpoint removed.",
        evidence=(ChangeEvidence(summary="Verified contract evidence."),),
    )


def _impact() -> RepositoryImpact:
    return RepositoryImpact(
        id="IMPACT-BBBBBBBBBBBB",
        api_change_id="CHANGE-AAAAAAAAAAAA",
        file_path="src/client.py",
        symbol_name="Client.create_customer",
        line_number=10,
        source_excerpt='self.post("/customers/create")',
        matched_text="/customers/create",
        context="executable",
        confidence="high",
        reason="Exact endpoint evidence.",
    )


def _action(**updates: object) -> MigrationAction:
    values: dict[str, object] = {
        "id": "ACTION-CCCCCCCCCCCC",
        "api_change_id": "CHANGE-AAAAAAAAAAAA",
        "title": "Update customer endpoint",
        "description": "Replace the verified legacy endpoint string.",
        "target_file": "src/client.py",
        "operation_type": MigrationOperationType.REPLACE_ENDPOINT,
        "risk": MigrationRisk.LOW,
        "evidence_ids": ("IMPACT-BBBBBBBBBBBB",),
    }
    values.update(updates)
    return MigrationAction.model_validate(values)


def _proposal(action: MigrationAction | None = None) -> MigrationPlanProposal:
    return MigrationPlanProposal(
        actions=(action or _action(),),
        summary="Update the verified AtlasPay client usage.",
    )


def test_planner_sends_sanitized_coordinates_without_source_excerpt() -> None:
    """The LLM boundary excludes source excerpts and full documents."""

    client = _RecordingClient(_proposal())
    planner = MigrationPlanner(client)

    planner.create_plan((_change(),), (_impact(),))

    assert client.request is not None
    evidence = client.request.repository_evidence[0]
    assert evidence.file_path == "src/client.py"
    assert "source_excerpt" not in type(evidence).model_fields


@pytest.mark.parametrize(
    "action",
    [
        _action(api_change_id="CHANGE-DDDDDDDDDDDD"),
        _action(evidence_ids=("IMPACT-EEEEEEEEEEEE",)),
        _action(target_file="src/unknown.py"),
    ],
)
def test_planner_rejects_invented_references(action: MigrationAction) -> None:
    """Unknown changes, evidence, and files cannot enter application state."""

    planner = MigrationPlanner(_RecordingClient(_proposal(action)))

    with pytest.raises(PlanningValidationError):
        planner.create_plan((_change(),), (_impact(),))


def test_human_input_action_requires_offered_answer() -> None:
    """Approval cannot bypass a required business decision."""

    action = _action(requires_human_input=True, question_key="currency_strategy")
    proposal = MigrationPlanProposal(
        actions=(action,),
        questions=(
            HumanQuestion(
                key="currency_strategy",
                prompt="How should currency be supplied?",
                options=("required_argument", "configured_default", "stop"),
            ),
        ),
        summary="Currency requires human input.",
    )
    planner = MigrationPlanner(_RecordingClient(proposal))

    with pytest.raises(HumanDecisionError):
        planner.review_plan(proposal, HumanPlanDecision(decision=PlanDecision.APPROVE))


def test_human_can_approve_with_valid_answer() -> None:
    """A valid selected option produces an approved reviewed action."""

    action = _action(requires_human_input=True, question_key="currency_strategy")
    proposal = MigrationPlanProposal(
        actions=(action,),
        questions=(
            HumanQuestion(
                key="currency_strategy",
                prompt="How should currency be supplied?",
                options=("required_argument", "configured_default", "stop"),
            ),
        ),
        summary="Currency requires human input.",
    )
    planner = MigrationPlanner(_RecordingClient(proposal))

    reviewed = planner.review_plan(
        proposal,
        HumanPlanDecision(
            decision=PlanDecision.APPROVE,
            answers={"currency_strategy": "required_argument"},
        ),
    )

    assert reviewed.actions[0].status.value == "approved"
