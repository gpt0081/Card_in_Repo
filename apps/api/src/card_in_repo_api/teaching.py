from __future__ import annotations

from typing import Any, Protocol


class UnverifiedExplanation(ValueError):
    """Raised when teaching text cites evidence outside the static fact layer."""


class TeachingProvider(Protocol):
    """Provider boundary: prose may vary, repository facts may not."""

    def explain_card(self, card: dict[str, Any], level: str) -> dict[str, Any]: ...


def evidence_id(concept_id: str, index: int) -> str:
    return f"{concept_id}:evidence:{index}"


def verify_explanation(
    explanation: dict[str, Any],
    available_evidence_ids: set[str],
    *,
    expected_level: str = "basic",
) -> dict[str, Any]:
    """Fail closed unless every teaching claim is backed by known evidence."""
    if explanation.get("level") != expected_level:
        raise UnverifiedExplanation(f"expected {expected_level} explanation")

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


def verify_on_demand_card_explanation(
    card: dict[str, Any], explanation: dict[str, Any], level: str
) -> dict[str, Any]:
    """Verify provider prose against immutable evidence already stored on the card."""
    if level not in {"intermediate", "advanced", "deep"}:
        raise UnverifiedExplanation("on-demand teaching level is not supported")
    available = {item["id"] for item in card.get("evidence", []) if item.get("id")}
    if not available:
        raise UnverifiedExplanation("cannot teach a card without source evidence")
    return verify_explanation(explanation, available, expected_level=level)


def generate_card_basic_explanation(
    card: dict[str, Any], provider: TeachingProvider | None
) -> dict[str, Any]:
    """Generate Basic teaching up front when a provider is configured, then verify it."""
    if provider is None:
        return build_card_basic_explanation(card)
    available = {item["id"] for item in card.get("evidence", []) if item.get("id")}
    if not available:
        raise UnverifiedExplanation("cannot teach a card without source evidence")
    explanation = provider.explain_card(card, "basic")
    return verify_explanation(explanation, available, expected_level="basic")


def _execution_order(item: dict[str, Any]) -> tuple[bool, int]:
    """Sort numbered execution evidence first and tolerate unresolved/null order facts."""
    order = item.get("order")
    return (order is None, order if isinstance(order, int) else 0)


def build_basic_explanation(concept: dict[str, Any]) -> dict[str, Any]:
    """Create the MVP Basic teaching layer from verified execution evidence."""
    evidence = concept.get("evidence", [])
    available = {item["id"] for item in evidence if item.get("id")}
    if not available:
        raise UnverifiedExplanation("cannot teach a concept without static evidence")

    ordered = sorted(evidence, key=_execution_order)
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


def build_card_basic_explanation(card: dict[str, Any]) -> dict[str, Any]:
    """Build the provider-free Basic fallback from source-range facts only."""
    evidence = card.get("evidence", [])
    available = {item["id"] for item in evidence if item.get("id")}
    if not available:
        raise UnverifiedExplanation("cannot teach a card without source evidence")
    segment = card.get("segment") or {}
    index = int(segment.get("index", 0)) + 1
    count = int(segment.get("count", 1))
    start = card["range"]["start"]["line"]
    end = card["range"]["end"]["line"]
    explanation = {
        "level": "basic",
        "claims": [{
            "text": f"This is {card['symbol_name']} segment {index} of {count}, covering {card['path']} lines {start}–{end}.",
            "evidence_ids": sorted(available),
        }],
        "verified": False,
    }
    return verify_explanation(explanation, available)
