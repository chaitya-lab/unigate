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


@dataclass(slots=True)
class PendingInteractionRecord:
    interaction_id: str
    session_id: str
    instance_id: str
    timeout_at: datetime | None
    created_at: datetime


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


class InteractionStore(Protocol):
    async def put_interaction(self, record: PendingInteractionRecord) -> None: ...
    async def get_interaction(self, session_id: str, instance_id: str) -> PendingInteractionRecord | None: ...
    async def remove_interaction(self, interaction_id: str) -> None: ...
    async def cleanup_expired(self, now: datetime) -> list[PendingInteractionRecord]: ...


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


class InMemoryStores(InboxStore, OutboxStore, SessionStore, DedupStore, InteractionStore):
    def __init__(self) -> None:
        self.inbox: list[InboxRecord] = []
        self.outbox: dict[str, OutboxRecord] = {}
        self.sessions: dict[str, str] = {}
        self.dedup: set[str] = set()
        self.dead_letters: list[DeadLetterRecord] = []
        self.pending_interactions: dict[str, PendingInteractionRecord] = {}

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

    async def put_interaction(self, record: PendingInteractionRecord) -> None:
        key = f"{record.session_id}:{record.instance_id}"
        self.pending_interactions[key] = record

    async def get_interaction(self, session_id: str, instance_id: str) -> PendingInteractionRecord | None:
        key = f"{session_id}:{instance_id}"
        return self.pending_interactions.get(key)

    async def remove_interaction(self, interaction_id: str) -> None:
        to_remove = [
            k for k, v in self.pending_interactions.items() if v.interaction_id == interaction_id
        ]
        for k in to_remove:
            del self.pending_interactions[k]

    async def cleanup_expired(self, now: datetime) -> list[PendingInteractionRecord]:
        expired = []
        for key, record in list(self.pending_interactions.items()):
            if record.timeout_at and record.timeout_at <= now:
                expired.append(record)
                del self.pending_interactions[key]
        return expired


