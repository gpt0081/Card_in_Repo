from card_in_repo_api.store import MemoryAnalysisStore


def test_memory_store_round_trips_analysis_and_card_without_aliasing():
    store = MemoryAnalysisStore()
    analysis = {"id": "analysis-1", "state": "READY", "features": [{"name": "entry"}]}
    card = {"id": "card-1", "analysis_id": "analysis-1", "source": "return 1"}

    store.put_analysis(analysis)
    store.put_card(card)

    analysis["state"] = "CORRUPTED"
    card["source"] = "changed"
    loaded_analysis = store.get_analysis("analysis-1")
    loaded_card = store.get_card("card-1")

    assert loaded_analysis is not None
    assert loaded_analysis["state"] == "READY"
    assert loaded_card is not None
    assert loaded_card["source"] == "return 1"

    loaded_analysis["features"][0]["name"] = "mutated"
    assert store.get_analysis("analysis-1")["features"][0]["name"] == "entry"


def test_memory_store_returns_none_for_missing_records():
    store = MemoryAnalysisStore()
    assert store.get_analysis("missing") is None
    assert store.get_card("missing") is None


def test_execution_claim_rejects_distinct_duplicate_but_allows_same_delivery_resume():
    store = MemoryAnalysisStore()
    store.put_analysis({"id": "analysis-1", "state": "QUEUED", "repository_url": "https://github.com/octo/demo"})

    first = store.claim_analysis_execution("analysis-1", "stream-1", 0)
    assert first is not None
    assert first["state"] == "RESOLVING"
    assert first["execution_delivery_id"] == "stream-1"

    assert store.claim_analysis_execution("analysis-1", "duplicate-stream-2", 0) is None

    store.put_analysis({**first, "state": "PARSING"})
    resumed = store.claim_analysis_execution("analysis-1", "stream-1", 1)
    assert resumed is not None
    assert resumed["state"] == "RESOLVING"
    assert resumed["retry_count"] == 1


def test_completed_snapshot_requires_current_execution_owner():
    store = MemoryAnalysisStore()
    parsing = {"id": "analysis-owned", "state": "PARSING", "execution_delivery_id": "stream-new"}
    stale_ready = {**parsing, "state": "READY", "card_ids": ["card-stale"]}
    stale_card = {"id": "card-stale", "analysis_id": parsing["id"], "source": "stale"}
    store.put_analysis(parsing)

    assert store.put_completed_analysis(stale_ready, [stale_card], expected_delivery_id="stream-old") is False
    assert store.get_analysis(parsing["id"]) == parsing
    assert store.get_card(stale_card["id"]) is None

    ready = {**parsing, "state": "READY", "card_ids": ["card-current"]}
    current_card = {"id": "card-current", "analysis_id": parsing["id"], "source": "current"}
    assert store.put_completed_analysis(ready, [current_card], expected_delivery_id="stream-new") is True
    assert store.get_analysis(parsing["id"]) == ready
    assert store.get_card(current_card["id"]) == current_card
