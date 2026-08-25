# Trusted repository intake security contract

This document defines the boundary required before the API Migration Agent can
accept a project other than the bundled AtlasPay fixture. It is an implementation
contract, not a claim that general repository intake already exists.

## Why a temporary directory is insufficient

Copying a repository to a temporary directory protects the original files from
accidental modification. It does not constrain code execution. Python imported
by pytest can still read accessible host files, create processes, use the
network, consume excessive resources, or modify files outside the temporary
directory. Consequently, the application must distinguish repository analysis
from repository execution.

## Trust classes

### Bundled trusted fixture

The repository is versioned with the application, reviewed by the project
maintainer, and covered by the automated suite. Deterministic analysis, patch
application in a temporary copy, and the fixed pytest validation command are
allowed. AtlasPay is currently the only target in this class.

### Operator-approved local project

The operator explicitly registers a project that they own and trust. The
browser selects only a stable target identifier; it never submits a filesystem
path. Deterministic analysis may be enabled after all intake checks pass.

Under the current MVP security policy, patch execution and pytest remain
disabled for this class. Operator approval establishes provenance, but it is not
an operating-system sandbox.

### Untrusted or public repository

Uploads, arbitrary local paths, and Git URLs are untrusted. They are rejected by
the MVP. Supporting them would require a separately approved operating-system
isolation boundary with restricted filesystem access, disabled network access,
resource limits, and disposable execution environments. A temporary directory
alone does not satisfy these requirements.

## Registration contract

The next implementation slice may register operator-approved projects only when
all of the following are true:

1. Registration occurs through an operator-controlled backend mechanism, not a
   browser request.
2. Each target has a stable identifier, display name, trusted root, old OpenAPI
   file, new OpenAPI file, and Python repository directory.
3. All component paths are relative to one configured allowlisted root.
4. Absolute request paths and `..` traversal are rejected.
5. Every path is resolved before use and must remain inside the target root.
6. Symlinks and reparse points are rejected for the root and every traversed
   component.
7. Protected filenames and directories are rejected without reading them.
8. Intake enforces file-count, per-file-size, total-size, and nesting limits.
9. Only supported OpenAPI JSON and Python analysis files are indexed.
10. No dependency installation, lifecycle script, repository command, Git
    operation, or network request is performed.
11. Target paths, manifests, source text, and specification contents are absent
    from logs and API responses.
12. Registration failures use stable sanitized error codes.

## Protected-name rejection

The intake scanner must reject protected content by path metadata before opening
the file. At minimum this includes environment files, credential and secret
directories, private keys, keystores, signing certificates, authentication
exports, service-account files, token caches, registry authentication, database
dumps, HTTP archives, and logs that may contain credentials.

Rejected protected files must not be opened, hashed, summarized, copied, logged,
or returned in an API response.

## Capability matrix

| Capability | Bundled AtlasPay | Operator-approved project | Untrusted/public project |
| --- | --- | --- | --- |
| Target discovery by stable ID | Allowed | Allowed after registration | Rejected |
| Deterministic OpenAPI analysis | Allowed | Allowed after intake checks | Rejected |
| Deterministic Python impact mapping | Allowed | Allowed after intake checks | Rejected |
| Evidence-backed planning | Allowed | Allowed using sanitized evidence | Rejected |
| Human review | Required | Required | Not applicable |
| Temporary patch application | Allowed | Disabled under current policy | Rejected |
| `python -m pytest` execution | Allowed | Disabled under current policy | Rejected |
| Dependency installation | Rejected | Rejected | Rejected |
| User-provided command | Rejected | Rejected | Rejected |

## Definition of done for the intake slice

Operator-approved analysis is complete only when tests prove that:

- browser and API requests cannot submit filesystem paths;
- only registered stable identifiers resolve;
- targets outside the allowlisted root are rejected;
- absolute paths and traversal are rejected;
- symlink and reparse-point escapes are rejected where supported;
- protected names are rejected without file reads;
- size, file-count, and nesting limits are enforced;
- no registered source file is modified;
- no subprocess or network operation occurs during intake or analysis;
- logs, agent state, reports, and API responses contain no private paths or
  protected values;
- AtlasPay patching and validation behavior remains unchanged.

## Path to broader execution

Executing tests from user-controlled repositories is a separate product and
security expansion. Before enabling it, the project must select and verify a
real isolation mechanism appropriate to the deployment platform. That decision
must include filesystem, process, network, CPU, memory, time, and cleanup
controls and must not be represented as complete through application-level path
checks alone.
