# Gemini provider smoke test

The automated test suite never contacts Gemini and never requires a credential.
Provider smoke testing is a deliberate manual operation because it sends bounded
synthetic AtlasPay evidence to the configured external provider.

From PowerShell, set the explicitly named configuration values using a safe local
credential supplied by the operator:

```powershell
$env:API_MIGRATION_AGENT_PLANNING_MODEL = "gemini/gemini-2.5-flash"
$env:API_MIGRATION_AGENT_PLANNING_API_KEY = "replace-me-locally"
uv run uvicorn api_migration_agent.api.main:app
```

Then follow [the API walkthrough](api.md). Do not print the environment, settings
object, credential, model messages, or provider response. A successful start and
review demonstrates both structured Gemini boundaries:

1. `create_plan` returns `MigrationPlanProposal`.
2. `generate_patch` returns `PatchProposal`.

Both results remain subject to deterministic validation. A successful provider
response does not authorize an unsupported action or file change.
