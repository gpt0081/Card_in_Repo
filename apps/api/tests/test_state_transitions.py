from concurrent.futures import ThreadPoolExecutor
from importlib import import_module

from fastapi.testclient import TestClient

from card_in_repo_api.jobs import MemoryAnalysisJobQueue
from card_in_repo_api.store import MemoryAnalysisStore


def test_concurrent_requeue_enqueues_exactly_one_job():
    app_module = import_module("card_in_repo_api.app")
    store = MemoryAnalysisStore()
    queue = MemoryAnalysisJobQueue()
    app_module.set_store(store)
    app_module.set_queue(queue)
    analysis_id = "analysis-concurrent-requeue"
    store.put_analysis({
        "id": analysis_id,
        "state": "FAILED_EXHAUSTED",
        "repository": "octo/demo",
        "source_repository_url": "https://github.com/octo/demo",
        "source_ref": "main",
        "retry_count": 3,
        "error": "exhausted",
    })

    def requeue() -> int:
        with TestClient(app_module.app) as client:
            return client.post(f"/v1/analyses/{analysis_id}/requeue").status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: requeue(), range(2)))

    assert statuses == [202, 202]
    first = queue.claim(0)
    assert first is not None
    assert first.job.analysis_id == analysis_id
    assert queue.claim(0) is None


def test_successful_completion_clears_transient_error():
    app_module = import_module("card_in_repo_api.app")
    store = MemoryAnalysisStore()
    app_module.set_store(store)
    analysis_id = "analysis-recovered"
    store.put_analysis({"id": analysis_id, "state": "PARSING", "error": "analysis worker failed"})
    source = "def entry():\n    return 1\n"
    facts = {"symbols": [{"id": "symbol:entry", "name": "entry", "kind": "function", "range": {"start": {"line": 1}, "end": {"line": 2}}}], "calls": [], "symbol_paths": {"symbol:entry": "app.py"}}

    app_module.store_completed_analysis("octo/demo", "a" * 40, {"app.py": source}, facts, analysis_id=analysis_id)

    persisted = store.get_analysis(analysis_id)
    assert persisted["state"] == "READY"
    assert "error" not in persisted
