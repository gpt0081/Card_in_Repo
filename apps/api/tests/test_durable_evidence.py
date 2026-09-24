import io

import pytest

from card_in_repo_api.evidence import DurableEvidenceError, reconstruct_card_evidence
from card_in_repo_api.source_artifacts import SourceArtifactStore
from card_in_repo_api.store import MemoryAnalysisStore


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


def _ready_card():
    store = MemoryAnalysisStore()
    artifacts = SourceArtifactStore(FakeS3(), "sources")
    repository = "owner/repo"
    commit = "a" * 40
    source = "def entry():\n    value = 1\n    return value\n"
    artifact = artifacts.put_snapshot(repository, commit, {"app.py": source})
    store.put_analysis({
        "id": "analysis-1",
        "state": "READY",
        "repository": repository,
        "commit_sha": commit,
        "facts": {"source_artifact": artifact.as_fact()},
    })
    card = {
        "id": "card-1",
        "analysis_id": "analysis-1",
        "repository": repository,
        "commit_sha": commit,
        "evidence": [{
            "id": "evidence-1",
            "type": "SOURCE_RANGE",
            "path": "app.py",
            "range": {"start": {"line": 2}, "end": {"line": 3}},
        }],
    }
    return store, artifacts, card


def test_card_evidence_is_reconstructed_from_verified_commit_artifact():
    store, artifacts, card = _ready_card()

    evidence = reconstruct_card_evidence(store, artifacts, card)

    assert evidence == [{
        **card["evidence"][0],
        "source": "    value = 1\n    return value\n",
        "verified": True,
    }]


def test_card_evidence_rejects_database_identity_drift():
    store, artifacts, card = _ready_card()
    card["commit_sha"] = "b" * 40

    with pytest.raises(DurableEvidenceError, match="identity"):
        reconstruct_card_evidence(store, artifacts, card)


def test_card_evidence_fails_closed_when_artifact_digest_changes():
    store, artifacts, card = _ready_card()
    artifacts.client.objects[0]["Body"] += b"tampered"

    with pytest.raises(DurableEvidenceError, match="verification failed"):
        reconstruct_card_evidence(store, artifacts, card)
