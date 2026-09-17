from __future__ import annotations

from card_in_repo_analyzer import analyze_python_repository

from .app import _STORE, store_completed_analysis
from .github_source import GitHubSourceError, resolve_github_repository
from .jobs import AnalysisJobQueue
from .runtime import build_analysis_queue


def run_one(queue: AnalysisJobQueue | None = None, timeout_seconds: int = 5) -> bool:
    """Process one claimed analysis; acknowledge only after a durable outcome is stored."""
    queue = queue or build_analysis_queue()
    delivery = queue.claim(timeout_seconds)
    if delivery is None:
        return False
    job = delivery.job
    current = _STORE.get_analysis(job.analysis_id)
    if current is None:
        # The request no longer exists, so replaying it cannot make useful progress.
        queue.ack(delivery)
        return True
    if current.get("state") == "READY":
        # Redelivery after a crash between persistence and ACK is idempotent.
        queue.ack(delivery)
        return True
    try:
        _STORE.put_analysis({**current, "state": "RESOLVING"})
        snapshot = resolve_github_repository(job.repository_url, job.ref)
        _STORE.put_analysis({**current, "state": "PARSING", "repository": snapshot.repository, "commit_sha": snapshot.commit_sha})
        facts = analyze_python_repository(snapshot.files)
        store_completed_analysis(snapshot.repository, snapshot.commit_sha, snapshot.files, facts, analysis_id=job.analysis_id)
    except GitHubSourceError as exc:
        latest = _STORE.get_analysis(job.analysis_id) or current
        _STORE.put_analysis({**latest, "state": "FAILED_TERMINAL", "error": str(exc)})
        queue.ack(delivery)
        return True
    except Exception:
        latest = _STORE.get_analysis(job.analysis_id) or current
        _STORE.put_analysis({**latest, "state": "FAILED_RETRYABLE", "error": "analysis worker failed"})
        # Deliberately leave the delivery pending. Redis XAUTOCLAIM can transfer it
        # to a healthy worker after the lease expires.
        raise
    queue.ack(delivery)
    return True


def main() -> None:
    queue = build_analysis_queue()
    while True:
        run_one(queue, timeout_seconds=5)


if __name__ == "__main__":
    main()
