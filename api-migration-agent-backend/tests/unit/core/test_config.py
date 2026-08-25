"""Tests for immutable, secret-safe backend configuration."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from api_migration_agent.core.config import Settings


def test_settings_keep_provider_credential_secret_wrapped() -> None:
    """Provider credentials remain SecretStr until the external constructor."""

    settings = Settings(planning_api_key=SecretStr("example-not-a-real-key"))

    assert isinstance(settings.planning_api_key, SecretStr)


def test_allowed_origins_are_normalized_and_deduplicated() -> None:
    """CORS configuration remains exact and stable for middleware wiring."""

    settings = Settings(allowed_origins=("http://localhost:3000/", "http://localhost:3000"))

    assert settings.allowed_origins == ("http://localhost:3000",)


@pytest.mark.parametrize(
    "origin",
    ["*", "https://*.example.com", "https://user@example.com", "file:///frontend"],
)
def test_rejects_unsafe_or_non_http_origins(origin: str) -> None:
    """Wildcards, embedded identity, and non-HTTP origins are forbidden."""

    with pytest.raises(ValidationError):
        Settings(allowed_origins=(origin,))
