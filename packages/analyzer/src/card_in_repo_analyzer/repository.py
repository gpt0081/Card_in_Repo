from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath
import posixpath
import re
from typing import Any

from .ecmascript import analyze_javascript, analyze_typescript
from .python import analyze_python


ECMASCRIPT_SUFFIXES = (".js", ".jsx", ".ts", ".tsx")
NAMED_IMPORT_RE = re.compile(r"^import\s*\{(?P<names>[^}]*)\}\s*from\s*['\"](?P<module>[^'\"]+)['\"]\s*;?$")
DEFAULT_IMPORT_RE = re.compile(r"^import\s+(?P<local>[A-Za-z_$][\w$]*)\s+from\s*['\"](?P<module>[^'\"]+)['\"]\s*;?$")
DEFAULT_NAMED_EXPORT_RE = re.compile(
    r"\bexport\s+default\s+(?:(?:async\s+)?function|class)\s+(?P<name>[A-Za-z_$][\w$]*)\b"
)
REEXPORT_RE = re.compile(r"^export\s*\{(?P<names>[^}]*)\}\s*from\s*['\"](?P<module>[^'\"]+)['\"]\s*;?$")


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


def _resolve_relative_ecmascript_module(importer: str, module: str, known_paths: set[str]) -> str | None:
    """Resolve only unambiguous relative source modules, without emulating a bundler."""
    if not module.startswith("."):
        return None
    normalized = posixpath.normpath(posixpath.join(posixpath.dirname(importer), module))
    if normalized == ".." or normalized.startswith("../"):
        return None
    candidates: list[str] = []
    if PurePosixPath(normalized).suffix in ECMASCRIPT_SUFFIXES:
        if normalized in known_paths:
            candidates.append(normalized)
    else:
        candidates.extend(path for path in (normalized + suffix for suffix in ECMASCRIPT_SUFFIXES) if path in known_paths)
        candidates.extend(path for path in (f"{normalized}/index{suffix}" for suffix in ECMASCRIPT_SUFFIXES) if path in known_paths)
    return candidates[0] if len(candidates) == 1 else None


def _resolve_python_import_module(importer: str, module: str) -> str | None:
    """Turn an explicit Python import module into its repository-qualified module name."""
    if not module.startswith("."):
        return module
    level = len(module) - len(module.lstrip("."))
    package_parts = importer[:-3].split("/")[:-1]
    if PurePosixPath(importer).name == "__init__.py":
        package_parts = importer[:-12].strip("/").split("/") if "/" in importer else []
    ascend = level - 1
    if ascend > len(package_parts):
        return None
    base = package_parts[: len(package_parts) - ascend] if ascend else package_parts
    remainder = module[level:]
    parts = [*base, *([part for part in remainder.split(".") if part] if remainder else [])]
    return ".".join(parts) if parts else None


