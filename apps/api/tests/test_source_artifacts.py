import gzip
import hashlib
import json

from card_in_repo_api.source_artifacts import SourceArtifactStore


class FakeS3:
    def __init__(self) -> None:
        self.bucket_exists = False
        self.created = []
        self.objects = []

    def head_bucket(self, *, Bucket):
        if not self.bucket_exists:
            raise RuntimeError("missing")
        return {}

    def create_bucket(self, *, Bucket):
        self.bucket_exists = True
        self.created.append(Bucket)
        return {}

    def put_object(self, **kwargs):
        self.objects.append(kwargs)
        return {}


def test_source_snapshot_is_commit_pinned_deterministic_and_self_describing():
    client = FakeS3()
    store = SourceArtifactStore(client, "sources")
    commit = "a" * 40

    artifact = store.put_snapshot(
        "owner/repo",
        commit,
        {"z.ts": "export const z = 1;\n", "src/a.ts": "export const a = 1;\n"},
    )

    assert client.created == ["sources"]
    assert artifact.key == f"repositories/owner/repo/{commit}/sources.json.gz"
    saved = client.objects[0]
    assert saved["Bucket"] == "sources"
    assert saved["Key"] == artifact.key
    assert saved["ContentEncoding"] == "gzip"
    assert saved["Metadata"]["sha256"] == hashlib.sha256(saved["Body"]).hexdigest() == artifact.sha256

    payload = json.loads(gzip.decompress(saved["Body"]))
    assert payload == {
        "format": "card-in-repo-source-snapshot-v1",
        "repository": "owner/repo",
        "commit_sha": commit,
        "files": {"src/a.ts": "export const a = 1;\n", "z.ts": "export const z = 1;\n"},
    }
    assert artifact.as_fact()["format"] == "card-in-repo-source-snapshot-v1+json+gzip"


def test_repeated_snapshot_reuses_bucket_and_produces_identical_content_address():
    client = FakeS3()
    store = SourceArtifactStore(client, "sources")
    commit = "b" * 40
    files = {"main.py": "print('hi')\n"}

    first = store.put_snapshot("owner/repo", commit, files)
    second = store.put_snapshot("owner/repo", commit, files)

    assert client.created == ["sources"]
    assert first.key == second.key
    assert first.sha256 == second.sha256
    assert client.objects[0]["Body"] == client.objects[1]["Body"]
