from __future__ import annotations

from collections import defaultdict
from typing import Any


def build_feature_map(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Build conservative feature candidates from resolved calls.

    Roots are repository-level functions and class-owned function-sized symbols that
    are not called by another resolved function. Nested local functions remain scoped
    implementation details rather than becoming repository features. Each feature is
    the deterministic reachable call flow from one root. Cycles are visited once.
    Unresolved calls never become graph edges, but statically observed call evidence is
    attached to its source step so downstream teaching/UI layers can explain dynamic or
    unknown dispatch without inventing a target. When the fact layer knows a symbol's
    repository path, expose it on the flow step too. Non-root steps explicitly record
    the resolved relation that reached them so consumers can distinguish graph edges
    from mere sequence position.
    """
    symbols_by_id = {symbol["id"]: symbol for symbol in facts["symbols"]}

    def is_feature_function(symbol: dict[str, Any]) -> bool:
        if symbol["kind"] != "function":
            return False
        parent_id = symbol.get("parent_symbol_id")
        if parent_id is None:
            return True
        parent = symbols_by_id.get(parent_id)
        return parent is not None and parent.get("kind") == "class"

    functions = {
        symbol["id"]: symbol
        for symbol in facts["symbols"]
        if is_feature_function(symbol)
    }
    symbol_paths = facts.get("symbol_paths") or {}
    edges: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, int] = {symbol_id: 0 for symbol_id in functions}
    unresolved_calls: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for call in facts["calls"]:
        source = call.get("source_symbol_id")
        target = call.get("resolved_target_id")
        if source in functions and target in functions and target not in edges[source]:
            edges[source].append(target)
            incoming[target] += 1
        elif source in functions and target is None:
            evidence = {
                key: call[key]
                for key in ("callee", "callee_kind", "receiver", "member_name", "dispatch", "range")
                if key in call
            }
            unresolved_calls[source].append(evidence)

    roots = [symbol_id for symbol_id in functions if incoming[symbol_id] == 0]
    # A pure cycle has no indegree-zero node. Keep it visible rather than dropping it.
    if not roots and functions:
        roots = [next(iter(functions))]

    def flow_step(symbol_id: str, position: int, relation: str | None = None) -> dict[str, Any]:
        symbol = functions[symbol_id]
        step = {
            "position": position,
            "symbol_id": symbol_id,
            "symbol_name": symbol["name"],
            "range": symbol["range"],
        }
        if relation is not None:
            step["relation"] = relation
        path = symbol_paths.get(symbol_id)
        if path:
            step["path"] = path
        parent_id = symbol.get("parent_symbol_id")
        parent = symbols_by_id.get(parent_id) if parent_id else None
        if parent is not None and parent.get("kind") == "class":
            step["owner_symbol_id"] = parent_id
            step["owner_symbol_name"] = parent["name"]
        if unresolved_calls.get(symbol_id):
            step["unresolved_calls"] = unresolved_calls[symbol_id]
        return step

    features: list[dict[str, Any]] = []
    globally_reached: set[str] = set()
    for root in roots:
        steps: list[dict[str, Any]] = []
        seen: set[str] = set()

        def walk(symbol_id: str, relation: str | None = None) -> None:
            if symbol_id in seen:
                return
            seen.add(symbol_id)
            globally_reached.add(symbol_id)
            steps.append(flow_step(symbol_id, len(steps) + 1, relation))
            for target in edges.get(symbol_id, []):
                walk(target, "calls")

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
