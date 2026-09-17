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


def test_memory_queue_preserves_fifo_order_and_empty_state():
    queue = MemoryAnalysisJobQueue()
    first = AnalysisJob("a1", "https://github.com/octo/one")
    second = AnalysisJob("a2", "https://github.com/octo/two", "dev")
    queue.enqueue(first)
    queue.enqueue(second)
    assert queue.dequeue() == first
    assert queue.dequeue() == second
    assert queue.dequeue() is None
