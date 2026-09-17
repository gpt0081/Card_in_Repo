from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from typing import Any

from tree_sitter import Language, Parser
import tree_sitter_python

ANALYZER_VERSION = "python-tree-sitter-v0.1.1"


def _point(node: Any, which: str) -> dict[str, int]:
    point = getattr(node, which)
    return {"line": point.row + 1, "column": point.column + 1}


def _range(node: Any) -> dict[str, dict[str, int]]:
    return {"start": _point(node, "start_point"), "end": _point(node, "end_point")}


def _text(source: bytes, node: Any) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8")


def analyze_python(path: str, source_text: str) -> dict[str, Any]:
    source = source_text.encode("utf-8")
    parser = Parser(Language(tree_sitter_python.language()))
    tree = parser.parse(source)

    symbols: list[dict[str, Any]] = []
    imports: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def visit(node: Any, parent_symbol: str | None = None) -> None:
        current_symbol = parent_symbol
        if node.type in {"function_definition", "class_definition"}:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = _text(source, name_node)
                kind = "class" if node.type == "class_definition" else "function"
                symbol_id = f"{path}:{kind}:{name}:{node.start_point.row + 1}"
                symbols.append({
                    "id": symbol_id,
                    "name": name,
                    "kind": kind,
                    "range": _range(node),
                    "parent_symbol_id": parent_symbol,
                    "is_async": False,
                })
                current_symbol = symbol_id
        elif node.type in {"import_statement", "import_from_statement"}:
            imports.append({"text": _text(source, node), "range": _range(node), "source_symbol_id": parent_symbol})
        elif node.type == "call":
            function_node = node.child_by_field_name("function")
            if function_node is not None:
                calls.append({
                    "source_symbol_id": parent_symbol,
                    "callee": _text(source, function_node),
                    "range": _range(node),
                    "resolved_target_id": None,
                })
        if node.type == "ERROR" or node.is_missing:
            warnings.append({"code": "PARSE_RECOVERY", "range": _range(node)})
        for child in node.children:
            visit(child, current_symbol)

    visit(tree.root_node)

    candidates: dict[str, list[str]] = defaultdict(list)
    for symbol in symbols:
        candidates[symbol["name"]].append(symbol["id"])

    lines = source_text.splitlines()
    for symbol in symbols:
        start_line = symbol["range"]["start"]["line"]
        symbol["is_async"] = bool(lines) and lines[start_line - 1].lstrip().startswith("async def ")

    for call in calls:
        callee = call["callee"]
        matches = candidates.get(callee, []) if callee.isidentifier() else []
        if len(matches) == 1:
            call["resolved_target_id"] = matches[0]
        elif len(matches) > 1:
            warnings.append({
                "code": "AMBIGUOUS_CALL_TARGET",
                "callee": callee,
                "range": call["range"],
                "candidate_target_ids": matches,
            })

    return {
        "schema_version": 1,
        "analyzer_version": ANALYZER_VERSION,
        "file": {
            "path": path,
            "language": "python",
            "content_hash": f"sha256:{sha256(source).hexdigest()}",
        },
        "symbols": symbols,
        "imports": imports,
        "calls": calls,
        "warnings": warnings,
    }
