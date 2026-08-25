"""Atomic exact-text patch application inside an isolated workspace."""

from __future__ import annotations

import ast
import hashlib
import os
import tempfile
from collections import defaultdict
from contextlib import suppress
from pathlib import Path

from api_migration_agent.core.exceptions import PatchApplicationError
from api_migration_agent.domain.applied_patch import AppliedPatch, ModifiedFile
from api_migration_agent.domain.patch import PatchOperation, PatchProposal
from api_migration_agent.domain.repository_impact import RepositoryFile
from api_migration_agent.domain.workspace import MigrationWorkspace


class ExactPatchApplier:
    """Apply exact replacements after independently rechecking all preconditions.

    All candidate contents are prepared and parsed before any destination file
    is replaced. Temporary files are created beside their destinations so
    ``os.replace`` remains atomic on the same filesystem.
    """

    def apply(
        self,
        *,
        proposal: PatchProposal,
        workspace: MigrationWorkspace,
        manifest: tuple[RepositoryFile, ...],
    ) -> AppliedPatch:
        """Apply an all-validated proposal to the temporary workspace only.

        Raises:
            PatchApplicationError: If confinement, approval, hash, match-count,
                encoding, syntax, staging, or replacement validation fails.
        """

        root = self._root(workspace)
        manifest_by_path = {item.relative_path: item for item in manifest}
        operations_by_file: dict[str, list[PatchOperation]] = defaultdict(list)
        for operation in proposal.operations:
            if (
                operation.target_file not in workspace.approved_files
                or operation.target_file not in manifest_by_path
                or not operation.human_approved
            ):
                raise PatchApplicationError
            operations_by_file[operation.target_file].append(operation)

        prepared: dict[Path, tuple[bytes, bytes, str, int]] = {}
        for relative_path, operations in operations_by_file.items():
            target = self._target(root, relative_path)
            try:
                original_bytes = target.read_bytes()
                original_hash = self._sha256(original_bytes)
                if original_hash != manifest_by_path[relative_path].sha256:
                    raise PatchApplicationError
                content = original_bytes.decode("utf-8")
                for operation in operations:
                    if content.count(operation.expected_original_text) != 1:
                        raise PatchApplicationError
                    content = content.replace(
                        operation.expected_original_text,
                        operation.replacement_text,
                        1,
                    )
                modified_bytes = content.encode("utf-8")
                ast.parse(content, filename=relative_path)
            except PatchApplicationError:
                raise
            except (OSError, UnicodeError, SyntaxError):
                raise PatchApplicationError from None
            prepared[target] = (
                original_bytes,
                modified_bytes,
                original_hash,
                len(operations),
            )

        staged: dict[Path, Path] = {}
        try:
            for target, (_, modified_bytes, _, _) in prepared.items():
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix=f".{target.name}.",
                    suffix=".patch",
                    dir=target.parent,
                )
                temporary_path = Path(temporary_name)
                staged[target] = temporary_path
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(modified_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
                ast.parse(temporary_path.read_text(encoding="utf-8"), filename=target.name)
            for target, temporary_path in staged.items():
                os.replace(temporary_path, target)
        except (OSError, UnicodeError, SyntaxError):
            raise PatchApplicationError from None
        finally:
            for temporary_path in staged.values():
                with suppress(OSError):
                    temporary_path.unlink(missing_ok=True)

        modified_files = tuple(
            ModifiedFile(
                relative_path=target.relative_to(root).as_posix(),
                original_sha256=original_hash,
                modified_sha256=self._sha256(modified_bytes),
                operation_count=operation_count,
            )
            for target, (_, modified_bytes, original_hash, operation_count) in sorted(
                prepared.items(), key=lambda item: item[0].as_posix()
            )
        )
        return AppliedPatch(modified_files=modified_files)

    @staticmethod
    def _root(workspace: MigrationWorkspace) -> Path:
        root = Path(workspace.root_path)
        if root.is_symlink() or not root.is_dir():
            raise PatchApplicationError
        try:
            return root.resolve(strict=True)
        except OSError:
            raise PatchApplicationError from None

    @staticmethod
    def _target(root: Path, relative_path: str) -> Path:
        path = Path(relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise PatchApplicationError
        candidate = root / path
        if candidate.is_symlink():
            raise PatchApplicationError
        try:
            target = candidate.resolve(strict=True)
            target.relative_to(root)
        except (OSError, ValueError):
            raise PatchApplicationError from None
        if not target.is_file():
            raise PatchApplicationError
        return target

    @staticmethod
    def _sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()
