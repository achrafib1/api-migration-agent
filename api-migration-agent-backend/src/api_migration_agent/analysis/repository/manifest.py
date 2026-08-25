"""Constrained manifest generation for trusted Python client repositories."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

from api_migration_agent.core.exceptions import RepositoryBoundaryError, RepositorySourceError
from api_migration_agent.domain.repository_impact import RepositoryFile

_APPROVED_SOURCE_DIRECTORIES: Final = ("src", "tests")
_MAXIMUM_SOURCE_BYTES: Final = 1_000_000


def build_repository_manifest(root: Path) -> tuple[RepositoryFile, ...]:
    """Index approved Python files without executing repository content.

    Args:
        root: Trusted AtlasPay repository root selected by application code.

    Returns:
        Stable manifest entries for regular `.py` files under `src/` and
        `tests/` only.

    Raises:
        RepositoryBoundaryError: If the root or a candidate resolves outside the
            trusted root, or any candidate is a symlink.
        RepositorySourceError: If a candidate is oversized or unreadable.
    """

    if root.is_symlink() or not root.is_dir():
        raise RepositoryBoundaryError
    resolved_root = root.resolve(strict=True)
    manifest: list[RepositoryFile] = []

    for directory_name in _APPROVED_SOURCE_DIRECTORIES:
        source_root = resolved_root / directory_name
        if not source_root.exists():
            continue
        if source_root.is_symlink() or not source_root.is_dir():
            raise RepositoryBoundaryError
        for candidate in sorted(source_root.rglob("*.py")):
            manifest.append(_manifest_file(resolved_root, candidate))
    return tuple(sorted(manifest, key=lambda item: item.relative_path))


def resolve_manifest_file(root: Path, relative_path: str) -> Path:
    """Resolve a manifest path again immediately before reading source."""

    if not relative_path or ".." in Path(relative_path).parts or Path(relative_path).is_absolute():
        raise RepositoryBoundaryError
    resolved_root = root.resolve(strict=True)
    candidate = resolved_root / Path(relative_path)
    if candidate.is_symlink():
        raise RepositoryBoundaryError
    try:
        resolved_candidate = candidate.resolve(strict=True)
        resolved_candidate.relative_to(resolved_root)
    except (OSError, ValueError):
        raise RepositoryBoundaryError from None
    if not resolved_candidate.is_file():
        raise RepositoryBoundaryError
    return resolved_candidate


def _manifest_file(resolved_root: Path, candidate: Path) -> RepositoryFile:
    """Validate and fingerprint one source file inside the approved root."""

    if candidate.is_symlink():
        raise RepositoryBoundaryError
    try:
        resolved_candidate = candidate.resolve(strict=True)
        resolved_candidate.relative_to(resolved_root)
        size = resolved_candidate.stat().st_size
        if size > _MAXIMUM_SOURCE_BYTES:
            raise RepositorySourceError
        content = resolved_candidate.read_bytes()
    except RepositorySourceError:
        raise
    except (OSError, ValueError):
        raise RepositoryBoundaryError from None
    return RepositoryFile(
        relative_path=resolved_candidate.relative_to(resolved_root).as_posix(),
        size_bytes=size,
        sha256=hashlib.sha256(content).hexdigest(),
    )
