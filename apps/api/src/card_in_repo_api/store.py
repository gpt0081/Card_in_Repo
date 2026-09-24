from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Protocol


class AnalysisStore(Protocol):
    """Persistence boundary for immutable analysis snapshots, generated cards, and learner state."""

    def put_analysis(self, analysis: dict[str, Any]) -> None: ...
    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None: ...
    def transition_analysis(self, analysis_id: str, expected_state: str, analysis: dict[str, Any]) -> bool: ...
    def claim_analysis_execution(self, analysis_id: str, delivery_id: str, retry_count: int) -> dict[str, Any] | None: ...
    def put_completed_analysis(self, analysis: dict[str, Any], cards: list[dict[str, Any]], *, expected_delivery_id: str | None = None) -> bool: ...
    def put_card(self, card: dict[str, Any]) -> None: ...
    def get_card(self, card_id: str) -> dict[str, Any] | None: ...
    def put_learning_state(self, github_user_id: int, repository: str, concept_id: str, mastery: str, review_due_at: str | None = None) -> dict[str, Any]: ...
    def get_learning_state(self, github_user_id: int, repository: str) -> list[dict[str, Any]]: ...
    def put_concept_vectors(self, analysis_id: str, concepts: list[dict[str, Any]]) -> None: ...
    def find_similar_concepts(self, analysis_id: str, concept_id: str, limit: int = 5) -> list[dict[str, Any]]: ...


class MemoryAnalysisStore:
    """Deterministic test/dev store with atomic state transitions."""

    def __init__(self) -> None:
        self._analyses: dict[str, dict[str, Any]] = {}
        self._cards: dict[str, dict[str, Any]] = {}
        self._learning: dict[tuple[int, str, str], dict[str, Any]] = {}
        self._concept_vectors: dict[tuple[str, str], dict[str, Any]] = {}
        self._lock = Lock()

    def put_analysis(self, analysis: dict[str, Any]) -> None:
        with self._lock:
            self._analyses[analysis["id"]] = deepcopy(analysis)

    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._analyses.get(analysis_id)
            return deepcopy(value) if value is not None else None

    def transition_analysis(self, analysis_id: str, expected_state: str, analysis: dict[str, Any]) -> bool:
        with self._lock:
            current = self._analyses.get(analysis_id)
            if current is None or current.get("state") != expected_state:
                return False
            self._analyses[analysis_id] = deepcopy(analysis)
            return True

    def claim_analysis_execution(self, analysis_id: str, delivery_id: str, retry_count: int) -> dict[str, Any] | None:
        with self._lock:
            current = self._analyses.get(analysis_id)
            if current is None:
                return None
            state = current.get("state")
            same_delivery = current.get("execution_delivery_id") == delivery_id
            if state not in {"QUEUED", "FAILED_RETRYABLE"} and not (state in {"RESOLVING", "PARSING"} and same_delivery):
                return None
            claimed = {**current, "state": "RESOLVING", "retry_count": retry_count, "execution_delivery_id": delivery_id}
            self._analyses[analysis_id] = deepcopy(claimed)
            return deepcopy(claimed)

    def put_completed_analysis(self, analysis: dict[str, Any], cards: list[dict[str, Any]], *, expected_delivery_id: str | None = None) -> bool:
        with self._lock:
            current = self._analyses.get(analysis["id"])
            if expected_delivery_id is not None and (
                current is None or current.get("state") != "PARSING" or current.get("execution_delivery_id") != expected_delivery_id
            ):
                return False
            for card in cards:
                if card["analysis_id"] != analysis["id"]:
                    raise ValueError("card belongs to a different analysis")
            for card in cards:
                self._cards[card["id"]] = deepcopy(card)
            self._analyses[analysis["id"]] = deepcopy(analysis)
            return True

    def put_card(self, card: dict[str, Any]) -> None:
        with self._lock:
            self._cards[card["id"]] = deepcopy(card)

    def get_card(self, card_id: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._cards.get(card_id)
            return deepcopy(value) if value is not None else None

    def put_learning_state(self, github_user_id: int, repository: str, concept_id: str, mastery: str, review_due_at: str | None = None) -> dict[str, Any]:
        if mastery not in {"unknown", "learning", "understood"}:
            raise ValueError("invalid mastery")
        value = {"github_user_id": github_user_id, "repository": repository, "concept_id": concept_id, "mastery": mastery, "review_due_at": review_due_at, "updated_at": datetime.now(timezone.utc).isoformat()}
        with self._lock:
            self._learning[(github_user_id, repository, concept_id)] = deepcopy(value)
        return deepcopy(value)

    def get_learning_state(self, github_user_id: int, repository: str) -> list[dict[str, Any]]:
        with self._lock:
            values = [deepcopy(value) for (user_id, repo, _), value in self._learning.items() if user_id == github_user_id and repo == repository]
        return sorted(values, key=lambda value: value["concept_id"])

    def put_concept_vectors(self, analysis_id: str, concepts: list[dict[str, Any]]) -> None:
        with self._lock:
            for concept in concepts:
                self._concept_vectors[(analysis_id, concept["id"])] = deepcopy(concept)

    def find_similar_concepts(self, analysis_id: str, concept_id: str, limit: int = 5) -> list[dict[str, Any]]:
        with self._lock:
            target = self._concept_vectors.get((analysis_id, concept_id))
            if target is None:
                return []
            vector = target["vector"]
            candidates = [deepcopy(value) for (aid, cid), value in self._concept_vectors.items() if aid == analysis_id and cid != concept_id]
        def distance(item: dict[str, Any]) -> float:
            return sum((left - right) ** 2 for left, right in zip(vector, item["vector"])) ** 0.5
        return [{"concept": item["concept"], "distance": distance(item)} for item in sorted(candidates, key=distance)[:limit]]
