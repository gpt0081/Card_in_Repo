from __future__ import annotations

import os

import pytest

from card_in_repo_api.postgres_store import PostgresAnalysisStore

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is required")


def test_stale_delivery_cannot_publish_ready_or_cards() -> None:
    store = PostgresAnalysisStore(DATABASE_URL)
    store.initialize()
    parsing = {
        "id": "analysis:owned-ready-stale",
        "state": "PARSING",
        "execution_delivery_id": "stream-current",
    }
    ready = {**parsing, "state": "READY", "card_ids": ["card:owned-ready-stale"]}
    card = {
        "id": "card:owned-ready-stale",
        "analysis_id": parsing["id"],
        "source": "stale",
    }
    store.put_analysis(parsing)

    assert store.put_completed_analysis(ready, [card], expected_delivery_id="stream-stale") is False
    assert store.get_analysis(parsing["id"]) == parsing
    assert store.get_card(card["id"]) is None


def test_current_delivery_atomically_publishes_ready_and_cards() -> None:
    store = PostgresAnalysisStore(DATABASE_URL)
    store.initialize()
    parsing = {
        "id": "analysis:owned-ready-current",
        "state": "PARSING",
        "execution_delivery_id": "stream-current",
    }
    ready = {**parsing, "state": "READY", "card_ids": ["card:owned-ready-current"]}
    card = {
        "id": "card:owned-ready-current",
        "analysis_id": parsing["id"],
        "source": "current",
    }
    store.put_analysis(parsing)

    assert store.put_completed_analysis(ready, [card], expected_delivery_id="stream-current") is True
    assert store.get_analysis(parsing["id"]) == ready
    assert store.get_card(card["id"]) == card
