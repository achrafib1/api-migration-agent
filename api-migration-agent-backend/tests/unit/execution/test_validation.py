"""Security tests for the fixed-command validation runner."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from api_migration_agent.domain.enums import ValidationStatus
from api_migration_agent.infrastructure.validation import PytestValidationRunner


def test_runner_uses_only_fixed_shell_free_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No user or model value can influence validation command arguments."""

    captured: dict[str, Any] = {}

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        captured["args"] = args
        captured.update(kwargs)
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = PytestValidationRunner(timeout_seconds=5).run(tmp_path)

    assert captured["args"] == [sys.executable, "-m", "pytest"]
    assert captured["shell"] is False
    assert captured["cwd"] == tmp_path.resolve()
    assert captured["stdout"] is subprocess.DEVNULL
    assert captured["stderr"] is subprocess.DEVNULL
    assert captured["check"] is False
    assert result.status is ValidationStatus.PASSED


def test_runner_reports_failure_without_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A nonzero exit becomes metadata without capturing repository output."""

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args=args, returncode=3)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = PytestValidationRunner().run(tmp_path)

    assert result.status is ValidationStatus.FAILED
    assert result.exit_code == 3
    assert result.timed_out is False


def test_runner_reports_timeout_without_exception_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timeouts become a sanitized result with no command output attached."""

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(cmd=args, timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = PytestValidationRunner(timeout_seconds=1).run(tmp_path)

    assert result.status is ValidationStatus.TIMED_OUT
    assert result.exit_code is None
    assert result.timed_out is True
    assert "output" not in type(result).model_fields
