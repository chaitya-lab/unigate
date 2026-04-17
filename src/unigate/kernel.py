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
from .storage_config import StorageConfig, StorageFactory
from .stores import (
    DedupStore,
    InboxRecord,
    InboxStore,
    InteractionStore,
    OutboxRecord,
    OutboxStore,
    PendingInteractionRecord,
    SessionStore,
)


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
        interactions: InteractionStore | None = None,
        max_concurrency: int = 64,
        routing_config: dict | None = None,
        cleanup_interval_seconds: int = 3600,
        default_storage: StorageConfig | None = None,
    ) -> None:
        self.instances: dict[str, RegisteredInstance] = {}
        self.events: list[KernelEvent] = []
        self._handler: Handler | None = None
        self._inbox = inbox
        self._outbox = outbox
        self._sessions = sessions
        self._dedup = dedup
        self._interactions = interactions
        self._lock = asyncio.Semaphore(max_concurrency)
        self._inbound_extensions: list[InboundExtension] = []
        self._outbound_extensions: list[OutboundExtension] = []
        self._event_extensions: list[EventExtension] = []
        self._tasks: set[asyncio.Task] = set()
        self._health_check_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._outbox_flush_task: asyncio.Task | None = None
        self._outbox_flush_interval = 1.0
        self._cleanup_interval = cleanup_interval_seconds
        self._default_storage = default_storage or StorageConfig(backend="memory")
        self.instance_manager = InstanceManager()
        
        # Per-instance storage overrides
        self._instance_storages: dict[str, tuple[InboxStore, OutboxStore, SessionStore, DedupStore, InteractionStore]] = {}
        
        # Routing engine
        self._routing_engine = None
        self._routing_enabled = False
        
        # Wire up state change callback
        self.instance_manager.set_state_change_callback(self._handle_instance_state_change)
        
        # Initialize routing if config provided
        if routing_config:
            self.setup_routing(routing_config)

    def get_instance_stores(self, instance_id: str) -> tuple[InboxStore, OutboxStore, SessionStore, DedupStore, InteractionStore]:
        """Get storage for a specific instance."""
        if instance_id in self._instance_storages:
            return self._instance_storages[instance_id]
        return self._inbox, self._outbox, self._sessions, self._dedup, self._interactions

    def register_instance(
        self, 
        instance_id: str, 
        channel: BaseChannel,
        fallback_instances: list[str] | None = None,
        storage: StorageConfig | None = None,
    ) -> RegisteredInstance:
        """Register one named instance with optional per-instance storage."""
        # Create per-instance storage if configured
        if storage and storage.backend != "memory":
            inbox, outbox, sessions, dedup, interactions = StorageFactory.create_stores(
                storage, namespace=instance_id
            )
            self._instance_storages[instance_id] = (inbox, outbox, sessions, dedup, interactions)
        
        runtime = self.instance_manager.register(
            instance_id, 
            channel,
            fallback_instances=fallback_instances,
        )
        registered = RegisteredInstance(instance_id=instance_id, channel=channel)
        self.instances[instance_id] = registered
        return registered

    def setup_routing(self, config: dict) -> None:
        """Set up routing engine with configuration."""
        from .routing import RoutingEngine
        self._routing_engine = RoutingEngine(self, config)
        self._routing_enabled = True

    def set_handler(self, handler: Handler) -> None:
        """Set the message handler (for backward compatibility)."""
        self._handler = handler

    def get_routing_engine(self) -> "RoutingEngine | None":
        """Get the routing engine."""
        return self._routing_engine

    def is_routing_enabled(self) -> bool:
        """Check if routing is enabled."""
        return self._routing_enabled

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

    def set_circuit_breaker(
        self,
        instance_id: str,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_requests: int = 1,
    ) -> None:
        from .resilience import CircuitBreaker
        runtime = self.instance_manager.instances[instance_id]
        runtime.circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_requests=half_open_max_requests,
        )

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
            await self._sessions.set_origin(message.session_id, instance_id)
            if self._interactions is not None and message.interactive:
                # Check for pending interaction for this session (try both by instance and by session)
                pending = await self._interactions.get_interaction(message.session_id, instance_id)
                if pending is None:
                    pending = await self._interactions.get_interaction_by_session(message.session_id)
                if pending is not None:
                    # Populate the response from raw data
                    from .message import InteractiveResponse
                    if message.interactive.response is None:
                        raw_resp = message.raw.get("interactive_response", {})
                        message.interactive.response = InteractiveResponse(
                            interaction_id=pending.interaction_id,
                            type=message.interactive.type or "unknown",
                            value=raw_resp.get("value"),
                            raw=raw_resp,
                        )
                    await self._interactions.remove_interaction(pending.interaction_id)
                    await self.emit_event(
                        KernelEvent(
                            name="interaction.correlated",
                            payload={"interaction_id": pending.interaction_id, "message_id": message.id},
                        )
                    )
            inbound = await self._apply_inbound_extensions(message)
            if inbound is None:
                await self.emit_event(KernelEvent(name="inbound.dropped", payload={"message_id": message.id}))
                return "dropped"
            
            # Check if routing is enabled
            if self._routing_enabled and self._routing_engine:
                await self.emit_event(KernelEvent(name="routing.started", payload={"message_id": message.id}))
                routed_messages = await self._routing_engine.route(inbound)
                
                for routed_msg in routed_messages:
                    await self.enqueue_outbound(instance_id, routed_msg, source_message=inbound)
                
                await self.emit_event(KernelEvent(name="routing.complete", payload={
                    "message_id": message.id, 
                    "forwarded_count": len(routed_messages)
                }))
                return "ack"
            
            # Backward compatible: use handler
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
        if self._interactions is not None and prepared.interactive is not None:
            timeout_at = None
            if prepared.interactive.timeout_seconds:
                timeout_at = datetime.now(UTC) + timedelta(seconds=prepared.interactive.timeout_seconds)
            for destination in destinations:
                await self._interactions.put_interaction(
                    PendingInteractionRecord(
                        interaction_id=prepared.interactive.interaction_id,
                        session_id=message.session_id,
                        instance_id=destination,  # Store with destination instance
                        timeout_at=timeout_at,
                        created_at=datetime.now(UTC),
                    )
                )
            await self.emit_event(
                KernelEvent(
                    name="interaction.pending",
                    payload={
                        "interaction_id": prepared.interactive.interaction_id,
                        "session_id": message.session_id,
                        "timeout_seconds": prepared.interactive.timeout_seconds,
                    },
                )
            )
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
            success = await self._send_to_instance(record, now)
            if not success:
                # Try fallback instances if primary failed
                runtime = self.instance_manager.instances.get(record.destination)
                if runtime and runtime.fallback_instances:
                    tried = {record.destination}
                    for fallback_id in runtime.fallback_instances:
                        if fallback_id in tried:
                            continue
                        fallback_record = record
                        fallback_record.destination = fallback_id
                        success = await self._send_to_instance(fallback_record, now)
                        if success:
                            await self.emit_event(
                                KernelEvent(
                                    name="outbox.sent_via_fallback",
                                    payload={
                                        "outbox_id": record.outbox_id,
                                        "primary": record.destination,
                                        "fallback": fallback_id,
                                    },
                                )
                            )
                            break
                        tried.add(fallback_id)

    async def _send_to_instance(self, record: OutboxRecord, now: datetime) -> bool:
        """Try to send a message to an instance. Returns True on success."""
        runtime = self.instance_manager.instances.get(record.destination)
        if runtime is None:
            await self._outbox.move_to_dead_letter(record.outbox_id, f"instance not found: {record.destination}")
            return False
        
        if not runtime.can_execute():
            await self.emit_event(
                KernelEvent(
                    name="circuit_breaker.open",
                    payload={"instance_id": record.destination, "outbox_id": record.outbox_id},
                )
            )
            return False
        
        channel = runtime.channel
        try:
            result = await channel.from_message(record.message)
            if result.success:
                await self._outbox.mark_sent(record.outbox_id)
                runtime.record_success()
                await self.emit_event(
                    KernelEvent(
                        name="outbox.sent",
                        payload={"outbox_id": record.outbox_id, "provider_id": result.provider_message_id},
                    )
                )
                return True
            else:
                runtime.record_failure()
                await self._schedule_retry_or_dead_letter(
                    record.destination,
                    record.outbox_id,
                    record.attempts,
                    result.error or "send failed",
                    now,
                )
                return False
        except Exception as exc:
            runtime.record_failure()
            await self._schedule_retry_or_dead_letter(
                record.destination,
                record.outbox_id,
                record.attempts,
                str(exc),
                now,
            )
            return False

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

    async def check_health(self) -> dict[str, str]:
        """
        Check health of all registered instances.
        Returns dict mapping instance_id to health status.
        """
        from .lifecycle import HealthStatus
        results = {}
        for instance_id in self.instances:
            try:
                health = await self.instance_manager.health(instance_id)
                results[instance_id] = health.value
            except Exception:
                results[instance_id] = "unhealthy"
        return results

    async def health_check_loop(self, interval_seconds: float = 60.0) -> None:
        """
        Background task that periodically checks instance health.
        Updates instance state based on health status.
        """
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                for instance_id in list(self.instances.keys()):
                    try:
                        health = await self.instance_manager.health(instance_id)
                        if health == HealthStatus.HEALTHY:
                            await self.emit_event(
                                KernelEvent(
                                    name="health.ok",
                                    payload={"instance_id": instance_id},
                                )
                            )
                        else:
                            await self.emit_event(
                                KernelEvent(
                                    name="health.degraded",
                                    payload={"instance_id": instance_id, "status": health.value},
                                )
                            )
                    except Exception:
                        pass
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def cleanup_loop(self) -> None:
        """
        Background task that periodically cleans up old data.
        Runs auto_cleanup on the storage backends.
        """
        while True:
            await asyncio.sleep(self._cleanup_interval)
            try:
                if hasattr(self._outbox, 'auto_cleanup'):
                    deleted = await self._outbox.auto_cleanup()
                    if deleted > 0:
                        await self.emit_event(
                            KernelEvent(
                                name="cleanup.completed",
                                payload={"deleted_count": deleted},
                            )
                        )
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def start_health_check_loop(self, interval_seconds: float = 60.0) -> None:
        """Start the background health check task."""
        if self._health_check_task is None or self._health_check_task.done():
            self._health_check_task = asyncio.create_task(
                self.health_check_loop(interval_seconds)
            )

    async def start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self.cleanup_loop())

    async def run_cleanup_once(self) -> int:
        """Run cleanup once and return deleted count."""
        if hasattr(self._outbox, 'auto_cleanup'):
            return await self._outbox.auto_cleanup()
        return 0

    async def outbox_flush_loop(self, interval_seconds: float = 1.0) -> None:
        """Background task that periodically flushes the outbox."""
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                await self._flush_all_instances_outbox()
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _flush_all_instances_outbox(self) -> None:
        """Flush outbox for all active instances."""
        try:
            flushed = await self.flush_all_outbox()
            if flushed > 0:
                print(f"Flushed {flushed} outbox messages")
        except Exception as e:
            print(f"Outbox flush error: {e}")

    def start_outbox_flush_loop(self, interval_seconds: float = 1.0) -> None:
        """Start the background outbox flush task."""
        if self._outbox_flush_task is None or self._outbox_flush_task.done():
            self._outbox_flush_task = asyncio.create_task(
                self.outbox_flush_loop(interval_seconds)
            )

    async def shutdown(self, timeout: float = 30.0) -> None:
        """
        Graceful shutdown - flush outbox and stop all instances.
        
        Args:
            timeout: Seconds to wait for shutdown completion
        """
        await self.emit_event(KernelEvent(name="shutdown.started", payload={}))
        
        # Stop health check loop first
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Stop cleanup loop
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Flush pending outbox messages
        await self.flush_outbox()
        
        # Stop outbox flush loop
        if self._outbox_flush_task and not self._outbox_flush_task.done():
            self._outbox_flush_task.cancel()
            try:
                await self._outbox_flush_task
            except asyncio.CancelledError:
                pass
        
        # Stop all running channel tasks
        stop_tasks = []
        for instance_id in list(self.instances.keys()):
            try:
                await self.instance_manager.stop(instance_id)
            except Exception:
                pass
        
        # Wait for pending tasks with timeout
        if self._tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*self._tasks, return_exceptions=True), timeout=timeout)
            except asyncio.TimeoutError:
                pass
        
        await self.emit_event(KernelEvent(name="shutdown.complete", payload={}))

    def _handle_instance_state_change(self, instance_id: str, old_state: str, new_state: str) -> None:
        """
        Called when an instance state changes.
        When instance becomes ACTIVE, schedule pending outbox flush.
        """
        from .lifecycle import InstanceState
        
        if new_state == InstanceState.ACTIVE.value:
            # Instance became active - schedule outbox flush
            asyncio.create_task(self._flush_instance_when_ready(instance_id))
            asyncio.create_task(self.emit_event(
                KernelEvent(
                    name="instance.activated",
                    payload={"instance_id": instance_id, "previous_state": old_state},
                )
            ))
        elif old_state == InstanceState.ACTIVE.value:
            # Instance went from active to something else
            asyncio.create_task(self.emit_event(
                KernelEvent(
                    name="instance.deactivated",
                    payload={"instance_id": instance_id, "new_state": new_state},
                )
            ))

    async def flush_instance_outbox(self, instance_id: str) -> int:
        """
        Flush all pending messages for a specific instance.
        Returns the number of messages flushed.
        """
        now = datetime.now(UTC)
        due_records = await self._outbox.due(now, limit=1000)
        flushed = 0
        
        for record in due_records:
            if record.destination != instance_id:
                continue
            
            runtime = self.instance_manager.instances.get(instance_id)
            if runtime is None:
                await self._outbox.move_to_dead_letter(record.outbox_id, "instance not found")
                continue
            
            if not runtime.can_execute():
                continue
            
            try:
                result = await runtime.channel.from_message(record.message)
                if result.success:
                    await self._outbox.mark_sent(record.outbox_id)
                    runtime.record_success()
                    flushed += 1
                    await self.emit_event(
                        KernelEvent(
                            name="outbox.sent",
                            payload={"outbox_id": record.outbox_id, "instance_id": instance_id},
                        )
                    )
                else:
                    runtime.record_failure()
            except Exception as exc:
                runtime.record_failure()
        
        return flushed

    async def flush_all_outbox(self) -> int:
        """Flush all pending outbox messages regardless of destination."""
        now = datetime.now(UTC)
        due_records = await self._outbox.due(now, limit=1000)
        flushed = 0
        
        for record in due_records:
            runtime = self.instance_manager.instances.get(record.destination)
            if runtime is None:
                await self._outbox.move_to_dead_letter(record.outbox_id, f"destination '{record.destination}' not found")
                continue
            
            if not runtime.can_execute():
                continue
            
            try:
                result = await runtime.channel.from_message(record.message)
                if result.success:
                    await self._outbox.mark_sent(record.outbox_id)
                    runtime.record_success()
                    flushed += 1
                    await self.emit_event(
                        KernelEvent(
                            name="outbox.sent",
                            payload={"outbox_id": record.outbox_id, "destination": record.destination},
                        )
                    )
                else:
                    runtime.record_failure()
            except Exception as exc:
                runtime.record_failure()
        
        return flushed

    async def _flush_instance_when_ready(self, instance_id: str) -> None:
        """Wait for instance to be ready, then flush its outbox."""
        max_wait = 10.0  # seconds
        waited = 0.0
        
        while waited < max_wait:
            runtime = self.instance_manager.instances.get(instance_id)
            if runtime and runtime.can_execute():
                flushed = await self.flush_instance_outbox(instance_id)
                if flushed > 0:
                    await self.emit_event(
                        KernelEvent(
                            name="instance.recovered",
                            payload={"instance_id": instance_id, "messages_flushed": flushed},
                        )
                    )
                return
            await asyncio.sleep(0.5)
            waited += 0.5

    async def recover_pending_outbox(self) -> int:
        """
        On startup/restart, recover and deliver pending outbox messages.
        Returns the number of messages recovered.
        """
        now = datetime.now(UTC)
        pending = await self._outbox.due(now, limit=1000)
        recovered = 0
        
        for record in pending:
            runtime = self.instance_manager.instances.get(record.destination)
            if runtime is None:
                continue
            if not runtime.can_execute():
                continue
            
            try:
                result = await runtime.channel.from_message(record.message)
                if result.success:
                    await self._outbox.mark_sent(record.outbox_id)
                    runtime.record_success()
                    recovered += 1
            except Exception:
                runtime.record_failure()
        
        if recovered > 0:
            await self.emit_event(
                KernelEvent(
                    name="outbox.recovered",
                    payload={"count": recovered},
                )
            )
        
        return recovered
