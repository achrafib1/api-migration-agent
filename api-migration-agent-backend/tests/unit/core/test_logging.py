"""Security tests for allowlisted structured logging."""

from __future__ import annotations

import json
import logging

import pytest

from api_migration_agent.core.logging import AllowlistedJsonFormatter, log_event


class _CapturingHandler(logging.Handler):
    """Capture formatted records without writing potentially sensitive output."""

    def __init__(self) -> None:
        super().__init__()
        self.rendered: list[str] = []
        self.setFormatter(AllowlistedJsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        """Store the security-filtered representation of one record."""

        self.rendered.append(self.format(record))


def test_emits_only_allowlisted_operational_context() -> None:
    """Structured events include useful metadata without raw message fields."""

    logger = logging.Logger("test-safe-logger")
    handler = _CapturingHandler()
    logger.addHandler(handler)

    log_event(
        logger, logging.INFO, "spec_analysis_completed", stage="analyze_specs", change_count=2
    )

    payload = json.loads(handler.rendered[0])
    assert payload["event"] == "spec_analysis_completed"
    assert payload["stage"] == "analyze_specs"
    assert payload["change_count"] == 2
    assert set(payload) == {"change_count", "event", "level", "stage", "timestamp"}


def test_rejects_non_allowlisted_context_without_echoing_its_name() -> None:
    """Callers cannot attach documents, source, or arbitrary dictionaries."""

    logger = logging.Logger("test-rejected-logger")

    with pytest.raises(ValueError) as captured:
        log_event(logger, logging.INFO, "unsafe_event", source_contents="synthetic-canary")

    assert "source_contents" not in str(captured.value)
    assert "synthetic-canary" not in str(captured.value)
