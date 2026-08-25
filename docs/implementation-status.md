# Implementation status

This document separates capabilities verified by the automated suite from
features that remain intentionally outside the current project scope.

## Verified capabilities

- Deterministic comparison of supported OpenAPI 3.x JSON compatibility rules.
- Exact Python repository impact mapping without importing analyzed code.
- Two Gemini-compatible structured-output boundaries through LangChain and
  LiteLLM: migration planning and patch proposal generation.
- Typed LangGraph orchestration with an explicit human-review interrupt.
- Evidence validation that prevents model output from inventing changes, files,
  operations, or repository evidence.
- Approval-gated temporary workspace creation for the bundled AtlasPay client.
- Manifest-hash and exact-text patch preconditions with Python syntax validation.
- Fixed pytest validation using `shell=False`, a strict timeout, and a sanitized
  environment.
- Structured success, rejection, and failure reports with workspace cleanup.
- FastAPI start, review, and polling endpoints with process-local persistence.
- Content-safe target discovery and stable-ID selection backed by a confined
  server-side registry; private paths never cross the API boundary.
- Target identity preserved through start, human review, finalization, polling,
  and the web report without leaking registered filesystem locations.
- Complete API-level AtlasPay scenarios using deterministic external-boundary
  fakes and no network credentials.

## Current limitations

- OpenAPI support is intentionally bounded and does not claim full compatibility.
- YAML, remote references, and arbitrary public repository execution are absent.
- Persistence is in-memory, single-process, and non-durable.
- The application does not install analyzed-project dependencies.
- Raw test output is discarded, so automated repair is skipped when no safe
  structured failure evidence exists.
- No authentication, database, Docker execution, MCP, embeddings, vector store,
  remote tracing, or automatic GitHub operation is implemented.
- Provider smoke testing is manual and requires explicit operator configuration.
- Repository intake is intentionally absent: the MVP accepts neither user paths nor
  uploads and operates only on the bundled trusted AtlasPay fixture. Supporting a
  user-selected repository requires the reviewed contract in
  [`repository-intake-security.md`](repository-intake-security.md).
