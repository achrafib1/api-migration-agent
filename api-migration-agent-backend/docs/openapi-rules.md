# Supported OpenAPI rules

## Operation removed

An HTTP method present for a path in the baseline and absent from the revision
is a confirmed breaking change with `high` severity.

## Operation added

An HTTP method absent from the baseline and present in the revision is recorded
as non-breaking information.

Both rules emit immutable evidence containing an RFC 6901 JSON pointer. Path Item
metadata and malformed scalar operation entries are not treated as operations.

Nested contracts are compared for exact operation coordinates and for moved
operations linked by a unique, non-empty `operationId` in each document. An
ambiguous or duplicated `operationId` is never used for pairing. Endpoint removal
and addition facts remain present even when nested contracts are safely paired.

## Parameters

Parameters are compared on operations that exist in both documents. The
analyzer implements OpenAPI inheritance semantics: path-level parameters apply
to every operation, and an operation-level parameter with the same `(name, in)`
identity overrides the inherited definition.

Implemented facts are:

- Required parameter added: breaking, `high` severity
- Optional parameter added: non-breaking, `info` severity
- Optional parameter becoming required: breaking, `high` severity
- Parameter removed: breaking, `high` severity
- Explicit schema type changed: breaking, `high` severity
- Parameter location changed: breaking, `high` severity

Location changes are reported only when one unmatched old parameter and one
unmatched new parameter share the same name. Multiple candidates are not paired
because doing so would require inference. Missing schema types do not establish
a type change, and duplicate `(name, in)` identities in one parameter list stop
analysis with a sanitized document error.

Inline parameters and local references under `#/components/parameters/` are
supported. Evidence points to the parameter occurrence on the path or operation;
the resolver never performs filesystem or network access.

## JSON request bodies

Request bodies are compared only on operations present in both documents. This
slice analyzes the `application/json` media type and ordinary object properties.

Implemented breaking facts are:

- Request body added as required or changed from optional to required
- Required request property added or an existing property becoming required
- Request property removed
- Explicit request property type changed
- One-to-one structurally identical request-property rename candidate

A rename candidate is intentionally not presented as confirmed business intent.
It is emitted only for a mutually unique match between removed and added
properties with identical schemas and requiredness. Multiple structural matches
or different schemas remain explicit removal and required-addition facts.

Inline request bodies, local `#/components/requestBodies/` references, and local
schema-reference chains are supported. Cycles, external references, and chains
beyond the fixed bound stop with sanitized reference errors.

## JSON responses

All response keys on shared operations are compared, including explicit status
codes, patterned keys, and `default`. Schema-property analysis is limited to the
`application/json` media type.

Implemented breaking facts are:

- Response status removed
- Required response property removed
- Required response property becoming optional
- Explicit response property type changed
- Explicit local response schema reference changed

Optional response-property removal is intentionally outside the current rule;
the implemented guarantee rule requires deterministic evidence that the baseline
declared the property as required. Missing schemas and missing explicit types do
not produce inferred property changes.

Inline Response Objects, local `#/components/responses/` references, and bounded
local schema-reference chains are supported. External references and cycles stop
with sanitized reference errors.

## Security requirements and schemes

Effective operation security is computed using OpenAPI inheritance. Root-level
requirements apply unless an operation provides its own `security` field.
Explicit `security: []` and an empty requirement alternative permit anonymous
access and are not reported as tighter security.

Implemented breaking facts are:

- Security requirement added or changed to a non-anonymous requirement
- Component security scheme removed
- Explicit security scheme type changed
- Explicit `apiKey` location changed

Requirement alternatives, scheme names, and scope lists are canonicalized before
comparison, so ordering differences do not create false positives. Malformed
explicit requirement structures stop with a sanitized document error rather
than being interpreted as anonymous access.

Only structural, non-sensitive security metadata is preserved in evidence:
scheme name, type, and API-key location. Descriptions, header values, tokens, and
credentials are never accepted as evidence or emitted. Local references under
`#/components/securitySchemes/` are supported without filesystem or network
access.

## Current limitations

This slice does not yet compare complex schema composition, OAuth-flow semantics,
or OpenID Connect discovery. It supports JSON OpenAPI 3.x inputs and approved
local schema, parameter, request-body, response, and security-scheme references;
it does not support YAML or external references.
