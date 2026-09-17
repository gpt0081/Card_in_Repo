import pytest

from card_in_repo_api.jobs import AnalysisJob, MemoryAnalysisJobQueue


def test_analysis_job_round_trip_is_stable():
    job = AnalysisJob("analysis-1", "https://github.com/octo/demo", "main")
    assert AnalysisJob.from_json(job.to_json()) == job
    assert job.to_json() == '{"analysis_id":"analysis-1","ref":"main","repository_url":"https://github.com/octo/demo"}'


def test_analysis_job_rejects_unknown_or_invalid_payloads():
    with pytest.raises(ValueError):
        AnalysisJob.from_json('{"analysis_id":"a","repository_url":"https://example.com/repo"}')
    with pytest.raises(ValueError):
        AnalysisJob.from_json('{"analysis_id":"a","repository_url":"https://github.com/o/r","extra":true}')


def test_memory_queue_preserves_fifo_and_requires_ack():
    queue = MemoryAnalysisJobQueue()
    first = AnalysisJob("a1", "https://github.com/octo/one")
    second = AnalysisJob("a2", "https://github.com/octo/two", "dev")
    queue.enqueue(first)
    queue.enqueue(second)

    first_delivery = queue.claim()
    assert first_delivery is not None and first_delivery.job == first
    assert first_delivery.attempts == 1
    queue.ack(first_delivery)
    second_delivery = queue.claim()
    assert second_delivery is not None and second_delivery.job == second
    queue.ack(second_delivery)
    assert queue.claim() is None


def test_unacked_memory_delivery_increments_attempt_on_redelivery():
    queue = MemoryAnalysisJobQueue()
    job = AnalysisJob("a1", "https://github.com/octo/one")
    queue.enqueue(job)
    abandoned = queue.claim()
    assert abandoned is not None and abandoned.attempts == 1

    queue.redeliver_pending()
    redelivery = queue.claim()
    assert redelivery is not None
    assert redelivery.job == job
    assert redelivery.delivery_id != abandoned.delivery_id
    assert redelivery.attempts == 2


def test_memory_queue_dead_letter_removes_pending_delivery():
    queue = MemoryAnalysisJobQueue()
    job = AnalysisJob("a1", "https://github.com/octo/one")
    queue.enqueue(job)
    delivery = queue.claim()
    assert delivery is not None
    queue.dead_letter(delivery, "exhausted")
    assert queue.claim() is None
    assert queue.dead_letters == ((job, 1, "exhausted"),)
