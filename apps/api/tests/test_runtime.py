from __future__ import annotations

import pytest

from card_in_repo_api.runtime import RuntimeConfigurationError, build_analysis_store
from card_in_repo_api.store import MemoryAnalysisStore


def test_memory_store_is_default_for_local_and_ci() -> None:
    store = build_analysis_store({})
    assert isinstance(store, MemoryAnalysisStore)


def test_postgres_requires_database_url() -> None:
    with pytest.raises(RuntimeConfigurationError, match="DATABASE_URL"):
        build_analysis_store({"CARD_IN_REPO_STORE": "postgres"})


def test_unknown_store_fails_closed() -> None:
    with pytest.raises(RuntimeConfigurationError, match="unsupported CARD_IN_REPO_STORE"):
        build_analysis_store({"CARD_IN_REPO_STORE": "sqlite"})
