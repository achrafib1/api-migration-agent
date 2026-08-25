# Temporary migration workspaces

The MVP modifies only a temporary copy of the bundled trusted AtlasPay client.
Human approval is required before the graph reaches `create_workspace`.
Rejection routes directly to the end of the graph.

The workspace creator:

1. Resolves and validates the trusted source root.
2. Confirms every approved action targets a file in the deterministic manifest.
3. Revalidates each source file hash immediately before copying.
4. Rejects source symlinks, absolute paths, and traversal components.
5. Copies verified source and test files without following symlinks.
6. Copies the fixed `pyproject.toml` required for later validation.
7. Revalidates copied hashes.
8. Records the exact approved modification scope.

The bundled original is never modified. Workspace paths are internal runtime
metadata and are not returned by the API. Workspaces currently survive until
operating-system temporary-file cleanup; explicit lifecycle cleanup will be
added with run finalization.

This boundary protects the trusted example repository from accidental
changes. It does not make execution of arbitrary or malicious repositories safe.

The trust classes and acceptance criteria for expanding beyond AtlasPay are
defined in [`repository-intake-security.md`](repository-intake-security.md).
Under the current policy, operator-approved projects may progress toward
deterministic analysis, but only the bundled fixture may enter patch execution
and pytest validation.
