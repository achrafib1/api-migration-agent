"""Fixed-command pytest validation for trusted temporary workspaces."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Final

from api_migration_agent.core.exceptions import WorkspaceBoundaryError
from api_migration_agent.domain.enums import ValidationStatus
from api_migration_agent.domain.validation import ValidationResult

_VALIDATION_ARGUMENTS: Final = ("-m", "pytest")


class PytestValidationRunner:
    """Run only Python's pytest module with no shell and bounded resources.

    Standard output and error are discarded deliberately. Repository-controlled
    test output is untrusted and must not enter logs, graph state, reports, or
    model prompts.
    """

    def __init__(self, *, timeout_seconds: float = 60.0) -> None:
        """Configure the strict positive validation timeout."""

        if timeout_seconds <= 0:
            raise ValueError("Validation timeout must be positive.")
        self._timeout_seconds = timeout_seconds

    def run(self, workspace_root: Path) -> ValidationResult:
        """Execute the one approved command inside the resolved workspace.

        Raises:
            WorkspaceBoundaryError: If the supplied workspace is invalid or a
                process cannot be started safely.
        """

        root = self._workspace_root(workspace_root)
        temporary_directory = root / ".validation-tmp"
        try:
            temporary_directory.mkdir(exist_ok=True)
            if temporary_directory.is_symlink() or not temporary_directory.is_dir():
                raise WorkspaceBoundaryError
        except OSError:
            raise WorkspaceBoundaryError from None
        start = time.monotonic()
        try:
            completed = subprocess.run(
                [sys.executable, *_VALIDATION_ARGUMENTS],
                cwd=root,
                env=self._sanitized_environment(temporary_directory),
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ValidationResult(
                status=ValidationStatus.TIMED_OUT,
                duration_ms=self._duration_ms(start),
                exit_code=None,
                timed_out=True,
            )
        except OSError:
            raise WorkspaceBoundaryError from None
        status = ValidationStatus.PASSED if completed.returncode == 0 else ValidationStatus.FAILED
        return ValidationResult(
            status=status,
            duration_ms=self._duration_ms(start),
            exit_code=completed.returncode,
            timed_out=False,
        )

    @staticmethod
    def _workspace_root(workspace_root: Path) -> Path:
        if workspace_root.is_symlink() or not workspace_root.is_dir():
            raise WorkspaceBoundaryError
        try:
            return workspace_root.resolve(strict=True)
        except OSError:
            raise WorkspaceBoundaryError from None

    @staticmethod
    def _sanitized_environment(temporary_directory: Path) -> dict[str, str]:
        environment = {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "TEMP": str(temporary_directory),
            "TMP": str(temporary_directory),
        }
        # Windows needs this explicitly named, non-secret runtime path to load
        # system libraries. The environment is never enumerated or logged.
        system_root = os.getenv("SYSTEMROOT")
        if system_root is not None:
            environment["SYSTEMROOT"] = system_root
        return environment

    @staticmethod
    def _duration_ms(start: float) -> int:
        return max(0, round((time.monotonic() - start) * 1000))
