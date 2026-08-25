"""Deterministic OpenAPI security-requirement compatibility rules.

The analyzer honors root-level security inheritance and operation-level
overrides, including ``security: []`` for explicit anonymous access. It compares
only structural scheme metadata and requirement names/scopes; descriptions and
credential values are never accepted or emitted.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from pydantic import JsonValue

from api_migration_agent.analysis.openapi.loader import OpenApiDocument
from api_migration_agent.analysis.openapi.ref_resolver import LocalSchemaResolver
from api_migration_agent.analysis.openapi.rules.operations import match_operations
from api_migration_agent.core.exceptions import OpenApiDocumentError
from api_migration_agent.domain.api_change import ApiChange, ChangeEvidence
from api_migration_agent.domain.enums import ChangeCategory, ChangeSeverity, HttpMethod

type SecurityAlternative = tuple[tuple[str, tuple[str, ...]], ...]
type SecurityRequirements = tuple[SecurityAlternative, ...]


@dataclass(frozen=True, slots=True)
class _EffectiveSecurity:
    """Canonical security alternatives and their source location."""

    requirements: SecurityRequirements
    pointer: str

    @property
    def permits_anonymous(self) -> bool:
        """Return whether at least one alternative requires no scheme."""

        return not self.requirements or () in self.requirements


@dataclass(frozen=True, slots=True)
class _SecuritySchemeFact:
    """Minimal non-sensitive metadata for one Security Scheme Object."""

    name: str
    scheme_type: str | None
    api_key_location: str | None
    pointer: str

    def as_json(self) -> JsonValue:
        """Return structural scheme metadata without descriptions or values."""

        return cast(
            JsonValue,
            {
                "name": self.name,
                "type": self.scheme_type,
                "in": self.api_key_location,
            },
        )


def compare_security(
    old_document: OpenApiDocument,
    new_document: OpenApiDocument,
) -> tuple[ApiChange, ...]:
    """Compare global security schemes and effective operation requirements.

    Args:
        old_document: Validated baseline OpenAPI contract.
        new_document: Validated revision OpenAPI contract.

    Returns:
        Stable scheme-level facts followed by operation-level requirement facts.

    Raises:
        OpenApiDocumentError: If an explicit security requirement has malformed
            structure and therefore cannot be compared deterministically.
    """

    old_resolver = LocalSchemaResolver(old_document)
    new_resolver = LocalSchemaResolver(new_document)
    old_schemes = _extract_security_schemes(old_document, old_resolver)
    new_schemes = _extract_security_schemes(new_document, new_resolver)
    changes: list[ApiChange] = []

    for name in sorted(old_schemes.keys() - new_schemes.keys()):
        changes.append(_scheme_removed(old_schemes[name]))
    for name in sorted(old_schemes.keys() & new_schemes.keys()):
        old_scheme = old_schemes[name]
        new_scheme = new_schemes[name]
        if (
            old_scheme.scheme_type is not None
            and new_scheme.scheme_type is not None
            and old_scheme.scheme_type != new_scheme.scheme_type
        ):
            changes.append(_scheme_type_changed(old_scheme, new_scheme))
        if (
            old_scheme.scheme_type == "apiKey"
            and new_scheme.scheme_type == "apiKey"
            and old_scheme.api_key_location is not None
            and new_scheme.api_key_location is not None
            and old_scheme.api_key_location != new_scheme.api_key_location
        ):
            changes.append(_api_key_location_changed(old_scheme, new_scheme))

    for pair in match_operations(old_document, new_document):
        old_security = _effective_security(old_document, pair.old_path, pair.old_method)
        new_security = _effective_security(new_document, pair.new_path, pair.new_method)
        if (
            old_security.requirements != new_security.requirements
            and not new_security.permits_anonymous
        ):
            changes.append(
                _security_requirement_added(
                    pair.new_path,
                    pair.new_method,
                    old_security,
                    new_security,
                )
            )
    return tuple(changes)


def _extract_security_schemes(
    document: OpenApiDocument,
    resolver: LocalSchemaResolver,
) -> dict[str, _SecuritySchemeFact]:
    """Extract supported structural fields from component security schemes."""

    components = document.get("components")
    raw_schemes = components.get("securitySchemes") if isinstance(components, Mapping) else None
    if not isinstance(raw_schemes, Mapping):
        return {}

    schemes: dict[str, _SecuritySchemeFact] = {}
    for name, raw_scheme in raw_schemes.items():
        if not isinstance(name, str) or not isinstance(raw_scheme, Mapping):
            continue
        reference = raw_scheme.get("$ref")
        scheme = (
            resolver.resolve_security_scheme(reference)
            if isinstance(reference, str)
            else raw_scheme
        )
        raw_type = scheme.get("type")
        raw_location = scheme.get("in")
        schemes[name] = _SecuritySchemeFact(
            name=name,
            scheme_type=raw_type if isinstance(raw_type, str) else None,
            api_key_location=raw_location if isinstance(raw_location, str) else None,
            pointer=f"#/components/securitySchemes/{_escape_pointer(name)}",
        )
    return schemes


def _effective_security(
    document: OpenApiDocument,
    path: str,
    method: HttpMethod,
) -> _EffectiveSecurity:
    """Return operation security after applying OpenAPI root inheritance."""

    paths = document.get("paths")
    path_item = paths.get(path) if isinstance(paths, Mapping) else None
    operation = path_item.get(method.value) if isinstance(path_item, Mapping) else None
    if not isinstance(operation, Mapping):
        return _EffectiveSecurity((), "#/security")

    if "security" in operation:
        raw_security = operation.get("security")
        pointer = f"#/paths/{_escape_pointer(path)}/{method.value}/security"
    else:
        raw_security = document.get("security")
        pointer = "#/security"
    return _EffectiveSecurity(_normalize_requirements(raw_security), pointer)


def _normalize_requirements(raw_security: Any) -> SecurityRequirements:
    """Validate and canonicalize OpenAPI Security Requirement Objects."""

    if raw_security is None:
        return ()
    if not isinstance(raw_security, Sequence) or isinstance(raw_security, (str, bytes)):
        raise OpenApiDocumentError

    alternatives: set[SecurityAlternative] = set()
    for raw_alternative in raw_security:
        if not isinstance(raw_alternative, Mapping):
            raise OpenApiDocumentError
        requirements: list[tuple[str, tuple[str, ...]]] = []
        for scheme_name, raw_scopes in raw_alternative.items():
            if (
                not isinstance(scheme_name, str)
                or not isinstance(raw_scopes, Sequence)
                or isinstance(raw_scopes, (str, bytes))
            ):
                raise OpenApiDocumentError
            if not all(isinstance(scope, str) for scope in raw_scopes):
                raise OpenApiDocumentError
            requirements.append((scheme_name, tuple(sorted(raw_scopes))))
        alternatives.add(tuple(sorted(requirements)))
    return tuple(sorted(alternatives))


def _requirements_as_json(requirements: SecurityRequirements) -> JsonValue:
    """Convert canonical alternatives into their safe JSON representation."""

    value = [
        {scheme_name: list(scopes) for scheme_name, scopes in alternative}
        for alternative in requirements
    ]
    return cast(JsonValue, value)


def _scheme_removed(old_scheme: _SecuritySchemeFact) -> ApiChange:
    """Build a component-level removed-security-scheme fact."""

    return _global_change(
        category=ChangeCategory.SECURITY_SCHEME_REMOVED,
        scheme=old_scheme,
        old_value=old_scheme.as_json(),
        new_value=None,
        old_pointer=old_scheme.pointer,
        new_pointer=None,
        description=f"Security scheme '{old_scheme.name}' was removed.",
        summary="The named scheme exists in baseline components and not in revision components.",
    )


def _scheme_type_changed(
    old_scheme: _SecuritySchemeFact,
    new_scheme: _SecuritySchemeFact,
) -> ApiChange:
    """Build a component-level security-scheme type-change fact."""

    return _global_change(
        category=ChangeCategory.SECURITY_SCHEME_TYPE_CHANGED,
        scheme=new_scheme,
        old_value=old_scheme.as_json(),
        new_value=new_scheme.as_json(),
        old_pointer=old_scheme.pointer,
        new_pointer=new_scheme.pointer,
        description=(
            f"Security scheme '{new_scheme.name}' changed type from "
            f"'{old_scheme.scheme_type}' to '{new_scheme.scheme_type}'."
        ),
        summary="The matched security scheme has different explicit type values.",
    )


def _api_key_location_changed(
    old_scheme: _SecuritySchemeFact,
    new_scheme: _SecuritySchemeFact,
) -> ApiChange:
    """Build an API-key location-change fact."""

    return _global_change(
        category=ChangeCategory.SECURITY_API_KEY_LOCATION_CHANGED,
        scheme=new_scheme,
        old_value=old_scheme.as_json(),
        new_value=new_scheme.as_json(),
        old_pointer=old_scheme.pointer,
        new_pointer=new_scheme.pointer,
        description=(
            f"API-key scheme '{new_scheme.name}' moved from '{old_scheme.api_key_location}' "
            f"to '{new_scheme.api_key_location}'."
        ),
        summary="The matched apiKey scheme has different explicit location values.",
    )


def _security_requirement_added(
    path: str,
    method: HttpMethod,
    old_security: _EffectiveSecurity,
    new_security: _EffectiveSecurity,
) -> ApiChange:
    """Build an operation-level added or tightened security fact."""

    identity = f"security_requirement\x00{path}\x00{method.value}".encode()
    return ApiChange(
        id=f"CHANGE-{hashlib.sha256(identity).hexdigest()[:12].upper()}",
        category=ChangeCategory.SECURITY_REQUIREMENT_ADDED,
        severity=ChangeSeverity.HIGH,
        breaking=True,
        path=path,
        method=method,
        location="security.requirement",
        old_value=_requirements_as_json(old_security.requirements),
        new_value=_requirements_as_json(new_security.requirements),
        description=(
            f"Security requirements were added or tightened for {method.value.upper()} {path}."
        ),
        evidence=(
            ChangeEvidence(
                old_document_pointer=old_security.pointer,
                new_document_pointer=new_security.pointer,
                summary=(
                    "The effective canonical requirement alternatives differ and the revision "
                    "does not permit anonymous access."
                ),
            ),
        ),
    )


def _global_change(
    *,
    category: ChangeCategory,
    scheme: _SecuritySchemeFact,
    old_value: JsonValue,
    new_value: JsonValue,
    old_pointer: str | None,
    new_pointer: str | None,
    description: str,
    summary: str,
) -> ApiChange:
    """Create a component-level security change without fake operation data."""

    identity = f"{category.value}\x00{scheme.name}".encode()
    return ApiChange(
        id=f"CHANGE-{hashlib.sha256(identity).hexdigest()[:12].upper()}",
        category=category,
        severity=ChangeSeverity.HIGH,
        breaking=True,
        path=None,
        method=None,
        location="components.securitySchemes",
        old_value=old_value,
        new_value=new_value,
        description=description,
        evidence=(
            ChangeEvidence(
                old_document_pointer=old_pointer,
                new_document_pointer=new_pointer,
                summary=summary,
            ),
        ),
    )


def _escape_pointer(value: str) -> str:
    """Escape one JSON Pointer token according to RFC 6901."""

    return value.replace("~", "~0").replace("/", "~1")
