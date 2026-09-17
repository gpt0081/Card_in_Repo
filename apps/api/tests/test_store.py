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
