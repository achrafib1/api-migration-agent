"""Enforce the human approval boundary before any future execution stage."""

from __future__ import annotations

from langgraph.types import interrupt
from pydantic import ValidationError

from api_migration_agent.agents.migration_agent.dependencies import MigrationGraphDependencies
from api_migration_agent.agents.migration_agent.nodes._logging import log_node_event
from api_migration_agent.agents.migration_agent.state import MigrationAgentState
from api_migration_agent.core.exceptions import HumanDecisionError
from api_migration_agent.domain.enums import PlanDecision, WorkflowStatus
from api_migration_agent.domain.migration_plan import HumanPlanDecision


def review_plan(
    state: MigrationAgentState,
    dependencies: MigrationGraphDependencies,
) -> dict[str, object]:
    """Pause for a human decision and reject malformed resume payloads.

    Raises:
        HumanDecisionError: If the decision is incomplete or invalid.
    """

    proposal = state["migration_plan"]
    raw_decision = interrupt(
        {
            "run_id": state["run_id"],
            "actions": [
                {
                    "id": action.id,
                    "title": action.title,
                    "target_file": action.target_file,
                    "risk": action.risk.value,
                    "requires_human_input": action.requires_human_input,
                    "question_key": action.question_key,
                }
                for action in proposal.actions
            ],
            "questions": [question.model_dump(mode="json") for question in proposal.questions],
        }
    )
    try:
        decision = HumanPlanDecision.model_validate(raw_decision)
    except ValidationError:
        raise HumanDecisionError from None

    reviewed = dependencies.planner.review_plan(proposal, decision)
    status = (
        WorkflowStatus.APPROVED
        if decision.decision is PlanDecision.APPROVE
        else WorkflowStatus.REJECTED
    )
    log_node_event(
        dependencies,
        state,
        "migration_plan_reviewed",
        "review_plan",
        status=status.value,
    )
    return {"reviewed_plan": reviewed, "status": status}