def analyze_repository(files: dict[str, str]) -> dict[str, Any]:
    """Combine supported source-file facts into one deterministic repository graph.

    Cross-file resolution is deliberately narrow. Python resolves explicit
    ``from module import name`` calls, including package-relative imports.
    JavaScript/TypeScript resolves named imports, named default declaration
    imports, and explicit named re-exports from an unambiguous relative source
    module (including extensionless and index paths). Package imports, wildcard
    re-exports, anonymous default exports, tsconfig aliases and bundler-specific
    rules remain unresolved rather than being guessed.
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
    by_path_name: dict[tuple[str, str], list[str]] = defaultdict(list)
    symbol_path: dict[str, str] = {}
    for facts in file_facts:
        path = facts["file"]["path"]
        for symbol in facts["symbols"]:
            symbol_path[symbol["id"]] = path
            if symbol["parent_symbol_id"] is None:
                by_path_name[(path, symbol["name"])].append(symbol["id"])
        if facts["file"]["language"] != "python":
            continue
        module = path[:-3].replace("/", ".")
        if module.endswith(".__init__"):
            module = module[:-9]
        for symbol in facts["symbols"]:
            if symbol["parent_symbol_id"] is None:
                by_module_name[(module, symbol["name"])].append(symbol["id"])

    default_exports_by_path: dict[str, str] = {}
    for facts in file_facts:
        path = facts["file"]["path"]
        if facts["file"]["language"] not in {"javascript", "typescript", "tsx"}:
            continue
        match = DEFAULT_NAMED_EXPORT_RE.search(files[path])
        if match is not None and len(by_path_name.get((path, match.group("name")), [])) == 1:
            default_exports_by_path[path] = match.group("name")

    imports_by_file: dict[str, dict[str, str]] = defaultdict(dict)
    js_imports_by_file: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    ecmascript_paths = {
        facts["file"]["path"]
        for facts in file_facts
        if facts["file"]["language"] in {"javascript", "typescript", "tsx"}
    }

    # Record only explicit ``export { x [as y] } from './module'`` bindings.
    # The value points at the next module/name pair, allowing deterministic barrel
    # chains to be followed without treating a re-export as a local declaration.
    reexports: dict[tuple[str, str], tuple[str, str]] = {}
    for path in sorted(ecmascript_paths):
        for line in files[path].splitlines():
            match = REEXPORT_RE.match(line.strip())
            if match is None:
                continue
            target_path = _resolve_relative_ecmascript_module(path, match.group("module"), ecmascript_paths)
            if target_path is None:
                continue
            for raw_name in match.group("names").split(","):
                part = raw_name.strip()
                if not part:
                    continue
                bits = re.split(r"\s+as\s+", part)
                imported = bits[0].strip()
                exported = bits[-1].strip()
                if imported == "default":
                    imported = default_exports_by_path.get(target_path, "")
                if imported.isidentifier() and exported.isidentifier():
                    reexports[(path, exported)] = (target_path, imported)

    def resolve_js_export(path: str, name: str) -> tuple[str, str] | None:
        """Follow explicit re-export chains, failing closed on cycles or ambiguity."""
        seen: set[tuple[str, str]] = set()
        current = (path, name)
        while current not in seen:
            seen.add(current)
            if len(by_path_name.get(current, [])) == 1:
                return current
            next_binding = reexports.get(current)
            if next_binding is None:
                return None
            current = next_binding
        return None

    for facts in file_facts:
        path = facts["file"]["path"]
        if facts["file"]["language"] == "python":
            for item in facts["imports"]:
                text = item["text"].strip()
                if text.startswith("from ") and " import " in text:
                    module, names = text[5:].split(" import ", 1)
                    resolved_module = _resolve_python_import_module(path, module.strip())
                    if resolved_module is None:
                        continue
                    for raw_name in names.split(","):
                        part = raw_name.strip()
                        if not part or part == "*":
                            continue
                        bits = part.split(" as ")
                        imported = bits[0].strip()
                        local = bits[-1].strip()
                        imports_by_file[path][local] = f"{resolved_module}:{imported}"
            continue
        if facts["file"]["language"] not in {"javascript", "typescript", "tsx"}:
            continue
        for item in facts["imports"]:
            text = item["text"].strip()
            match = NAMED_IMPORT_RE.match(text)
            if match is not None:
                target_path = _resolve_relative_ecmascript_module(path, match.group("module"), ecmascript_paths)
                if target_path is None:
                    continue
                for raw_name in match.group("names").split(","):
                    part = raw_name.strip()
                    if not part:
                        continue
                    bits = re.split(r"\s+as\s+", part)
                    imported = bits[0].strip()
                    local = bits[-1].strip()
                    if imported.isidentifier() and local.isidentifier():
                        resolved = resolve_js_export(target_path, imported)
                        if resolved is not None:
                            js_imports_by_file[path][local] = resolved
                continue
            default_match = DEFAULT_IMPORT_RE.match(text)
            if default_match is None:
                continue
            target_path = _resolve_relative_ecmascript_module(path, default_match.group("module"), ecmascript_paths)
            if target_path is None:
                continue
            exported_name = default_exports_by_path.get(target_path)
            if exported_name is not None:
                js_imports_by_file[path][default_match.group("local")] = (target_path, exported_name)

    python_paths = {facts["file"]["path"] for facts in file_facts if facts["file"]["language"] == "python"}
    for call in calls:
        if call.get("resolved_target_id") is not None or not call["callee"].isidentifier():
            continue
        if call["path"] in python_paths:
            imported = imports_by_file[call["path"]].get(call["callee"])
            if not imported:
                continue
            module, name = imported.split(":", 1)
            matches = by_module_name.get((module, name), [])
        elif call["path"] in ecmascript_paths:
            imported = js_imports_by_file[call["path"]].get(call["callee"])
            if not imported:
                continue
            target_path, name = imported
            matches = by_path_name.get((target_path, name), [])
        else:
            continue
        if len(matches) == 1:
            call["resolved_target_id"] = matches[0]
            call["resolution"] = "repository-import"
        elif len(matches) > 1:
            warnings.append({"code": "AMBIGUOUS_REPOSITORY_CALL_TARGET", "path": call["path"], "callee": call["callee"], "candidate_target_ids": matches})

    return {
        "schema_version": 1,
        "analyzer_version": "repository-v0.5.0",
        "files": [facts["file"] for facts in file_facts],
        "symbols": symbols,
        "calls": calls,
        "warnings": warnings,
        "symbol_paths": symbol_path,
    }


def analyze_python_repository(files: dict[str, str]) -> dict[str, Any]:
    """Backward-compatible entry point; now returns all supported repository facts."""
    return analyze_repository(files)
