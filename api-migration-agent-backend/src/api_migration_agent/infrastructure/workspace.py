"""Filesystem-confined temporary workspace implementation."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path
from threading import RLock

from api_migration_agent.analysis.repository.manifest import resolve_manifest_file
from api_migration_agent.core.exceptions import WorkspaceBoundaryError
from api_migration_agent.domain.enums import ActionStatus
from api_migration_agent.domain.migration_plan import ReviewedMigrationPlan
from api_migration_agent.domain.repository_impact import RepositoryFile
from api_migration_agent.domain.workspace import MigrationWorkspace


class TemporaryWorkspaceCreator:
    """Copy only verified AtlasPay files into a new temporary directory.

    The implementation never mutates the source repository, never follows
    symlinks, and copies only manifest files plus the fixed project descriptor.
    """

    def __init__(self, *, temporary_parent: Path | None = None) -> None:
        """Optionally confine created directories beneath a test-owned parent."""

        self._temporary_parent = temporary_parent
        self._created_roots: set[Path] = set()
        self._lock = RLock()

    def create(
        self,
        *,
        source_root: Path,
        manifest: tuple[RepositoryFile, ...],
        reviewed_plan: ReviewedMigrationPlan,
    ) -> MigrationWorkspace:
        """Create and verify one isolated copy for approved target files.

        Raises:
            WorkspaceBoundaryError: If paths, hashes, symlinks, or approvals do
                not satisfy the workspace confinement policy.
        """

        resolved_source = self._resolve_source_root(source_root)
        manifest_by_path = {item.relative_path: item for item in manifest}
        approved_files = tuple(
            sorted(
                {
                    action.target_file
                    for action in reviewed_plan.actions
                    if action.status is ActionStatus.APPROVED
                }
            )
        )
        if not approved_files or not set(approved_files) <= manifest_by_path.keys():
            raise WorkspaceBoundaryError

        workspace_root = Path(
            tempfile.mkdtemp(
                prefix="api-migration-",
                dir=self._temporary_parent,
            )
        ).resolve(strict=True)
        try:
            for manifest_file in manifest:
                source = resolve_manifest_file(resolved_source, manifest_file.relative_path)
                if self._sha256(source) != manifest_file.sha256:
                    raise WorkspaceBoundaryError
                destination = self._destination(workspace_root, manifest_file.relative_path)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination, follow_symlinks=False)
                if self._sha256(destination) != manifest_file.sha256:
                    raise WorkspaceBoundaryError
            self._copy_project_descriptor(resolved_source, workspace_root)
        except Exception:
            shutil.rmtree(workspace_root, ignore_errors=True)
            raise WorkspaceBoundaryError from None
        with self._lock:
            self._created_roots.add(workspace_root)
        return MigrationWorkspace(
            root_path=str(workspace_root),
            approved_files=approved_files,
        )

    def cleanup(self, workspace: MigrationWorkspace) -> None:
        """Remove only a directory registered by this creator instance.

        Raises:
            WorkspaceBoundaryError: If the path is unknown, replaced by a
                symlink, or cannot be removed completely.
        """

        root = Path(workspace.root_path)
        with self._lock:
            if root not in self._created_roots or root.is_symlink() or not root.is_dir():
                raise WorkspaceBoundaryError
            try:
                shutil.rmtree(root)
            except OSError:
                raise WorkspaceBoundaryError from None
            self._created_roots.remove(root)

    @staticmethod
    def _resolve_source_root(source_root: Path) -> Path:
        if source_root.is_symlink() or not source_root.is_dir():
            raise WorkspaceBoundaryError
        try:
            return source_root.resolve(strict=True)
        except OSError:
            raise WorkspaceBoundaryError from None

    @staticmethod
    def _destination(root: Path, relative_path: str) -> Path:
        path = Path(relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise WorkspaceBoundaryError
        destination = root / path
        try:
            destination.resolve().relative_to(root)
        except ValueError:
            raise WorkspaceBoundaryError from None
        return destination

    @classmethod
    def _copy_project_descriptor(cls, source_root: Path, workspace_root: Path) -> None:
        descriptor = source_root / "pyproject.toml"
        if descriptor.is_symlink() or not descriptor.is_file():
            raise WorkspaceBoundaryError
        resolved = descriptor.resolve(strict=True)
        try:
            resolved.relative_to(source_root)
        except ValueError:
            raise WorkspaceBoundaryError from None
        shutil.copyfile(resolved, workspace_root / "pyproject.toml", follow_symlinks=False)

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
