from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from typing import Any

from tree_sitter import Language, Parser
import tree_sitter_javascript
import tree_sitter_typescript

ANALYZER_VERSION = "ecmascript-tree-sitter-v0.3.0"


def _point(node: Any, which: str) -> dict[str, int]:
    point = getattr(node, which)
    return {"line": point.row + 1, "column": point.column + 1}


def _range(node: Any) -> dict[str, dict[str, int]]:
    return {"start": _point(node, "start_point"), "end": _point(node, "end_point")}


def _text(source: bytes, node: Any) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8")


def _analyze(path: str, source_text: str, language_name: str, grammar: Any) -> dict[str, Any]:
    source = source_text.encode("utf-8")
    tree = Parser(Language(grammar)).parse(source)
    symbols: list[dict[str, Any]] = []
    imports: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def add_symbol(node: Any, name: str, kind: str, parent: str | None, is_async: bool = False) -> str:
        symbol_id = f"{path}:{kind}:{name}:{node.start_point.row + 1}"
        symbols.append({"id": symbol_id, "name": name, "kind": kind, "range": _range(node), "parent_symbol_id": parent, "is_async": is_async})
        return symbol_id

    def visit(node: Any, parent_symbol: str | None = None) -> None:
        current = parent_symbol
        if node.type in {"function_declaration", "generator_function_declaration", "class_declaration"}:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                kind = "class" if node.type == "class_declaration" else "function"
                current = add_symbol(node, _text(source, name_node), kind, parent_symbol, _text(source, node).lstrip().startswith("async "))
        elif node.type == "method_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                current = add_symbol(node, _text(source, name_node), "function", parent_symbol, _text(source, node).lstrip().startswith("async "))
        elif node.type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")
            if name_node is not None and value_node is not None and value_node.type in {"arrow_function", "function_expression", "generator_function"}:
                current = add_symbol(node, _text(source, name_node), "function", parent_symbol, _text(source, value_node).lstrip().startswith("async "))
        elif node.type in {"field_definition", "public_field_definition"}:
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")
            if name_node is not None and value_node is not None and value_node.type in {"arrow_function", "function_expression", "generator_function"}:
                current = add_symbol(node, _text(source, name_node), "function", parent_symbol, _text(source, value_node).lstrip().startswith("async "))
        elif node.type == "import_statement":
            imports.append({"text": _text(source, node), "range": _range(node), "source_symbol_id": parent_symbol})
        elif node.type == "call_expression":
            function_node = node.child_by_field_name("function")
            if function_node is not None:
                calls.append({"source_symbol_id": parent_symbol, "callee": _text(source, function_node), "range": _range(node), "resolved_target_id": None})
        if node.type == "ERROR" or node.is_missing:
            warnings.append({"code": "PARSE_RECOVERY", "range": _range(node)})
        for child in node.children:
            visit(child, current)

    visit(tree.root_node)
    candidates: dict[str, list[str]] = defaultdict(list)
    symbols_by_id = {symbol["id"]: symbol for symbol in symbols}
    class_members: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for symbol in symbols:
        candidates[symbol["name"]].append(symbol["id"])
        parent_id = symbol["parent_symbol_id"]
        if parent_id is not None and symbols_by_id.get(parent_id, {}).get("kind") == "class":
            class_members[parent_id][symbol["name"]].append(symbol["id"])

    for call in calls:
        callee = call["callee"]
        matches: list[str] = []
        if callee.isidentifier():
            matches = candidates.get(callee, [])
        elif callee.startswith("this.") and callee.count(".") == 1:
            member_name = callee.removeprefix("this.")
            source_symbol = symbols_by_id.get(call["source_symbol_id"])
            if source_symbol is not None:
                class_id = source_symbol["parent_symbol_id"]
                if class_id is not None and symbols_by_id.get(class_id, {}).get("kind") == "class":
                    matches = class_members[class_id].get(member_name, [])
        if len(matches) == 1:
            call["resolved_target_id"] = matches[0]
        elif len(matches) > 1:
            warnings.append({"code": "AMBIGUOUS_CALL_TARGET", "callee": callee, "range": call["range"], "candidate_target_ids": matches})

    return {"schema_version": 1, "analyzer_version": ANALYZER_VERSION, "file": {"path": path, "language": language_name, "content_hash": f"sha256:{sha256(source).hexdigest()}"}, "symbols": symbols, "imports": imports, "calls": calls, "warnings": warnings}


def analyze_javascript(path: str, source_text: str) -> dict[str, Any]:
    return _analyze(path, source_text, "javascript", tree_sitter_javascript.language())


def analyze_typescript(path: str, source_text: str, *, tsx: bool = False) -> dict[str, Any]:
    grammar = tree_sitter_typescript.language_tsx() if tsx else tree_sitter_typescript.language_typescript()
    return _analyze(path, source_text, "tsx" if tsx else "typescript", grammar)
