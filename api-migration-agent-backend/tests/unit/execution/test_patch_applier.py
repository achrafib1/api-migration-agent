"""Security tests for deterministic exact patch application."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from api_migration_agent.core.exceptions import PatchApplicationError
from api_migration_agent.domain.enums import MigrationOperationType
from api_migration_agent.domain.patch import PatchOperation, PatchProposal
from api_migration_agent.domain.repository_impact import RepositoryFile
from api_migration_agent.domain.workspace import MigrationWorkspace
from api_migration_agent.infrastructure.patch_applier import ExactPatchApplier


def _setup(tmp_path: Path, content: str) -> tuple[MigrationWorkspace, tuple[RepositoryFile, ...]]:
    root = tmp_path / "workspace"
    (root / "src").mkdir(parents=True)
    target = root / "src" / "client.py"
    target.write_text(content, encoding="utf-8")
    raw = target.read_bytes()
    return (
        MigrationWorkspace(root_path=str(root), approved_files=("src/client.py",)),
        (
            RepositoryFile(
                relative_path="src/client.py",
                size_bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(),
            ),
        ),
    )


def _proposal(**updates: object) -> PatchProposal:
    values: dict[str, object] = {
        "id": "PATCH-AAAAAAAAAAAA",
        "migration_action_id": "ACTION-BBBBBBBBBBBB",
        "api_change_id": "CHANGE-CCCCCCCCCCCC",
        "operation_type": MigrationOperationType.REPLACE_ENDPOINT,
        "target_file": "src/client.py",
        "expected_original_text": "/old",
        "replacement_text": "/new",
        "evidence_ids": ("IMPACT-DDDDDDDDDDDD",),
        "human_approved": True,
        "explanation": "Replace one approved endpoint.",
    }
    values.update(updates)
    return PatchProposal(
        operations=(PatchOperation.model_validate(values),),
        summary="Apply one exact replacement.",
    )


def test_applies_single_match_and_records_hashes(tmp_path: Path) -> None:
    """A valid operation changes only the workspace and returns metadata."""

    workspace, manifest = _setup(tmp_path, 'endpoint = "/old"\n')

    result = ExactPatchApplier().apply(
        proposal=_proposal(),
        workspace=workspace,
        manifest=manifest,
    )

    assert (Path(workspace.root_path) / "src/client.py").read_text(encoding="utf-8") == (
        'endpoint = "/new"\n'
    )
    assert result.modified_files[0].original_sha256 != result.modified_files[0].modified_sha256


def test_rejects_hash_conflict_without_modifying_file(tmp_path: Path) -> None:
    """A changed workspace file invalidates the original manifest precondition."""

    workspace, manifest = _setup(tmp_path, 'endpoint = "/old"\n')
    target = Path(workspace.root_path) / "src/client.py"
    target.write_text('endpoint = "/old"\nchanged = True\n', encoding="utf-8")
    before = target.read_bytes()

    with pytest.raises(PatchApplicationError):
        ExactPatchApplier().apply(
            proposal=_proposal(),
            workspace=workspace,
            manifest=manifest,
        )

    assert target.read_bytes() == before


@pytest.mark.parametrize(
    "content",
    ['a = "/old"\nb = "/old"\n', 'endpoint = "/different"\n'],
)
def test_rejects_ambiguous_or_missing_match(tmp_path: Path, content: str) -> None:
    """Patch application stops unless the expected text occurs exactly once."""

    workspace, manifest = _setup(tmp_path, content)

    with pytest.raises(PatchApplicationError):
        ExactPatchApplier().apply(
            proposal=_proposal(),
            workspace=workspace,
            manifest=manifest,
        )


def test_rejects_invalid_python_before_writing(tmp_path: Path) -> None:
    """All candidate Python must parse before any destination is replaced."""

    workspace, manifest = _setup(tmp_path, 'endpoint = "/old"\n')
    target = Path(workspace.root_path) / "src/client.py"
    original = target.read_bytes()

    with pytest.raises(PatchApplicationError):
        ExactPatchApplier().apply(
            proposal=_proposal(replacement_text='"unterminated'),
            workspace=workspace,
            manifest=manifest,
        )

    assert target.read_bytes() == original
