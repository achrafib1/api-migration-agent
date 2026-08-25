"""Deterministic comparison entry points for supported OpenAPI rules."""

from __future__ import annotations

from api_migration_agent.analysis.openapi.loader import OpenApiDocument
from api_migration_agent.analysis.openapi.rules.operations import compare_operation_sets
from api_migration_agent.analysis.openapi.rules.parameters import compare_parameters
from api_migration_agent.analysis.openapi.rules.request_bodies import compare_request_bodies
from api_migration_agent.analysis.openapi.rules.responses import compare_responses
from api_migration_agent.analysis.openapi.rules.security import compare_security
from api_migration_agent.domain.api_change import ApiChange


def compare_operations(
    old_document: OpenApiDocument,
    new_document: OpenApiDocument,
) -> tuple[ApiChange, ...]:
    """Compare operation sets from two validated OpenAPI documents.

    Args:
        old_document: Baseline OpenAPI document.
        new_document: Revision OpenAPI document.

    Returns:
        Stable, path-and-method-sorted operation changes.
    """

    return compare_operation_sets(old_document, new_document)


def compare_api_documents(
    old_document: OpenApiDocument,
    new_document: OpenApiDocument,
) -> tuple[ApiChange, ...]:
    """Run every implemented compatibility rule in deterministic order.

    Args:
        old_document: Validated baseline contract.
        new_document: Validated revision contract.

    Returns:
        Operation, parameter, request-body, response, and security facts. Each
        rule family provides stable ordering internally.
    """

    return (
        *compare_operation_sets(old_document, new_document),
        *compare_parameters(old_document, new_document),
        *compare_request_bodies(old_document, new_document),
        *compare_responses(old_document, new_document),
        *compare_security(old_document, new_document),
    )
