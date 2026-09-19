from __future__ import annotations

import json
from typing import Any

import psycopg
from psycopg.types.json import Jsonb


class PostgresAnalysisStore:
    """PostgreSQL-backed store for durable analysis snapshots, cards, and job outbox."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def initialize(self) -> None:
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS analyses (
                        id text PRIMARY KEY,
                        payload jsonb NOT NULL,
                        created_at timestamptz NOT NULL DEFAULT now()
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cards (
                        id text PRIMARY KEY,
                        analysis_id text NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                        payload jsonb NOT NULL,
                        created_at timestamptz NOT NULL DEFAULT now()
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS cards_analysis_id_idx ON cards (analysis_id)")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS analysis_job_outbox (
                        analysis_id text PRIMARY KEY REFERENCES analyses(id) ON DELETE CASCADE,
                        payload jsonb NOT NULL,
                        created_at timestamptz NOT NULL DEFAULT now(),
                        published_at timestamptz
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS analysis_job_outbox_pending_idx ON analysis_job_outbox (created_at) WHERE published_at IS NULL")

    def put_analysis(self, analysis: dict[str, Any]) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute("""
                INSERT INTO analyses (id, payload) VALUES (%s, %s)
                ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload
            """, (analysis["id"], Jsonb(analysis)))

    def put_analysis_with_job(self, analysis: dict[str, Any], job: dict[str, Any], *, expected_state: str | None = None) -> bool:
        """Persist state and an unpublished job atomically; one analysis has at most one pending outbox row."""
        with psycopg.connect(self.database_url) as connection:
            if expected_state is None:
                cursor = connection.execute("""
                    INSERT INTO analyses (id, payload) VALUES (%s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (analysis["id"], Jsonb(analysis)))
            else:
                cursor = connection.execute("""
                    UPDATE analyses SET payload = %s
                    WHERE id = %s AND payload->>'state' = %s
                """, (Jsonb(analysis), analysis["id"], expected_state))
            if cursor.rowcount != 1:
                return False
            connection.execute("""
                INSERT INTO analysis_job_outbox (analysis_id, payload, published_at)
                VALUES (%s, %s, NULL)
                ON CONFLICT (analysis_id) DO UPDATE SET payload = EXCLUDED.payload, published_at = NULL, created_at = now()
            """, (analysis["id"], Jsonb(job)))
            return True

    def get_pending_job(self) -> tuple[str, dict[str, Any]] | None:
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute("""
                SELECT analysis_id, payload FROM analysis_job_outbox
                WHERE published_at IS NULL ORDER BY created_at, analysis_id LIMIT 1
            """).fetchone()
        if row is None:
            return None
        payload = row[1]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return row[0], payload

    def mark_job_published(self, analysis_id: str) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute("UPDATE analysis_job_outbox SET published_at = now() WHERE analysis_id = %s AND published_at IS NULL", (analysis_id,))

    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute("SELECT payload FROM analyses WHERE id = %s", (analysis_id,)).fetchone()
        return self._payload(row)

    def transition_analysis(self, analysis_id: str, expected_state: str, analysis: dict[str, Any]) -> bool:
        with psycopg.connect(self.database_url) as connection:
            cursor = connection.execute("UPDATE analyses SET payload = %s WHERE id = %s AND payload->>'state' = %s", (Jsonb(analysis), analysis_id, expected_state))
            return cursor.rowcount == 1

    def claim_analysis_execution(self, analysis_id: str, delivery_id: str, retry_count: int) -> dict[str, Any] | None:
        """Atomically claim execution, allowing only the same Redis delivery to resume after a crash."""
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute("""
                UPDATE analyses
                SET payload = jsonb_set(
                    jsonb_set(
                        jsonb_set(payload, '{state}', to_jsonb('RESOLVING'::text)),
                        '{retry_count}', to_jsonb(%s::int)
                    ),
                    '{execution_delivery_id}', to_jsonb(%s::text)
                )
                WHERE id = %s
                  AND (
                    payload->>'state' IN ('QUEUED', 'FAILED_RETRYABLE')
                    OR (
                        payload->>'state' IN ('RESOLVING', 'PARSING')
                        AND payload->>'execution_delivery_id' = %s
                    )
                  )
                RETURNING payload
            """, (retry_count, delivery_id, analysis_id, delivery_id)).fetchone()
        return self._payload(row)

    def put_completed_analysis(self, analysis: dict[str, Any], cards: list[dict[str, Any]], *, expected_delivery_id: str | None = None) -> bool:
        """Commit cards + READY atomically, optionally requiring the current execution owner."""
        with psycopg.connect(self.database_url) as connection:
            if expected_delivery_id is not None:
                owner = connection.execute("""
                    SELECT 1 FROM analyses
                    WHERE id = %s
                      AND payload->>'state' = 'PARSING'
                      AND payload->>'execution_delivery_id' = %s
                    FOR UPDATE
                """, (analysis["id"], expected_delivery_id)).fetchone()
                if owner is None:
                    return False
            for card in cards:
                if card["analysis_id"] != analysis["id"]:
                    raise ValueError("card belongs to a different analysis")
                connection.execute("""
                    INSERT INTO cards (id, analysis_id, payload) VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET analysis_id = EXCLUDED.analysis_id, payload = EXCLUDED.payload
                """, (card["id"], card["analysis_id"], Jsonb(card)))
            if expected_delivery_id is None:
                connection.execute("""
                    INSERT INTO analyses (id, payload) VALUES (%s, %s)
                    ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload
                """, (analysis["id"], Jsonb(analysis)))
            else:
                cursor = connection.execute("""
                    UPDATE analyses SET payload = %s
                    WHERE id = %s
                      AND payload->>'state' = 'PARSING'
                      AND payload->>'execution_delivery_id' = %s
                """, (Jsonb(analysis), analysis["id"], expected_delivery_id))
                if cursor.rowcount != 1:
                    raise RuntimeError("analysis execution ownership changed during completion")
            return True

    def put_card(self, card: dict[str, Any]) -> None:
        """Upsert a card while merging independently generated teaching levels.

        A request may have read the card before another request persisted a different
        on-demand level. Merge the nested cache in PostgreSQL so the stale snapshot
        cannot erase teaching that committed first.
        """
        with psycopg.connect(self.database_url) as connection:
            connection.execute("""
                INSERT INTO cards (id, analysis_id, payload) VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    analysis_id = EXCLUDED.analysis_id,
                    payload = CASE
                        WHEN EXCLUDED.payload ? 'on_demand_teaching' THEN
                            jsonb_set(
                                EXCLUDED.payload,
                                '{on_demand_teaching}',
                                COALESCE(cards.payload->'on_demand_teaching', '{}'::jsonb)
                                || COALESCE(EXCLUDED.payload->'on_demand_teaching', '{}'::jsonb),
                                true
                            )
                        ELSE EXCLUDED.payload
                    END
            """, (card["id"], card["analysis_id"], Jsonb(card)))

    def get_card(self, card_id: str) -> dict[str, Any] | None:
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute("SELECT payload FROM cards WHERE id = %s", (card_id,)).fetchone()
        return self._payload(row)

    @staticmethod
    def _payload(row: tuple[Any, ...] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        payload = row[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return payload
