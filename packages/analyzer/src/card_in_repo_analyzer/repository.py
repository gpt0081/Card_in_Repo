from __future__ import annotations

from collections import defaultdict
from typing import Any

from .python import analyze_python


def analyze_python_repository(files: dict[str, str]) -> dict[str, Any]:
    """Combine Python file facts and conservatively resolve cross-file imports/calls.

    Resolution is deliberately narrow: `from module import name` followed by `name()`
    can cross a file boundary when exactly one matching top-level symbol exists in the
    imported module. Ambiguous or dynamic cases remain unresolved repository truth.
    """
    file_facts = [analyze_python(path, files[path]) for path in sorted(files) if path.endswith(".py")]
    symbols = [symbol for facts in file_facts for symbol in facts["symbols"]]
    calls = [dict(call, path=facts["file"]["path"]) for facts in file_facts for call in facts["calls"]]
    warnings = [dict(warning, path=facts["file"]["path"]) for facts in file_facts for warning in facts["warnings"]]

    by_module_name: dict[tuple[str, str], list[str]] = defaultdict(list)
    symbol_path: dict[str, str] = {}
    for facts in file_facts:
        path = facts["file"]["path"]
        module = path[:-3].replace("/", ".")
        if module.endswith(".__init__"):
            module = module[:-9]
        for symbol in facts["symbols"]:
            symbol_path[symbol["id"]] = path
            if symbol["parent_symbol_id"] is None:
                by_module_name[(module, symbol["name"])].append(symbol["id"])

    imports_by_file: dict[str, dict[str, str]] = defaultdict(dict)
    for facts in file_facts:
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

    for call in calls:
        if call.get("resolved_target_id") is not None or not call["callee"].isidentifier():
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
        "analyzer_version": "python-repository-v0.1.0",
        "files": [facts["file"] for facts in file_facts],
        "symbols": symbols,
        "calls": calls,
        "warnings": warnings,
        "symbol_paths": symbol_path,
    }
