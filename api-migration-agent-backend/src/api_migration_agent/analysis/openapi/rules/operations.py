"""Rules detecting added and removed HTTP operations."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from api_migration_agent.analysis.openapi.loader import OpenApiDocument
from api_migration_agent.domain.api_change import ApiChange, ChangeEvidence
from api_migration_agent.domain.enums import ChangeCategory, ChangeSeverity, HttpMethod

OperationKey = tuple[str, HttpMethod]


@dataclass(frozen=True, order=True, slots=True)
class OperationPair:
    """Pair baseline and revision operations using deterministic evidence.

    Exact path-and-method matches are always paired. Moved operations are paired
    only when one baseline and one revision operation share a non-empty,
    document-unique ``operationId``.
    """

    old_path: str
    old_method: HttpMethod
    new_path: str
    new_method: HttpMethod


def compare_operation_sets(
    old_document: OpenApiDocument,
    new_document: OpenApiDocument,
) -> tuple[ApiChange, ...]:
    """Return deterministic additions and removals between operation sets."""

    old_operations = extract_operations(old_document)
    new_operations = extract_operations(new_document)
    changes: list[ApiChange] = []

    for path, method in sorted(old_operations - new_operations):
        changes.append(_removed_operation(path, method))
    for path, method in sorted(new_operations - old_operations):
        changes.append(_added_operation(path, method))
    return tuple(changes)


def extract_operations(document: OpenApiDocument) -> set[OperationKey]:
    """Extract recognized methods while ignoring Path Item metadata.

    Args:
        document: Validated OpenAPI root document.

    Returns:
        Unique path-and-method coordinates for structurally valid operations.
    """

    paths = document.get("paths")
    if not isinstance(paths, Mapping):
        return set()

    operations: set[OperationKey] = set()
    for path, path_item in paths.items():
        if not isinstance(path, str) or not isinstance(path_item, Mapping):
            continue
        for raw_method, operation in path_item.items():
            try:
                method = HttpMethod(str(raw_method).lower())
            except ValueError:
                continue
            # An OpenAPI operation must be an object. Scalars are malformed and
            # cannot serve as confirmed compatibility evidence.
            if isinstance(operation, Mapping):
                operations.add((path, method))
    return operations


def match_operations(
    old_document: OpenApiDocument,
    new_document: OpenApiDocument,
) -> tuple[OperationPair, ...]:
    """Match operations for nested contract comparison without guessing.

    Args:
        old_document: Baseline OpenAPI document.
        new_document: Revision OpenAPI document.

    Returns:
        Exact matches plus uniquely matched moved operations, in stable order.
    """

    old_operations = extract_operations(old_document)
    new_operations = extract_operations(new_document)
    exact = old_operations & new_operations
    pairs = [OperationPair(path, method, path, method) for path, method in sorted(exact)]

    old_by_id = _unique_operation_ids(old_document, old_operations - exact)
    new_by_id = _unique_operation_ids(new_document, new_operations - exact)
    for operation_id in sorted(old_by_id.keys() & new_by_id.keys()):
        old_path, old_method = old_by_id[operation_id]
        new_path, new_method = new_by_id[operation_id]
        pairs.append(OperationPair(old_path, old_method, new_path, new_method))
    return tuple(sorted(pairs))


def get_operation(
    document: OpenApiDocument,
    path: str,
    method: HttpMethod,
) -> Mapping[str, Any] | None:
    """Return a structurally valid operation object at exact coordinates."""

    paths = document.get("paths")
    path_item = paths.get(path) if isinstance(paths, Mapping) else None
    operation = path_item.get(method.value) if isinstance(path_item, Mapping) else None
    return operation if isinstance(operation, Mapping) else None


def _unique_operation_ids(
    document: OpenApiDocument,
    operations: set[OperationKey],
) -> dict[str, OperationKey]:
    """Return only operationIds that occur exactly once in the supplied set."""

    candidates: dict[str, list[OperationKey]] = {}
    for path, method in sorted(operations):
        operation = get_operation(document, path, method)
        operation_id = operation.get("operationId") if operation is not None else None
        if isinstance(operation_id, str) and operation_id:
            candidates.setdefault(operation_id, []).append((path, method))
    return {
        operation_id: coordinates[0]
        for operation_id, coordinates in candidates.items()
        if len(coordinates) == 1
    }


def _removed_operation(path: str, method: HttpMethod) -> ApiChange:
    """Build a breaking removed-operation fact."""

    return ApiChange(
        id=_change_id(ChangeCategory.OPERATION_REMOVED, path, method),
        category=ChangeCategory.OPERATION_REMOVED,
        severity=ChangeSeverity.HIGH,
        breaking=True,
        path=path,
        method=method,
        old_value={"path": path, "method": method.value},
        new_value=None,
        description=f"{method.value.upper()} {path} is no longer present in the revised API.",
        evidence=(
            ChangeEvidence(
                old_document_pointer=_operation_pointer(path, method),
                summary=(
                    "Operation exists in the baseline document and is absent from the revision."
                ),
            ),
        ),
    )


def _added_operation(path: str, method: HttpMethod) -> ApiChange:
    """Build a non-breaking added-operation fact."""

    return ApiChange(
        id=_change_id(ChangeCategory.OPERATION_ADDED, path, method),
        category=ChangeCategory.OPERATION_ADDED,
        severity=ChangeSeverity.INFO,
        breaking=False,
        path=path,
        method=method,
        old_value=None,
        new_value={"path": path, "method": method.value},
        description=f"{method.value.upper()} {path} is newly present in the revised API.",
        evidence=(
            ChangeEvidence(
                new_document_pointer=_operation_pointer(path, method),
                summary=(
                    "Operation is absent from the baseline document and exists in the revision."
                ),
            ),
        ),
    )


def _change_id(category: ChangeCategory, path: str, method: HttpMethod) -> str:
    """Generate a stable identifier from non-sensitive change coordinates."""

    identity = f"{category.value}\x00{path}\x00{method.value}".encode()
    return f"CHANGE-{hashlib.sha256(identity).hexdigest()[:12].upper()}"


def _operation_pointer(path: str, method: HttpMethod) -> str:
    """Return the RFC 6901 pointer for an operation."""

    escaped_path = path.replace("~", "~0").replace("/", "~1")
    return f"#/paths/{escaped_path}/{method.value}"
