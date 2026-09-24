from __future__ import annotations

from datetime import datetime, timezone

from card_in_repo_api.recommendations import recommend_next_concept


class FakeIndex:
    def __init__(self, results: list[dict]) -> None:
        self.results = results
        self.indexed = False

    def index(self, analysis_id: str, concepts: list[dict]) -> None:
        self.indexed = True

    def similar(self, analysis_id: str, concept_id: str, limit: int = 5) -> list[dict]:
        return self.results[:limit]


def concepts() -> list[dict]:
    return [
        {"id": "concept:a", "name": "A"},
        {"id": "concept:b", "name": "B"},
        {"id": "concept:c", "name": "C"},
    ]


def test_due_review_wins_without_vector_detour() -> None:
    index = FakeIndex([])
    result = recommend_next_concept(
        "analysis-1",
        concepts(),
        [{"concept_id": "concept:b", "mastery": "understood", "review_due_at": "2026-01-01T00:00:00+00:00"}],
        index,
        now=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    assert result is not None
    assert result["concept"]["id"] == "concept:b"
    assert result["reason"] == "review_due"
    assert index.indexed is False


def test_learning_anchor_uses_pgvector_and_skips_understood_neighbor() -> None:
    index = FakeIndex([
        {"concept": {"id": "concept:b", "name": "B"}, "distance": 0.05},
        {"concept": {"id": "concept:c", "name": "C"}, "distance": 0.12},
    ])
    result = recommend_next_concept(
        "analysis-1",
        concepts(),
        [
            {"concept_id": "concept:a", "mastery": "learning", "updated_at": "2026-01-02T00:00:00+00:00"},
            {"concept_id": "concept:b", "mastery": "understood", "updated_at": "2026-01-01T00:00:00+00:00"},
        ],
        index,
    )
    assert result is not None
    assert result["concept"]["id"] == "concept:c"
    assert result["anchor_concept_id"] == "concept:a"
    assert result["reason"] == "structurally_related_to_learning"
    assert index.indexed is True


def test_execution_flow_is_fallback_and_all_understood_finishes() -> None:
    index = FakeIndex([])
    result = recommend_next_concept(
        "analysis-1",
        concepts(),
        [{"concept_id": "concept:a", "mastery": "understood"}],
        index,
    )
    assert result is not None
    assert result["concept"]["id"] == "concept:b"
    assert result["reason"] == "execution_flow"

    done = recommend_next_concept(
        "analysis-1",
        concepts(),
        [{"concept_id": concept["id"], "mastery": "understood"} for concept in concepts()],
        index,
    )
    assert done is None
