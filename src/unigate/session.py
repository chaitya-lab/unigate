"""Session records and in-memory session store."""

from __future__ import annotations

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
