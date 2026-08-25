# Deterministic repository analysis

Repository analysis operates only on the bundled, trusted AtlasPay client. It is
not a sandbox for arbitrary repositories and never imports or executes analyzed
modules.

## Manifest boundary

The manifest includes regular `.py` files under `src/` and `tests/` only. Every
candidate is resolved against the trusted root, symlinks and traversal are
rejected, source size is bounded, and a SHA-256 precondition is recorded. The
digest is checked again immediately before source analysis.

## Impact evidence

Terms come from structured baseline values in authoritative `ApiChange` models.
Revision-only values cannot establish an occurrence in the pre-migration client.
Lowercase Python field names use identifier boundaries, preventing a field such
as `status` from matching `raise_for_status`.

Python is parsed with `ast` and tokenized without execution. Each exact match
records its file, qualified enclosing symbol, line, excerpt, syntactic context,
and confidence. Executable code is high-confidence; comments and docstrings are
retained only as low-confidence evidence.

The AtlasPay integration fixture locks 29 exact occurrences across six affected
files. The added endpoint, required `currency`, and new security requirement have
no direct baseline text match and remain unresolved for migration planning.
