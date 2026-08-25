"""Sanitized domain exceptions for deterministic OpenAPI analysis."""

from __future__ import annotations


class ApiMigrationError(Exception):
    """Base exception carrying a stable code and a safe public message."""

    error_code = "API_MIGRATION_ERROR"
    public_message = "The migration operation could not be completed."

    def __init__(self) -> None:
        """Initialize the exception without accepting unsafe source content."""

        super().__init__(self.public_message)


class OpenApiInputError(ApiMigrationError):
    """Indicate that an OpenAPI input cannot be loaded safely."""

    error_code = "OPENAPI_INPUT_INVALID"
    public_message = "The OpenAPI input is invalid or unsupported."


class OpenApiDocumentError(ApiMigrationError):
    """Indicate that parsed JSON is not a supported OpenAPI document."""

    error_code = "OPENAPI_DOCUMENT_INVALID"
    public_message = "The OpenAPI document does not satisfy the supported structure."


class UnsupportedReferenceError(ApiMigrationError):
    """Indicate that a reference is outside supported local schema references."""

    error_code = "OPENAPI_REFERENCE_UNSUPPORTED"
    public_message = "The OpenAPI reference is unsupported."


class ReferenceResolutionError(ApiMigrationError):
    """Indicate that a supported local reference has no unambiguous target."""

    error_code = "OPENAPI_REFERENCE_UNRESOLVED"
    public_message = "The OpenAPI reference could not be resolved."


class RepositoryBoundaryError(ApiMigrationError):
    """Indicate that repository analysis would leave its approved boundary."""

    error_code = "REPOSITORY_BOUNDARY_VIOLATION"
    public_message = "The repository path is outside the approved analysis boundary."


class RepositorySourceError(ApiMigrationError):
    """Indicate that an approved source file cannot be analyzed deterministically."""

    error_code = "REPOSITORY_SOURCE_INVALID"
    public_message = "A repository source file is invalid or unsupported."


class PlanningValidationError(ApiMigrationError):
    """Indicate that structured planner output violates deterministic evidence."""

    error_code = "PLANNING_OUTPUT_INVALID"
    public_message = "The proposed migration plan is invalid or unsupported."


class ModelConfigurationError(ApiMigrationError):
    """Indicate that the configured planning provider cannot be initialized."""

    error_code = "MODEL_CONFIGURATION_INVALID"
    public_message = "The planning model configuration is incomplete or invalid."


class HumanDecisionError(ApiMigrationError):
    """Indicate that a review decision is incomplete or inconsistent."""

    error_code = "HUMAN_DECISION_INVALID"
    public_message = "The human review decision is invalid or incomplete."


class WorkspaceBoundaryError(ApiMigrationError):
    """Indicate that isolated workspace creation violated confinement rules."""

    error_code = "WORKSPACE_BOUNDARY_VIOLATION"
    public_message = "The isolated migration workspace could not be created safely."


class PatchApplicationError(ApiMigrationError):
    """Indicate that an approved patch cannot be applied deterministically."""

    error_code = "PATCH_APPLICATION_FAILED"
    public_message = "The approved patch could not be applied safely."


class MigrationRunNotFoundError(ApiMigrationError):
    """Indicate that process-local run metadata is unavailable."""

    error_code = "MIGRATION_RUN_NOT_FOUND"
    public_message = "The requested migration run was not found."


class MigrationTargetNotFoundError(ApiMigrationError):
    """Indicate that a requested stable target identifier is unavailable."""

    error_code = "MIGRATION_TARGET_NOT_FOUND"
    public_message = "The requested migration target is not available."


class MigrationTargetConfigurationError(ApiMigrationError):
    """Indicate that a server-approved target violates confinement requirements."""

    error_code = "MIGRATION_TARGET_CONFIGURATION_INVALID"
    public_message = "A configured migration target is invalid or unavailable."
