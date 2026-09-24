from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .concept_index import ConceptIndex


def _due(review_due_at: str | None, now: datetime) -> bool:
    if not review_due_at:
        return False
    try:
        value = datetime.fromisoformat(review_due_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= now


def recommend_next_concept(
    analysis_id: str,
    concepts: list[dict[str, Any]],
    states: list[dict[str, Any]],
    index: ConceptIndex,
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Choose the next fact-layer concept without letting retrieval invent curriculum facts."""
    if not concepts:
        return None
    now = now or datetime.now(timezone.utc)
    by_id = {concept["id"]: concept for concept in concepts}
    state_by_id = {state["concept_id"]: state for state in states if state.get("concept_id") in by_id}

    due = [
        state
        for state in states
        if state.get("concept_id") in by_id
        and state.get("mastery") != "unknown"
        and _due(state.get("review_due_at"), now)
    ]
    if due:
        due.sort(key=lambda state: (state.get("review_due_at") or "", state["concept_id"]))
        concept = by_id[due[0]["concept_id"]]
        return {"concept": concept, "reason": "review_due", "anchor_concept_id": concept["id"], "distance": None}

    learning = [state for state in states if state.get("concept_id") in by_id and state.get("mastery") == "learning"]
    if learning:
        learning.sort(key=lambda state: (state.get("updated_at") or "", state["concept_id"]), reverse=True)
        anchor_id = learning[0]["concept_id"]
        index.index(analysis_id, concepts)
        for result in index.similar(analysis_id, anchor_id, min(20, max(1, len(concepts) - 1))):
            candidate = result["concept"]
            if state_by_id.get(candidate["id"], {}).get("mastery") == "understood":
                continue
            return {
                "concept": candidate,
                "reason": "structurally_related_to_learning",
                "anchor_concept_id": anchor_id,
                "distance": result["distance"],
            }

    for concept in concepts:
        if state_by_id.get(concept["id"], {}).get("mastery") != "understood":
            return {"concept": concept, "reason": "execution_flow", "anchor_concept_id": None, "distance": None}
    return None
