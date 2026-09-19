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
    suffix = uuid.uuid4()
    queue.KEY = f"card-in-repo:test:analysis-jobs:{suffix}"
    queue.DLQ_KEY = f"card-in-repo:test:analysis-jobs:dead:{suffix}"
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
    second.DLQ_KEY = first.DLQ_KEY
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


def test_repeated_stale_delivery_reaches_dlq_with_attempt_count():
    first = _queue("worker-attempt-1", stale_ms=1)
    job = AnalysisJob("analysis-redis-dlq", "https://github.com/octo/demo")
    first.enqueue(job)

    delivery = first.claim(timeout_seconds=0)
    assert delivery is not None and delivery.attempts == 1

    # Simulate two consecutive worker crashes. Each new consumer reclaims the
    # same pending stream entry, which must advance Redis' delivery counter.
    for expected_attempt, consumer in ((2, "worker-attempt-2"), (3, "worker-attempt-3")):
        time.sleep(0.01)
        recovery = RedisAnalysisJobQueue(REDIS_URL, consumer_id=consumer, stale_ms=1)
        recovery.KEY = first.KEY
        recovery.DLQ_KEY = first.DLQ_KEY
        delivery = recovery.claim(timeout_seconds=0)
        assert delivery is not None
        assert delivery.job == job
        assert delivery.attempts == expected_attempt

    recovery.dead_letter(delivery, "retry budget exhausted")

    # Dead-lettering is a transfer: the source delivery is ACKed/deleted and one
    # auditable record remains with the final attempt count and original payload.
    assert recovery._redis.xlen(recovery.KEY) == 0
    dead = recovery._redis.xrange(recovery.DLQ_KEY)
    assert len(dead) == 1
    _dead_id, fields = dead[0]
    assert AnalysisJob.from_json(fields["payload"]) == job
    assert fields["attempts"] == "3"
    assert fields["reason"] == "retry budget exhausted"
    assert fields["source_delivery_id"] == delivery.delivery_id
