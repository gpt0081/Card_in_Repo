from fastapi.testclient import TestClient

from card_in_repo_api import app


client = TestClient(app)
SOURCE = '''def normalize(name: str) -> str:
    return name.strip().lower()

async def load_user(name: str):
    key = normalize(name)
    return external_client.fetch(key)

def entry(name: str):
    return load_user(name)
'''


def test_fixture_analysis_reaches_ready_feature_map_and_evidence_card():
    assert client.get("/health").json() == {"status": "ok"}

    created = client.post("/v1/fixture-analyses", json={
        "repository": "fixture/example",
        "commit_sha": "a" * 40,
        "path": "sample.py",
        "source": SOURCE,
    })
    assert created.status_code == 201
    body = created.json()
    assert body["state"] == "READY"

    analysis = client.get(f"/v1/analyses/{body['id']}").json()
    assert analysis["commit_sha"] == "a" * 40

    features = client.get(f"/v1/analyses/{body['id']}/features").json()["features"]
    entry = next(feature for feature in features if feature["name"] == "entry")
    assert [step["symbol_name"] for step in entry["flow_steps"]] == [
        "entry", "load_user", "normalize"
    ]

    card = client.get(f"/v1/cards/{body['card_ids'][0]}")
    assert card.status_code == 200
    payload = card.json()
    assert payload["commit_sha"] == "a" * 40
    assert payload["source"]
    assert payload["basic_explanation"]["status"] == "STUB_VERIFIED"
    evidence_ids = payload["basic_explanation"]["evidence_ids"]
    assert evidence_ids == [payload["evidence"][0]["id"]]
    assert payload["evidence"][0]["path"] == "sample.py"


def test_fixture_analysis_rejects_unsupported_language():
    response = client.post("/v1/fixture-analyses", json={
        "commit_sha": "b" * 40,
        "path": "sample.rs",
        "source": "fn main() {}",
        "language": "rust",
    })
    assert response.status_code == 422
