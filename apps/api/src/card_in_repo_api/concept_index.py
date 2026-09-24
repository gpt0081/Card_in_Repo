from __future__ import annotations

import json
from typing import Any, Protocol

import psycopg
from psycopg.types.json import Jsonb

from .concept_vectors import VECTOR_DIMENSIONS, vectorized_concepts


class ConceptIndex(Protocol):
    def index(self, analysis_id: str, concepts: list[dict[str, Any]]) -> None: ...
    def similar(self, analysis_id: str, concept_id: str, limit: int = 5) -> list[dict[str, Any]]: ...


class PgvectorConceptIndex:
    """Retrieval index over deterministic static-analysis concept features."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def initialize(self) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
            connection.execute(f"""
                CREATE TABLE IF NOT EXISTS concept_vectors (
                    analysis_id text NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                    concept_id text NOT NULL,
                    payload jsonb NOT NULL,
                    embedding vector({VECTOR_DIMENSIONS}) NOT NULL,
                    PRIMARY KEY (analysis_id, concept_id)
                )
            """)
            connection.execute("CREATE INDEX IF NOT EXISTS concept_vectors_analysis_idx ON concept_vectors (analysis_id)")

    @staticmethod
    def _vector_literal(vector: list[float]) -> str:
        return "[" + ",".join(f"{value:.9f}" for value in vector) + "]"

    def index(self, analysis_id: str, concepts: list[dict[str, Any]]) -> None:
        rows = vectorized_concepts(concepts)
        with psycopg.connect(self.database_url) as connection:
            for row in rows:
                connection.execute("""
                    INSERT INTO concept_vectors (analysis_id, concept_id, payload, embedding)
                    VALUES (%s, %s, %s, %s::vector)
                    ON CONFLICT (analysis_id, concept_id) DO UPDATE SET
                        payload = EXCLUDED.payload, embedding = EXCLUDED.embedding
                """, (analysis_id, row["id"], Jsonb(row["concept"]), self._vector_literal(row["vector"])))

    def similar(self, analysis_id: str, concept_id: str, limit: int = 5) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 20))
        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute("""
                SELECT candidate.payload, candidate.embedding <=> target.embedding AS distance
                FROM concept_vectors AS target
                JOIN concept_vectors AS candidate ON candidate.analysis_id = target.analysis_id
                WHERE target.analysis_id = %s AND target.concept_id = %s AND candidate.concept_id <> target.concept_id
                ORDER BY candidate.embedding <=> target.embedding, candidate.concept_id
                LIMIT %s
            """, (analysis_id, concept_id, limit)).fetchall()
        results = []
        for payload, distance in rows:
            if isinstance(payload, str):
                payload = json.loads(payload)
            results.append({"concept": payload, "distance": float(distance)})
        return results
