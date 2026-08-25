"""Centralized, side-effect-free backend configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Define immutable application and model-provider configuration.

    Secret values remain wrapped until the final provider-library boundary. The
    settings object must never be serialized, logged, or added to graph state.
    Construction is local and performs no network or credential validation.
    """

    model_config = SettingsConfigDict(
        env_prefix="API_MIGRATION_AGENT_",
        extra="ignore",
        frozen=True,
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    maximum_spec_bytes: int = Field(default=5_000_000, ge=1, le=20_000_000)
    planning_model: str = Field(default="gemini/gemini-2.5-flash", min_length=1)
    planning_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    planning_api_key: SecretStr | None = None
    allowed_origins: tuple[str, ...] = ("http://localhost:3000",)

    @field_validator("allowed_origins")
    @classmethod
    def validate_allowed_origins(cls, origins: tuple[str, ...]) -> tuple[str, ...]:
        """Require explicit HTTP origins without wildcards, paths, or credentials."""

        if not origins:
            raise ValueError("At least one frontend origin must be configured.")
        for origin in origins:
            if (
                "*" in origin
                or "@" in origin
                or not origin.startswith(("http://", "https://"))
                or origin.rstrip("/").count("/") != 2
            ):
                raise ValueError("Frontend origins must be explicit HTTP origins.")
        return tuple(dict.fromkeys(origin.rstrip("/") for origin in origins))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance.

    Returns:
        The lazily constructed application settings. Construction performs no
        network access and validates no external credentials.
    """

    return Settings()
