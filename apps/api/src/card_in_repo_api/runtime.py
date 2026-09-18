from __future__ import annotations

import os

import psycopg

from .jobs import AnalysisJobQueue, MemoryAnalysisJobQueue, RedisAnalysisJobQueue
from .postgres_store import PostgresAnalysisStore
from .store import AnalysisStore, MemoryAnalysisStore


class RuntimeConfigurationError(RuntimeError):
    """Raised when runtime configuration is incomplete or unsafe."""


def _initialize_postgres_store(store: PostgresAnalysisStore) -> None:
    """Tolerate the one startup race where API and worker bootstrap schema together.

    PostgreSQL's CREATE TABLE IF NOT EXISTS can still raise UniqueViolation when
    two transactions create the same relation concurrently. The conflicting
    transaction has resolved before PostgreSQL reports that violation, so one
    clean retry observes the schema created by the winner. Other database
    failures remain fatal rather than being hidden behind startup retries.
    """
    try:
        store.initialize()
    except psycopg.errors.UniqueViolation:
        store.initialize()


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
        _initialize_postgres_store(store)
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
