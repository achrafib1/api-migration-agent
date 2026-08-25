"""Explicit runtime dependencies injected into migration graph nodes."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from api_migration_agent.execution.patch_applier import PatchApplier
from api_migration_agent.execution.validation import ValidationRunner
from api_migration_agent.execution.workspace import WorkspaceCreator
from api_migration_agent.services.migration_planner import MigrationPlanner
from api_migration_agent.services.patch_generator import PatchGenerator
from api_migration_agent.services.reporting import ReportRenderer


@dataclass(frozen=True, slots=True)
class MigrationGraphDependencies:
    """Hold collaborators without placing clients or settings in graph state."""

    planner: MigrationPlanner
    logger: logging.Logger
    workspace_creator: WorkspaceCreator
    patch_generator: PatchGenerator
    patch_applier: PatchApplier
    validation_runner: ValidationRunner
    report_renderer: ReportRenderer
