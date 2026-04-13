"""Deduplication helpers for inbound message intake."""

from __future__ import annotations

import sqlite3


class InMemoryDeduplicator:
    """Tracks seen inbound transport message ids."""

    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()

    def check_and_mark(self, instance_id: str, channel_message_id: str) -> bool:
        key = (instance_id, channel_message_id)
        if key in self._seen:
            return True
        self._seen.add(key)
        return False


class SqliteDeduplicator:
    """SQLite-backed deduplication store."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dedup_seen (
                    instance_id TEXT NOT NULL,
                    channel_message_id TEXT NOT NULL,
                    PRIMARY KEY (instance_id, channel_message_id)
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def check_and_mark(self, instance_id: str, channel_message_id: str) -> bool:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT 1
                FROM dedup_seen
                WHERE instance_id = ? AND channel_message_id = ?
                """,
                (instance_id, channel_message_id),
            ).fetchone()
            if row is not None:
                return True
            conn.execute(
                """
                INSERT INTO dedup_seen (instance_id, channel_message_id)
                VALUES (?, ?)
                """,
                (instance_id, channel_message_id),
            )
            conn.commit()
        finally:
            conn.close()
        return False
