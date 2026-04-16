"""Storage abstractions and built-in backends."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from .message import Message


@dataclass(slots=True)
class InboxRecord:
    message_id: str
    instance_id: str
    message: Message
    received_at: datetime


@dataclass(slots=True)
class OutboxRecord:
    outbox_id: str
    instance_id: str
    destination: str
    message: Message
    status: str
    attempts: int
    next_attempt_at: datetime | None = None
    last_error: str | None = None


class InboxStore(Protocol):
    async def put(self, record: InboxRecord) -> None: ...
    async def list_inbox(self, limit: int = 50) -> list[InboxRecord]: ...


class OutboxStore(Protocol):
    async def put_many(self, records: list[OutboxRecord]) -> None: ...
    async def list_outbox(self, limit: int = 50) -> list[OutboxRecord]: ...
    async def due(self, now: datetime, limit: int = 100) -> list[OutboxRecord]: ...
    async def mark_sent(self, outbox_id: str) -> None: ...
    async def mark_failed(self, outbox_id: str, error: str, retry_at: datetime | None) -> None: ...


class SessionStore(Protocol):
    async def set_origin(self, session_id: str, destination: str) -> None: ...
    async def get_origin(self, session_id: str) -> str | None: ...


class DedupStore(Protocol):
    async def seen(self, key: str) -> bool: ...
    async def mark(self, key: str) -> None: ...


class SecureStore(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str) -> None: ...
    async def delete(self, key: str) -> None: ...


def _message_to_json(message: Message) -> str:
    payload = {
        "id": message.id,
        "session_id": message.session_id,
        "from_instance": message.from_instance,
        "sender": {
            "platform_id": message.sender.platform_id,
            "name": message.sender.name,
            "handle": message.sender.handle,
            "is_bot": message.sender.is_bot,
            "canonical_id": message.sender.canonical_id,
            "raw": message.sender.raw,
        },
        "ts": message.ts.isoformat(),
        "platform_id": message.platform_id,
        "to": message.to,
        "text": message.text,
        "bot_mentioned": message.bot_mentioned,
        "metadata": message.metadata,
        "raw": message.raw,
    }
    return json.dumps(payload)


def _message_from_json(raw: str) -> Message:
    from .message import Sender

    data = json.loads(raw)
    sender = Sender(**data["sender"])
    return Message(
        id=data["id"],
        session_id=data["session_id"],
        from_instance=data["from_instance"],
        sender=sender,
        ts=datetime.fromisoformat(data["ts"]),
        platform_id=data.get("platform_id"),
        to=list(data.get("to") or []),
        text=data.get("text"),
        bot_mentioned=bool(data.get("bot_mentioned", True)),
        metadata=dict(data.get("metadata") or {}),
        raw=dict(data.get("raw") or {}),
    )


class InMemorySecureStore(SecureStore):
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._values.get(key)

    async def set(self, key: str, value: str) -> None:
        self._values[key] = value

    async def delete(self, key: str) -> None:
        self._values.pop(key, None)


class InMemoryStores(InboxStore, OutboxStore, SessionStore, DedupStore):
    def __init__(self) -> None:
        self.inbox: list[InboxRecord] = []
        self.outbox: dict[str, OutboxRecord] = {}
        self.sessions: dict[str, str] = {}
        self.dedup: set[str] = set()

    async def put(self, record: InboxRecord) -> None:
        self.inbox.append(record)

    async def list_inbox(self, limit: int = 50) -> list[InboxRecord]:
        return self.inbox[-limit:]

    async def put_many(self, records: list[OutboxRecord]) -> None:
        for record in records:
            self.outbox[record.outbox_id] = record

    async def list_outbox(self, limit: int = 50) -> list[OutboxRecord]:
        return list(self.outbox.values())[-limit:]

    async def due(self, now: datetime, limit: int = 100) -> list[OutboxRecord]:
        due_items: list[OutboxRecord] = []
        for record in self.outbox.values():
            if record.status not in {"pending", "retry"}:
                continue
            if record.next_attempt_at is None or record.next_attempt_at <= now:
                due_items.append(record)
        due_items.sort(key=lambda item: item.outbox_id)
        return due_items[:limit]

    async def mark_sent(self, outbox_id: str) -> None:
        if outbox_id in self.outbox:
            self.outbox[outbox_id].status = "sent"

    async def mark_failed(self, outbox_id: str, error: str, retry_at: datetime | None) -> None:
        if outbox_id not in self.outbox:
            return
        record = self.outbox[outbox_id]
        record.status = "retry" if retry_at else "failed"
        record.attempts += 1
        record.last_error = error
        record.next_attempt_at = retry_at

    async def set_origin(self, session_id: str, destination: str) -> None:
        self.sessions[session_id] = destination

    async def get_origin(self, session_id: str) -> str | None:
        return self.sessions.get(session_id)

    async def seen(self, key: str) -> bool:
        return key in self.dedup

    async def mark(self, key: str) -> None:
        self.dedup.add(key)


class SQLiteStores(InboxStore, OutboxStore, SessionStore, DedupStore):
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS inbox (
                    message_id TEXT PRIMARY KEY,
                    instance_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    received_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS outbox (
                    outbox_id TEXT PRIMARY KEY,
                    instance_id TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    next_attempt_at TEXT NULL,
                    last_error TEXT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_origin (
                    session_id TEXT PRIMARY KEY,
                    destination TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dedup (
                    key TEXT PRIMARY KEY
                )
                """
            )

    async def put(self, record: InboxRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO inbox(message_id, instance_id, payload, received_at) VALUES(?,?,?,?)",
                (
                    record.message_id,
                    record.instance_id,
                    _message_to_json(record.message),
                    record.received_at.isoformat(),
                ),
            )

    async def list_inbox(self, limit: int = 50) -> list[InboxRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM inbox ORDER BY received_at DESC LIMIT ?", (limit,)).fetchall()
        return [InboxRecord(message_id=str(row["message_id"]), instance_id=str(row["instance_id"]), message=_message_from_json(str(row["payload"])), received_at=datetime.fromisoformat(str(row["received_at"]))) for row in rows]

    async def put_many(self, records: list[OutboxRecord]) -> None:
        with self._connect() as conn:
            for record in records:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO outbox(
                        outbox_id, instance_id, destination, payload, status, attempts, next_attempt_at, last_error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.outbox_id,
                        record.instance_id,
                        record.destination,
                        _message_to_json(record.message),
                        record.status,
                        record.attempts,
                        record.next_attempt_at.isoformat() if record.next_attempt_at else None,
                        record.last_error,
                    ),
                )

    async def due(self, now: datetime, limit: int = 100) -> list[OutboxRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM outbox
                WHERE status IN ('pending', 'retry')
                AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                ORDER BY outbox_id ASC
                LIMIT ?
                """,
                (now.isoformat(), limit),
            ).fetchall()
        return [self._to_outbox_record(row) for row in rows]

    async def mark_sent(self, outbox_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE outbox SET status='sent' WHERE outbox_id=?", (outbox_id,))

    async def mark_failed(self, outbox_id: str, error: str, retry_at: datetime | None) -> None:
        status = "retry" if retry_at else "failed"
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE outbox
                SET status=?, attempts=attempts+1, last_error=?, next_attempt_at=?
                WHERE outbox_id=?
                """,
                (status, error, retry_at.isoformat() if retry_at else None, outbox_id),
            )

    def _to_outbox_record(self, row: sqlite3.Row) -> OutboxRecord:
        next_attempt = row["next_attempt_at"]
        return OutboxRecord(
            outbox_id=str(row["outbox_id"]),
            instance_id=str(row["instance_id"]),
            destination=str(row["destination"]),
            message=_message_from_json(str(row["payload"])),
            status=str(row["status"]),
            attempts=int(row["attempts"]),
            next_attempt_at=datetime.fromisoformat(str(next_attempt)) if next_attempt else None,
            last_error=str(row["last_error"]) if row["last_error"] else None,
        )

    async def list_outbox(self, limit: int = 50) -> list[OutboxRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM outbox ORDER BY outbox_id DESC LIMIT ?", (limit,)).fetchall()
        return [self._to_outbox_record(row) for row in rows]

    async def set_origin(self, session_id: str, destination: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO session_origin(session_id, destination) VALUES(?,?)",
                (session_id, destination),
            )

    async def get_origin(self, session_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT destination FROM session_origin WHERE session_id=?", (session_id,)
            ).fetchone()
        if row is None:
            return None
        return str(row["destination"])

    async def seen(self, key: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM dedup WHERE key=?", (key,)).fetchone()
        return row is not None

    async def mark(self, key: str) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO dedup(key) VALUES(?)", (key,))


class NamespacedSecureStore(SecureStore):
    def __init__(self) -> None:
        self._values: dict[str, dict[str, str]] = defaultdict(dict)

    def for_instance(self, instance_id: str) -> "_ScopedSecureStore":
        return _ScopedSecureStore(self, instance_id)

    async def get(self, key: str) -> str | None:
        raise NotImplementedError("Use scoped store")

    async def set(self, key: str, value: str) -> None:
        raise NotImplementedError("Use scoped store")

    async def delete(self, key: str) -> None:
        raise NotImplementedError("Use scoped store")


class _ScopedSecureStore(SecureStore):
    def __init__(self, parent: NamespacedSecureStore, instance_id: str) -> None:
        self.parent = parent
        self.instance_id = instance_id

    async def get(self, key: str) -> str | None:
        return self.parent._values[self.instance_id].get(key)

    async def set(self, key: str, value: str) -> None:
        self.parent._values[self.instance_id][key] = value

    async def delete(self, key: str) -> None:
        self.parent._values[self.instance_id].pop(key, None)
