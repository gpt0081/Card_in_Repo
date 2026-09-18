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
