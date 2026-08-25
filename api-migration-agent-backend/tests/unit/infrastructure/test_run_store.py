"""Tests for process-local migration snapshot persistence."""

from __future__ import annotations

from api_migration_agent.domain.enums import WorkflowStatus
from api_migration_agent.domain.migration_run import MigrationRunRecord
from api_migration_agent.infrastructure.run_store import MemoryMigrationRunStore


def test_store_atomically_replaces_run_snapshot() -> None:
    """A run ID retains only its latest immutable safe snapshot."""

    store = MemoryMigrationRunStore()
    store.save(
        MigrationRunRecord(
            run_id="run-one",
            target_id="atlaspay",
            status=WorkflowStatus.AWAITING_REVIEW,
        )
    )
    store.save(
        MigrationRunRecord(
            run_id="run-one",
            target_id="atlaspay",
            status=WorkflowStatus.FINALIZED,
        )
    )

    record = store.get("run-one")

    assert record is not None
    assert record.status is WorkflowStatus.FINALIZED


def test_store_returns_none_for_unknown_run() -> None:
    """Unknown identifiers have no implicit or fabricated snapshot."""

    assert MemoryMigrationRunStore().get("unknown") is None
