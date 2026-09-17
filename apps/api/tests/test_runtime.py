from __future__ import annotations

import pytest

from card_in_repo_api.jobs import MemoryAnalysisJobQueue
from card_in_repo_api.runtime import RuntimeConfigurationError, build_analysis_queue, build_analysis_store
from card_in_repo_api.store import MemoryAnalysisStore


def test_memory_store_and_queue_are_defaults_for_local_and_ci() -> None:
    assert isinstance(build_analysis_store({}), MemoryAnalysisStore)
    assert isinstance(build_analysis_queue({}), MemoryAnalysisJobQueue)


def test_postgres_requires_database_url() -> None:
    with pytest.raises(RuntimeConfigurationError, match="DATABASE_URL"):
        build_analysis_store({"CARD_IN_REPO_STORE": "postgres"})


def test_redis_requires_redis_url() -> None:
    with pytest.raises(RuntimeConfigurationError, match="REDIS_URL"):
        build_analysis_queue({"CARD_IN_REPO_QUEUE": "redis"})


def test_unknown_backends_fail_closed() -> None:
    with pytest.raises(RuntimeConfigurationError, match="unsupported CARD_IN_REPO_STORE"):
        build_analysis_store({"CARD_IN_REPO_STORE": "sqlite"})
    with pytest.raises(RuntimeConfigurationError, match="unsupported CARD_IN_REPO_QUEUE"):
        build_analysis_queue({"CARD_IN_REPO_QUEUE": "rabbitmq"})
