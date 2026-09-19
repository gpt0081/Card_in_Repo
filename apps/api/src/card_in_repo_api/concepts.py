from __future__ import annotations

from typing import Any

from .teaching import build_basic_explanation, evidence_id


def build_concept_candidates(facts: dict[str, Any], features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive teachable concept candidates from static-analysis evidence only."""
    symbols = {symbol["id"]: symbol for symbol in facts.get("symbols", []) if symbol.get("id")}
    symbol_paths = facts.get("symbol_paths", {})
    concepts: list[dict[str, Any]] = []
    seen: set[str] = set()

    for feature in features:
        steps = feature.get("flow_steps", [])
        if not steps:
            continue
        concept_id = f"concept:flow:{feature['id']}"
        evidence: list[dict[str, Any]] = []
        for index, step in enumerate(steps):
            symbol = symbols.get(step.get("symbol_id"))
            if not symbol:
                continue
            evidence.append({
                "id": evidence_id(concept_id, index),
                "symbol_id": symbol["id"],
                "symbol_name": symbol.get("name"),
                "path": symbol_paths.get(symbol["id"]),
                "range": symbol.get("range"),
                "relation": step.get("relation"),
                "order": step.get("order"),
            })
        if not evidence:
            continue
        if concept_id in seen:
            continue
        seen.add(concept_id)
        concept = {
            "id": concept_id,
            "kind": "execution_flow",
            "name": feature.get("name") or evidence[0].get("symbol_name") or "Execution flow",
            "feature_id": feature["id"],
            "evidence": evidence,
        }
        concept["explanation"] = build_basic_explanation(concept)
        concepts.append(concept)
    return concepts
