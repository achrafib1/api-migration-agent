"""Tests for bounded and sanitized OpenAPI JSON loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from api_migration_agent.analysis.openapi.loader import load_openapi_document
from api_migration_agent.core.exceptions import OpenApiDocumentError, OpenApiInputError


def _write_json(path: Path, value: object) -> Path:
    """Write one synthetic, credential-free JSON test document."""

    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_loads_supported_openapi_document(tmp_path: Path) -> None:
    """A minimal OpenAPI 3.x document is accepted."""

    path = _write_json(tmp_path / "api.json", {"openapi": "3.1.0", "paths": {}})

    assert load_openapi_document(path)["openapi"] == "3.1.0"


@pytest.mark.parametrize("suffix", [".yaml", ".txt"])
def test_rejects_non_json_input(tmp_path: Path, suffix: str) -> None:
    """The MVP must not imply support for YAML or arbitrary text."""

    path = _write_json(tmp_path / f"api{suffix}", {"openapi": "3.1.0", "paths": {}})

    with pytest.raises(OpenApiInputError, match="invalid or unsupported"):
        load_openapi_document(path)


def test_rejects_oversized_input(tmp_path: Path) -> None:
    """The loader enforces its byte ceiling before parsing content."""

    path = _write_json(tmp_path / "api.json", {"openapi": "3.1.0", "paths": {}})

    with pytest.raises(OpenApiInputError):
        load_openapi_document(path, maximum_bytes=1)


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"paths": {}},
        {"openapi": "2.0", "paths": {}},
        {"openapi": "3.1.0"},
        {"openapi": "3.1.0", "paths": [], "components": {}},
        {"openapi": "3.1.0", "paths": {}, "components": []},
    ],
)
def test_rejects_unsupported_root_structure(tmp_path: Path, document: object) -> None:
    """Malformed roots fail with a stable sanitized domain exception."""

    path = _write_json(tmp_path / "api.json", document)

    with pytest.raises(OpenApiDocumentError, match="supported structure"):
        load_openapi_document(path)
