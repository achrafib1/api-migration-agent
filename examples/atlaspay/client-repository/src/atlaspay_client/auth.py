"""Non-sensitive authentication metadata for the AtlasPay v1 client."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AtlasPayApiKeyAuthMetadata:
    """Describe v1 authentication without storing or receiving its value."""

    scheme_name: str
    header_name: str


ATLASPAY_V1_AUTH = AtlasPayApiKeyAuthMetadata(
    scheme_name="ApiKeyAuth",
    header_name="X-API-Key",
)
