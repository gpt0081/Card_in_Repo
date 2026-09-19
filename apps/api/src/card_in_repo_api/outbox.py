from __future__ import annotations

from .jobs import AnalysisJob, AnalysisJobQueue


def dispatch_one(store: object, queue: AnalysisJobQueue) -> bool:
    """Publish one durable PostgreSQL outbox row, marking it only after Redis accepts it."""
    getter = getattr(store, "get_pending_job", None)
    marker = getattr(store, "mark_job_published", None)
    if getter is None or marker is None:
        return False
    pending = getter()
    if pending is None:
        return False
    analysis_id, payload = pending
    job = AnalysisJob.from_json(__import__("json").dumps(payload))
    if job.analysis_id != analysis_id:
        raise ValueError("outbox analysis_id does not match job payload")
    queue.enqueue(job)
    marker(analysis_id)
    return True
