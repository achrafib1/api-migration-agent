"""Evidence validation and human review for structured migration plans."""

from __future__ import annotations

from api_migration_agent.core.exceptions import HumanDecisionError, PlanningValidationError
from api_migration_agent.domain.api_change import ApiChange
from api_migration_agent.domain.enums import ActionStatus, PlanDecision
from api_migration_agent.domain.migration_plan import (
    HumanPlanDecision,
    MigrationPlanProposal,
    ReviewedMigrationPlan,
)
from api_migration_agent.domain.repository_impact import RepositoryImpact
from api_migration_agent.services.llm import LLMClient
from api_migration_agent.services.planning_models import (
    PlanningChangeEvidence,
    PlanningRepositoryEvidence,
    PlanningRequest,
)


class MigrationPlanner:
    """Create and review plans while treating model output as untrusted data."""

    def __init__(self, llm_client: LLMClient) -> None:
        """Inject the only boundary permitted to generate planning proposals."""

        self._llm_client = llm_client

    def create_plan(
        self,
        api_changes: tuple[ApiChange, ...],
        repository_impacts: tuple[RepositoryImpact, ...],
    ) -> MigrationPlanProposal:
        """Generate a plan and validate every reference against known evidence.

        Args:
            api_changes: Authoritative deterministic contract changes.
            repository_impacts: Authoritative deterministic source locations.

        Returns:
            A structured proposal whose changes, files, and evidence are known.

        Raises:
            PlanningValidationError: If generated output invents a change,
                evidence item, target file, status, or unsupported relationship.
        """

        request = _planning_request(api_changes, repository_impacts)
        proposal = self._llm_client.create_migration_plan(request)
        _validate_proposal(proposal, request)
        return proposal

    def review_plan(
        self,
        proposal: MigrationPlanProposal,
        decision: HumanPlanDecision,
    ) -> ReviewedMigrationPlan:
        """Apply an explicit human decision without modifying any files.

        Raises:
            HumanDecisionError: If action selections or required answers are
                missing, unknown, or outside the offered choices.
        """

        known_actions = {action.id: action for action in proposal.actions}
        if decision.decision is PlanDecision.REJECT:
            if decision.approved_action_ids:
                raise HumanDecisionError
            reviewed_actions = tuple(
                action.model_copy(update={"status": ActionStatus.REJECTED})
                for action in proposal.actions
            )
            return ReviewedMigrationPlan(
                proposal=proposal,
                decision=decision,
                actions=reviewed_actions,
            )

        selected_ids = set(decision.approved_action_ids or tuple(known_actions))
        if not selected_ids or not selected_ids <= known_actions.keys():
            raise HumanDecisionError
        questions = {question.key: question for question in proposal.questions}
        for action_id in selected_ids:
            action = known_actions[action_id]
            if action.question_key is None:
                continue
            answer = decision.answers.get(action.question_key)
            question = questions[action.question_key]
            if answer is None or answer not in question.options:
                raise HumanDecisionError

        reviewed_actions = tuple(
            action.model_copy(
                update={
                    "status": (
                        ActionStatus.APPROVED
                        if action.id in selected_ids
                        else ActionStatus.REJECTED
                    )
                }
            )
            for action in proposal.actions
        )
        return ReviewedMigrationPlan(
            proposal=proposal,
            decision=decision,
            actions=reviewed_actions,
        )


def _planning_request(
    api_changes: tuple[ApiChange, ...],
    repository_impacts: tuple[RepositoryImpact, ...],
) -> PlanningRequest:
    """Project deterministic models into the sanitized planner boundary."""

    return PlanningRequest(
        changes=tuple(
            PlanningChangeEvidence(
                id=change.id,
                category=change.category,
                path=change.path,
                method=change.method,
                old_value=change.old_value,
                new_value=change.new_value,
                description=change.description,
            )
            for change in api_changes
        ),
        repository_evidence=tuple(
            PlanningRepositoryEvidence(
                id=impact.id,
                api_change_id=impact.api_change_id,
                file_path=impact.file_path,
                symbol_name=impact.symbol_name,
                line_number=impact.line_number,
                matched_text=impact.matched_text,
                reason=impact.reason,
            )
            for impact in repository_impacts
        ),
    )


def _validate_proposal(proposal: MigrationPlanProposal, request: PlanningRequest) -> None:
    """Reject invented or unsupported references in generated output."""

    known_change_ids = {change.id for change in request.changes}
    evidence_by_id = {evidence.id: evidence for evidence in request.repository_evidence}
    known_files = {evidence.file_path for evidence in request.repository_evidence}

    for action in proposal.actions:
        if (
            action.api_change_id not in known_change_ids
            or action.status is not ActionStatus.PROPOSED
            or action.target_file not in known_files
            or not set(action.evidence_ids) <= evidence_by_id.keys()
            or not any(
                evidence_by_id[evidence_id].file_path == action.target_file
                for evidence_id in action.evidence_ids
            )
            or not all(
                evidence_by_id[evidence_id].api_change_id == action.api_change_id
                for evidence_id in action.evidence_ids
            )
        ):
            raise PlanningValidationError
