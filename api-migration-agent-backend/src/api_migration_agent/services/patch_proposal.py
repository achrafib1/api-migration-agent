"""Deterministic acceptance boundary for untrusted patch proposals."""

from __future__ import annotations

from pathlib import Path

from api_migration_agent.core.exceptions import PlanningValidationError, WorkspaceBoundaryError
from api_migration_agent.domain.enums import ActionStatus
from api_migration_agent.domain.migration_plan import ReviewedMigrationPlan
from api_migration_agent.domain.patch import PatchProposal
from api_migration_agent.domain.repository_impact import RepositoryImpact
from api_migration_agent.domain.workspace import MigrationWorkspace


class PatchProposalValidator:
    """Validate proposed exact replacements against approval and filesystem facts."""

    def validate(
        self,
        proposal: PatchProposal,
        *,
        reviewed_plan: ReviewedMigrationPlan,
        repository_impacts: tuple[RepositoryImpact, ...],
        workspace: MigrationWorkspace,
    ) -> PatchProposal:
        """Return a proposal only when every operation is supported and unambiguous.

        Raises:
            PlanningValidationError: If an operation invents or mismatches plan evidence.
            WorkspaceBoundaryError: If a target escapes the workspace or has an
                absent or ambiguous expected-text precondition.
        """

        approved_actions = {
            action.id: action
            for action in reviewed_plan.actions
            if action.status is ActionStatus.APPROVED
        }
        impacts = {impact.id: impact for impact in repository_impacts}
        approved_files = set(workspace.approved_files)
        root = self._workspace_root(workspace)

        for operation in proposal.operations:
            action = approved_actions.get(operation.migration_action_id)
            if (
                action is None
                or not operation.human_approved
                or operation.api_change_id != action.api_change_id
                or operation.operation_type is not action.operation_type
                or operation.target_file != action.target_file
                or operation.target_file not in approved_files
                or not set(operation.evidence_ids) <= set(action.evidence_ids)
                or not all(
                    evidence_id in impacts
                    and impacts[evidence_id].file_path == operation.target_file
                    and impacts[evidence_id].api_change_id == operation.api_change_id
                    for evidence_id in operation.evidence_ids
                )
            ):
                raise PlanningValidationError

            target = self._target(root, operation.target_file)
            try:
                content = target.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                raise WorkspaceBoundaryError from None
            if content.count(operation.expected_original_text) != 1:
                raise WorkspaceBoundaryError

        return proposal

    @staticmethod
    def _workspace_root(workspace: MigrationWorkspace) -> Path:
        root = Path(workspace.root_path)
        if root.is_symlink() or not root.is_dir():
            raise WorkspaceBoundaryError
        try:
            return root.resolve(strict=True)
        except OSError:
            raise WorkspaceBoundaryError from None

    @staticmethod
    def _target(root: Path, relative_path: str) -> Path:
        path = Path(relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise WorkspaceBoundaryError
        candidate = root / path
        if candidate.is_symlink():
            raise WorkspaceBoundaryError
        try:
            target = candidate.resolve(strict=True)
            target.relative_to(root)
        except (OSError, ValueError):
            raise WorkspaceBoundaryError from None
        if not target.is_file():
            raise WorkspaceBoundaryError
        return target
