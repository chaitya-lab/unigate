"""Storage abstractions and built-in backends."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from .message import Action, FormField, Interactive, InteractiveResponse, MediaRef, MediaType, Message, Reaction, Sender


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


@dataclass(slots=True)
class DeadLetterRecord:
    outbox_id: str
    instance_id: str
    destination: str
    message: Message
    attempts: int
    last_error: str
    failed_at: datetime


class InboxStore(Protocol):
    async def put(self, record: InboxRecord) -> None: ...
    async def list_inbox(self, limit: int = 50) -> list[InboxRecord]: ...


class OutboxStore(Protocol):
    async def put_many(self, records: list[OutboxRecord]) -> None: ...
    async def list_outbox(self, limit: int = 50) -> list[OutboxRecord]: ...
    async def due(self, now: datetime, limit: int = 100) -> list[OutboxRecord]: ...
    async def mark_sent(self, outbox_id: str) -> None: ...
    async def mark_failed(self, outbox_id: str, error: str, retry_at: datetime | None) -> None: ...
    async def move_to_dead_letter(self, outbox_id: str, error: str) -> None: ...
    async def list_dead_letters(self, limit: int = 50) -> list[DeadLetterRecord]: ...


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
        "thread_id": message.thread_id,
        "group_id": message.group_id,
        "receiver_id": message.receiver_id,
        "bot_mentioned": message.bot_mentioned,
        "text": message.text,
        "media": [
            {
                "media_id": media.media_id,
                "type": media.type.value,
                "mime_type": media.mime_type,
                "size_bytes": media.size_bytes,
                "filename": media.filename,
                "duration_seconds": media.duration_seconds,
                "dimensions": media.dimensions,
                "thumbnail_url": media.thumbnail_url,
                "full_url": media.full_url,
                "resolved": media.resolved,
                "metadata": media.metadata,
            }
            for media in message.media
        ],
        "interactive": (
            {
                "interaction_id": message.interactive.interaction_id,
                "type": message.interactive.type,
                "prompt": message.interactive.prompt,
                "options": message.interactive.options,
                "fields": (
                    [
                        {
                            "name": field.name,
                            "label": field.label,
                            "type": field.type,
                            "required": field.required,
                            "options": field.options,
                        }
                        for field in message.interactive.fields
                    ]
                    if message.interactive.fields
                    else None
                ),
                "min_value": message.interactive.min_value,
                "max_value": message.interactive.max_value,
                "timeout_seconds": message.interactive.timeout_seconds,
                "context": message.interactive.context,
                "response": (
                    {
                        "interaction_id": message.interactive.response.interaction_id,
                        "type": message.interactive.response.type,
                        "value": message.interactive.response.value,
                        "raw": message.interactive.response.raw,
                    }
                    if message.interactive.response
                    else None
                ),
            }
            if message.interactive
            else None
        ),
        "actions": [{"type": action.type, "payload": action.payload} for action in message.actions],
        "reply_to_id": message.reply_to_id,
        "reactions": [
            {"emoji": reaction.emoji, "sender_id": reaction.sender_id, "ts": reaction.ts.isoformat()}
            for reaction in message.reactions
        ],
        "edit_of_id": message.edit_of_id,
        "deleted_id": message.deleted_id,
        "stream_id": message.stream_id,
        "is_final": message.is_final,
        "raw": message.raw,
        "metadata": message.metadata,
    }
    return json.dumps(payload, separators=(",", ":"))


def _message_from_json(raw: str) -> Message:
    data = json.loads(raw)
    sender = Sender(**data["sender"])
    interactive_data = data.get("interactive")
    interactive: Interactive | None = None
    if interactive_data is not None:
        fields = interactive_data.get("fields")
        response_data = interactive_data.get("response")
        interactive = Interactive(
            interaction_id=interactive_data["interaction_id"],
            type=interactive_data["type"],
            prompt=interactive_data["prompt"],
            options=interactive_data.get("options"),
            fields=[FormField(**field) for field in fields] if fields else None,
            min_value=interactive_data.get("min_value"),
            max_value=interactive_data.get("max_value"),
            timeout_seconds=interactive_data.get("timeout_seconds"),
            context=dict(interactive_data.get("context") or {}),
            response=InteractiveResponse(**response_data) if response_data else None,
        )
    return Message(
        id=data["id"],
        session_id=data["session_id"],
        from_instance=data["from_instance"],
        sender=sender,
        ts=datetime.fromisoformat(data["ts"]),
        platform_id=data.get("platform_id"),
        to=list(data.get("to") or []),
        thread_id=data.get("thread_id"),
        group_id=data.get("group_id"),
        receiver_id=data.get("receiver_id"),
        text=data.get("text"),
        bot_mentioned=bool(data.get("bot_mentioned", True)),
        media=[
            MediaRef(
                media_id=media["media_id"],
                type=MediaType(media["type"]),
                mime_type=media.get("mime_type"),
                size_bytes=media.get("size_bytes"),
                filename=media.get("filename"),
                duration_seconds=media.get("duration_seconds"),
                dimensions=tuple(media["dimensions"]) if media.get("dimensions") else None,
                thumbnail_url=media.get("thumbnail_url"),
                full_url=media.get("full_url"),
                resolved=bool(media.get("resolved", False)),
                metadata=dict(media.get("metadata") or {}),
            )
            for media in data.get("media") or []
        ],
        interactive=interactive,
        actions=[Action(type=action["type"], payload=dict(action.get("payload") or {})) for action in data.get("actions") or []],
        reply_to_id=data.get("reply_to_id"),
        reactions=[
            Reaction(
                emoji=reaction["emoji"],
                sender_id=reaction["sender_id"],
                ts=datetime.fromisoformat(reaction["ts"]),
            )
            for reaction in data.get("reactions") or []
        ],
        edit_of_id=data.get("edit_of_id"),
        deleted_id=data.get("deleted_id"),
        stream_id=data.get("stream_id"),
        is_final=bool(data.get("is_final", True)),
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
        self.dead_letters: list[DeadLetterRecord] = []

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

    async def move_to_dead_letter(self, outbox_id: str, error: str) -> None:
        if outbox_id not in self.outbox:
            return
        record = self.outbox[outbox_id]
        record.status = "dead_letter"
        record.attempts += 1
        record.last_error = error
        record.next_attempt_at = None
        self.dead_letters.append(
            DeadLetterRecord(
                outbox_id=record.outbox_id,
                instance_id=record.instance_id,
                destination=record.destination,
                message=record.message,
                attempts=record.attempts,
                last_error=error,
                failed_at=datetime.now().astimezone(),
            )
        )

    async def list_dead_letters(self, limit: int = 50) -> list[DeadLetterRecord]:
        return self.dead_letters[-limit:]

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
                CREATE TABLE IF NOT EXISTS dead_letter (
                    outbox_id TEXT PRIMARY KEY,
                    instance_id TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    last_error TEXT NOT NULL,
                    failed_at TEXT NOT NULL
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

    async def move_to_dead_letter(self, outbox_id: str, error: str) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM outbox WHERE outbox_id=?", (outbox_id,)).fetchone()
            if row is None:
                return
            conn.execute(
                """
                INSERT OR REPLACE INTO dead_letter(
                    outbox_id, instance_id, destination, payload, attempts, last_error, failed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(row["outbox_id"]),
                    str(row["instance_id"]),
                    str(row["destination"]),
                    str(row["payload"]),
                    int(row["attempts"]) + 1,
                    error,
                    datetime.now().astimezone().isoformat(),
                ),
            )
            conn.execute("UPDATE outbox SET status='dead_letter', attempts=attempts+1, last_error=?, next_attempt_at=NULL WHERE outbox_id=?", (error, outbox_id))

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

    async def list_dead_letters(self, limit: int = 50) -> list[DeadLetterRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM dead_letter ORDER BY failed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            DeadLetterRecord(
                outbox_id=str(row["outbox_id"]),
                instance_id=str(row["instance_id"]),
                destination=str(row["destination"]),
                message=_message_from_json(str(row["payload"])),
                attempts=int(row["attempts"]),
                last_error=str(row["last_error"]),
                failed_at=datetime.fromisoformat(str(row["failed_at"])),
            )
            for row in rows
        ]

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
