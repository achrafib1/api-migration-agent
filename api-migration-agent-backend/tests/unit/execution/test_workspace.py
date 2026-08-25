"""Security tests for isolated temporary workspace creation."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from api_migration_agent.core.exceptions import WorkspaceBoundaryError
from api_migration_agent.domain.enums import (
    ActionStatus,
    MigrationOperationType,
    MigrationRisk,
    PlanDecision,
)
from api_migration_agent.domain.migration_plan import (
    HumanPlanDecision,
    MigrationAction,
    MigrationPlanProposal,
    ReviewedMigrationPlan,
)
from api_migration_agent.domain.repository_impact import RepositoryFile
from api_migration_agent.domain.workspace import MigrationWorkspace
from api_migration_agent.infrastructure.workspace import TemporaryWorkspaceCreator


def _manifest(root: Path, relative_path: str = "src/client.py") -> tuple[RepositoryFile, ...]:
    content = (root / relative_path).read_bytes()
    return (
        RepositoryFile(
            relative_path=relative_path,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        ),
    )


def _reviewed_plan(target_file: str = "src/client.py") -> ReviewedMigrationPlan:
    action = MigrationAction(
        id="ACTION-AAAAAAAAAAAA",
        api_change_id="CHANGE-BBBBBBBBBBBB",
        title="Replace endpoint",
        description="Replace one deterministically verified endpoint.",
        target_file=target_file,
        operation_type=MigrationOperationType.REPLACE_ENDPOINT,
        risk=MigrationRisk.LOW,
        evidence_ids=("IMPACT-CCCCCCCCCCCC",),
        status=ActionStatus.APPROVED,
    )
    proposal = MigrationPlanProposal(actions=(action,), summary="Approved fixture migration.")
    return ReviewedMigrationPlan(
        proposal=proposal,
        decision=HumanPlanDecision(decision=PlanDecision.APPROVE),
        actions=(action,),
    )


def _repository(root: Path) -> Path:
    repository = root / "trusted"
    (repository / "src").mkdir(parents=True)
    (repository / "src" / "client.py").write_text("ENDPOINT = '/v1'\n", encoding="utf-8")
    (repository / "pyproject.toml").write_text(
        "[project]\nname='trusted-fixture'\nversion='1.0.0'\n",
        encoding="utf-8",
    )
    return repository


def test_workspace_is_isolated_and_preserves_original(tmp_path: Path) -> None:
    """Verified files are copied while the trusted original remains unchanged."""

    source = _repository(tmp_path)
    original = (source / "src" / "client.py").read_bytes()
    creator = TemporaryWorkspaceCreator(temporary_parent=tmp_path / "workspaces")
    (tmp_path / "workspaces").mkdir()

    workspace = creator.create(
        source_root=source,
        manifest=_manifest(source),
        reviewed_plan=_reviewed_plan(),
    )

    copied = Path(workspace.root_path) / "src" / "client.py"
    assert copied.read_bytes() == original
    copied.write_text("changed only in workspace\n", encoding="utf-8")
    assert (source / "src" / "client.py").read_bytes() == original
    assert workspace.approved_files == ("src/client.py",)

    creator.cleanup(workspace)

    assert not Path(workspace.root_path).exists()


def test_cleanup_rejects_unowned_directory(tmp_path: Path) -> None:
    """Cleanup cannot be repurposed to delete an arbitrary directory."""

    source = _repository(tmp_path)
    creator = TemporaryWorkspaceCreator(temporary_parent=tmp_path)
    unowned = MigrationWorkspace(
        root_path=str(source),
        approved_files=("src/client.py",),
    )

    with pytest.raises(WorkspaceBoundaryError):
        creator.cleanup(unowned)

    assert source.is_dir()


def test_unapproved_target_is_rejected(tmp_path: Path) -> None:
    """A reviewed action cannot target a file absent from the verified manifest."""

    source = _repository(tmp_path)
    creator = TemporaryWorkspaceCreator(temporary_parent=tmp_path)

    with pytest.raises(WorkspaceBoundaryError):
        creator.create(
            source_root=source,
            manifest=_manifest(source),
            reviewed_plan=_reviewed_plan("src/unknown.py"),
        )


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires privileges.")
def test_symlink_source_file_is_rejected(tmp_path: Path) -> None:
    """Workspace copying must never follow a source-file symlink."""

    source = _repository(tmp_path)
    external = tmp_path / "external.py"
    external.write_text("outside = True\n", encoding="utf-8")
    (source / "src" / "client.py").unlink()
    (source / "src" / "client.py").symlink_to(external)
    creator = TemporaryWorkspaceCreator(temporary_parent=tmp_path)

    with pytest.raises(WorkspaceBoundaryError):
        creator.create(
            source_root=source,
            manifest=_manifest(source),
            reviewed_plan=_reviewed_plan(),
        )
