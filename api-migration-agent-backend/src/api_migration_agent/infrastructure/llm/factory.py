"""Construct the configured LangChain chat model through LiteLLM."""

from __future__ import annotations

from typing import Any, Protocol

from langchain_litellm import ChatLiteLLM

from api_migration_agent.core.config import Settings
from api_migration_agent.core.exceptions import ModelConfigurationError


class StructuredChatModel(Protocol):
    """Minimal LangChain capability required by the planning adapter."""

    def with_structured_output(self, schema: type[Any]) -> Any:
        """Return a runnable that validates responses against ``schema``."""

        ...


def create_planning_model(settings: Settings) -> StructuredChatModel:
    """Create a model-agnostic LiteLLM chat client for migration planning.

    Args:
        settings: Immutable application configuration. It is not retained by
            this function or added to workflow state.

    Returns:
        A LangChain chat model supporting Pydantic structured output.

    Raises:
        ModelConfigurationError: If the provider credential is not configured.
    """

    if settings.planning_api_key is None:
        raise ModelConfigurationError
    return ChatLiteLLM(
        model=settings.planning_model,
        temperature=settings.planning_temperature,
        api_key=settings.planning_api_key.get_secret_value(),
    )
