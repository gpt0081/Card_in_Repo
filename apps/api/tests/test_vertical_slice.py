from importlib import import_module

from fastapi.testclient import TestClient

from card_in_repo_api import app
from card_in_repo_api.github_source import GitHubRepositorySnapshot
from card_in_repo_api.jobs import MemoryAnalysisJobQueue
from card_in_repo_api.store import MemoryAnalysisStore

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
    created = client.post("/v1/fixture-analyses", json={"repository": "fixture/example", "commit_sha": "a" * 40, "path": "sample.py", "source": SOURCE})
    assert created.status_code == 201
    body = created.json()
    assert body["state"] == "READY"
    features = client.get(f"/v1/analyses/{body['id']}/features").json()["features"]
    entry = next(feature for feature in features if feature["name"] == "entry")
    assert [step["symbol_name"] for step in entry["flow_steps"]] == ["entry", "load_user", "normalize"]
    payload = client.get(f"/v1/cards/{body['card_ids'][0]}").json()
    assert payload["basic_explanation"]["status"] == "STUB_VERIFIED"


def test_fixture_analysis_rejects_unsupported_language():
    response = client.post("/v1/fixture-analyses", json={"commit_sha": "b" * 40, "path": "sample.rs", "source": "fn main() {}", "language": "rust"})
    assert response.status_code == 422


def test_public_github_analysis_is_queued_then_worker_reaches_ready(monkeypatch):
    app_module = import_module("card_in_repo_api.app")
    worker_module = import_module("card_in_repo_api.worker")
    store = MemoryAnalysisStore()
    queue = MemoryAnalysisJobQueue()
    app_module.set_store(store)
    app_module.set_queue(queue)
    monkeypatch.setattr(worker_module, "_STORE", store)
    sha = "c" * 40
    files = {"app.py": "from services.user import load_user\n\ndef entry(name):\n    return load_user(name)\n", "services/user.py": "def load_user(name):\n    return name.strip()\n"}
    monkeypatch.setattr(worker_module, "resolve_github_repository", lambda repository_url, ref=None: GitHubRepositorySnapshot(repository="octo/demo", commit_sha=sha, files=files))

    response = client.post("/v1/analyses", json={"repository_url": "https://github.com/octo/demo"})
    assert response.status_code == 202
    payload = response.json()
    assert payload["state"] == "QUEUED"
    assert client.get(f"/v1/analyses/{payload['id']}").json()["state"] == "QUEUED"

    assert worker_module.run_one(queue, timeout_seconds=0) is True
    analysis = store.get_analysis(payload["id"])
    assert analysis["state"] == "READY"
    assert analysis["commit_sha"] == sha
    entry = next(feature for feature in analysis["features"] if feature["name"] == "entry")
    assert [step["symbol_name"] for step in entry["flow_steps"]] == ["entry", "load_user"]
    cards = [store.get_card(card_id) for card_id in analysis["card_ids"]]
    assert {card["path"] for card in cards} == {"app.py", "services/user.py"}


def test_long_function_cards_are_syntax_aligned_and_linked():
    statements = [f"    value_{index} = {index}" for index in range(45)]
    source = "def long_job():\n" + "\n".join(statements) + "\n    return value_44\n"
    response = client.post("/v1/fixture-analyses", json={"repository": "fixture/long", "commit_sha": "d" * 40, "path": "long.py", "source": source})
    assert response.status_code == 201
    card_ids = response.json()["card_ids"]
    cards = [client.get(f"/v1/cards/{card_id}").json() for card_id in card_ids]
    long_cards = [card for card in cards if card["symbol_name"] == "long_job"]
    assert len(long_cards) == 2
    assert long_cards[0]["segment"]["next_card_id"] == long_cards[1]["id"]
    assert long_cards[1]["segment"]["previous_card_id"] == long_cards[0]["id"]
    assert long_cards[0]["evidence"][0]["range"] == long_cards[0]["range"]
