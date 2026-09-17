from __future__ import annotations

from card_in_repo_analyzer import analyze_python_repository

from .app import _STORE, store_completed_analysis
from .github_source import GitHubSourceError, resolve_github_repository
from .jobs import AnalysisJobQueue
from .runtime import build_analysis_queue


def run_one(queue: AnalysisJobQueue | None = None, timeout_seconds: int = 5) -> bool:
    """Process one queued analysis. Returns False when no job was available."""
    queue = queue or build_analysis_queue()
    job = queue.dequeue(timeout_seconds)
    if job is None:
        return False
    current = _STORE.get_analysis(job.analysis_id)
    if current is None:
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
    except Exception:
        latest = _STORE.get_analysis(job.analysis_id) or current
        _STORE.put_analysis({**latest, "state": "FAILED_RETRYABLE", "error": "analysis worker failed"})
        raise
    return True


def main() -> None:
    queue = build_analysis_queue()
    while True:
        run_one(queue, timeout_seconds=5)


if __name__ == "__main__":
    main()
