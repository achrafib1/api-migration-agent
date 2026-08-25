# Backend configuration

Configuration is centralized in `api_migration_agent.core.config.Settings`.
Only explicitly named variables are read; the environment is never enumerated.

| Variable | Safe example | Purpose |
| --- | --- | --- |
| `API_MIGRATION_AGENT_LOG_LEVEL` | `INFO` | Local structured-log threshold |
| `API_MIGRATION_AGENT_MAXIMUM_SPEC_BYTES` | `5000000` | Maximum accepted JSON specification size |

No provider credential is configured in the deterministic analyzer slice. When
a real external provider boundary is implemented, credential-bearing settings
must use Pydantic `SecretStr` and may be revealed only at that final boundary.
