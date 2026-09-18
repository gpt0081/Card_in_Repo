from __future__ import annotations

from copy import deepcopy
from threading import Lock
from typing import Any, Protocol


class AnalysisStore(Protocol):
    """Persistence boundary for immutable analysis snapshots and generated cards."""

    def put_analysis(self, analysis: dict[str, Any]) -> None: ...
    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None: ...
    def transition_analysis(self, analysis_id: str, expected_state: str, analysis: dict[str, Any]) -> bool: ...
    def claim_analysis_execution(self, analysis_id: str, delivery_id: str, retry_count: int) -> dict[str, Any] | None: ...
    def put_card(self, card: dict[str, Any]) -> None: ...
    def get_card(self, card_id: str) -> dict[str, Any] | None: ...


class MemoryAnalysisStore:
    """Deterministic test/dev store with atomic state transitions."""

    def __init__(self) -> None:
        self._analyses: dict[str, dict[str, Any]] = {}
        self._cards: dict[str, dict[str, Any]] = {}
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
        """Claim one analysis execution; only the same delivery may resume an active claim."""
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

    def put_card(self, card: dict[str, Any]) -> None:
        with self._lock:
            self._cards[card["id"]] = deepcopy(card)

    def get_card(self, card_id: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._cards.get(card_id)
            return deepcopy(value) if value is not None else None
