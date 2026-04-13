"""In-memory outbox record storage."""

from __future__ import annotations

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
