"""Structured migration planning and human-review value objects."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api_migration_agent.domain.enums import (
    ActionStatus,
    MigrationOperationType,
    MigrationRisk,
    PlanDecision,
)


class HumanQuestion(BaseModel):
    """Represent one business decision the system cannot infer safely."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    prompt: str = Field(min_length=1, max_length=500)
    options: tuple[str, ...] = Field(min_length=2, max_length=5)


class MigrationAction(BaseModel):
    """Describe one evidence-backed, human-reviewable migration action."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^ACTION-[0-9A-F]{12}$")
    api_change_id: str = Field(pattern=r"^CHANGE-[0-9A-F]{12}$")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    target_file: str = Field(min_length=1)
    operation_type: MigrationOperationType
    risk: MigrationRisk
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    requires_human_input: bool = False
    question_key: str | None = None
    status: ActionStatus = ActionStatus.PROPOSED

    @model_validator(mode="after")
    def validate_question_link(self) -> MigrationAction:
        """Require exactly one question link when human input is necessary."""

        if self.requires_human_input != (self.question_key is not None):
            raise ValueError("Human-input actions must reference one question key.")
        return self


class MigrationPlanProposal(BaseModel):
    """Validated structured output returned by an LLM client implementation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    actions: tuple[MigrationAction, ...] = Field(min_length=1)
    questions: tuple[HumanQuestion, ...] = ()
    summary: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_unique_identifiers(self) -> MigrationPlanProposal:
        """Reject duplicate action IDs, question keys, and dangling questions."""

        action_ids = [action.id for action in self.actions]
        question_keys = [question.key for question in self.questions]
        if len(action_ids) != len(set(action_ids)) or len(question_keys) != len(set(question_keys)):
            raise ValueError("Plan identifiers must be unique.")
        known_questions = set(question_keys)
        if any(
            action.question_key is not None and action.question_key not in known_questions
            for action in self.actions
        ):
            raise ValueError("Every action question key must reference a plan question.")
        return self


class HumanPlanDecision(BaseModel):
    """Validated payload supplied when resuming the human-review interrupt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: PlanDecision
    approved_action_ids: tuple[str, ...] = ()
    answers: dict[str, str] = Field(default_factory=dict)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewedMigrationPlan(BaseModel):
    """Migration plan after an explicit human approve or reject decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    proposal: MigrationPlanProposal
    decision: HumanPlanDecision
    actions: tuple[MigrationAction, ...]
