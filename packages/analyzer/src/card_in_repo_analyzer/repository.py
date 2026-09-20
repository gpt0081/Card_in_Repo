from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath
from typing import Any

from .ecmascript import analyze_javascript, analyze_typescript
from .python import analyze_python


def _analyze_file(path: str, source: str) -> dict[str, Any] | None:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix == ".py":
        return analyze_python(path, source)
    if suffix in {".js", ".jsx"}:
        return analyze_javascript(path, source)
    if suffix == ".ts":
        return analyze_typescript(path, source)
    if suffix == ".tsx":
        return analyze_typescript(path, source, tsx=True)
    return None


def analyze_repository(files: dict[str, str]) -> dict[str, Any]:
    """Combine supported source-file facts into one deterministic repository graph.

    Python cross-file resolution remains deliberately narrow: `from module import name`
    followed by `name()` can cross a file boundary when exactly one matching top-level
    Python symbol exists in the imported module. ECMAScript files participate in the
    same fact graph, but cross-module JS/TS resolution stays unresolved until an import
    resolver can prove the target without guessing bundler/module-resolution behavior.
    """
    file_facts: list[dict[str, Any]] = []
    for path in sorted(files):
        facts = _analyze_file(path, files[path])
        if facts is not None:
            file_facts.append(facts)

    symbols = [symbol for facts in file_facts for symbol in facts["symbols"]]
    calls = [dict(call, path=facts["file"]["path"]) for facts in file_facts for call in facts["calls"]]
    warnings = [dict(warning, path=facts["file"]["path"]) for facts in file_facts for warning in facts["warnings"]]

    by_module_name: dict[tuple[str, str], list[str]] = defaultdict(list)
    symbol_path: dict[str, str] = {}
    for facts in file_facts:
        path = facts["file"]["path"]
        for symbol in facts["symbols"]:
            symbol_path[symbol["id"]] = path
        if facts["file"]["language"] != "python":
            continue
        module = path[:-3].replace("/", ".")
        if module.endswith(".__init__"):
            module = module[:-9]
        for symbol in facts["symbols"]:
            if symbol["parent_symbol_id"] is None:
                by_module_name[(module, symbol["name"])].append(symbol["id"])

    imports_by_file: dict[str, dict[str, str]] = defaultdict(dict)
    for facts in file_facts:
        if facts["file"]["language"] != "python":
            continue
        path = facts["file"]["path"]
        for item in facts["imports"]:
            text = item["text"].strip()
            if text.startswith("from ") and " import " in text:
                module, names = text[5:].split(" import ", 1)
                for raw_name in names.split(","):
                    part = raw_name.strip()
                    if not part or part == "*":
                        continue
                    bits = part.split(" as ")
                    imported = bits[0].strip()
                    local = bits[-1].strip()
                    imports_by_file[path][local] = f"{module.strip()}:{imported}"

    python_paths = {facts["file"]["path"] for facts in file_facts if facts["file"]["language"] == "python"}
    for call in calls:
        if call["path"] not in python_paths or call.get("resolved_target_id") is not None or not call["callee"].isidentifier():
            continue
        imported = imports_by_file[call["path"]].get(call["callee"])
        if not imported:
            continue
        module, name = imported.split(":", 1)
        matches = by_module_name.get((module, name), [])
        if len(matches) == 1:
            call["resolved_target_id"] = matches[0]
            call["resolution"] = "repository-import"
        elif len(matches) > 1:
            warnings.append({"code": "AMBIGUOUS_REPOSITORY_CALL_TARGET", "path": call["path"], "callee": call["callee"], "candidate_target_ids": matches})

    return {
        "schema_version": 1,
        "analyzer_version": "repository-v0.2.0",
        "files": [facts["file"] for facts in file_facts],
        "symbols": symbols,
        "calls": calls,
        "warnings": warnings,
        "symbol_paths": symbol_path,
    }


def analyze_python_repository(files: dict[str, str]) -> dict[str, Any]:
    """Backward-compatible entry point; now returns all supported repository facts."""
    return analyze_repository(files)