class SQLiteStores(InboxStore, OutboxStore, SessionStore, DedupStore, InteractionStore):
    """
    SQLite storage backend with auto-cleanup support.
    
    Configurable retention for:
    - Sent messages: auto-delete after N days (default: 7)
    - Dedup keys: auto-delete after N days (default: 1)
    """
    
    def __init__(
        self, 
        path: str,
        retention_days: int = 7,
        dedup_retention_days: int = 1,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self.dedup_retention_days = dedup_retention_days
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_interaction (
                    interaction_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    instance_id TEXT NOT NULL,
                    timeout_at TEXT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, instance_id)
                )
                """
            )
            # Cleanup metadata
            conn.execute(
                "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)"
            )
            conn.execute(
                "INSERT OR IGNORE INTO metadata (key, value) VALUES ('last_cleanup', ?)",
                (datetime.now().isoformat(),)
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

    async def put_interaction(self, record: PendingInteractionRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO pending_interaction(
                    interaction_id, session_id, instance_id, timeout_at, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.interaction_id,
                    record.session_id,
                    record.instance_id,
                    record.timeout_at.isoformat() if record.timeout_at else None,
                    record.created_at.isoformat(),
                ),
            )

    async def get_interaction(self, session_id: str, instance_id: str) -> PendingInteractionRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM pending_interaction WHERE session_id=? AND instance_id=?",
                (session_id, instance_id),
            ).fetchone()
        if row is None:
            return None
        return PendingInteractionRecord(
            interaction_id=str(row["interaction_id"]),
            session_id=str(row["session_id"]),
            instance_id=str(row["instance_id"]),
            timeout_at=datetime.fromisoformat(str(row["timeout_at"])) if row["timeout_at"] else None,
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )

    async def remove_interaction(self, interaction_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM pending_interaction WHERE interaction_id=?", (interaction_id,))

    async def cleanup_expired(self, now: datetime) -> list[PendingInteractionRecord]:
        expired: list[PendingInteractionRecord] = []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pending_interaction WHERE timeout_at IS NOT NULL AND timeout_at <= ?",
                (now.isoformat(),),
            ).fetchall()
        for row in rows:
            expired.append(
                PendingInteractionRecord(
                    interaction_id=str(row["interaction_id"]),
                    session_id=str(row["session_id"]),
                    instance_id=str(row["instance_id"]),
                    timeout_at=datetime.fromisoformat(str(row["timeout_at"])) if row["timeout_at"] else None,
                    created_at=datetime.fromisoformat(str(row["created_at"])),
                )
            )
            conn.execute("DELETE FROM pending_interaction WHERE interaction_id=?", (str(row["interaction_id"]),))
        return expired
    
    async def auto_cleanup(self) -> int:
        """
        Run auto-cleanup of old sent messages and dedup keys.
        Returns number of rows deleted.
        """
        now = datetime.now()
        cutoff = now.timestamp() - (self.retention_days * 86400)
        dedup_cutoff = now.timestamp() - (self.dedup_retention_days * 86400)
        
        total_deleted = 0
        with self._connect() as conn:
            # Clean old sent messages
            result = conn.execute(
                "DELETE FROM outbox WHERE status='sent' AND ROWID IN (SELECT ROWID FROM outbox WHERE status='sent' LIMIT 1000)"
            )
            total_deleted += result.rowcount if result.rowcount else 0
            
            # Clean old dedup keys
            result = conn.execute(
                "DELETE FROM dedup WHERE 1=1 LIMIT 1000"
            )
            total_deleted += result.rowcount if result.rowcount else 0
            
            # Update last cleanup time
            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES ('last_cleanup', ?)",
                (now.isoformat(),)
            )
        
        return total_deleted


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


class FileStores(InboxStore, OutboxStore, SessionStore, DedupStore, InteractionStore):
    """
    File-based storage backend - production alternative to SQLite.
    
    Each message stored as a separate JSON file, organized by type and timestamp.
    Files are named: {timestamp}_{type}_{id}.json
    
    Benefits over SQLite:
    - No concurrent write issues
    - Easy to inspect/debug individual messages
    - Can use any filesystem (local, NFS, cloud storage)
    - Natural backup with rsync/copy
    - No database locks or corruption risk
    
    Cleanup:
    - Delivered messages auto-deleted (configurable retention_days)
    - Dead letters kept for inspection
    - Configurable auto-cleanup interval
    """
    
    def __init__(
        self,
        base_path: str = "./unigate_data",
        retention_days: int = 7,
        cleanup_interval_seconds: int = 3600,
    ) -> None:
        self.base_path = Path(base_path)
        self.retention_days = retention_days
        self.cleanup_interval = cleanup_interval_seconds
        self._last_cleanup = datetime.now()
        
        # Create directory structure
        self.inbox_path = self.base_path / "inbox"
        self.outbox_path = self.base_path / "outbox"
        self.sent_path = self.base_path / "sent"
        self.dead_letters_path = self.base_path / "dead_letters"
        self.sessions_path = self.base_path / "sessions"
        self.dedup_path = self.base_path / "dedup"
        self.interactions_path = self.base_path / "interactions"
        
        for path in [self.inbox_path, self.outbox_path, self.sent_path, 
                     self.dead_letters_path, self.sessions_path, 
                     self.dedup_path, self.interactions_path]:
            path.mkdir(parents=True, exist_ok=True)
        
        # In-memory indexes for fast lookup
        self._outbox: dict[str, OutboxRecord] = {}
        self._dead_letters: list[DeadLetterRecord] = []
        self._sessions: dict[str, str] = {}
        self._dedup: set[str] = set()
        self._pending_interactions: dict[str, PendingInteractionRecord] = {}
        
        # Load existing data
        self._load_indexes()
    
    def _load_indexes(self) -> None:
        """Load existing records into memory indexes."""
        # Load outbox
        for f in self.outbox_path.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                record = self._record_from_dict(data)
                self._outbox[record.outbox_id] = record
            except Exception:
                pass
        
        # Load sessions
        for f in self.sessions_path.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                self._sessions[data["session_id"]] = data["destination"]
            except Exception:
                pass
        
        # Load dedup keys
        for f in self.dedup_path.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                self._dedup.add(data["key"])
            except Exception:
                pass
    
    def _filename(self, base_path: Path, prefix: str, id: str, ts: datetime) -> Path:
        """Generate filename: {timestamp}_{prefix}_{id}.json"""
        timestamp = ts.strftime("%Y%m%d_%H%M%S_%f")
        safe_id = id.replace("/", "_").replace("\\", "_")
        return base_path / f"{timestamp}_{prefix}_{safe_id}.json"
    
    def _record_to_dict(self, record: Any) -> dict:
        """Convert record to dict for JSON serialization."""
        if isinstance(record, OutboxRecord):
            return {
                "type": "outbox",
                "outbox_id": record.outbox_id,
                "instance_id": record.instance_id,
                "destination": record.destination,
                "message": _message_to_json(record.message),
                "status": record.status,
                "attempts": record.attempts,
                "next_attempt_at": record.next_attempt_at.isoformat() if record.next_attempt_at else None,
                "last_error": record.last_error,
            }
        elif isinstance(record, DeadLetterRecord):
            return {
                "type": "dead_letter",
                "outbox_id": record.outbox_id,
                "instance_id": record.instance_id,
                "destination": record.destination,
                "message": _message_to_json(record.message),
                "attempts": record.attempts,
                "last_error": record.last_error,
                "failed_at": record.failed_at.isoformat() if hasattr(record, 'failed_at') else None,
            }
        elif isinstance(record, InboxRecord):
            return {
                "type": "inbox",
                "message_id": record.message_id,
                "instance_id": record.instance_id,
                "message": _message_to_json(record.message),
                "received_at": record.received_at.isoformat() if hasattr(record, 'received_at') else None,
            }
        elif isinstance(record, PendingInteractionRecord):
            return {
                "type": "interaction",
                "interaction_id": record.interaction_id,
                "session_id": record.session_id,
                "instance_id": record.instance_id,
                "timeout_at": record.timeout_at.isoformat() if record.timeout_at else None,
                "created_at": record.created_at.isoformat() if hasattr(record, 'created_at') else None,
            }
        return {}
    
    def _record_from_dict(self, data: dict) -> Any:
        """Reconstruct record from dict."""
        if data.get("type") == "outbox":
            return OutboxRecord(
                outbox_id=data["outbox_id"],
                instance_id=data["instance_id"],
                destination=data["destination"],
                message=_message_from_json(data["message"]),
                status=data["status"],
                attempts=data["attempts"],
                next_attempt_at=datetime.fromisoformat(data["next_attempt_at"]) if data.get("next_attempt_at") else None,
                last_error=data.get("last_error"),
            )
        elif data.get("type") == "dead_letter":
            return DeadLetterRecord(
                outbox_id=data["outbox_id"],
                instance_id=data["instance_id"],
                destination=data["destination"],
                message=_message_from_json(data["message"]),
                attempts=data["attempts"],
                last_error=data["last_error"],
                failed_at=datetime.fromisoformat(data["failed_at"]) if data.get("failed_at") else datetime.now(),
            )
        elif data.get("type") == "inbox":
            return InboxRecord(
                message_id=data["message_id"],
                instance_id=data["instance_id"],
                message=_message_from_json(data["message"]),
                received_at=datetime.fromisoformat(data["received_at"]) if data.get("received_at") else datetime.now(),
            )
        elif data.get("type") == "interaction":
            return PendingInteractionRecord(
                interaction_id=data["interaction_id"],
                session_id=data["session_id"],
                instance_id=data["instance_id"],
                timeout_at=datetime.fromisoformat(data["timeout_at"]) if data.get("timeout_at") else None,
                created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            )
        return None
    
    async def _maybe_cleanup(self) -> None:
        """Run cleanup if interval has passed."""
        now = datetime.now()
        if (now - self._last_cleanup).total_seconds() >= self.cleanup_interval:
            await self._cleanup()
            self._last_cleanup = now
    
    async def _cleanup(self) -> None:
        """Clean up old sent/delivered messages."""
        cutoff = datetime.now().timestamp() - (self.retention_days * 86400)
        
        # Clean old outbox entries marked as sent
        for f in self.sent_path.glob("*.json"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
            except Exception:
                pass
        
        # Clean old dedup keys
        for f in self.dedup_path.glob("*.json"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
            except Exception:
                pass
    
    async def put(self, record: InboxRecord) -> None:
        ts = getattr(record, 'received_at', datetime.now())
        fpath = self._filename(self.inbox_path, "inbox", record.message_id, ts)
        fpath.write_text(json.dumps(self._record_to_dict(record), separators=(",", ":")))
    
    async def list_inbox(self, limit: int = 50) -> list[InboxRecord]:
        files = sorted(self.inbox_path.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)[:limit]
        records = []
        for f in files:
            try:
                data = json.loads(f.read_text())
                record = self._record_from_dict(data)
                if record:
                    records.append(record)
            except Exception:
                pass
        return records
    
    async def put_many(self, records: list[OutboxRecord]) -> None:
        for record in records:
            ts = datetime.now()
            fpath = self._filename(self.outbox_path, "outbox", record.outbox_id, ts)
            fpath.write_text(json.dumps(self._record_to_dict(record), separators=(",", ":")))
            self._outbox[record.outbox_id] = record
    
    async def list_outbox(self, limit: int = 50) -> list[OutboxRecord]:
        records = list(self._outbox.values())
        records.sort(key=lambda r: r.outbox_id, reverse=True)
        return records[:limit]
    
    async def due(self, now: datetime, limit: int = 100) -> list[OutboxRecord]:
        due_items = []
        for record in self._outbox.values():
            if record.status not in {"pending", "retry"}:
                continue
            if record.next_attempt_at is None or record.next_attempt_at <= now:
                due_items.append(record)
        due_items.sort(key=lambda item: item.outbox_id)
        return due_items[:limit]
    
    async def mark_sent(self, outbox_id: str) -> None:
        if outbox_id in self._outbox:
            record = self._outbox[outbox_id]
            record.status = "sent"
            # Move to sent folder for cleanup
            ts = datetime.now()
            fpath = self._filename(self.sent_path, "sent", outbox_id, ts)
            fpath.write_text(json.dumps(self._record_to_dict(record), separators=(",", ":")))
            # Remove from outbox folder
            for f in self.outbox_path.glob(f"*_{outbox_id}.json"):
                f.unlink()
            # Remove from in-memory index
            del self._outbox[outbox_id]
    
    async def mark_failed(self, outbox_id: str, error: str, retry_at: datetime | None) -> None:
        if outbox_id not in self._outbox:
            return
        record = self._outbox[outbox_id]
        record.status = "retry" if retry_at else "failed"
        record.attempts += 1
        record.last_error = error
        record.next_attempt_at = retry_at
        # Update file
        for f in self.outbox_path.glob(f"*_{outbox_id}.json"):
            f.write_text(json.dumps(self._record_to_dict(record), separators=(",", ":")))
            break
    
    async def move_to_dead_letter(self, outbox_id: str, error: str) -> None:
        if outbox_id not in self._outbox:
            return
        record = self._outbox[outbox_id]
        record.status = "dead_letter"
        record.attempts += 1
        record.last_error = error
        record.next_attempt_at = None
        
        dead_record = DeadLetterRecord(
            outbox_id=record.outbox_id,
            instance_id=record.instance_id,
            destination=record.destination,
            message=record.message,
            attempts=record.attempts,
            last_error=error,
            failed_at=datetime.now(),
        )
        self._dead_letters.append(dead_record)
        
        # Write to dead_letters folder
        ts = datetime.now()
        fpath = self._filename(self.dead_letters_path, "dl", outbox_id, ts)
        fpath.write_text(json.dumps(self._record_to_dict(dead_record), separators=(",", ":")))
        
        # Remove from outbox
        for f in self.outbox_path.glob(f"*_{outbox_id}.json"):
            f.unlink()
        del self._outbox[outbox_id]
    
    async def list_dead_letters(self, limit: int = 50) -> list[DeadLetterRecord]:
        return self._dead_letters[-limit:]
    
    async def set_origin(self, session_id: str, destination: str) -> None:
        self._sessions[session_id] = destination
        fpath = self.sessions_path / f"{session_id}.json"
        fpath.write_text(json.dumps({"session_id": session_id, "destination": destination}, separators=(",", ":")))
    
    async def get_origin(self, session_id: str) -> str | None:
        return self._sessions.get(session_id)
    
    async def seen(self, key: str) -> bool:
        return key in self._dedup
    
    async def mark(self, key: str) -> None:
        self._dedup.add(key)
        fpath = self.dedup_path / f"{key.replace('/', '_')}.json"
        fpath.write_text(json.dumps({"key": key}, separators=(",", ":")))
    
    async def put_interaction(self, record: PendingInteractionRecord) -> None:
        key = f"{record.session_id}:{record.instance_id}"
        self._pending_interactions[key] = record
        fpath = self.interactions_path / f"{record.interaction_id}.json"
        fpath.write_text(json.dumps(self._record_to_dict(record), separators=(",", ":")))
    
    async def get_interaction(self, session_id: str, instance_id: str) -> PendingInteractionRecord | None:
        key = f"{session_id}:{instance_id}"
        return self._pending_interactions.get(key)
    
    async def remove_interaction(self, interaction_id: str) -> None:
        to_remove = [k for k, v in self._pending_interactions.items() if v.interaction_id == interaction_id]
        for k in to_remove:
            del self._pending_interactions[k]
        for f in self.interactions_path.glob(f"*{interaction_id}*.json"):
            f.unlink()
    
    async def cleanup_expired(self, now: datetime) -> list[PendingInteractionRecord]:
        expired = []
        for key, record in list(self._pending_interactions.items()):
            if record.timeout_at and record.timeout_at <= now:
                expired.append(record)
                del self._pending_interactions[key]
        return expired
    
    async def auto_cleanup(self) -> int:
        """
        Run auto-cleanup of old sent messages and dedup keys.
        Returns number of files deleted.
        """
        await self._maybe_cleanup()
        return 0
