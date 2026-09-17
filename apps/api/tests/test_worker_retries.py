from importlib import import_module

import pytest

from card_in_repo_api.github_source import GitHubRepositorySnapshot
from card_in_repo_api.jobs import AnalysisJob, MemoryAnalysisJobQueue
from card_in_repo_api.store import MemoryAnalysisStore


def test_retryable_failure_is_dead_lettered_after_bounded_attempts(monkeypatch):
    worker = import_module("card_in_repo_api.worker")
    store = MemoryAnalysisStore()
    queue = MemoryAnalysisJobQueue()
    analysis_id = "analysis-retry"
    store.put_analysis({"id": analysis_id, "state": "QUEUED", "repository_url": "https://github.com/octo/demo"})
    queue.enqueue(AnalysisJob(analysis_id, "https://github.com/octo/demo"))
    monkeypatch.setattr(worker, "_STORE", store)
    monkeypatch.setattr(worker, "resolve_github_repository", lambda *_args, **_kwargs: GitHubRepositorySnapshot(repository="octo/demo", commit_sha="a" * 40, files={"app.py": "def run():\n    return 1\n"}))
    monkeypatch.setattr(worker, "analyze_python_repository", lambda _files: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setenv("CARD_IN_REPO_MAX_ANALYSIS_ATTEMPTS", "3")

    with pytest.raises(RuntimeError):
        worker.run_one(queue, timeout_seconds=0)
    assert store.get_analysis(analysis_id)["state"] == "FAILED_RETRYABLE"
    assert store.get_analysis(analysis_id)["retry_count"] == 0

    queue.redeliver_pending()
    with pytest.raises(RuntimeError):
        worker.run_one(queue, timeout_seconds=0)
    assert store.get_analysis(analysis_id)["retry_count"] == 1

    queue.redeliver_pending()
    assert worker.run_one(queue, timeout_seconds=0) is True
    exhausted = store.get_analysis(analysis_id)
    assert exhausted["state"] == "FAILED_EXHAUSTED"
    assert exhausted["retry_count"] == 2
    assert len(queue.dead_letters) == 1
    assert queue.dead_letters[0][0].analysis_id == analysis_id


def test_retry_budget_must_be_positive(monkeypatch):
    worker = import_module("card_in_repo_api.worker")
    monkeypatch.setenv("CARD_IN_REPO_MAX_ANALYSIS_ATTEMPTS", "0")
    with pytest.raises(ValueError):
        worker._max_attempts()
