"""Enumerations used by deterministic API-change models."""

from __future__ import annotations

from enum import StrEnum


class ChangeCategory(StrEnum):
    """Supported API compatibility categories for the current slice."""

    OPERATION_ADDED = "operation_added"
    OPERATION_REMOVED = "operation_removed"
    PARAMETER_ADDED_OPTIONAL = "parameter_added_optional"
    PARAMETER_ADDED_REQUIRED = "parameter_added_required"
    PARAMETER_BECAME_REQUIRED = "parameter_became_required"
    PARAMETER_LOCATION_CHANGED = "parameter_location_changed"
    PARAMETER_REMOVED = "parameter_removed"
    PARAMETER_TYPE_CHANGED = "parameter_type_changed"
    REQUEST_BODY_BECAME_REQUIRED = "request_body_became_required"
    REQUEST_PROPERTY_ADDED_REQUIRED = "request_property_added_required"
    REQUEST_PROPERTY_REMOVED = "request_property_removed"
    REQUEST_PROPERTY_RENAMED = "request_property_renamed"
    REQUEST_PROPERTY_TYPE_CHANGED = "request_property_type_changed"
    RESPONSE_PROPERTY_TYPE_CHANGED = "response_property_type_changed"
    RESPONSE_REQUIRED_PROPERTY_REMOVED = "response_required_property_removed"
    RESPONSE_SCHEMA_REFERENCE_CHANGED = "response_schema_reference_changed"
    RESPONSE_STATUS_REMOVED = "response_status_removed"
    SECURITY_API_KEY_LOCATION_CHANGED = "security_api_key_location_changed"
    SECURITY_REQUIREMENT_ADDED = "security_requirement_added"
    SECURITY_SCHEME_REMOVED = "security_scheme_removed"
    SECURITY_SCHEME_TYPE_CHANGED = "security_scheme_type_changed"


class ChangeSeverity(StrEnum):
    """Engineering severity assigned by deterministic compatibility rules."""

    INFO = "info"
    HIGH = "high"


class HttpMethod(StrEnum):
    """HTTP methods permitted by OpenAPI Path Item objects."""

    GET = "get"
    PUT = "put"
    POST = "post"
    DELETE = "delete"
    OPTIONS = "options"
    HEAD = "head"
    PATCH = "patch"
    TRACE = "trace"


class ParameterLocation(StrEnum):
    """Locations supported by OpenAPI Parameter Objects."""

    QUERY = "query"
    HEADER = "header"
    PATH = "path"
    COOKIE = "cookie"


class ImpactConfidence(StrEnum):
    """Confidence derived from deterministic source-code context."""

    HIGH = "high"
    LOW = "low"


class SourceContext(StrEnum):
    """Syntactic context containing an exact repository match."""

    EXECUTABLE = "executable"
    COMMENT = "comment"
    DOCSTRING = "docstring"


class ActionStatus(StrEnum):
    """Human-review lifecycle for a proposed migration action."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class MigrationOperationType(StrEnum):
    """Narrow patch-operation families supported by the MVP."""

    REPLACE_ENDPOINT = "replace_endpoint"
    RENAME_KEY = "rename_key"
    ADD_APPROVED_FIELD = "add_approved_field"


class MigrationRisk(StrEnum):
    """Review risk assigned to a structured migration action."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PlanDecision(StrEnum):
    """Human decisions accepted by the review interrupt."""

    APPROVE = "approve"
    REJECT = "reject"


class WorkflowStatus(StrEnum):
    """Status values spanning planning, execution, validation, and reporting."""

    PENDING = "pending"
    ANALYZING = "analyzing"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    WORKSPACE_READY = "workspace_ready"
    PATCH_PROPOSED = "patch_proposed"
    PATCH_APPLIED = "patch_applied"
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"
    FINALIZED = "finalized"
    REJECTED = "rejected"
    FAILED = "failed"


class ValidationStatus(StrEnum):
    """Deterministic outcomes from the fixed workspace validation command."""

    PASSED = "passed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class ReportOutcome(StrEnum):
    """Terminal outcomes represented by deterministic migration reports."""

    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    FAILED = "failed"
