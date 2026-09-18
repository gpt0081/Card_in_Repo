from __future__ import annotations

import os
import pytest
from card_in_repo_api.postgres_store import PostgresAnalysisStore

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is required")


def test_snapshots_survive_store_recreation() -> None:
    first = PostgresAnalysisStore(DATABASE_URL); first.initialize()
    analysis = {"id": "analysis:restart-proof", "state": "READY", "repository": "fixture/repo", "commit_sha": "a" * 40, "features": [{"id": "feature:1", "flow_steps": []}], "card_ids": ["card:restart-proof"]}
    card = {"id": "card:restart-proof", "analysis_id": analysis["id"], "repository": analysis["repository"], "commit_sha": analysis["commit_sha"], "path": "app.py", "source": "def main():\n    return 1"}
    first.put_analysis(analysis); first.put_card(card)
    second = PostgresAnalysisStore(DATABASE_URL)
    assert second.get_analysis(analysis["id"]) == analysis
    assert second.get_card(card["id"]) == card


def test_state_transition_is_compare_and_set() -> None:
    store = PostgresAnalysisStore(DATABASE_URL); store.initialize()
    original = {"id": "analysis:cas", "state": "FAILED_EXHAUSTED", "retry_count": 3}
    queued = {"id": "analysis:cas", "state": "QUEUED", "retry_count": 0, "requeued": True}
    store.put_analysis(original)
    assert store.transition_analysis(original["id"], "FAILED_EXHAUSTED", queued) is True
    assert store.transition_analysis(original["id"], "FAILED_EXHAUSTED", queued) is False
    assert store.get_analysis(original["id"]) == queued


def test_analysis_and_job_outbox_are_committed_together() -> None:
    store = PostgresAnalysisStore(DATABASE_URL); store.initialize()
    analysis = {"id": "analysis:outbox", "state": "QUEUED"}
    job = {"analysis_id": analysis["id"], "repository_url": "https://github.com/octo/demo", "ref": None}
    assert store.put_analysis_with_job(analysis, job) is True
    restarted = PostgresAnalysisStore(DATABASE_URL)
    assert restarted.get_analysis(analysis["id"]) == analysis
    assert restarted.get_pending_job() == (analysis["id"], job)
    restarted.mark_job_published(analysis["id"])
    assert restarted.get_pending_job() is None


def test_requeue_state_and_outbox_use_one_compare_and_set_transaction() -> None:
    store = PostgresAnalysisStore(DATABASE_URL); store.initialize()
    original = {"id": "analysis:outbox-requeue", "state": "FAILED_EXHAUSTED"}
    queued = {"id": original["id"], "state": "QUEUED", "requeued": True}
    job = {"analysis_id": original["id"], "repository_url": "https://github.com/octo/demo", "ref": "main"}
    store.put_analysis(original)
    assert store.put_analysis_with_job(queued, job, expected_state="FAILED_EXHAUSTED") is True
    assert store.put_analysis_with_job(queued, job, expected_state="FAILED_EXHAUSTED") is False
    assert store.get_pending_job() == (original["id"], job)


def test_postgres_execution_claim_has_single_delivery_owner() -> None:
    store = PostgresAnalysisStore(DATABASE_URL); store.initialize()
    analysis = {"id": "analysis:execution-owner", "state": "QUEUED", "retry_count": 0}
    store.put_analysis(analysis)

    first = store.claim_analysis_execution(analysis["id"], "stream-1", 0)
    assert first is not None
    assert first["state"] == "RESOLVING"
    assert first["execution_delivery_id"] == "stream-1"
    assert store.claim_analysis_execution(analysis["id"], "stream-2", 0) is None

    store.put_analysis({**first, "state": "PARSING"})
    resumed = store.claim_analysis_execution(analysis["id"], "stream-1", 1)
    assert resumed is not None
    assert resumed["state"] == "RESOLVING"
    assert resumed["retry_count"] == 1


def test_card_requires_existing_analysis() -> None:
    store = PostgresAnalysisStore(DATABASE_URL); store.initialize()
    orphan = {"id": "card:orphan", "analysis_id": "analysis:does-not-exist", "source": "pass"}
    with pytest.raises(Exception):
        store.put_card(orphan)
