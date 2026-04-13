"""Minimum runnable gateway orchestration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from inspect import isawaitable
from typing import Any
from uuid import uuid4

from .dedup import InMemoryDeduplicator, SqliteDeduplicator
from .envelope import OutboundMessage, SenderProfile, UniversalMessage
from .events import InMemoryEventBus
from .inbox import InboxRecord, InMemoryInbox, SqliteInbox
from .instance import InstanceRegistry
from .outbox import InMemoryOutbox, OutboxRecord, SqliteOutbox
from .session import InMemorySessionStore, SqliteSessionStore


MessageHandler = Callable[[UniversalMessage], Awaitable[OutboundMessage | None] | OutboundMessage | None]


class Unigate:
    """Minimum working runtime with in-memory state."""

    def __init__(self, *, storage: str = "memory", sqlite_path: str | None = None) -> None:
        self.events = InMemoryEventBus()
        if storage == "memory":
            self.sessions = InMemorySessionStore()
            self.dedup = InMemoryDeduplicator()
            self.inbox = InMemoryInbox()
            self.outbox = InMemoryOutbox()
        elif storage == "sqlite":
            if sqlite_path is None:
                raise ValueError("sqlite_path is required when storage='sqlite'")
            self.sessions = SqliteSessionStore(sqlite_path)
            self.dedup = SqliteDeduplicator(sqlite_path)
            self.inbox = SqliteInbox(sqlite_path)
            self.outbox = SqliteOutbox(sqlite_path)
        else:
            raise ValueError(f"Unsupported storage backend: {storage}")
        self.instances = InstanceRegistry()
        self._handler: MessageHandler | None = None

    def on_message(self, handler: MessageHandler) -> MessageHandler:
        """Register the single inbound handler."""

        self._handler = handler
        return handler

    def register_instance(self, instance_id: str, channel: Any) -> None:
        """Register a channel instance and bind it to this gate when possible."""

        binder = getattr(channel, "bind_gate", None)
        if callable(binder):
            binder(self, instance_id)
        self.instances.add(instance_id, channel)

    async def receive_text(
        self,
        *,
        instance_id: str,
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
        """Accept a simple text inbound event and run the minimum pipeline."""

        is_duplicate = self.dedup.check_and_mark(instance_id, channel_message_id)
        session, created = self.sessions.get_or_create(instance_id, channel_session_key)
        message = UniversalMessage(
            id=str(uuid4()),
            channel_message_id=channel_message_id,
            instance_id=instance_id,
            channel_type=self.instances.get(instance_id).channel_type,
            session_id=session.session_id,
            sender=SenderProfile(
                platform_id=sender_id,
                name=sender_name,
                handle=sender_handle,
            ),
            receiver_id=receiver_id,
            bot_mentioned=bot_mentioned,
            text=text,
            raw=raw or {},
            ts=datetime.now(UTC),
            is_duplicate=is_duplicate,
        )

        if created:
            await self.events.emit(
                "session.created",
                {"instance_id": instance_id, "session_id": session.session_id},
            )

        if is_duplicate:
            await self.events.emit(
                "message.duplicate",
                {"instance_id": instance_id, "channel_message_id": channel_message_id},
            )
            return message

        self.inbox.add(
            InboxRecord(
                message_id=message.id,
                channel_message_id=message.channel_message_id,
                instance_id=message.instance_id,
                session_id=message.session_id,
                status="received",
                raw=message.raw,
            )
        )
        await self.events.emit(
            "message.received",
            {
                "instance_id": message.instance_id,
                "message_id": message.id,
                "session_id": message.session_id,
            },
        )

        channel = self.instances.get(instance_id).channel
        await channel.acknowledge(message)

        outbound: OutboundMessage | None = None
        if self._handler is not None:
            result = self._handler(message)
            outbound = await result if isawaitable(result) else result

        self.inbox.mark_processed(message.id)
        await self.events.emit(
            "message.processed",
            {"instance_id": message.instance_id, "message_id": message.id},
        )

        if outbound is not None:
            await self.send(outbound)

        return message

    async def send(self, outbound: OutboundMessage) -> str:
        """Persist and deliver one outbound message."""

        self.outbox.add(
            OutboxRecord(
                outbound_id=outbound.outbound_id,
                destination_instance_id=outbound.destination_instance_id,
                session_id=outbound.session_id,
                status="pending",
                text=outbound.text,
                metadata=dict(outbound.metadata),
            )
        )
        await self.events.emit(
            "message.delivery_pending",
            {
                "outbound_id": outbound.outbound_id,
                "instance_id": outbound.destination_instance_id,
                "session_id": outbound.session_id,
            },
        )
        channel = self.instances.get(outbound.destination_instance_id).channel
        channel_message_id = await channel.send(outbound)
        self.outbox.mark_delivered(outbound.outbound_id, channel_message_id)
        await self.events.emit(
            "message.delivered",
            {
                "outbound_id": outbound.outbound_id,
                "instance_id": outbound.destination_instance_id,
                "channel_message_id": channel_message_id,
            },
        )
        return channel_message_id

    def reply(
        self,
        message: UniversalMessage,
        *,
        text: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> OutboundMessage:
        """Build the common reply shape for the originating instance/session."""

        return OutboundMessage(
            destination_instance_id=message.instance_id,
            session_id=message.session_id,
            outbound_id=str(uuid4()),
            text=text,
            reply_to_id=message.channel_message_id,
            metadata=metadata or {},
        )

    def event_payloads(self, name: str) -> list[dict[str, Any]]:
        """Helper for tests and simple inspection."""

        return [event.payload for event in self.events.events if event.name == name]
