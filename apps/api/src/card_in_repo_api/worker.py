from __future__ import annotations

import os

from card_in_repo_analyzer import analyze_python_repository

from .app import _STORE, store_completed_analysis
from .github_source import GitHubSourceError, resolve_github_repository
from .jobs import AnalysisJobQueue
from .runtime import build_analysis_queue


def _max_attempts() -> int:
    value = int(os.getenv("CARD_IN_REPO_MAX_ANALYSIS_ATTEMPTS", "3"))
    if value < 1:
        raise ValueError("CARD_IN_REPO_MAX_ANALYSIS_ATTEMPTS must be at least 1")
    return value


def run_one(queue: AnalysisJobQueue | None = None, timeout_seconds: int = 5) -> bool:
    """Process one claimed analysis; acknowledge only after a durable outcome is stored."""
    queue = queue or build_analysis_queue()
    delivery = queue.claim(timeout_seconds)
    if delivery is None:
        return False
    job = delivery.job
    current = _STORE.get_analysis(job.analysis_id)
    if current is None:
        queue.ack(delivery)
        return True
    if current.get("state") in {"READY", "FAILED_EXHAUSTED"}:
        queue.ack(delivery)
        return True
    try:
        _STORE.put_analysis({**current, "state": "RESOLVING", "retry_count": delivery.attempts - 1})
        snapshot = resolve_github_repository(job.repository_url, job.ref)
        _STORE.put_analysis({**current, "state": "PARSING", "retry_count": delivery.attempts - 1, "repository": snapshot.repository, "commit_sha": snapshot.commit_sha})
        facts = analyze_python_repository(snapshot.files)
        store_completed_analysis(snapshot.repository, snapshot.commit_sha, snapshot.files, facts, analysis_id=job.analysis_id)
    except GitHubSourceError as exc:
        latest = _STORE.get_analysis(job.analysis_id) or current
        _STORE.put_analysis({**latest, "state": "FAILED_TERMINAL", "retry_count": delivery.attempts - 1, "error": str(exc)})
        queue.ack(delivery)
        return True
    except Exception:
        latest = _STORE.get_analysis(job.analysis_id) or current
        if delivery.attempts >= _max_attempts():
            reason = "analysis worker exhausted retry budget"
            _STORE.put_analysis({**latest, "state": "FAILED_EXHAUSTED", "retry_count": delivery.attempts - 1, "error": reason})
            queue.dead_letter(delivery, reason)
            return True
        _STORE.put_analysis({**latest, "state": "FAILED_RETRYABLE", "retry_count": delivery.attempts - 1, "error": "analysis worker failed"})
        # Leave pending so Redis XAUTOCLAIM can transfer it after the lease expires.
        raise
    queue.ack(delivery)
    return True


def main() -> None:
    queue = build_analysis_queue()
    while True:
        run_one(queue, timeout_seconds=5)


if __name__ == "__main__":
    main()
