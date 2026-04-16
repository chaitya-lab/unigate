"""Exchange kernel with inbox/outbox pipelines."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from .channel import BaseChannel
from .extensions import EventExtension, ExtensionDecision, InboundExtension, OutboundExtension
from .events import KernelEvent
from .instance_manager import InstanceManager
from .message import Message
from .stores import DedupStore, InboxRecord, InboxStore, OutboxRecord, OutboxStore, SessionStore


Handler = Callable[[Message], Awaitable[Message | list[Message] | None] | Message | list[Message] | None]


@dataclass(slots=True)
class RegisteredInstance:
    """One named instance in the exchange."""

    instance_id: str
    channel: BaseChannel


class Exchange:
    """1.5 exchange pipeline implementation."""

    def __init__(
        self,
        inbox: InboxStore,
        outbox: OutboxStore,
        sessions: SessionStore,
        dedup: DedupStore,
        max_concurrency: int = 64,
    ) -> None:
        self.instances: dict[str, RegisteredInstance] = {}
        self.events: list[KernelEvent] = []
        self._handler: Handler | None = None
        self._inbox = inbox
        self._outbox = outbox
        self._sessions = sessions
        self._dedup = dedup
        self._lock = asyncio.Semaphore(max_concurrency)
        self._inbound_extensions: list[InboundExtension] = []
        self._outbound_extensions: list[OutboundExtension] = []
        self._event_extensions: list[EventExtension] = []
        self.instance_manager = InstanceManager()

    def register_instance(self, instance_id: str, channel: BaseChannel) -> None:
        """Register one named instance."""
        self.instance_manager.register(instance_id, channel)
        self.instances[instance_id] = RegisteredInstance(instance_id=instance_id, channel=channel)

    def set_retry_policy(
        self,
        instance_id: str,
        *,
        max_attempts: int,
        retry_base_seconds: int = 2,
        retry_max_seconds: int = 30,
    ) -> None:
        runtime = self.instance_manager.instances[instance_id]
        runtime.max_attempts = max_attempts
        runtime.retry_base_seconds = retry_base_seconds
        runtime.retry_max_seconds = retry_max_seconds

    def set_handler(self, handler: Handler) -> Handler:
        """Attach the exchange handler."""

        self._handler = handler
        return handler

    async def emit_event(self, event: KernelEvent) -> None:
        """Record an operational event."""
        self.events.append(event)
        for extension in sorted(self._event_extensions, key=lambda item: item.priority):
            await extension.handle(event)

    def add_inbound_extension(self, extension: InboundExtension) -> None:
        self._inbound_extensions.append(extension)

    def add_outbound_extension(self, extension: OutboundExtension) -> None:
        self._outbound_extensions.append(extension)

    def add_event_extension(self, extension: EventExtension) -> None:
        self._event_extensions.append(extension)

    async def ingest(self, instance_id: str, raw: dict[str, object]) -> str:
        async with self._lock:
            channel = self.instances[instance_id].channel
            message = channel.to_message(raw)
            dedup_key = f"{instance_id}:{message.id}"
            if await self._dedup.seen(dedup_key):
                await self.emit_event(KernelEvent(name="dedup.skipped", payload={"message_id": message.id}))
                return "duplicate"
            await self._dedup.mark(dedup_key)
            await self._inbox.put(
                InboxRecord(
                    message_id=message.id,
                    instance_id=instance_id,
                    message=message,
                    received_at=datetime.now(UTC),
                )
            )
            await self.emit_event(KernelEvent(name="inbox.persisted", payload={"message_id": message.id}))
            if message.sender.platform_id:
                await self._sessions.set_origin(message.session_id, message.sender.platform_id)
            inbound = await self._apply_inbound_extensions(message)
            if inbound is None:
                await self.emit_event(KernelEvent(name="inbound.dropped", payload={"message_id": message.id}))
                return "dropped"
            if self._handler is None:
                return "ack"
            produced = self._handler(inbound)
            if asyncio.iscoroutine(produced):
                produced = await produced
            outbound_messages = self._normalize_handler_output(produced)
            for outbound in outbound_messages:
                await self.enqueue_outbound(instance_id, outbound, source_message=inbound)
            return "ack"

    def _normalize_handler_output(self, output: Message | list[Message] | None) -> list[Message]:
        if output is None:
            return []
        if isinstance(output, list):
            return output
        return [output]

    async def _apply_inbound_extensions(self, message: Message) -> Message | None:
        current: Message | None = message
        for extension in sorted(self._inbound_extensions, key=lambda item: item.priority):
            if current is None:
                return None
            decision = await extension.handle(current)
            if not decision.continue_flow:
                return None
            current = decision.message or current
        return current

    async def _apply_outbound_extensions(self, message: Message) -> Message | None:
        current: Message | None = message
        for extension in sorted(self._outbound_extensions, key=lambda item: item.priority):
            if current is None:
                return None
            decision: ExtensionDecision = await extension.handle(current)
            if not decision.continue_flow:
                return None
            current = decision.message or current
        return current

    async def enqueue_outbound(
        self, from_instance: str, message: Message, source_message: Message | None = None
    ) -> None:
        destinations = list(message.to)
        if not destinations:
            resolved = await self._sessions.get_origin(message.session_id)
            if resolved:
                destinations = [resolved]
        if not destinations:
            await self.emit_event(
                KernelEvent(name="outbound.no_destination", payload={"message_id": message.id})
            )
            return
        prepared = await self._apply_outbound_extensions(message)
        if prepared is None:
            await self.emit_event(KernelEvent(name="outbound.dropped", payload={"message_id": message.id}))
            return
        records: list[OutboxRecord] = []
        for destination in destinations:
            fanout_message = replace(
                prepared,
                to=[destination],
                reply_to_id=prepared.reply_to_id or (source_message.id if source_message else None),
            )
            records.append(
                OutboxRecord(
                    outbox_id=f"{prepared.id}:{destination}:{uuid4().hex[:8]}",
                    instance_id=from_instance,
                    destination=destination,
                    message=fanout_message,
                    status="pending",
                    attempts=0,
                )
            )
        await self._outbox.put_many(records)
        await self.emit_event(KernelEvent(name="outbox.persisted", payload={"count": len(records)}))

    async def flush_outbox(self, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        due_records = await self._outbox.due(now)
        for record in due_records:
            channel = self.instances[record.instance_id].channel
            try:
                result = await channel.from_message(record.message)
                if result.success:
                    await self._outbox.mark_sent(record.outbox_id)
                    await self.emit_event(
                        KernelEvent(
                            name="outbox.sent",
                            payload={"outbox_id": record.outbox_id, "provider_id": result.provider_message_id},
                        )
                    )
                else:
                    await self._schedule_retry_or_dead_letter(
                        record.instance_id,
                        record.outbox_id,
                        record.attempts,
                        result.error or "send failed",
                        now,
                    )
            except Exception as exc:
                await self._schedule_retry_or_dead_letter(
                    record.instance_id,
                    record.outbox_id,
                    record.attempts,
                    str(exc),
                    now,
                )

    async def _schedule_retry_or_dead_letter(
        self,
        instance_id: str,
        outbox_id: str,
        attempts: int,
        error: str,
        now: datetime,
    ) -> None:
        runtime = self.instance_manager.instances.get(instance_id)
        if runtime is None:
            await self._outbox.move_to_dead_letter(outbox_id, error)
            await self.emit_event(
                KernelEvent(
                    name="outbox.dead_letter",
                    payload={"outbox_id": outbox_id, "instance_id": instance_id, "error": error},
                )
            )
            return
        if attempts + 1 >= runtime.max_attempts:
            await self._outbox.move_to_dead_letter(outbox_id, error)
            runtime.retries += 1
            await self.emit_event(
                KernelEvent(
                    name="outbox.dead_letter",
                    payload={"outbox_id": outbox_id, "instance_id": instance_id, "error": error},
                )
            )
            return
        delay_seconds = min(runtime.retry_max_seconds, runtime.retry_base_seconds ** (attempts + 1))
        retry_at = now + timedelta(seconds=delay_seconds)
        await self._outbox.mark_failed(outbox_id, error, retry_at)
        runtime.retries += 1
