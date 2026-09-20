from __future__ import annotations

from collections import defaultdict
from typing import Any


def build_feature_map(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Build conservative feature candidates from resolved calls.

    Roots are top-level functions that are not called by another resolved function.
    Each feature is the deterministic reachable call flow from one root. Cycles are
    visited once. Unresolved calls never become graph edges. When the fact layer
    knows a symbol's repository path, expose it on the flow step so downstream
    teaching surfaces can show cross-file execution without re-inferring ownership.
    """
    functions = {
        symbol["id"]: symbol
        for symbol in facts["symbols"]
        if symbol["kind"] == "function" and symbol.get("parent_symbol_id") is None
    }
    symbol_paths = facts.get("symbol_paths") or {}
    edges: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, int] = {symbol_id: 0 for symbol_id in functions}

    for call in facts["calls"]:
        source = call.get("source_symbol_id")
        target = call.get("resolved_target_id")
        if source in functions and target in functions and target not in edges[source]:
            edges[source].append(target)
            incoming[target] += 1

    roots = [symbol_id for symbol_id in functions if incoming[symbol_id] == 0]
    # A pure cycle has no indegree-zero node. Keep it visible rather than dropping it.
    if not roots and functions:
        roots = [next(iter(functions))]

    def flow_step(symbol_id: str, position: int) -> dict[str, Any]:
        symbol = functions[symbol_id]
        step = {
            "position": position,
            "symbol_id": symbol_id,
            "symbol_name": symbol["name"],
            "range": symbol["range"],
        }
        path = symbol_paths.get(symbol_id)
        if path:
            step["path"] = path
        return step

    features: list[dict[str, Any]] = []
    globally_reached: set[str] = set()
    for root in roots:
        steps: list[dict[str, Any]] = []
        seen: set[str] = set()

        def walk(symbol_id: str) -> None:
            if symbol_id in seen:
                return
            seen.add(symbol_id)
            globally_reached.add(symbol_id)
            steps.append(flow_step(symbol_id, len(steps) + 1))
            for target in edges.get(symbol_id, []):
                walk(target)

        walk(root)
        features.append({
            "id": f"feature:{root}",
            "name": functions[root]["name"],
            "confidence": 1.0,
            "provenance": "deterministic-resolved-call-graph",
            "flow_steps": steps,
        })

    # Defensive visibility for disconnected nodes when roots overlap oddly.
    for symbol_id, symbol in functions.items():
        if symbol_id not in globally_reached:
            features.append({
                "id": f"feature:{symbol_id}",
                "name": symbol["name"],
                "confidence": 1.0,
                "provenance": "deterministic-disconnected-symbol",
                "flow_steps": [flow_step(symbol_id, 1)],
            })

    return features
