"""Structured logging with an explicit metadata allowlist.

The formatter emits only operational metadata added by :func:`log_event`. It
never serializes source text, specification content, exception messages,
settings objects, or arbitrary dictionaries.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Final

type LogValue = str | int | float | bool | None

ALLOWED_LOG_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "event",
        "run_id",
        "stage",
        "status",
        "change_count",
        "affected_file_count",
        "modified_file_count",
        "test_count",
        "passed_test_count",
        "failed_test_count",
        "duration_ms",
        "retry_count",
        "exception_type",
        "error_code",
    }
)
_CONTEXT_ATTRIBUTE: Final = "safe_context"


class AllowlistedJsonFormatter(logging.Formatter):
    """Render a log record as JSON containing allowlisted fields only."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize safe context without including the record message.

        Args:
            record: Standard-library log record created by :func:`log_event`.

        Returns:
            A compact JSON object suitable for local structured logs.
        """

        context = getattr(record, _CONTEXT_ATTRIBUTE, {})
        safe_context = context if isinstance(context, Mapping) else {}
        payload: dict[str, LogValue] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
        }
        payload.update(
            {
                key: value
                for key, value in safe_context.items()
                if key in ALLOWED_LOG_FIELDS
                and isinstance(value, (str, int, float, bool, type(None)))
            }
        )
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def configure_logging(*, level: int = logging.INFO) -> logging.Logger:
    """Configure and return the package logger for local structured output.

    Args:
        level: Standard-library logging threshold.

    Returns:
        The configured package logger. Repeated calls do not duplicate the
        package-owned handler.
    """

    logger = logging.getLogger("api_migration_agent")
    logger.setLevel(level)
    logger.propagate = False

    if not any(getattr(handler, "_api_migration_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(AllowlistedJsonFormatter())
        # This private marker preserves handlers installed by host applications.
        handler._api_migration_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)

    return logger


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: LogValue,
) -> None:
    """Emit one structured event after enforcing the logging allowlist.

    Args:
        logger: Destination logger.
        level: Standard-library log level.
        event: Stable machine-readable event name.
        **fields: Additional allowlisted operational metadata.

    Raises:
        ValueError: If a caller attempts to attach a non-allowlisted field.
    """

    unknown_fields = fields.keys() - ALLOWED_LOG_FIELDS
    if unknown_fields:
        # Keep the error constant: rejected field names may originate in
        # untrusted integrations and should not be reflected into output.
        raise ValueError("Structured log event contains a non-allowlisted field.")

    context: dict[str, LogValue] = {"event": event, **fields}
    logger.log(level, event, extra={_CONTEXT_ATTRIBUTE: context})
