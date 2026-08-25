# AtlasPay migration demonstration

AtlasPay is synthetic, trusted demonstration data for the API Migration Agent.
It is not an external repository and contains no usable credential values.

The two OpenAPI JSON contracts model a migration from
`POST /customers/create` to `POST /customers`. Their unique shared
`operationId` provides deterministic evidence that nested request, response, and
security contracts belong to the same logical operation even though its path
changed.

The expected analysis fixture is generated from deterministic analyzer output
and locked by an integration test. Rename findings are conservative structural
candidates; they are not claims of confirmed business intent.

The bundled `client-repository` is the trusted AtlasPay v1 application used for
repository-impact analysis. The analyzer indexes only its `src/` and `tests/`
Python files, never imports or executes them, and locks exact affected-file and
line evidence in `expected/repository-impacts.json`.

The required v2 `currency` field has no exact v1 source occurrence. That absence
is intentional: a later migration planner must request a human business decision
instead of inventing a value.
