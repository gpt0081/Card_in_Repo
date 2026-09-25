from __future__ import annotations

import os
from urllib.parse import urlparse

import psycopg

from .concept_index import ConceptIndex, PgvectorConceptIndex
from .jobs import AnalysisJobQueue, MemoryAnalysisJobQueue, RedisAnalysisJobQueue
from .postgres_store import PostgresAnalysisStore
from .store import AnalysisStore, MemoryAnalysisStore
from .teaching import TeachingProvider
from .teaching_provider import DeterministicTestTeachingProvider, JsonHttpTeachingProvider


class RuntimeConfigurationError(RuntimeError):
    """Raised when runtime configuration is incomplete or unsafe."""


def _initialize_postgres_store(store: PostgresAnalysisStore) -> None:
    """Tolerate the one startup race where API and worker bootstrap schema together."""
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


def build_concept_index(env: dict[str, str] | None = None) -> ConceptIndex | None:
    values = os.environ if env is None else env
    if values.get("CARD_IN_REPO_STORE", "memory").strip().lower() != "postgres":
        return None
    database_url = values.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeConfigurationError("DATABASE_URL is required for pgvector concept retrieval")
    index = PgvectorConceptIndex(database_url)
    index.initialize()
    return index


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


def _validate_teaching_endpoint(endpoint: str) -> None:
    """Keep provider credentials off cleartext remote transports while allowing local model servers."""
    parsed = urlparse(endpoint)
    if parsed.scheme == "https" and parsed.hostname:
        return
    local_hosts = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
    if parsed.scheme == "http" and parsed.hostname in local_hosts:
        return
    raise RuntimeConfigurationError(
        "TEACHING_LLM_ENDPOINT must use HTTPS; HTTP is allowed only for localhost, loopback, or host.docker.internal"
    )


def build_teaching_provider(env: dict[str, str] | None = None) -> TeachingProvider | None:
    """Build optional prose generation without granting it fact-layer authority."""
    values = os.environ if env is None else env
    backend = values.get("CARD_IN_REPO_TEACHING_PROVIDER", "none").strip().lower()
    if backend in {"", "none"}:
        return None
    if backend == "deterministic_test":
        if values.get("CARD_IN_REPO_ALLOW_TEST_PROVIDER", "").strip() != "1":
            raise RuntimeConfigurationError("deterministic_test teaching provider requires CARD_IN_REPO_ALLOW_TEST_PROVIDER=1")
        return DeterministicTestTeachingProvider()
    if backend != "json_http":
        raise RuntimeConfigurationError(
            "unsupported CARD_IN_REPO_TEACHING_PROVIDER="
            f"{backend!r}; expected 'none', 'json_http', or guarded 'deterministic_test'"
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
        raise RuntimeConfigurationError("json_http teaching provider requires " + ", ".join(missing))
    _validate_teaching_endpoint(endpoint)
    return JsonHttpTeachingProvider(endpoint=endpoint, model=model, api_key=api_key)
