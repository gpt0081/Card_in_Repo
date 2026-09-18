import pytest

from card_in_repo_api.jobs import MemoryAnalysisJobQueue
from card_in_repo_api.outbox import dispatch_one


class Store:
    def __init__(self):
        self.pending = ("analysis-1", {"analysis_id": "analysis-1", "repository_url": "https://github.com/octo/demo", "ref": None})
        self.published = False

    def get_pending_job(self):
        return None if self.published else self.pending

    def mark_job_published(self, analysis_id):
        assert analysis_id == "analysis-1"
        self.published = True


class BrokenQueue(MemoryAnalysisJobQueue):
    def enqueue(self, job):
        raise RuntimeError("redis unavailable")


def test_dispatch_marks_published_only_after_queue_accepts_job():
    store = Store()
    with pytest.raises(RuntimeError):
        dispatch_one(store, BrokenQueue())
    assert store.published is False

    queue = MemoryAnalysisJobQueue()
    assert dispatch_one(store, queue) is True
    assert store.published is True
    delivery = queue.claim(0)
    assert delivery is not None and delivery.job.analysis_id == "analysis-1"
