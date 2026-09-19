from __future__ import annotations

from typing import Any

from tree_sitter import Language, Parser
import tree_sitter_python

DEFAULT_MAX_CARD_LINES = 40


def _line_range(node: Any) -> tuple[int, int]:
    return node.start_point.row + 1, node.end_point.row + 1


def _function_node(source: bytes, symbol: dict[str, Any]) -> Any | None:
    parser = Parser(Language(tree_sitter_python.language()))
    tree = parser.parse(source)
    wanted_start = symbol["range"]["start"]["line"]
    wanted_end = symbol["range"]["end"]["line"]
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type == "function_definition":
            start, end = _line_range(node)
            if start == wanted_start and end == wanted_end:
                return node
        stack.extend(reversed(node.children))
    return None


def split_python_symbol(
    source_text: str,
    symbol: dict[str, Any],
    max_lines: int = DEFAULT_MAX_CARD_LINES,
) -> list[dict[str, Any]]:
    """Return syntax-aligned card segments for a Python function.

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
    function = _function_node(source, symbol)
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
