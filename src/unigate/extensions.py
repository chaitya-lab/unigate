"""Extension hooks for inbound/outbound/event processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

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
