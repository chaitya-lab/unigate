"""Outbox record storage backends."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class OutboxRecord:
    """Durable-ish record of an outbound intent for the minimum runtime."""

    outbound_id: str
    destination_instance_id: str
    session_id: str
    status: str
    text: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    delivered_channel_message_id: str | None = None


class InMemoryOutbox:
    """Stores outbound records and their delivery status."""

    def __init__(self) -> None:
        self.records: list[OutboxRecord] = []

    def add(self, record: OutboxRecord) -> None:
        self.records.append(record)

    def mark_delivered(self, outbound_id: str, channel_message_id: str) -> None:
        for record in self.records:
            if record.outbound_id == outbound_id:
                record.status = "delivered"
                record.delivered_channel_message_id = channel_message_id
                return

    def list_pending(self) -> list[OutboxRecord]:
        return [record for record in self.records if record.status == "pending"]


class SqliteOutbox:
    """SQLite-backed outbox storage."""

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
                CREATE TABLE IF NOT EXISTS outbox_records (
                    outbound_id TEXT PRIMARY KEY,
                    destination_instance_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    text TEXT,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    delivered_channel_message_id TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    @property
    def records(self) -> list[OutboxRecord]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT outbound_id, destination_instance_id, session_id, status, text, metadata_json,
                       created_at, delivered_channel_message_id
                FROM outbox_records
                ORDER BY created_at, rowid
                """
            ).fetchall()
        finally:
            conn.close()
        return [
            OutboxRecord(
                outbound_id=row[0],
                destination_instance_id=row[1],
                session_id=row[2],
                status=row[3],
                text=row[4],
                metadata=json.loads(row[5]),
                created_at=datetime.fromisoformat(row[6]),
                delivered_channel_message_id=row[7],
            )
            for row in rows
        ]

    def add(self, record: OutboxRecord) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO outbox_records (
                    outbound_id, destination_instance_id, session_id, status, text,
                    metadata_json, created_at, delivered_channel_message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.outbound_id,
                    record.destination_instance_id,
                    record.session_id,
                    record.status,
                    record.text,
                    json.dumps(record.metadata),
                    record.created_at.isoformat(),
                    record.delivered_channel_message_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def mark_delivered(self, outbound_id: str, channel_message_id: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE outbox_records
                SET status = 'delivered', delivered_channel_message_id = ?
                WHERE outbound_id = ?
                """,
                (channel_message_id, outbound_id),
            )
            conn.commit()
        finally:
            conn.close()

    def list_pending(self) -> list[OutboxRecord]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT outbound_id, destination_instance_id, session_id, status, text, metadata_json,
                       created_at, delivered_channel_message_id
                FROM outbox_records
                WHERE status = 'pending'
                ORDER BY created_at, rowid
                """
            ).fetchall()
        finally:
            conn.close()
        return [
            OutboxRecord(
                outbound_id=row[0],
                destination_instance_id=row[1],
                session_id=row[2],
                status=row[3],
                text=row[4],
                metadata=json.loads(row[5]),
                created_at=datetime.fromisoformat(row[6]),
                delivered_channel_message_id=row[7],
            )
            for row in rows
        ]
