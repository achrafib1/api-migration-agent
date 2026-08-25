"""Exact text and Python AST mapping from API changes to trusted source files."""

from __future__ import annotations

import ast
import hashlib
import io
import re
import tokenize
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api_migration_agent.analysis.repository.manifest import resolve_manifest_file
from api_migration_agent.core.exceptions import RepositorySourceError
from api_migration_agent.domain.api_change import ApiChange
from api_migration_agent.domain.enums import ImpactConfidence, SourceContext
from api_migration_agent.domain.repository_impact import RepositoryFile, RepositoryImpact


@dataclass(frozen=True, slots=True)
class _SymbolSpan:
    """Qualified Python symbol and inclusive source-line span."""

    qualified_name: str
    start_line: int
    end_line: int


def map_repository_impacts(
    root: Path,
    manifest: tuple[RepositoryFile, ...],
    api_changes: tuple[ApiChange, ...],
) -> tuple[RepositoryImpact, ...]:
    """Map verified API-change terms to exact Python source occurrences.

    Args:
        root: Trusted repository root used to create the manifest.
        manifest: Previously validated Python file manifest.
        api_changes: Authoritative deterministic contract changes.

    Returns:
        Stable evidence ordered by API change, file, line, and matched text.

    Raises:
        RepositoryBoundaryError: Through `resolve_manifest_file` if a path no
            longer remains inside the approved root.
        RepositorySourceError: If source changed after manifesting, is not valid
            UTF-8, or cannot be parsed as Python.
    """

    impacts: list[RepositoryImpact] = []
    for file_entry in manifest:
        source_path = resolve_manifest_file(root, file_entry.relative_path)
        source = _read_verified_source(source_path, file_entry)
        tree = _parse_source(source)
        lines = source.splitlines()
        comments = _comment_lines(source)
        docstring_lines = _docstring_lines(tree)
        symbols = _symbol_spans(tree)

        for change in api_changes:
            for term in _change_terms(change):
                impacts.extend(
                    _find_term_impacts(
                        change,
                        file_entry.relative_path,
                        lines,
                        term,
                        comments,
                        docstring_lines,
                        symbols,
                    )
                )
    return tuple(
        sorted(
            impacts,
            key=lambda item: (
                item.api_change_id,
                item.file_path,
                item.line_number,
                item.matched_text,
            ),
        )
    )


def _read_verified_source(path: Path, file_entry: RepositoryFile) -> str:
    """Read UTF-8 source and enforce the manifest hash precondition."""

    try:
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != file_entry.sha256:
            raise RepositorySourceError
        return content.decode("utf-8")
    except RepositorySourceError:
        raise
    except (OSError, UnicodeError):
        raise RepositorySourceError from None


def _parse_source(source: str) -> ast.Module:
    """Parse source without importing or executing repository modules."""

    try:
        return ast.parse(source)
    except SyntaxError:
        raise RepositorySourceError from None


def _change_terms(change: ApiChange) -> tuple[str, ...]:
    """Extract precise identifiers from structured old/new change values."""

    # Impact analysis targets the pre-migration repository, so only baseline
    # evidence can establish an exact existing usage. Revision-only values such
    # as a newly required field remain unresolved questions, not text matches.
    terms = set(_selected_json_strings(change.old_value))
    # Common protocol and schema words create noise rather than repository
    # evidence. Paths and domain field names remain eligible.
    excluded = {
        "apiKey",
        "array",
        "boolean",
        "cookie",
        "delete",
        "get",
        "header",
        "http",
        "integer",
        "number",
        "object",
        "patch",
        "post",
        "put",
        "query",
        "string",
    }
    return tuple(sorted(term for term in terms if len(term) >= 3 and term not in excluded))


