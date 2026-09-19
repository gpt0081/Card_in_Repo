from importlib import import_module

from fastapi.testclient import TestClient

from card_in_repo_api import app
from card_in_repo_api.store import MemoryAnalysisStore

client = TestClient(app)


class Provider:
    def __init__(self, evidence_id=None):
        self.evidence_id = evidence_id
        self.calls = []

    def explain_card(self, card, level):
        self.calls.append((card["id"], level))
        evidence_id = self.evidence_id or card["evidence"][0]["id"]
        return {
            "level": level,
            "claims": [{"text": "The source range supports this teaching claim.", "evidence_ids": [evidence_id]}],
            "verified": False,
        }


def _ready_card():
    module = import_module("card_in_repo_api.app")
    store = MemoryAnalysisStore()
    module.set_store(store)
    created = client.post(
        "/v1/fixture-analyses",
        json={
            "repository": "fixture/teaching",
            "commit_sha": "a" * 40,
            "path": "app.py",
            "source": "def entry(name):\n    return name.strip()\n",
        },
    )
    assert created.status_code == 201
    return module, created.json()["card_ids"][0]


def test_intermediate_teaching_is_generated_only_on_demand_and_verified():
    module, card_id = _ready_card()
    provider = Provider()
    module.set_teaching_provider(provider)
    try:
        response = client.get(f"/v1/cards/{card_id}/teaching?level=intermediate")
    finally:
        module.set_teaching_provider(None)

    assert response.status_code == 200
    body = response.json()
    assert body["level"] == "intermediate"
    assert body["verified"] is True
    assert provider.calls == [(card_id, "intermediate")]


def test_verified_teaching_is_persisted_and_reused_without_provider():
    module, card_id = _ready_card()
    provider = Provider()
    module.set_teaching_provider(provider)
    first = client.get(f"/v1/cards/{card_id}/teaching?level=deep")
    module.set_teaching_provider(None)
    second = client.get(f"/v1/cards/{card_id}/teaching?level=deep")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert provider.calls == [(card_id, "deep")]
    persisted = client.get(f"/v1/cards/{card_id}").json()
    assert persisted["on_demand_teaching"]["deep"]["verified"] is True


def test_on_demand_teaching_fails_closed_for_unknown_evidence():
    module, card_id = _ready_card()
    module.set_teaching_provider(Provider("evidence:invented"))
    try:
        response = client.get(f"/v1/cards/{card_id}/teaching?level=advanced")
    finally:
        module.set_teaching_provider(None)

    assert response.status_code == 422
    assert response.json()["detail"] == "teaching output failed evidence verification"


def test_basic_is_not_an_on_demand_level_and_missing_provider_is_explicit():
    module, card_id = _ready_card()
    module.set_teaching_provider(None)

    assert client.get(f"/v1/cards/{card_id}/teaching?level=basic").status_code == 422
    response = client.get(f"/v1/cards/{card_id}/teaching?level=deep")
    assert response.status_code == 503
    assert response.json()["detail"] == "on-demand teaching provider is not configured"
