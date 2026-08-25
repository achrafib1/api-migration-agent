"""Replaceable structured-output boundary for migration planning."""

from __future__ import annotations

from typing import Protocol

from api_migration_agent.domain.migration_plan import MigrationPlanProposal
from api_migration_agent.services.planning_models import PlanningRequest


class LLMClient(Protocol):
    """Generate schema-validated plans from sanitized deterministic evidence."""

    def create_migration_plan(self, request: PlanningRequest) -> MigrationPlanProposal:
        """Return a structured proposal without executing tools or commands."""

        ...
