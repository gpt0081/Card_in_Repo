from __future__ import annotations

import json
import os
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


@dataclass(frozen=True)
class ClaimedAnalysisJob:
    delivery_id: str
    job: AnalysisJob
    attempts: int = 1


class AnalysisJobQueue(Protocol):
    def enqueue(self, job: AnalysisJob) -> None: ...
    def claim(self, timeout_seconds: int = 5) -> ClaimedAnalysisJob | None: ...
    def ack(self, delivery: ClaimedAnalysisJob) -> None: ...
    def dead_letter(self, delivery: ClaimedAnalysisJob, reason: str) -> None: ...


class MemoryAnalysisJobQueue:
    """Deterministic acknowledged queue for tests; production uses Redis Streams."""

    def __init__(self) -> None:
        self._jobs: deque[tuple[AnalysisJob, int]] = deque()
        self._pending: dict[str, tuple[AnalysisJob, int]] = {}
        self._dead: list[tuple[AnalysisJob, int, str]] = []
        self._sequence = 0

    def enqueue(self, job: AnalysisJob) -> None:
        self._jobs.append((job, 1))

    def claim(self, timeout_seconds: int = 5) -> ClaimedAnalysisJob | None:
        del timeout_seconds
        if not self._jobs:
            return None
        self._sequence += 1
        delivery_id = str(self._sequence)
        job, attempts = self._jobs.popleft()
        self._pending[delivery_id] = (job, attempts)
        return ClaimedAnalysisJob(delivery_id, job, attempts)

    def ack(self, delivery: ClaimedAnalysisJob) -> None:
        self._pending.pop(delivery.delivery_id, None)

    def dead_letter(self, delivery: ClaimedAnalysisJob, reason: str) -> None:
        pending = self._pending.pop(delivery.delivery_id, None)
        if pending is not None:
            job, attempts = pending
            self._dead.append((job, attempts, reason))

    def redeliver_pending(self) -> None:
        for delivery_id, (job, attempts) in list(self._pending.items()):
            self._jobs.appendleft((job, attempts + 1))
            del self._pending[delivery_id]

    @property
    def dead_letters(self) -> tuple[tuple[AnalysisJob, int, str], ...]:
        return tuple(self._dead)


class RedisAnalysisJobQueue:
    """Redis Streams queue with ACK, stale recovery, delivery counts, and a DLQ."""

    KEY = "card-in-repo:analysis-jobs:v2"
    GROUP = "analysis-workers-v1"
    DLQ_KEY = "card-in-repo:analysis-jobs:dead:v1"
    STALE_MS = 60_000

    def __init__(self, redis_url: str, *, consumer_id: str | None = None, stale_ms: int | None = None) -> None:
        if not redis_url:
            raise ValueError("redis_url is required")
        if stale_ms is not None and stale_ms < 0:
            raise ValueError("stale_ms must be non-negative")
        from redis import Redis
        from redis.exceptions import ResponseError

        self._redis = Redis.from_url(redis_url, decode_responses=True)
        self._consumer = consumer_id or os.getenv("CARD_IN_REPO_WORKER_ID") or f"worker-{os.getpid()}"
        self._stale_ms = self.STALE_MS if stale_ms is None else stale_ms
        try:
            self._redis.xgroup_create(self.KEY, self.GROUP, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def enqueue(self, job: AnalysisJob) -> None:
        self._redis.xadd(self.KEY, {"payload": job.to_json()})

    def _attempts(self, message_id: str) -> int:
        pending = self._redis.xpending_range(self.KEY, self.GROUP, min=message_id, max=message_id, count=1)
        if not pending:
            return 1
        return max(1, int(pending[0].get("times_delivered", 1)))

    def _delivery(self, message_id: str, fields: dict[str, str]) -> ClaimedAnalysisJob:
        payload = fields.get("payload")
        if payload is None:
            raise ValueError("analysis job stream entry has no payload")
        return ClaimedAnalysisJob(message_id, AnalysisJob.from_json(payload), self._attempts(message_id))

    def claim(self, timeout_seconds: int = 5) -> ClaimedAnalysisJob | None:
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative")
        _next, stale, _deleted = self._redis.xautoclaim(
            self.KEY, self.GROUP, self._consumer, self._stale_ms, start_id="0-0", count=1
        )
        if stale:
            message_id, fields = stale[0]
            return self._delivery(message_id, fields)
        read_options: dict[str, int] = {"count": 1}
        # Redis XREADGROUP interprets BLOCK 0 as "block forever", not
        # "do not block". Omit BLOCK entirely for an explicit zero timeout.
        if timeout_seconds > 0:
            read_options["block"] = timeout_seconds * 1000
        items = self._redis.xreadgroup(
            self.GROUP, self._consumer, {self.KEY: ">"}, **read_options
        )
        if not items:
            return None
        _stream, messages = items[0]
        message_id, fields = messages[0]
        return self._delivery(message_id, fields)

    def ack(self, delivery: ClaimedAnalysisJob) -> None:
        self._redis.xack(self.KEY, self.GROUP, delivery.delivery_id)
        self._redis.xdel(self.KEY, delivery.delivery_id)

    def dead_letter(self, delivery: ClaimedAnalysisJob, reason: str) -> None:
        self._redis.xadd(self.DLQ_KEY, {
            "payload": delivery.job.to_json(),
            "attempts": str(delivery.attempts),
            "reason": reason,
            "source_delivery_id": delivery.delivery_id,
        })
        self.ack(delivery)
