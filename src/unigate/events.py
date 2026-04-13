"""In-memory operational event bus for the minimum runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


EventHandler = Callable[[str, dict[str, Any]], Awaitable[None] | None]


@dataclass(slots=True)
class KernelEvent:
    """One emitted operational event."""

    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: datetime = field(default_factory=lambda: datetime.now(UTC))


class InMemoryEventBus:
    """Simple async-friendly event bus used by the minimum runtime."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}
        self.events: list[KernelEvent] = []

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    async def emit(self, event_name: str, payload: dict[str, Any] | None = None) -> None:
        event_payload = payload or {}
        self.events.append(KernelEvent(name=event_name, payload=event_payload))
        for handler in self._handlers.get(event_name, []):
            result = handler(event_name, event_payload)
            if result is not None:
                await result
