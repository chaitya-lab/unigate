"""Extension hooks for inbound/outbound/event processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .events import KernelEvent
from .message import Message


@dataclass(slots=True)
class ExtensionDecision:
    continue_flow: bool = True
    message: Message | None = None


class InboundExtension(Protocol):
    priority: int
    async def handle(self, message: Message) -> ExtensionDecision: ...


class OutboundExtension(Protocol):
    priority: int
    async def handle(self, message: Message) -> ExtensionDecision: ...


class EventExtension(Protocol):
    priority: int
    async def handle(self, event: KernelEvent) -> None: ...


class LoggingExtension:
    __slots__ = ("priority",)

    def __init__(self, priority: int = 100) -> None:
        self.priority = priority

    async def handle(self, message: Message) -> ExtensionDecision:
        print(f"[unigate] inbound: {message.id} from {message.from_instance}: {message.text[:50] if message.text else '(no text)'}")
        return ExtensionDecision(continue_flow=True)


class LoggingOutboundExtension:
    __slots__ = ("priority",)

    def __init__(self, priority: int = 100) -> None:
        self.priority = priority

    async def handle(self, message: Message) -> ExtensionDecision:
        print(f"[unigate] outbound: {message.id} to {message.to}")
        return ExtensionDecision(continue_flow=True)


class LoggingEventExtension:
    __slots__ = ("priority",)

    def __init__(self, priority: int = 100) -> None:
        self.priority = priority

    async def handle(self, event: KernelEvent) -> None:
        print(f"[unigate] event: {event.name} {event.payload}")


_EXTENSION_REGISTRY: dict[str, type] = {
    "log": LoggingExtension,
    "log_outbound": LoggingOutboundExtension,
    "log_event": LoggingEventExtension,
}


def create_extension(config: dict[str, Any]) -> InboundExtension | OutboundExtension | EventExtension | None:
    """Create an extension instance from configuration."""
    from .plugins.extension_identity import IdentityExtension
    
    name = config.get("name")
    if name == "log":
        priority = config.get("priority", 100)
        return LoggingExtension(priority=priority)
    if name == "log_outbound":
        priority = config.get("priority", 100)
        return LoggingOutboundExtension(priority=priority)
    if name == "log_event":
        priority = config.get("priority", 100)
        return LoggingEventExtension(priority=priority)
    if name == "identity":
        ext_config = config.get("config", {})
        return IdentityExtension(ext_config)
    return None
