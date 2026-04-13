"""In-memory inbox record storage."""

from __future__ import annotations

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