def _selected_json_strings(value: Any, *, parent_key: str | None = None) -> Iterable[str]:
    """Yield strings from evidence fields that identify API usages."""

    if isinstance(value, Mapping):
        for key, nested in value.items():
            if isinstance(key, str):
                yield from _selected_json_strings(nested, parent_key=key)
        return
    if isinstance(value, list):
        for nested in value:
            yield from _selected_json_strings(nested, parent_key=parent_key)
        return
    if isinstance(value, str) and parent_key in {"$ref", "name", "path"}:
        yield value


def _find_term_impacts(
    change: ApiChange,
    file_path: str,
    lines: list[str],
    term: str,
    comments: Mapping[int, tuple[str, ...]],
    docstring_lines: frozenset[int],
    symbols: tuple[_SymbolSpan, ...],
) -> list[RepositoryImpact]:
    """Create one impact per source line containing an exact term."""

    impacts: list[RepositoryImpact] = []
    for line_number, line in enumerate(lines, start=1):
        if not _line_contains_term(line, term):
            continue
        context = _source_context(line_number, term, comments, docstring_lines)
        confidence = (
            ImpactConfidence.HIGH if context is SourceContext.EXECUTABLE else ImpactConfidence.LOW
        )
        symbol = _enclosing_symbol(line_number, symbols)
        identity = f"{change.id}\x00{file_path}\x00{line_number}\x00{term}".encode()
        impacts.append(
            RepositoryImpact(
                id=f"IMPACT-{hashlib.sha256(identity).hexdigest()[:12].upper()}",
                api_change_id=change.id,
                file_path=file_path,
                symbol_name=symbol,
                line_number=line_number,
                source_excerpt=line.strip()[:300],
                matched_text=term,
                context=context,
                confidence=confidence,
                reason=(f"Exact API evidence text appears in {context.value} Python source."),
            )
        )
    return impacts


def _line_contains_term(line: str, term: str) -> bool:
    """Match Python-style field names without accepting identifier substrings."""

    if term.isidentifier() and term == term.lower():
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])"
        return re.search(pattern, line) is not None
    return term in line


def _comment_lines(source: str) -> dict[int, tuple[str, ...]]:
    """Return comment tokens by line without interpreting their instructions."""

    comments: dict[int, list[str]] = {}
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                comments.setdefault(token.start[0], []).append(token.string)
    except (IndentationError, tokenize.TokenError):
        raise RepositorySourceError from None
    return {line: tuple(values) for line, values in comments.items()}


def _docstring_lines(tree: ast.Module) -> frozenset[int]:
    """Return every line occupied by a module, class, or function docstring."""

    lines: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            lines.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return frozenset(lines)


def _symbol_spans(tree: ast.Module) -> tuple[_SymbolSpan, ...]:
    """Collect qualified class and function spans for line-to-symbol mapping."""

    spans: list[_SymbolSpan] = []

    def visit(node: ast.AST, parents: tuple[str, ...]) -> None:
        next_parents = parents
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            qualified_name = ".".join((*parents, node.name))
            spans.append(
                _SymbolSpan(
                    qualified_name=qualified_name,
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                )
            )
            next_parents = (*parents, node.name)
        for child in ast.iter_child_nodes(node):
            visit(child, next_parents)

    visit(tree, ())
    return tuple(spans)


def _source_context(
    line_number: int,
    term: str,
    comments: Mapping[int, tuple[str, ...]],
    docstring_lines: frozenset[int],
) -> SourceContext:
    """Classify one exact match using tokenizer and AST evidence."""

    if any(term in comment for comment in comments.get(line_number, ())):
        return SourceContext.COMMENT
    if line_number in docstring_lines:
        return SourceContext.DOCSTRING
    return SourceContext.EXECUTABLE


def _enclosing_symbol(line_number: int, symbols: tuple[_SymbolSpan, ...]) -> str | None:
    """Return the narrowest qualified symbol containing a source line."""

    candidates = [
        symbol for symbol in symbols if symbol.start_line <= line_number <= symbol.end_line
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda symbol: symbol.end_line - symbol.start_line).qualified_name
