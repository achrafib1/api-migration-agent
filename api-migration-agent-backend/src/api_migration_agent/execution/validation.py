"""Protocol for fixed, isolated workspace validation."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from api_migration_agent.domain.validation import ValidationResult


class ValidationRunner(Protocol):
    """Run the single approved validation command in a trusted workspace."""

    def run(self, workspace_root: Path) -> ValidationResult:
        """Execute fixed validation and return sanitized metadata."""

        ...
