import os
import time
import uuid

import pytest

from card_in_repo_api.jobs import AnalysisJob, RedisAnalysisJobQueue


REDIS_URL = os.getenv("TEST_REDIS_URL")
pytestmark = pytest.mark.skipif(not REDIS_URL, reason="TEST_REDIS_URL is not configured")


def _queue(consumer: str, *, stale_ms: int = 60_000) -> RedisAnalysisJobQueue:
    queue = RedisAnalysisJobQueue(REDIS_URL, consumer_id=consumer, stale_ms=stale_ms)
    # Isolate this integration test from previous CI attempts while retaining the
    # production stream/group implementation under test.
    queue.KEY = f"card-in-repo:test:analysis-jobs:{uuid.uuid4()}"
    from redis.exceptions import ResponseError

    try:
        queue._redis.xgroup_create(queue.KEY, queue.GROUP, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise
    return queue


def test_redis_stream_ack_removes_delivery():
    queue = _queue("worker-a")
    job = AnalysisJob("analysis-redis-ack", "https://github.com/octo/demo")
    queue.enqueue(job)

    delivery = queue.claim(timeout_seconds=0)
    assert delivery is not None and delivery.job == job
    queue.ack(delivery)

    assert queue.claim(timeout_seconds=0) is None
    assert queue._redis.xlen(queue.KEY) == 0


def test_stale_delivery_is_reclaimed_by_another_worker():
    first = _queue("worker-crashed")
    second = RedisAnalysisJobQueue(REDIS_URL, consumer_id="worker-recovery", stale_ms=1)
    second.KEY = first.KEY
    job = AnalysisJob("analysis-redis-redelivery", "https://github.com/octo/demo")
    first.enqueue(job)

    abandoned = first.claim(timeout_seconds=0)
    assert abandoned is not None and abandoned.job == job

    # Redis idle time is millisecond-granular. The production lease is 60s; this
    # short test lease proves the same XAUTOCLAIM path without slowing CI.
    time.sleep(0.01)
    recovered = second.claim(timeout_seconds=0)
    assert recovered is not None
    assert recovered.delivery_id == abandoned.delivery_id
    assert recovered.job == job
    second.ack(recovered)

    assert second._redis.xlen(second.KEY) == 0
