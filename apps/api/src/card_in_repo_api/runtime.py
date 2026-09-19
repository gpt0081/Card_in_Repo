from __future__ import annotations

import os

import psycopg

from .jobs import AnalysisJobQueue, MemoryAnalysisJobQueue, RedisAnalysisJobQueue
from .postgres_store import PostgresAnalysisStore
from .store import AnalysisStore, MemoryAnalysisStore
from .teaching import TeachingProvider
from .teaching_provider import JsonHttpTeachingProvider


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


def build_teaching_provider(env: dict[str, str] | None = None) -> TeachingProvider | None:
    """Build an optional LLM prose adapter without changing the static fact layer."""
    values = os.environ if env is None else env
    backend = values.get("CARD_IN_REPO_TEACHING_PROVIDER", "none").strip().lower()
    if backend in {"", "none"}:
        return None
    if backend != "json_http":
        raise RuntimeConfigurationError(
            f"unsupported CARD_IN_REPO_TEACHING_PROVIDER={backend!r}; expected 'none' or 'json_http'"
        )
    endpoint = values.get("TEACHING_LLM_ENDPOINT", "").strip()
    model = values.get("TEACHING_LLM_MODEL", "").strip()
    api_key = values.get("TEACHING_LLM_API_KEY", "").strip()
    missing = [name for name, value in (
        ("TEACHING_LLM_ENDPOINT", endpoint),
        ("TEACHING_LLM_MODEL", model),
        ("TEACHING_LLM_API_KEY", api_key),
    ) if not value]
    if missing:
        raise RuntimeConfigurationError(
            "json_http teaching provider requires " + ", ".join(missing)
        )
    return JsonHttpTeachingProvider(endpoint=endpoint, model=model, api_key=api_key)
