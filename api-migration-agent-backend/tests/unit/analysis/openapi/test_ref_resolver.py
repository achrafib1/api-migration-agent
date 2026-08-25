"""Tests for local schema reference resolution."""

from __future__ import annotations

import pytest

from api_migration_agent.analysis.openapi.ref_resolver import LocalSchemaResolver
from api_migration_agent.core.exceptions import ReferenceResolutionError, UnsupportedReferenceError


def test_resolves_local_component_schema() -> None:
    """A supported local schema reference resolves deterministically."""

    schema = {"type": "object", "properties": {"id": {"type": "string"}}}
    resolver = LocalSchemaResolver({"components": {"schemas": {"Customer": schema}}})

    assert resolver.resolve("#/components/schemas/Customer") == schema


def test_decodes_json_pointer_token() -> None:
    """Escaped slashes and tildes in component names follow RFC 6901."""

    schema = {"type": "string"}
    resolver = LocalSchemaResolver({"components": {"schemas": {"A/B~C": schema}}})

    assert resolver.resolve("#/components/schemas/A~1B~0C") == schema


def test_resolves_local_parameter_component() -> None:
    """Reusable Parameter Objects resolve only through their approved section."""

    parameter = {"name": "currency", "in": "query", "required": True}
    resolver = LocalSchemaResolver({"components": {"parameters": {"Currency": parameter}}})

    assert resolver.resolve_parameter("#/components/parameters/Currency") == parameter


def test_resolves_local_request_body_component() -> None:
    """Reusable Request Body Objects resolve only through their approved section."""

    request_body = {"required": True, "content": {}}
    resolver = LocalSchemaResolver(
        {"components": {"requestBodies": {"CreateCustomer": request_body}}}
    )

    assert (
        resolver.resolve_request_body("#/components/requestBodies/CreateCustomer") == request_body
    )


def test_resolves_local_response_component() -> None:
    """Reusable Response Objects resolve only through their approved section."""

    response = {"description": "Customer", "content": {}}
    resolver = LocalSchemaResolver({"components": {"responses": {"Customer": response}}})

    assert resolver.resolve_response("#/components/responses/Customer") == response


def test_resolves_local_security_scheme_component() -> None:
    """Security schemes resolve only through their approved component section."""

    scheme = {"type": "apiKey", "in": "header", "name": "X-Key"}
    resolver = LocalSchemaResolver({"components": {"securitySchemes": {"Auth": scheme}}})

    assert resolver.resolve_security_scheme("#/components/securitySchemes/Auth") == scheme


@pytest.mark.parametrize(
    "reference",
    ["https://example.invalid/schema.json", "#/paths/~1customers", "Customer"],
)
def test_rejects_references_outside_local_schemas(reference: str) -> None:
    """Resolution never performs network access or traverses other sections."""

    with pytest.raises(UnsupportedReferenceError):
        LocalSchemaResolver({}).resolve(reference)


@pytest.mark.parametrize(
    "reference",
    ["#/components/schemas/", "#/components/schemas/Missing", "#/components/schemas/A~2B"],
)
def test_rejects_missing_or_malformed_local_reference(reference: str) -> None:
    """Ambiguous and absent targets fail rather than returning an empty schema."""

    with pytest.raises(ReferenceResolutionError):
        LocalSchemaResolver({"components": {"schemas": {}}}).resolve(reference)
