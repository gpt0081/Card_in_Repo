from __future__ import annotations

import psycopg
import pytest

from card_in_repo_api import runtime


class RacingPostgresStore:
    attempts = 0

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def initialize(self) -> None:
        type(self).attempts += 1
        if type(self).attempts == 1:
            raise psycopg.errors.UniqueViolation("concurrent CREATE TABLE")


def test_postgres_store_retries_one_concurrent_schema_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    RacingPostgresStore.attempts = 0
    monkeypatch.setattr(runtime, "PostgresAnalysisStore", RacingPostgresStore)

    store = runtime.build_analysis_store({
        "CARD_IN_REPO_STORE": "postgres",
        "DATABASE_URL": "postgresql://fixture/card_in_repo",
    })

    assert isinstance(store, RacingPostgresStore)
    assert RacingPostgresStore.attempts == 2


def test_postgres_store_does_not_hide_non_unique_initialization_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenPostgresStore(RacingPostgresStore):
        def initialize(self) -> None:
            raise psycopg.errors.OperationalError("database unavailable")

    monkeypatch.setattr(runtime, "PostgresAnalysisStore", BrokenPostgresStore)

    with pytest.raises(psycopg.errors.OperationalError):
        runtime.build_analysis_store({
            "CARD_IN_REPO_STORE": "postgres",
            "DATABASE_URL": "postgresql://fixture/card_in_repo",
        })
