"""Security tests for deterministic patch-proposal acceptance."""

from __future__ import annotations

from pathlib import Path

import pytest

from api_migration_agent.core.exceptions import PlanningValidationError, WorkspaceBoundaryError
from api_migration_agent.domain.enums import (
    ActionStatus,
    ImpactConfidence,
    MigrationOperationType,
    MigrationRisk,
    PlanDecision,
    SourceContext,
)
from api_migration_agent.domain.migration_plan import (
    HumanPlanDecision,
    MigrationAction,
    MigrationPlanProposal,
    ReviewedMigrationPlan,
)
from api_migration_agent.domain.patch import PatchOperation, PatchProposal
from api_migration_agent.domain.repository_impact import RepositoryImpact
from api_migration_agent.domain.workspace import MigrationWorkspace
from api_migration_agent.services.patch_proposal import PatchProposalValidator


def _action() -> MigrationAction:
    return MigrationAction(
        id="ACTION-AAAAAAAAAAAA",
        api_change_id="CHANGE-BBBBBBBBBBBB",
        title="Replace endpoint",
        description="Replace the approved endpoint occurrence.",
        target_file="src/client.py",
        operation_type=MigrationOperationType.REPLACE_ENDPOINT,
        risk=MigrationRisk.LOW,
        evidence_ids=("IMPACT-CCCCCCCCCCCC",),
        status=ActionStatus.APPROVED,
    )


def _reviewed() -> ReviewedMigrationPlan:
    action = _action()
    return ReviewedMigrationPlan(
        proposal=MigrationPlanProposal(actions=(action,), summary="Approved migration."),
        decision=HumanPlanDecision(decision=PlanDecision.APPROVE),
        actions=(action,),
    )


def _impact() -> RepositoryImpact:
    return RepositoryImpact(
        id="IMPACT-CCCCCCCCCCCC",
        api_change_id="CHANGE-BBBBBBBBBBBB",
        file_path="src/client.py",
        symbol_name="Client.create",
        line_number=1,
        source_excerpt='endpoint = "/customers/create"',
        matched_text="/customers/create",
        context=SourceContext.EXECUTABLE,
        confidence=ImpactConfidence.HIGH,
        reason="Exact executable endpoint occurrence.",
    )


def _proposal(**updates: object) -> PatchProposal:
    values: dict[str, object] = {
        "id": "PATCH-DDDDDDDDDDDD",
        "migration_action_id": "ACTION-AAAAAAAAAAAA",
        "api_change_id": "CHANGE-BBBBBBBBBBBB",
        "operation_type": MigrationOperationType.REPLACE_ENDPOINT,
        "target_file": "src/client.py",
        "expected_original_text": "/customers/create",
        "replacement_text": "/customers",
        "evidence_ids": ("IMPACT-CCCCCCCCCCCC",),
        "human_approved": True,
        "explanation": "Replace the exact approved endpoint literal.",
    }
    values.update(updates)
    return PatchProposal(
        operations=(PatchOperation.model_validate(values),),
        summary="Replace one endpoint literal.",
    )


def _workspace(tmp_path: Path, text: str) -> MigrationWorkspace:
    root = tmp_path / "workspace"
    (root / "src").mkdir(parents=True)
    (root / "src" / "client.py").write_text(text, encoding="utf-8")
    return MigrationWorkspace(root_path=str(root), approved_files=("src/client.py",))


def test_accepts_single_exact_approved_match(tmp_path: Path) -> None:
    """A fully evidenced operation with one precondition match is accepted."""

    proposal = _proposal()

    result = PatchProposalValidator().validate(
        proposal,
        reviewed_plan=_reviewed(),
        repository_impacts=(_impact(),),
        workspace=_workspace(tmp_path, 'endpoint = "/customers/create"\n'),
    )

    assert result is proposal


@pytest.mark.parametrize(
    "text",
    ["endpoint = '/different'\n", 'a = "/customers/create"\nb = "/customers/create"\n'],
)
def test_rejects_missing_or_ambiguous_precondition(tmp_path: Path, text: str) -> None:
    """Expected original text must occur exactly once in the approved target."""

    with pytest.raises(WorkspaceBoundaryError):
        PatchProposalValidator().validate(
            _proposal(),
            reviewed_plan=_reviewed(),
            repository_impacts=(_impact(),),
            workspace=_workspace(tmp_path, text),
        )


def test_rejects_unapproved_or_invented_relationship(tmp_path: Path) -> None:
    """Model output cannot override human approval or deterministic evidence."""

    with pytest.raises(PlanningValidationError):
        PatchProposalValidator().validate(
            _proposal(human_approved=False),
            reviewed_plan=_reviewed(),
            repository_impacts=(_impact(),),
            workspace=_workspace(tmp_path, 'endpoint = "/customers/create"\n'),
        )
