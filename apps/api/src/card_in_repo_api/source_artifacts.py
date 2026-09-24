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

    def get_snapshot(
        self,
        repository: str,
        commit_sha: str,
        *,
        expected_sha256: str | None = None,
    ) -> dict[str, Any]:
        key = self.object_key(repository, commit_sha)
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        stream = response["Body"]
        body = stream.read() if hasattr(stream, "read") else stream
        if not isinstance(body, (bytes, bytearray)):
            raise RuntimeError("source snapshot body must be bytes")
        body = bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise RuntimeError("source snapshot sha256 mismatch")
        try:
            payload = json.loads(gzip.decompress(body))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RuntimeError("invalid source snapshot payload") from exc
        if payload.get("format") != "card-in-repo-source-snapshot-v1":
            raise RuntimeError("unsupported source snapshot format")
        if payload.get("repository") != repository or payload.get("commit_sha") != commit_sha:
            raise RuntimeError("source snapshot identity mismatch")
        files = payload.get("files")
        if not isinstance(files, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in files.items()):
            raise RuntimeError("invalid source snapshot files")
        return payload

    def get_source_range(
        self,
        repository: str,
        commit_sha: str,
        path: str,
        start_line: int,
        end_line: int,
        *,
        expected_sha256: str | None = None,
    ) -> str:
        if start_line < 1 or end_line < start_line:
            raise ValueError("invalid source range")
        snapshot = self.get_snapshot(repository, commit_sha, expected_sha256=expected_sha256)
        try:
            source = snapshot["files"][path]
        except KeyError as exc:
            raise KeyError(f"source path not found in snapshot: {path}") from exc
        lines = source.splitlines(keepends=True)
        if start_line > len(lines):
            raise ValueError("source range starts beyond end of file")
        return "".join(lines[start_line - 1 : end_line])


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
