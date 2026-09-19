from importlib import import_module

from fastapi.testclient import TestClient

from card_in_repo_api import app
from card_in_repo_api.store import MemoryAnalysisStore

client = TestClient(app)


def test_analysis_cards_are_gated_until_map_is_ready():
    app_module = import_module("card_in_repo_api.app")
    store = MemoryAnalysisStore()
    app_module.set_store(store)
    store.put_analysis({"id": "queued-cards", "state": "QUEUED", "card_ids": []})

    response = client.get("/v1/analyses/queued-cards/cards")

    assert response.status_code == 409


def test_analysis_cards_preserve_learning_order_and_verified_source_evidence():
    app_module = import_module("card_in_repo_api.app")
    store = MemoryAnalysisStore()
    app_module.set_store(store)
    source = "def entry(name):\n    cleaned = name.strip()\n    return cleaned.lower()\n"

    created = client.post(
        "/v1/fixture-analyses",
        json={"repository": "fixture/cards", "commit_sha": "f" * 40, "path": "app.py", "source": source},
    )
    assert created.status_code == 201

    response = client.get(f"/v1/analyses/{created.json()['id']}/cards")

    assert response.status_code == 200
    cards = response.json()["cards"]
    assert cards
    assert [card["id"] for card in cards] == created.json()["card_ids"]
    first = cards[0]
    assert first["symbol_name"] == "entry"
    assert first["path"] == "app.py"
    assert "def entry" in first["source"]
    assert first["evidence"][0]["range"] == first["range"]
    explanation = first["basic_explanation"]
    assert explanation["level"] == "basic"
    assert explanation["verified"] is True
    assert explanation["claims"]
    assert explanation["claims"][0]["evidence_ids"] == [first["evidence"][0]["id"]]
    assert "STUB_VERIFIED" not in str(first)
