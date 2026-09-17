from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol


class AnalysisStore(Protocol):
    """Persistence boundary for immutable analysis snapshots and generated cards."""

    def put_analysis(self, analysis: dict[str, Any]) -> None: ...
    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None: ...
    def put_card(self, card: dict[str, Any]) -> None: ...
    def get_card(self, card_id: str) -> dict[str, Any] | None: ...


class MemoryAnalysisStore:
    """Deterministic test/dev store. Production will bind this contract to PostgreSQL."""

    def __init__(self) -> None:
        self._analyses: dict[str, dict[str, Any]] = {}
        self._cards: dict[str, dict[str, Any]] = {}

    def put_analysis(self, analysis: dict[str, Any]) -> None:
        self._analyses[analysis["id"]] = deepcopy(analysis)

    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        value = self._analyses.get(analysis_id)
        return deepcopy(value) if value is not None else None

    def put_card(self, card: dict[str, Any]) -> None:
        self._cards[card["id"]] = deepcopy(card)

    def get_card(self, card_id: str) -> dict[str, Any] | None:
        value = self._cards.get(card_id)
        return deepcopy(value) if value is not None else None
