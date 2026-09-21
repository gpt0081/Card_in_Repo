from __future__ import annotations

from pathlib import Path
from typing import Any

from tree_sitter import Language, Parser
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript

DEFAULT_MAX_CARD_LINES = 40


def _line_range(node: Any) -> tuple[int, int]:
    return node.start_point.row + 1, node.end_point.row + 1


def _language_for_path(path: str) -> tuple[Language, set[str]]:
    suffix = Path(path).suffix.lower()
    if suffix == ".py":
        return Language(tree_sitter_python.language()), {"function_definition"}
    if suffix in {".js", ".jsx"}:
        return Language(tree_sitter_javascript.language()), {"function_declaration", "function_expression", "arrow_function", "method_definition"}
    if suffix == ".ts":
        return Language(tree_sitter_typescript.language_typescript()), {"function_declaration", "function_expression", "arrow_function", "method_definition"}
    if suffix == ".tsx":
        return Language(tree_sitter_typescript.language_tsx()), {"function_declaration", "function_expression", "arrow_function", "method_definition"}
    raise ValueError(f"unsupported source path for card splitting: {path}")


def _function_node(source: bytes, symbol: dict[str, Any], path: str) -> Any | None:
    language, function_types = _language_for_path(path)
    parser = Parser(language)
    tree = parser.parse(source)
    wanted_start = symbol["range"]["start"]["line"]
    wanted_end = symbol["range"]["end"]["line"]
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type in function_types:
            start, end = _line_range(node)
            if start == wanted_start and end == wanted_end:
                return node
        stack.extend(reversed(node.children))
    return None


def split_symbol(
    source_text: str,
    symbol: dict[str, Any],
    path: str,
    max_lines: int = DEFAULT_MAX_CARD_LINES,
) -> list[dict[str, Any]]:
    """Return syntax-aligned card segments for a supported function symbol.

    Short functions remain one card. Long functions are split only between direct
    body statements, never at arbitrary line counts. A single oversized statement
    remains intact rather than violating the syntax boundary contract.
    """
    if max_lines < 1:
        raise ValueError("max_lines must be positive")
    start = symbol["range"]["start"]["line"]
    end = symbol["range"]["end"]["line"]
    if end - start + 1 <= max_lines or symbol.get("kind") != "function":
        return [{"start_line": start, "end_line": end}]

    source = source_text.encode("utf-8")
    function = _function_node(source, symbol, path)
    if function is None:
        return [{"start_line": start, "end_line": end}]
    body = function.child_by_field_name("body")
    statements = list(body.named_children) if body is not None else []
    if not statements:
        return [{"start_line": start, "end_line": end}]

    segments: list[dict[str, int]] = []
    current_start = start
    current_end = _line_range(statements[0])[1]
    for statement in statements[1:]:
        statement_start, statement_end = _line_range(statement)
        if statement_end - current_start + 1 > max_lines:
            segments.append({"start_line": current_start, "end_line": current_end})
            current_start = statement_start
        current_end = statement_end
    segments.append({"start_line": current_start, "end_line": max(current_end, end)})

    for index, segment in enumerate(segments):
        segment["index"] = index
        segment["count"] = len(segments)
    return segments


def split_python_symbol(
    source_text: str,
    symbol: dict[str, Any],
    max_lines: int = DEFAULT_MAX_CARD_LINES,
) -> list[dict[str, Any]]:
    """Backward-compatible Python-specific splitter."""
    return split_symbol(source_text, symbol, "source.py", max_lines)
