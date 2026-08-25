"""OpenAPI loading, reference resolution, and compatibility comparison."""

from api_migration_agent.analysis.openapi.comparator import (
    compare_api_documents,
    compare_operations,
)
from api_migration_agent.analysis.openapi.loader import OpenApiDocument, load_openapi_document
from api_migration_agent.analysis.openapi.ref_resolver import LocalSchemaResolver

__all__ = [
    "LocalSchemaResolver",
    "OpenApiDocument",
    "compare_api_documents",
    "compare_operations",
    "load_openapi_document",
]
