from __future__ import annotations

import os

import pytest

from card_in_repo_api.postgres_store import PostgresAnalysisStore

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is required")


def test_stale_card_snapshots_merge_independent_teaching_levels() -> None:
    store = PostgresAnalysisStore(DATABASE_URL)
    store.initialize()
    analysis = {"id": "analysis:teaching-merge", "state": "READY"}
    card = {
        "id": "card:teaching-merge",
        "analysis_id": analysis["id"],
        "source": "def main():\n    return 1",
        "evidence": [{"id": "evidence:source", "kind": "SOURCE_RANGE"}],
    }
    store.put_analysis(analysis)
    store.put_card(card)

    # Model two requests that both read before either generated teaching is saved.
    intermediate_snapshot = store.get_card(card["id"])
    deep_snapshot = store.get_card(card["id"])
    assert intermediate_snapshot is not None
    assert deep_snapshot is not None

    intermediate = {
        "level": "intermediate",
        "verified": True,
        "claims": [{"text": "Intermediate", "evidence_ids": ["evidence:source"]}],
    }
    deep = {
        "level": "deep",
        "verified": True,
        "claims": [{"text": "Deep", "evidence_ids": ["evidence:source"]}],
    }
    intermediate_snapshot["on_demand_teaching"] = {"intermediate": intermediate}
    deep_snapshot["on_demand_teaching"] = {"deep": deep}

    store.put_card(intermediate_snapshot)
    store.put_card(deep_snapshot)

    persisted = store.get_card(card["id"])
    assert persisted is not None
    assert persisted["on_demand_teaching"] == {
        "intermediate": intermediate,
        "deep": deep,
    }
