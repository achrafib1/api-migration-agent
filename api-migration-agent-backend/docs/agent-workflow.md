# Planning-only agent workflow

The first agentic slice orchestrates verified deterministic tools and stops after
human review. LangGraph does not determine whether an API or repository change
exists.

```text
validate_inputs
      ↓
analyze_specs
      ↓
index_repository
      ↓
map_impact
      ↓
create_plan
      ↓
review_plan ── interrupt ── human approve/reject
```

## Structured planning boundary

`MigrationPlanner` receives an injected `LLMClient` protocol. The request sent to
that boundary contains validated API-change values and repository coordinates,
but excludes source excerpts, file contents, complete specifications, settings,
and credentials.

Every returned `MigrationPlanProposal` is Pydantic-validated. Application-level
validation then rejects actions that reference unknown API changes, impact IDs,
or target files; evidence must include the target file. Only the three MVP
operation families are representable.

No external provider is configured in this slice. Tests use a deterministic fake
that returns structured AtlasPay actions without network access.

## Human review

`review_plan` calls LangGraph's `interrupt()` with action metadata and business
questions only. Resumption requires a validated `HumanPlanDecision`. Approval of
an action linked to `currency_strategy` requires one offered answer; missing or
invented answers stop with a sanitized domain error.

The reviewed plan updates action statuses but performs no file operation. The
next execution slice must create a confined temporary workspace before any
approved patch can be represented as applied.

## Persistence limitation

The integration uses LangGraph's process-local `InMemorySaver`. Planning state is
lost when the backend process restarts and is not suitable for multiple workers
or durable audit history.
