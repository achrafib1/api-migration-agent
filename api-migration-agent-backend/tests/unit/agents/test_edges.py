"""Tests for pure conditional workflow routing."""

from __future__ import annotations

from api_migration_agent.agents.migration_agent.edges import (
    route_after_review,
    route_after_validation,
)
from api_migration_agent.agents.migration_agent.state import MigrationAgentState
from api_migration_agent.domain.enums import WorkflowStatus


def test_approved_review_routes_to_workspace_creation() -> None:
    """Explicit approval is the only route into controlled execution."""

    state = MigrationAgentState(status=WorkflowStatus.APPROVED)

    assert route_after_review(state) == "create_workspace"


def test_rejected_review_routes_to_end() -> None:
    """A rejection must terminate without creating a temporary copy."""

    state = MigrationAgentState(status=WorkflowStatus.REJECTED)

    assert route_after_review(state) == "finalize_report"


def test_failed_validation_routes_to_investigation() -> None:
    """Validation failure must be examined before terminal reporting."""

    state = MigrationAgentState(status=WorkflowStatus.VALIDATION_FAILED)

    assert route_after_validation(state) == "investigate_failure"


def test_passed_validation_routes_to_report() -> None:
    """Successful deterministic validation needs no repair investigation."""

    state = MigrationAgentState(status=WorkflowStatus.VALIDATION_PASSED)

    assert route_after_validation(state) == "finalize_report"
