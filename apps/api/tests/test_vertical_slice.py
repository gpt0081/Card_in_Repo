from importlib import import_module

from fastapi.testclient import TestClient

from card_in_repo_api import app
from card_in_repo_api.github_source import GitHubSource


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


def test_public_github_analysis_uses_resolved_immutable_snapshot(monkeypatch):
    app_module = import_module("card_in_repo_api.app")
    sha = "c" * 40
    monkeypatch.setattr(
        app_module,
        "resolve_github_file",
        lambda repository_url, path, ref=None: GitHubSource(
            repository="octo/demo", commit_sha=sha, path="sample.py", source=SOURCE
        ),
    )

    response = client.post("/v1/analyses", json={
        "repository_url": "https://github.com/octo/demo",
        "path": "sample.py",
    })
    assert response.status_code == 201
    payload = response.json()
    assert payload["state"] == "READY"
    assert payload["repository"] == "octo/demo"
    assert payload["commit_sha"] == sha
    stored = client.get(f"/v1/analyses/{payload['id']}").json()
    assert stored["commit_sha"] == sha
