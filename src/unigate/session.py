"""Session records and storage backends."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass(slots=True)
class Session:
    """Transport-local conversation state."""

    session_id: str
    instance_id: str
    channel_session_key: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, object] = field(default_factory=dict)


class InMemorySessionStore:
    """Maps transport conversation keys to kernel session ids."""

    def __init__(self) -> None:
        self._sessions_by_key: dict[tuple[str, str], Session] = {}
        self._sessions_by_id: dict[str, Session] = {}

    def get(self, session_id: str) -> Session | None:
        return self._sessions_by_id.get(session_id)

    def get_or_create(self, instance_id: str, channel_session_key: str) -> tuple[Session, bool]:
        key = (instance_id, channel_session_key)
        existing = self._sessions_by_key.get(key)
        if existing is not None:
            existing.last_activity = datetime.now(UTC)
            return existing, False

        session = Session(
            session_id=str(uuid4()),
            instance_id=instance_id,
            channel_session_key=channel_session_key,
        )
        self._sessions_by_key[key] = session
        self._sessions_by_id[session.session_id] = session
        return session, True


class SqliteSessionStore:
    """SQLite-backed session store."""

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
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    instance_id TEXT NOT NULL,
                    channel_session_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_activity TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    UNIQUE(instance_id, channel_session_key)
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def get(self, session_id: str) -> Session | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT session_id, instance_id, channel_session_key, created_at, last_activity, metadata_json
                FROM sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return Session(
            session_id=row[0],
            instance_id=row[1],
            channel_session_key=row[2],
            created_at=datetime.fromisoformat(row[3]),
            last_activity=datetime.fromisoformat(row[4]),
            metadata=json.loads(row[5]),
        )

    def get_or_create(self, instance_id: str, channel_session_key: str) -> tuple[Session, bool]:
        now = datetime.now(UTC)
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT session_id, instance_id, channel_session_key, created_at, last_activity, metadata_json
                FROM sessions
                WHERE instance_id = ? AND channel_session_key = ?
                """,
                (instance_id, channel_session_key),
            ).fetchone()
            if row is not None:
                conn.execute(
                    """
                    UPDATE sessions
                    SET last_activity = ?
                    WHERE session_id = ?
                    """,
                    (now.isoformat(), row[0]),
                )
                return (
                    Session(
                        session_id=row[0],
                        instance_id=row[1],
                        channel_session_key=row[2],
                        created_at=datetime.fromisoformat(row[3]),
                        last_activity=now,
                        metadata=json.loads(row[5]),
                    ),
                    False,
                )

            session = Session(
                session_id=str(uuid4()),
                instance_id=instance_id,
                channel_session_key=channel_session_key,
                created_at=now,
                last_activity=now,
            )
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, instance_id, channel_session_key, created_at, last_activity, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.instance_id,
                    session.channel_session_key,
                    session.created_at.isoformat(),
                    session.last_activity.isoformat(),
                    json.dumps(session.metadata),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return session, True
