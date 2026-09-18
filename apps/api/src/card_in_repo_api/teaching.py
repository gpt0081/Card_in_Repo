from __future__ import annotations

from typing import Any


class UnverifiedExplanation(ValueError):
    """Raised when teaching text cites evidence outside the static fact layer."""


def evidence_id(concept_id: str, index: int) -> str:
    return f"{concept_id}:evidence:{index}"


def verify_explanation(
    explanation: dict[str, Any],
    available_evidence_ids: set[str],
) -> dict[str, Any]:
    """Fail closed unless every teaching claim is backed by known evidence."""
    if explanation.get("level") != "basic":
        raise UnverifiedExplanation("only Basic explanations are generated up front")

    claims = explanation.get("claims")
    if not isinstance(claims, list) or not claims:
        raise UnverifiedExplanation("an explanation must contain at least one claim")

    for claim in claims:
        text = claim.get("text") if isinstance(claim, dict) else None
        cited = claim.get("evidence_ids") if isinstance(claim, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise UnverifiedExplanation("every claim must contain teaching text")
        if not isinstance(cited, list) or not cited:
            raise UnverifiedExplanation("every claim must cite evidence")
        if any(item not in available_evidence_ids for item in cited):
            raise UnverifiedExplanation("claim cites evidence outside the static fact layer")

    return {**explanation, "verified": True}


def build_basic_explanation(concept: dict[str, Any]) -> dict[str, Any]:
    """Create the MVP Basic teaching layer from verified execution evidence.

    This deterministic generator keeps the first runnable slice provider-independent.
    A later LLM adapter may replace the wording, but must submit the same structured
    claims to ``verify_explanation`` before anything is shown to the learner.
    """
    evidence = concept.get("evidence", [])
    available = {item["id"] for item in evidence if item.get("id")}
    if not available:
        raise UnverifiedExplanation("cannot teach a concept without static evidence")

    ordered = sorted(evidence, key=lambda item: item.get("order", 0))
    names = [item.get("symbol_name") or item["symbol_id"] for item in ordered]
    path = " → ".join(names)
    explanation = {
        "level": "basic",
        "claims": [{
            "text": f"This flow runs in this analyzed order: {path}.",
            "evidence_ids": [item["id"] for item in ordered],
        }],
        "verified": False,
    }
    return verify_explanation(explanation, available)
