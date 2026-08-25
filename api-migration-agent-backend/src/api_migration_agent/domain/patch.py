"""Structured, reviewable patch-operation value objects."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api_migration_agent.domain.enums import MigrationOperationType


class PatchOperation(BaseModel):
    """Describe one exact replacement proposed for an approved source file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^PATCH-[0-9A-F]{12}$")
    migration_action_id: str = Field(pattern=r"^ACTION-[0-9A-F]{12}$")
    api_change_id: str = Field(pattern=r"^CHANGE-[0-9A-F]{12}$")
    operation_type: MigrationOperationType
    target_file: str = Field(min_length=1)
    expected_original_text: str = Field(min_length=1, max_length=2_000)
    replacement_text: str = Field(min_length=1, max_length=2_000)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    human_approved: bool
    explanation: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def validate_replacement_changes_content(self) -> PatchOperation:
        """Reject no-op replacements that cannot produce a migration."""

        if self.expected_original_text == self.replacement_text:
            raise ValueError("Patch replacement must change the expected text.")
        return self


class PatchProposal(BaseModel):
    """Validated collection of exact operations proposed for one workspace."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operations: tuple[PatchOperation, ...] = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def validate_unique_operation_ids(self) -> PatchProposal:
        """Require stable unique identifiers for review and reporting."""

        identifiers = [operation.id for operation in self.operations]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Patch operation identifiers must be unique.")
        return self
