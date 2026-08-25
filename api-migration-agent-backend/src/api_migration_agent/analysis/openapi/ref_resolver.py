"""Strict resolver for supported local OpenAPI component references."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from api_migration_agent.core.exceptions import ReferenceResolutionError, UnsupportedReferenceError

_SCHEMA_PREFIX: Final = "#/components/schemas/"
_PARAMETER_PREFIX: Final = "#/components/parameters/"
_REQUEST_BODY_PREFIX: Final = "#/components/requestBodies/"
_RESPONSE_PREFIX: Final = "#/components/responses/"
_SECURITY_SCHEME_PREFIX: Final = "#/components/securitySchemes/"
_MAX_SCHEMA_REFERENCE_DEPTH: Final = 32


class LocalSchemaResolver:
    """Resolve local schema references without filesystem or network access."""

    def __init__(self, document: Mapping[str, Any]) -> None:
        """Bind the resolver to one validated OpenAPI document."""

        self._document = document

    def resolve(self, reference: str) -> Mapping[str, Any]:
        """Resolve one supported local schema reference.

        Raises:
            UnsupportedReferenceError: If the reference is remote or outside
                ``components/schemas``.
            ReferenceResolutionError: If pointer syntax is malformed or its
                target is absent or not a schema object.
        """

        return self._resolve_component(reference, prefix=_SCHEMA_PREFIX, section="schemas")

    def resolve_parameter(self, reference: str) -> Mapping[str, Any]:
        """Resolve one local ``components/parameters`` reference.

        Args:
            reference: Local JSON reference for a reusable Parameter Object.

        Returns:
            The referenced Parameter Object.

        Raises:
            UnsupportedReferenceError: If the reference is not within the
                supported local parameter component section.
            ReferenceResolutionError: If the pointer or target is invalid.
        """

        return self._resolve_component(
            reference,
            prefix=_PARAMETER_PREFIX,
            section="parameters",
        )

    def resolve_request_body(self, reference: str) -> Mapping[str, Any]:
        """Resolve one local ``components/requestBodies`` reference.

        Args:
            reference: Local JSON reference for a reusable Request Body Object.

        Returns:
            The referenced Request Body Object.

        Raises:
            UnsupportedReferenceError: If the reference is outside the approved
                local request-body component section.
            ReferenceResolutionError: If the pointer or target is invalid.
        """

        return self._resolve_component(
            reference,
            prefix=_REQUEST_BODY_PREFIX,
            section="requestBodies",
        )

    def resolve_response(self, reference: str) -> Mapping[str, Any]:
        """Resolve one local ``components/responses`` reference.

        Args:
            reference: Local JSON reference for a reusable Response Object.

        Returns:
            The referenced Response Object.

        Raises:
            UnsupportedReferenceError: If the reference is outside the approved
                local response component section.
            ReferenceResolutionError: If the pointer or target is invalid.
        """

        return self._resolve_component(
            reference,
            prefix=_RESPONSE_PREFIX,
            section="responses",
        )

    def resolve_security_scheme(self, reference: str) -> Mapping[str, Any]:
        """Resolve one local ``components/securitySchemes`` reference.

        Args:
            reference: Local JSON reference for a reusable Security Scheme Object.

        Returns:
            The referenced Security Scheme Object.

        Raises:
            UnsupportedReferenceError: If the reference is outside the approved
                local security-scheme component section.
            ReferenceResolutionError: If the pointer or target is invalid.
        """

        return self._resolve_component(
            reference,
            prefix=_SECURITY_SCHEME_PREFIX,
            section="securitySchemes",
        )

    def resolve_schema_object(self, schema: Mapping[str, Any]) -> Mapping[str, Any]:
        """Resolve a chain of local schema references with cycle protection.

        Args:
            schema: Inline schema or schema containing a local ``$ref``.

        Returns:
            The first schema object that does not contain a ``$ref``.

        Raises:
            UnsupportedReferenceError: If a reference leaves the approved local
                schema component section.
            ReferenceResolutionError: If a target is absent, a cycle is found,
                or the fixed reference-depth bound is exceeded.
        """

        current = schema
        visited: set[str] = set()
        for _ in range(_MAX_SCHEMA_REFERENCE_DEPTH):
            reference = current.get("$ref")
            if not isinstance(reference, str):
                return current
            if reference in visited:
                raise ReferenceResolutionError
            visited.add(reference)
            current = self.resolve(reference)
        raise ReferenceResolutionError

    def _resolve_component(
        self,
        reference: str,
        *,
        prefix: str,
        section: str,
    ) -> Mapping[str, Any]:
        """Resolve a component from one explicitly approved section."""

        if not reference.startswith(prefix):
            raise UnsupportedReferenceError

        encoded_name = reference.removeprefix(prefix)
        if not encoded_name or "/" in encoded_name:
            raise ReferenceResolutionError

        component_name = _decode_pointer_token(encoded_name)
        components = self._document.get("components")
        component_section = components.get(section) if isinstance(components, Mapping) else None
        component = (
            component_section.get(component_name)
            if isinstance(component_section, Mapping)
            else None
        )
        if not isinstance(component, Mapping):
            raise ReferenceResolutionError
        return component


def _decode_pointer_token(token: str) -> str:
    """Decode one RFC 6901 token while rejecting invalid escapes."""

    index = 0
    decoded: list[str] = []
    while index < len(token):
        character = token[index]
        if character != "~":
            decoded.append(character)
            index += 1
            continue
        if index + 1 >= len(token) or token[index + 1] not in {"0", "1"}:
            raise ReferenceResolutionError
        decoded.append("~" if token[index + 1] == "0" else "/")
        index += 2
    return "".join(decoded)
