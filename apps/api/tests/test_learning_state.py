from __future__ import annotations

import os

import pytest

from card_in_repo_api.postgres_store import PostgresAnalysisStore

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is required")


def test_learning_state_is_scoped_to_github_user_and_repository() -> None:
    store = PostgresAnalysisStore(DATABASE_URL)
    store.initialize()

    store.put_learning_state(101, "octo/alpha", "concept:loops", "learning")
    store.put_learning_state(202, "octo/alpha", "concept:loops", "understood")
    store.put_learning_state(101, "octo/beta", "concept:loops", "understood")

    alpha = store.get_learning_state(101, "octo/alpha")
    assert len(alpha) == 1
    assert alpha[0]["github_user_id"] == 101
    assert alpha[0]["repository"] == "octo/alpha"
    assert alpha[0]["concept_id"] == "concept:loops"
    assert alpha[0]["mastery"] == "learning"


def test_learning_state_upsert_preserves_one_identity_key() -> None:
    store = PostgresAnalysisStore(DATABASE_URL)
    store.initialize()

    first = store.put_learning_state(303, "octo/repo", "concept:imports", "learning")
    second = store.put_learning_state(303, "octo/repo", "concept:imports", "understood", "2030-01-02T03:04:05+00:00")

    states = store.get_learning_state(303, "octo/repo")
    assert len(states) == 1
    assert first["concept_id"] == second["concept_id"]
    assert states[0]["mastery"] == "understood"
    assert states[0]["review_due_at"].startswith("2030-01-02T03:04:05")


def test_learning_state_rejects_unknown_mastery_value() -> None:
    store = PostgresAnalysisStore(DATABASE_URL)
    store.initialize()
    with pytest.raises(ValueError, match="invalid mastery"):
        store.put_learning_state(404, "octo/repo", "concept:x", "magic")
