"""Simple in-process channel implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from ..channel import ChannelCapabilities, HealthStatus, SetupResult, SetupStatus
from ..envelope import OutboundMessage, UniversalMessage

if TYPE_CHECKING:
    from ..gate import Unigate


@dataclass(slots=True)
class DeliveredMessage:
    """Captured outbound delivery for tests and local use."""

    instance_id: str
    session_id: str
    channel_message_id: str
    text: str | None


class InternalChannel:
    """In-process channel that records outbound deliveries."""

    contract_version = "1"
    channel_type = "internal"
    capabilities = ChannelCapabilities()

    def __init__(self) -> None:
        self.gate: Unigate | None = None
        self.instance_id: str | None = None
        self.acknowledged_message_ids: list[str] = []
        self.sent_messages: list[DeliveredMessage] = []

    def bind_gate(self, gate: Unigate, instance_id: str) -> None:
        self.gate = gate
        self.instance_id = instance_id

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def send(self, message: OutboundMessage) -> str:
        channel_message_id = f"out-{uuid4()}"
        self.sent_messages.append(
            DeliveredMessage(
                instance_id=message.destination_instance_id,
                session_id=message.session_id,
                channel_message_id=channel_message_id,
                text=message.text,
            )
        )
        return channel_message_id

    async def acknowledge(self, message: UniversalMessage) -> None:
        self.acknowledged_message_ids.append(message.channel_message_id)

    async def health_check(self) -> HealthStatus:
        return HealthStatus.HEALTHY

    async def setup(self) -> SetupResult:
        return SetupResult(status=SetupStatus.COMPLETE)
