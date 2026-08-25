"""Generate and deterministically validate structured patch proposals."""

from __future__ import annotations

from typing import Protocol

from api_migration_agent.core.exceptions import PlanningValidationError
from api_migration_agent.domain.enums import ActionStatus
from api_migration_agent.domain.migration_plan import ReviewedMigrationPlan
from api_migration_agent.domain.patch import PatchProposal
from api_migration_agent.domain.repository_impact import RepositoryImpact
from api_migration_agent.domain.workspace import MigrationWorkspace
from api_migration_agent.services.patch_models import (
    PatchActionInput,
    PatchEvidenceInput,
    PatchGenerationRequest,
)
from api_migration_agent.services.patch_proposal import PatchProposalValidator


class PatchLLMClient(Protocol):
    """Generate schema-validated operations from approved bounded evidence."""

    def create_patch_proposal(self, request: PatchGenerationRequest) -> PatchProposal:
        """Return exact replacement operations without modifying files."""

        ...


class PatchGenerator:
    """Coordinate untrusted LLM generation and deterministic acceptance."""

    def __init__(self, *, client: PatchLLMClient, validator: PatchProposalValidator) -> None:
        """Inject the structured model boundary and authoritative validator."""

        self._client = client
        self._validator = validator

    def generate(
        self,
        *,
        reviewed_plan: ReviewedMigrationPlan,
        repository_impacts: tuple[RepositoryImpact, ...],
        workspace: MigrationWorkspace,
    ) -> PatchProposal:
        """Generate a proposal and reject unsupported or incomplete output."""

        request = _request(reviewed_plan, repository_impacts)
        proposal = self._client.create_patch_proposal(request)
        proposed_actions = {operation.migration_action_id for operation in proposal.operations}
        approved_actions = {
            action.id for action in reviewed_plan.actions if action.status is ActionStatus.APPROVED
        }
        if proposed_actions != approved_actions:
            raise PlanningValidationError
        return self._validator.validate(
            proposal,
            reviewed_plan=reviewed_plan,
            repository_impacts=repository_impacts,
            workspace=workspace,
        )


def _request(
    reviewed_plan: ReviewedMigrationPlan,
    repository_impacts: tuple[RepositoryImpact, ...],
) -> PatchGenerationRequest:
    """Project reviewed state into the bounded model-generation schema."""

    approved = tuple(
        action for action in reviewed_plan.actions if action.status is ActionStatus.APPROVED
    )
    if not approved:
        raise PlanningValidationError
    answers = reviewed_plan.decision.answers
    evidence_ids = {identifier for action in approved for identifier in action.evidence_ids}
    selected_evidence = tuple(impact for impact in repository_impacts if impact.id in evidence_ids)
    if {impact.id for impact in selected_evidence} != evidence_ids:
        raise PlanningValidationError
    return PatchGenerationRequest(
        actions=tuple(
            PatchActionInput(
                id=action.id,
                api_change_id=action.api_change_id,
                operation_type=action.operation_type,
                target_file=action.target_file,
                title=action.title,
                description=action.description,
                evidence_ids=action.evidence_ids,
                approved_answer=(
                    answers.get(action.question_key) if action.question_key is not None else None
                ),
            )
            for action in approved
        ),
        evidence=tuple(
            PatchEvidenceInput(
                id=impact.id,
                api_change_id=impact.api_change_id,
                target_file=impact.file_path,
                line_number=impact.line_number,
                matched_text=impact.matched_text,
                source_excerpt=impact.source_excerpt,
            )
            for impact in selected_evidence
        ),
    )
