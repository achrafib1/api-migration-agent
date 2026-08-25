"""Pure business models shared by analysis and orchestration layers."""

from api_migration_agent.domain.api_change import ApiChange, ChangeEvidence
from api_migration_agent.domain.enums import (
    ChangeCategory,
    ChangeSeverity,
    HttpMethod,
    ImpactConfidence,
    ParameterLocation,
    SourceContext,
)
from api_migration_agent.domain.repository_impact import RepositoryFile, RepositoryImpact

__all__ = [
    "ApiChange",
    "ChangeCategory",
    "ChangeEvidence",
    "ChangeSeverity",
    "HttpMethod",
    "ImpactConfidence",
    "ParameterLocation",
    "RepositoryFile",
    "RepositoryImpact",
    "SourceContext",
]
