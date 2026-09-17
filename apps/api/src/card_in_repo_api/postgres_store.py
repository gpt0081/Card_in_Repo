from __future__ import annotations

import json
from typing import Any

import psycopg
from psycopg.types.json import Jsonb


class PostgresAnalysisStore:
    """PostgreSQL-backed store for durable analysis snapshots and cards."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def initialize(self) -> None:
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS analyses (
                        id text PRIMARY KEY,
                        payload jsonb NOT NULL,
                        created_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cards (
                        id text PRIMARY KEY,
                        analysis_id text NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                        payload jsonb NOT NULL,
                        created_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS cards_analysis_id_idx ON cards (analysis_id)"
                )

    def put_analysis(self, analysis: dict[str, Any]) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                INSERT INTO analyses (id, payload) VALUES (%s, %s)
                ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload
                """,
                (analysis["id"], Jsonb(analysis)),
            )

    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                "SELECT payload FROM analyses WHERE id = %s", (analysis_id,)
            ).fetchone()
        return self._payload(row)

    def put_card(self, card: dict[str, Any]) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                INSERT INTO cards (id, analysis_id, payload) VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    analysis_id = EXCLUDED.analysis_id,
                    payload = EXCLUDED.payload
                """,
                (card["id"], card["analysis_id"], Jsonb(card)),
            )

    def get_card(self, card_id: str) -> dict[str, Any] | None:
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                "SELECT payload FROM cards WHERE id = %s", (card_id,)
            ).fetchone()
        return self._payload(row)

    @staticmethod
    def _payload(row: tuple[Any, ...] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        payload = row[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return payload
