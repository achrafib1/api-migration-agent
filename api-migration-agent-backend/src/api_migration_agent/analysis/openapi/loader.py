"""Bounded JSON loader for the supported OpenAPI 3.x input subset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from api_migration_agent.core.config import get_settings
from api_migration_agent.core.exceptions import OpenApiDocumentError, OpenApiInputError

type OpenApiDocument = dict[str, JsonValue]


def load_openapi_document(path: Path, *, maximum_bytes: int | None = None) -> OpenApiDocument:
    """Load and minimally validate a JSON OpenAPI 3.x document.

    Args:
        path: Trusted caller-selected path to a JSON specification.
        maximum_bytes: Optional per-call size ceiling. The configured safe
            ceiling is used when omitted.

    Returns:
        A JSON mapping ready for deterministic analysis.

    Raises:
        OpenApiInputError: If the path is missing, non-JSON, non-regular, a
            symlink, oversized, unreadable, or contains invalid JSON.
        OpenApiDocumentError: If JSON lacks the supported OpenAPI 3.x root
            structure.
    """

    size_limit = maximum_bytes if maximum_bytes is not None else get_settings().maximum_spec_bytes
    if size_limit < 1:
        raise OpenApiInputError
    if path.suffix.lower() != ".json" or path.is_symlink() or not path.is_file():
        raise OpenApiInputError

    try:
        if path.stat().st_size > size_limit:
            raise OpenApiInputError
        raw_document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise OpenApiInputError from None

    if not isinstance(raw_document, dict):
        raise OpenApiDocumentError

    document = cast(OpenApiDocument, raw_document)
    _validate_root(document)
    return document


def _validate_root(document: OpenApiDocument) -> None:
    """Validate only invariants required by implemented comparison rules."""

    version = document.get("openapi")
    paths = document.get("paths")
    components = document.get("components")
    if not isinstance(version, str) or not version.startswith("3."):
        raise OpenApiDocumentError
    if not isinstance(paths, dict):
        raise OpenApiDocumentError
    if components is not None and not isinstance(components, dict):
        raise OpenApiDocumentError
