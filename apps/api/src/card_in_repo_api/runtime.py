from __future__ import annotations

import os

from .jobs import AnalysisJobQueue, MemoryAnalysisJobQueue, RedisAnalysisJobQueue
from .postgres_store import PostgresAnalysisStore
from .store import AnalysisStore, MemoryAnalysisStore


class RuntimeConfigurationError(RuntimeError):
    """Raised when runtime configuration is incomplete or unsafe."""


def build_analysis_store(env: dict[str, str] | None = None) -> AnalysisStore:
    values = os.environ if env is None else env
    backend = values.get("CARD_IN_REPO_STORE", "memory").strip().lower()
    if backend == "memory":
        return MemoryAnalysisStore()
    if backend == "postgres":
        database_url = values.get("DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeConfigurationError("DATABASE_URL is required when CARD_IN_REPO_STORE=postgres")
        store = PostgresAnalysisStore(database_url)
        store.initialize()
        return store
    raise RuntimeConfigurationError(f"unsupported CARD_IN_REPO_STORE={backend!r}; expected 'memory' or 'postgres'")


def build_analysis_queue(env: dict[str, str] | None = None) -> AnalysisJobQueue:
    """Build a deterministic memory queue for dev/tests or Redis for workers."""
    values = os.environ if env is None else env
    backend = values.get("CARD_IN_REPO_QUEUE", "memory").strip().lower()
    if backend == "memory":
        return MemoryAnalysisJobQueue()
    if backend == "redis":
        redis_url = values.get("REDIS_URL", "").strip()
        if not redis_url:
            raise RuntimeConfigurationError("REDIS_URL is required when CARD_IN_REPO_QUEUE=redis")
        return RedisAnalysisJobQueue(redis_url)
    raise RuntimeConfigurationError(f"unsupported CARD_IN_REPO_QUEUE={backend!r}; expected 'memory' or 'redis'")
