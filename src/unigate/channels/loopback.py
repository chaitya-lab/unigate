"""Shared helpers for simple in-process channels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from ..channel import ChannelCapabilities, HealthStatus, SetupResult, SetupStatus
from ..envelope import OutboundMessage, UniversalMessage

if TYPE_CHECKING:
    from ..gate import Unigate


@dataclass(slots=True)
class DeliveredMessage:
    """Captured outbound delivery for simple loopback channels."""

    instance_id: str
    session_id: str
    channel_message_id: str
    text: str | None
    metadata: dict[str, Any]


class LoopbackChannel:
    """Base implementation for in-process channels used in local runtimes."""

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
                metadata=dict(message.metadata),
            )
        )
        return channel_message_id

    async def acknowledge(self, message: UniversalMessage) -> None:
        self.acknowledged_message_ids.append(message.channel_message_id)

    async def health_check(self) -> HealthStatus:
        return HealthStatus.HEALTHY

    async def setup(self) -> SetupResult:
        return SetupResult(status=SetupStatus.COMPLETE)

    async def inject_text(
        self,
        *,
        channel_message_id: str,
        channel_session_key: str,
        sender_id: str,
        sender_name: str,
        text: str,
        raw: dict[str, Any] | None = None,
        sender_handle: str | None = None,
        receiver_id: str | None = None,
        bot_mentioned: bool = True,
    ) -> UniversalMessage:
        """Inject one inbound text message through the gate."""

        if self.gate is None or self.instance_id is None:
            raise RuntimeError(f"{self.__class__.__name__} must be registered before use.")

        return await self.gate.receive_text(
            instance_id=self.instance_id,
            channel_message_id=channel_message_id,
            channel_session_key=channel_session_key,
            sender_id=sender_id,
            sender_name=sender_name,
            text=text,
            raw=raw or {},
            sender_handle=sender_handle,
            receiver_id=receiver_id,
            bot_mentioned=bot_mentioned,
        )
