"""Tests for confined trusted-repository manifest generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from api_migration_agent.analysis.repository.manifest import (
    build_repository_manifest,
    resolve_manifest_file,
)
from api_migration_agent.core.exceptions import RepositoryBoundaryError, RepositorySourceError


def test_indexes_only_python_files_under_approved_directories(tmp_path: Path) -> None:
    """Manifest scope excludes root files, docs, and non-Python artifacts."""

    (tmp_path / "src" / "package").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "package" / "client.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "tests" / "test_client.py").write_text("def test_value(): pass\n", encoding="utf-8")
    (tmp_path / "src" / "notes.txt").write_text("ignored", encoding="utf-8")
    (tmp_path / "docs" / "example.py").write_text("IGNORED = True\n", encoding="utf-8")
    (tmp_path / "root.py").write_text("IGNORED = True\n", encoding="utf-8")

    manifest = build_repository_manifest(tmp_path)

    assert [entry.relative_path for entry in manifest] == [
        "src/package/client.py",
        "tests/test_client.py",
    ]
    assert all(len(entry.sha256) == 64 for entry in manifest)


def test_rejects_relative_path_traversal(tmp_path: Path) -> None:
    """Manifest paths cannot escape through parent-directory components."""

    (tmp_path / "src").mkdir()

    with pytest.raises(RepositoryBoundaryError):
        resolve_manifest_file(tmp_path, "../outside.py")


def test_rejects_absolute_manifest_path(tmp_path: Path) -> None:
    """Absolute paths cannot be smuggled into a manifest read."""

    (tmp_path / "src").mkdir()

    with pytest.raises(RepositoryBoundaryError):
        resolve_manifest_file(tmp_path, str((tmp_path / "src" / "client.py").resolve()))


def test_rejects_oversized_python_source(tmp_path: Path) -> None:
    """The fixed source-size ceiling is applied before analysis."""

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "large.py").write_text("x" * 1_000_001, encoding="utf-8")

    with pytest.raises(RepositorySourceError):
        build_repository_manifest(tmp_path)


def test_rejects_symlinked_source_file_when_supported(tmp_path: Path) -> None:
    """A source symlink cannot redirect analysis outside the trusted root."""

    (tmp_path / "src").mkdir()
    outside = tmp_path.parent / f"{tmp_path.name}-outside.py"
    outside.write_text("VALUE = 1\n", encoding="utf-8")
    link = tmp_path / "src" / "linked.py"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("File symlinks are unavailable in this Windows environment.")

    with pytest.raises(RepositoryBoundaryError):
        build_repository_manifest(tmp_path)
