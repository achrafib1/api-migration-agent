"""Process-local migration-run persistence for the single-worker MVP."""

from __future__ import annotations

from threading import RLock

from api_migration_agent.domain.migration_run import MigrationRunRecord


class MemoryMigrationRunStore:
    """Store run metadata in memory with thread-safe replacement semantics.

    Records disappear on restart and are not shared across worker processes.
    LangGraph checkpoint data remains owned by the injected checkpointer.
    """

    def __init__(self) -> None:
        self._records: dict[str, MigrationRunRecord] = {}
        self._lock = RLock()

    def save(self, record: MigrationRunRecord) -> None:
        """Insert or atomically replace a run record."""

        with self._lock:
            self._records[record.run_id] = record

    def get(self, run_id: str) -> MigrationRunRecord | None:
        """Return the immutable record associated with ``run_id``."""

        with self._lock:
            return self._records.get(run_id)
