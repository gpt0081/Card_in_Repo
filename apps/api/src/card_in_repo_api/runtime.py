from __future__ import annotations

import os

from .postgres_store import PostgresAnalysisStore
from .store import AnalysisStore, MemoryAnalysisStore


class RuntimeConfigurationError(RuntimeError):
    """Raised when persistence configuration is incomplete or unsafe."""


def build_analysis_store(env: dict[str, str] | None = None) -> AnalysisStore:
    """Build the analysis store at the application composition boundary.

    Memory storage is an explicit development/test mode. PostgreSQL is selected
    with CARD_IN_REPO_STORE=postgres and requires DATABASE_URL. This keeps
    persistence choice out of request handlers and makes production startup fail
    closed instead of silently losing analysis snapshots.
    """
    values = os.environ if env is None else env
    backend = values.get("CARD_IN_REPO_STORE", "memory").strip().lower()

    if backend == "memory":
        return MemoryAnalysisStore()
    if backend == "postgres":
        database_url = values.get("DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeConfigurationError(
                "DATABASE_URL is required when CARD_IN_REPO_STORE=postgres"
            )
        store = PostgresAnalysisStore(database_url)
        store.initialize()
        return store
    raise RuntimeConfigurationError(
        f"unsupported CARD_IN_REPO_STORE={backend!r}; expected 'memory' or 'postgres'"
    )
