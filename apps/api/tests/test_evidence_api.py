import io
from importlib import import_module

from fastapi.testclient import TestClient

from card_in_repo_api import app
from card_in_repo_api.source_artifacts import SourceArtifactStore
from card_in_repo_api.store import MemoryAnalysisStore

client = TestClient(app)


class FakeS3:
    def __init__(self):
        self.objects = []

    def head_bucket(self, **kwargs):
        return {}

    def create_bucket(self, **kwargs):
        return {}

    def put_object(self, **kwargs):
        self.objects.append(kwargs)
        return {}

    def get_object(self, *, Bucket, Key):
        saved = next(item for item in self.objects if item["Bucket"] == Bucket and item["Key"] == Key)
        return {"Body": io.BytesIO(saved["Body"])}


def test_card_evidence_endpoint_reads_verified_durable_source():
    app_module = import_module("card_in_repo_api.app")
    store = MemoryAnalysisStore()
    artifacts = SourceArtifactStore(FakeS3(), "sources")
    app_module.set_store(store)
    app_module.set_source_artifact_store(artifacts)

    repository = "owner/repo"
    commit = "a" * 40
    source = "def entry():\n    value = 1\n    return value\n"
    artifact = artifacts.put_snapshot(repository, commit, {"app.py": source})
    analysis_id = "analysis-1"
    card_id = "card-1"
    store.put_analysis({
        "id": analysis_id,
        "state": "READY",
        "repository": repository,
        "commit_sha": commit,
        "facts": {"source_artifact": artifact.as_fact()},
        "card_ids": [card_id],
    })
    store.put_card({
        "id": card_id,
        "analysis_id": analysis_id,
        "repository": repository,
        "commit_sha": commit,
        "source": "this database copy is deliberately not authoritative",
        "evidence": [{
            "id": "evidence-1",
            "type": "SOURCE_RANGE",
            "path": "app.py",
            "range": {"start": {"line": 2}, "end": {"line": 3}},
        }],
    })

    response = client.get(f"/v1/cards/{card_id}/evidence")

    assert response.status_code == 200
    payload = response.json()
    assert payload["repository"] == repository
    assert payload["commit_sha"] == commit
    assert payload["evidence"][0]["verified"] is True
    assert payload["evidence"][0]["source"] == "    value = 1\n    return value\n"


def test_card_evidence_endpoint_fails_closed_when_artifact_is_tampered():
    app_module = import_module("card_in_repo_api.app")
    store = MemoryAnalysisStore()
    artifacts = SourceArtifactStore(FakeS3(), "sources")
    app_module.set_store(store)
    app_module.set_source_artifact_store(artifacts)

    repository = "owner/repo"
    commit = "b" * 40
    artifact = artifacts.put_snapshot(repository, commit, {"app.py": "def entry():\n    return 1\n"})
    artifacts.client.objects[0]["Body"] += b"tampered"
    store.put_analysis({"id": "analysis-2", "state": "READY", "repository": repository, "commit_sha": commit, "facts": {"source_artifact": artifact.as_fact()}, "card_ids": ["card-2"]})
    store.put_card({"id": "card-2", "analysis_id": "analysis-2", "repository": repository, "commit_sha": commit, "evidence": [{"id": "evidence-2", "type": "SOURCE_RANGE", "path": "app.py", "range": {"start": {"line": 1}, "end": {"line": 1}}}]})

    response = client.get("/v1/cards/card-2/evidence")

    assert response.status_code == 409
    assert response.json()["detail"] == "card evidence could not be verified"
