"""Inbox record storage backends."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class InboxRecord:
    """Durable-ish record of an inbound receipt for the minimum runtime."""

    message_id: str
    channel_message_id: str
    instance_id: str
    session_id: str
    status: str
    raw: dict[str, Any] = field(default_factory=dict)
    received_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class InMemoryInbox:
    """Stores inbound processing records in arrival order."""

    def __init__(self) -> None:
        self.records: list[InboxRecord] = []

    def add(self, record: InboxRecord) -> None:
        self.records.append(record)

    def mark_processed(self, message_id: str) -> None:
        for record in self.records:
            if record.message_id == message_id:
                record.status = "processed"
                return


class SqliteInbox:
    """SQLite-backed inbox storage."""

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
                CREATE TABLE IF NOT EXISTS inbox_records (
                    message_id TEXT PRIMARY KEY,
                    channel_message_id TEXT NOT NULL,
                    instance_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    received_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    @property
    def records(self) -> list[InboxRecord]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT message_id, channel_message_id, instance_id, session_id, status, raw_json, received_at
                FROM inbox_records
                ORDER BY received_at, rowid
                """
            ).fetchall()
        finally:
            conn.close()
        return [
            InboxRecord(
                message_id=row[0],
                channel_message_id=row[1],
                instance_id=row[2],
                session_id=row[3],
                status=row[4],
                raw=json.loads(row[5]),
                received_at=datetime.fromisoformat(row[6]),
            )
            for row in rows
        ]

    def add(self, record: InboxRecord) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO inbox_records (
                    message_id, channel_message_id, instance_id, session_id, status, raw_json, received_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.message_id,
                    record.channel_message_id,
                    record.instance_id,
                    record.session_id,
                    record.status,
                    json.dumps(record.raw),
                    record.received_at.isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def mark_processed(self, message_id: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE inbox_records SET status = 'processed' WHERE message_id = ?",
                (message_id,),
            )
            conn.commit()
        finally:
            conn.close()
