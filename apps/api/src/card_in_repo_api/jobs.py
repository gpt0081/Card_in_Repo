from __future__ import annotations

import json
from collections import deque
from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(frozen=True)
class AnalysisJob:
    analysis_id: str
    repository_url: str
    ref: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"), sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> "AnalysisJob":
        value = json.loads(payload)
        if not isinstance(value, dict):
            raise ValueError("analysis job must be a JSON object")
        allowed = {"analysis_id", "repository_url", "ref"}
        if set(value) - allowed:
            raise ValueError("analysis job contains unknown fields")
        analysis_id = value.get("analysis_id")
        repository_url = value.get("repository_url")
        ref = value.get("ref")
        if not isinstance(analysis_id, str) or not analysis_id:
            raise ValueError("analysis_id must be a non-empty string")
        if not isinstance(repository_url, str) or not repository_url.startswith("https://github.com/"):
            raise ValueError("repository_url must be an https://github.com URL")
        if ref is not None and not isinstance(ref, str):
            raise ValueError("ref must be a string or null")
        return cls(analysis_id=analysis_id, repository_url=repository_url, ref=ref)


class AnalysisJobQueue(Protocol):
    def enqueue(self, job: AnalysisJob) -> None: ...
    def dequeue(self, timeout_seconds: int = 5) -> AnalysisJob | None: ...


class MemoryAnalysisJobQueue:
    """Deterministic queue for tests; production uses RedisAnalysisJobQueue."""

    def __init__(self) -> None:
        self._jobs: deque[AnalysisJob] = deque()

    def enqueue(self, job: AnalysisJob) -> None:
        self._jobs.append(job)

    def dequeue(self, timeout_seconds: int = 5) -> AnalysisJob | None:
        del timeout_seconds
        return self._jobs.popleft() if self._jobs else None


class RedisAnalysisJobQueue:
    """Minimal Redis list queue with no framework-specific job serialization."""

    KEY = "card-in-repo:analysis-jobs:v1"

    def __init__(self, redis_url: str) -> None:
        if not redis_url:
            raise ValueError("redis_url is required")
        from redis import Redis

        self._redis = Redis.from_url(redis_url, decode_responses=True)

    def enqueue(self, job: AnalysisJob) -> None:
        self._redis.rpush(self.KEY, job.to_json())

    def dequeue(self, timeout_seconds: int = 5) -> AnalysisJob | None:
        item = self._redis.blpop(self.KEY, timeout=max(0, timeout_seconds))
        if item is None:
            return None
        _key, payload = item
        return AnalysisJob.from_json(payload)
