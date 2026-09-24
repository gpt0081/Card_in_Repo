from __future__ import annotations

import os

import pytest

from card_in_repo_api.concept_index import PgvectorConceptIndex
from card_in_repo_api.concept_vectors import VECTOR_DIMENSIONS, structural_concept_vector
from card_in_repo_api.postgres_store import PostgresAnalysisStore


def concept(concept_id: str, name: str, symbol: str, relation: str, path: str = "src/app.py") -> dict:
    return {
        "id": concept_id,
        "kind": "execution_flow",
        "name": name,
        "feature_id": f"feature:{concept_id}",
        "evidence": [{"id": f"e:{concept_id}", "symbol_name": symbol, "path": path, "relation": relation, "order": 1}],
        "explanation": {"level": "basic", "claims": [{"text": name, "evidence_ids": [f"e:{concept_id}"]}], "verified": True},
    }


def test_structural_vector_is_deterministic_normalized_and_fact_derived() -> None:
    first = concept("concept:a", "request flow", "handle_request", "calls")
    same_facts = {**first, "explanation": {"level": "basic", "claims": [{"text": "different prose", "evidence_ids": ["e:concept:a"]}], "verified": True}}
    changed_facts = concept("concept:a", "storage flow", "persist_record", "writes", "src/store.py")
    a = structural_concept_vector(first)
    b = structural_concept_vector(same_facts)
    c = structural_concept_vector(changed_facts)
    assert len(a) == VECTOR_DIMENSIONS
    assert a == b
    assert a != c
    assert sum(value * value for value in a) == pytest.approx(1.0)


DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is required")
def test_pgvector_index_returns_nearest_structural_concept() -> None:
    store = PostgresAnalysisStore(DATABASE_URL)
    store.initialize()
    analysis_id = "analysis:pgvector-retrieval"
    store.put_analysis({"id": analysis_id, "state": "READY"})
    index = PgvectorConceptIndex(DATABASE_URL)
    index.initialize()
    concepts = [
        concept("concept:target", "request flow", "handle_request", "calls"),
        concept("concept:near", "request handler", "handle_request", "calls"),
        concept("concept:far", "database storage", "persist_record", "writes", "src/store.py"),
    ]
    index.index(analysis_id, concepts)
    results = index.similar(analysis_id, "concept:target", 2)
    assert [item["concept"]["id"] for item in results] == ["concept:near", "concept:far"]
    assert results[0]["distance"] < results[1]["distance"]
