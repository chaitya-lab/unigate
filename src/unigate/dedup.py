"""Deduplication helpers for inbound message intake."""

from __future__ import annotations


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
