# Backend configuration

Backend configuration uses the `API_MIGRATION_AGENT_` prefix and is loaded by
`pydantic-settings`. Do not place credentials in documentation, source control,
logs, API responses, graph state, or migration reports.

| Variable | Purpose | Safe local placeholder |
| --- | --- | --- |
| `API_MIGRATION_AGENT_LOG_LEVEL` | Local structured log threshold | `INFO` |
| `API_MIGRATION_AGENT_MAXIMUM_SPEC_BYTES` | Maximum accepted JSON specification size | `5000000` |
| `API_MIGRATION_AGENT_PLANNING_MODEL` | LiteLLM model identifier | `gemini/gemini-2.5-flash` |
| `API_MIGRATION_AGENT_PLANNING_TEMPERATURE` | Planning sampling temperature | `0.0` |
| `API_MIGRATION_AGENT_PLANNING_API_KEY` | Credential for the selected LiteLLM provider | `replace-me-locally` |
| `API_MIGRATION_AGENT_ALLOWED_ORIGINS` | JSON array of exact frontend origins | `["http://localhost:3000"]` |

The provider credential is optional during deterministic analysis and tests. It
is required only when application wiring constructs the production planning
model. The value is held as `SecretStr` and revealed only in the external model
constructor call.
