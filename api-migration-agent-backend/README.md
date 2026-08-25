# API Migration Agent Backend

This `uv` project contains the deterministic analysis, agentic planning,
human-review, confined execution, validation, and reporting backend for the API
Migration Agent MVP.

## Implemented slice

- Bounded JSON loading for OpenAPI 3.x documents
- Strict local references under `#/components/schemas/`
- Deterministic detection of added and removed HTTP operations
- Deterministic parameter additions, removals, requirement changes, explicit
  schema-type changes, and conservative location changes
- Deterministic JSON request-body requirement, property, type, and bounded
  rename-candidate analysis
- Deterministic response-status, required-property guarantee, explicit type,
  and schema-reference analysis
- Deterministic inherited and operation-level security requirement analysis,
  plus structural security-scheme compatibility rules
- Trusted AtlasPay v1-to-v2 acceptance fixture with full locked analyzer output
- Confined Python repository manifests and exact text/AST impact mapping
- Typed LangGraph planning workflow with validated structured output and a real
  human-review interrupt
- Model-agnostic LangChain planning adapter backed by LiteLLM, with Gemini as
  the default configured provider model
- Production composition root that injects the LiteLLM model into the planner
  and compiled LangGraph without placing provider settings in graph state
- FastAPI lifespan and dependency wiring with trusted AtlasPay start/review
  routes, process-local run metadata, and sanitized domain-error responses
- Approval-gated temporary workspace creation that copies only verified AtlasPay
  manifest files and preserves the bundled original repository
- Structured exact-replacement patch proposals with deterministic approval,
  evidence, target-confinement, and ambiguity validation before mutation
- Gemini/LangChain patch generation using only approved bounded evidence and
  mandatory deterministic proposal validation
- Atomic exact-text patch application confined to the temporary workspace with
  manifest hashes, single-match preconditions, and Python syntax validation
- Fixed `python -m pytest` validation with `shell=False`, a strict timeout,
  sanitized environment, discarded subprocess output, and typed outcomes
- Evidence-aware failure investigation, deterministic final reporting, and
  creator-owned temporary workspace cleanup for every terminal accepted run
- Stable process-local API snapshots for review, patch metadata, validation,
  final reports, and frontend-safe run-status polling
- Immutable, evidence-backed `ApiChange` domain models
- Sanitized domain exceptions
- Allowlisted local JSON logging

The analyzer does not call an LLM. It does not claim complete OpenAPI
compatibility: YAML, remote references, complex schema composition, OAuth-flow
semantics, and OpenID Connect discovery are not implemented yet.

## Windows development

From PowerShell:

```powershell
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest
```

Run the API after configuring the planning provider credential:

```powershell
uv run uvicorn api_migration_agent.api.main:app --reload
```

No real credentials or network services are required by the test suite.

## Security boundary

Inputs are treated as untrusted data. The loader accepts only bounded JSON
files, rejects symlinks, and reports constant sanitized errors. Local schema
resolution never accesses the filesystem or network. Logs contain only explicit
operational metadata and never include specification contents or exception text.

Execution is limited to a temporary copy of the bundled trusted AtlasPay client.
The MVP does not claim to safely execute arbitrary or malicious repositories.

## AtlasPay acceptance test

The integration test loads the synthetic contracts under `../examples/atlaspay`,
runs every implemented deterministic rule, and compares all resulting domain
models with the reviewed `expected/api-changes.json` fixture. A unique shared
`operationId` pairs nested contracts across the endpoint move without suppressing
the separate operation-removed and operation-added facts.

Repository analysis then indexes only trusted `src/` and `tests/` Python files,
revalidates file hashes before reading, parses source without importing it, and
maps baseline API evidence to qualified symbols and lines. Comments and
docstrings remain low-confidence evidence; executable occurrences receive high
confidence. Revision-only values without baseline text remain explicitly
unresolved.

## Migration workflow

The LangGraph workflow runs input validation, specification analysis, repository
indexing, impact mapping, structured plan creation, human review, temporary
workspace creation, structured patch generation, exact patch application, fixed
pytest validation, bounded failure investigation, reporting, and cleanup.
It uses an injected `LLMClient` protocol. The production adapter requests a
Pydantic-structured response through LangChain and LiteLLM, while tests use
deterministic local fakes and make no provider or network calls. Model settings
and credentials are never placed in graph state or logs.

Planner input excludes source excerpts, full specifications, settings, and
credentials. Generated actions are rejected if they reference unknown changes,
evidence, files, unsupported operation types, or non-proposed statuses. The graph
pauses at `review_plan` and cannot approve an action requiring business input
until the human supplies one of the offered values.

The graph is separated into state, nodes, edges, dependencies, and composition
modules. Approval routes to confined execution; rejection routes directly to a
terminal report. Validation executes only the fixed `python -m pytest` command.
Automated repair is skipped when sanitized evidence is insufficient. Embeddings,
vector storage, remote observability, and arbitrary commands remain absent.

## Temporary workspace boundary

Workspace creation copies the hash-verified Python manifest and the fixed
`pyproject.toml` descriptor into a newly created temporary directory. It rejects
symlinks, unknown approved targets, traversal, absolute relative paths, hash
changes, and destinations outside the new workspace. Only files belonging to
approved migration actions are recorded as modifiable; all other copied files
remain validation context. Temporary workspaces are process-local artifacts and
are not a security sandbox for arbitrary repositories.

## Patch proposal generation

After workspace creation, `generate_patch` calls Gemini through the shared
LangChain/LiteLLM model. The model receives approved actions, human-approved
answers, and bounded synthetic AtlasPay evidence only. Its Pydantic
`PatchProposal` is treated as untrusted and rejected unless it covers every
approved action and matches deterministic action, change, evidence, file,
operation, and exact-text preconditions. A separate deterministic applier performs
per-file atomic writes only after all candidate Python contents parse successfully.

## API and frontend contract

The typed API contract is documented in [`../docs/api.md`](../docs/api.md).
Configuration is documented in
[`../docs/configuration.md`](../docs/configuration.md). The implemented Next.js
review interface lives in [`../web`](../web) and uses `pnpm` exclusively; npm
is not part of the project workflow.

Migration runs start with a stable target identifier selected from the public
catalog. The registry resolves that identifier to startup-validated private
paths; API clients cannot submit filesystem paths. AtlasPay is the initial
registered target. Operator-managed trusted-project registration is the next
repository-intake slice and must follow the security contract in
[`../docs/repository-intake-security.md`](../docs/repository-intake-security.md).
