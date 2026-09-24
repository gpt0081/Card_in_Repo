from __future__ import annotations

import gzip
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Protocol


class S3Client(Protocol):
    def head_bucket(self, *, Bucket: str) -> Any: ...
    def create_bucket(self, *, Bucket: str) -> Any: ...
    def put_object(self, **kwargs: Any) -> Any: ...
    def get_object(self, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class SourceArtifact:
    bucket: str
    key: str
    sha256: str
    size_bytes: int

    def as_fact(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "key": self.key,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "format": "card-in-repo-source-snapshot-v1+json+gzip",
        }


class SourceArtifactStore:
    def __init__(self, client: S3Client, bucket: str) -> None:
        self.client = client
        self.bucket = bucket
        self._bucket_ready = False

    def _ensure_bucket(self) -> None:
        if self._bucket_ready:
            return
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)
        self._bucket_ready = True

    @staticmethod
    def object_key(repository: str, commit_sha: str) -> str:
        owner, name = repository.split("/", 1)
        return f"repositories/{owner}/{name}/{commit_sha}/sources.json.gz"

    def put_snapshot(self, repository: str, commit_sha: str, files: dict[str, str]) -> SourceArtifact:
        payload = json.dumps(
            {
                "format": "card-in-repo-source-snapshot-v1",
                "repository": repository,
                "commit_sha": commit_sha,
                "files": {path: files[path] for path in sorted(files)},
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        body = gzip.compress(payload, mtime=0)
        digest = hashlib.sha256(body).hexdigest()
        key = self.object_key(repository, commit_sha)
        self._ensure_bucket()
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
            ContentEncoding="gzip",
            Metadata={"sha256": digest, "commit-sha": commit_sha},
        )
        return SourceArtifact(self.bucket, key, digest, len(body))


def build_source_artifact_store() -> SourceArtifactStore | None:
    backend = os.getenv("CARD_IN_REPO_SOURCE_ARTIFACTS", "none").strip().lower()
    if backend in {"", "none"}:
        return None
    if backend != "s3":
        raise RuntimeError(f"unsupported source artifact backend: {backend}")

    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT_URL"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )
    return SourceArtifactStore(client, os.getenv("CARD_IN_REPO_SOURCE_BUCKET", "card-in-repo-sources"))
