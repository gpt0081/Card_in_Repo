from importlib import import_module

from fastapi.testclient import TestClient

from card_in_repo_analyzer import analyze_repository
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


def test_typescript_class_method_flows_from_repository_map_into_semantic_cards():
    app_module = import_module("card_in_repo_api.app")
    store = MemoryAnalysisStore()
    app_module.set_store(store)
    source = """export class Greeter {
  greet(name: string) {
    const normalized = name.trim();
    const upper = normalized.toUpperCase();
    const message = `Hello ${upper}`;
    console.log(message);
    return message;
  }
}
"""
    path = "src/greeter.ts"
    facts = analyze_repository({path: source})

    created = app_module.store_completed_analysis(
        "fixture/typescript-class",
        "a" * 40,
        {path: source},
        facts,
    )

    features = client.get(f"/v1/analyses/{created['id']}/features")
    assert features.status_code == 200
    greet_steps = [
        step
        for feature in features.json()["features"]
        for step in feature["flow_steps"]
        if step["symbol_name"] == "greet"
    ]
    assert greet_steps
    assert greet_steps[0]["path"] == path
    assert greet_steps[0]["owner_symbol_name"] == "Greeter"

    response = client.get(f"/v1/analyses/{created['id']}/cards")
    assert response.status_code == 200
    greet_cards = [card for card in response.json()["cards"] if card["symbol_name"] == "greet"]
    assert greet_cards
    assert [card["segment"]["index"] for card in greet_cards] == list(range(len(greet_cards)))
    assert all(card["path"] == path for card in greet_cards)
    assert all(card["evidence"][0]["range"] == card["range"] for card in greet_cards)
    assert all(card["basic_explanation"]["verified"] is True for card in greet_cards)
    assert all(card["source"] in source for card in greet_cards)
