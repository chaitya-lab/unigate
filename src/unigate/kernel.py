"""Base exchange skeleton for the 1.5 rewrite."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .channel import BaseChannel
from .events import KernelEvent
from .message import Message


Handler = Callable[[Message], Awaitable[Message | list[Message] | None] | Message | list[Message] | None]


@dataclass(slots=True)
class RegisteredInstance:
    """One named instance in the exchange."""

    instance_id: str
    channel: BaseChannel


class Exchange:
    """Minimal 1.5 exchange skeleton."""

    def __init__(self) -> None:
        self.instances: dict[str, RegisteredInstance] = {}
        self.events: list[KernelEvent] = []
        self._handler: Handler | None = None

    def register_instance(self, instance_id: str, channel: BaseChannel) -> None:
        """Register one named instance."""

        self.instances[instance_id] = RegisteredInstance(instance_id=instance_id, channel=channel)

    def set_handler(self, handler: Handler) -> Handler:
        """Attach the exchange handler."""

        self._handler = handler
        return handler

    async def emit_event(self, event: KernelEvent) -> None:
        """Record an operational event."""

        self.events.append(event)
