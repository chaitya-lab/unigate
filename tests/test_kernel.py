from __future__ import annotations

from datetime import UTC, datetime
import unittest

from unigate import Exchange, InternalAdapter, Message, NamespacedSecureStore, Sender
from unigate.resilience import CircuitBreaker, CircuitState
from unigate.stores import InMemoryStores


class KernelTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.memory = InMemoryStores()
        self.exchange = Exchange(
            inbox=self.memory, outbox=self.memory, sessions=self.memory, dedup=self.memory
        )
        store = NamespacedSecureStore()
        self.adapter = InternalAdapter(
            "default", store.for_instance("default"), self.exchange, config={}
        )
        self.exchange.register_instance("default", self.adapter)

    async def test_ingest_persists_and_dedups(self) -> None:
        status_1 = await self.exchange.ingest(
            "default", {"id": "a1", "session_id": "s1", "sender_id": "u1", "text": "hello"}
        )
        status_2 = await self.exchange.ingest(
            "default", {"id": "a1", "session_id": "s1", "sender_id": "u1", "text": "hello"}
        )

        self.assertEqual(status_1, "ack")
        self.assertEqual(status_2, "duplicate")
        self.assertEqual(len(self.memory.inbox), 1)

    async def test_to_empty_routes_via_session_origin(self) -> None:
        await self.exchange.ingest(
            "default", {"id": "in-1", "session_id": "s2", "sender_id": "origin-user", "text": "hi"}
        )
        outbound = Message(
            id="out-1",
            session_id="s2",
            from_instance="default",
            sender=Sender(platform_id="bot", name="Bot", is_bot=True),
            ts=datetime.now(UTC),
            to=[],
            text="reply",
        )
        await self.exchange.enqueue_outbound("default", outbound)
        await self.exchange.flush_outbox()
        self.assertEqual(len(self.adapter.sent), 1)
        self.assertEqual(self.adapter.sent[0].to, ["default"])

    async def test_fanout_isolated_records(self) -> None:
        outbound = Message(
            id="out-fan",
            session_id="s3",
            from_instance="default",
            sender=Sender(platform_id="bot", name="Bot", is_bot=True),
            ts=datetime.now(UTC),
            to=["a", "b", "c"],
            text="broadcast",
        )
        await self.exchange.enqueue_outbound("default", outbound)
        all_outbox = await self.memory.list_outbox()
        self.assertEqual(len(all_outbox), 3)

    async def test_retry_on_send_failure(self) -> None:
        self.adapter.fail_next_send = True
        outbound = Message(
            id="out-retry",
            session_id="s4",
            from_instance="default",
            sender=Sender(platform_id="bot", name="Bot", is_bot=True),
            ts=datetime.now(UTC),
            to=["default"],
            text="will retry",
        )
        await self.exchange.enqueue_outbound("default", outbound)
        await self.exchange.flush_outbox()
        all_outbox = await self.memory.list_outbox()
        self.assertEqual(len(all_outbox), 1)
        self.assertEqual(all_outbox[0].status, "retry")

    async def test_dead_letter_when_attempts_exhausted(self) -> None:
        self.exchange.set_retry_policy("default", max_attempts=1)
        self.adapter.fail_next_send = True
        outbound = Message(
            id="out-dead",
            session_id="s5",
            from_instance="default",
            sender=Sender(platform_id="bot", name="Bot", is_bot=True),
            ts=datetime.now(UTC),
            to=["default"],
            text="dead letter case",
        )
        await self.exchange.enqueue_outbound("default", outbound)
        await self.exchange.flush_outbox()
        dead_letters = await self.memory.list_dead_letters()
        self.assertEqual(len(dead_letters), 1)
        self.assertEqual(dead_letters[0].message.id, "out-dead")


class CircuitBreakerTests(unittest.IsolatedAsyncioTestCase):
    def test_circuit_breaker_closed_by_default(self) -> None:
        cb = CircuitBreaker()
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_circuit_breaker_opens_after_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_circuit_breaker_half_open_after_timeout(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)
        import time
        time.sleep(0.15)
        self.assertTrue(cb.can_execute())
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

    def test_circuit_breaker_success_resets_after_half_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)
        import time
        time.sleep(0.02)
        cb.can_execute()
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)
        cb.record_success()
        self.assertEqual(cb.state, CircuitState.CLOSED)

    async def test_circuit_breaker_integration(self) -> None:
        memory = InMemoryStores()
        exchange = Exchange(
            inbox=memory, outbox=memory, sessions=memory, dedup=memory
        )
        store = NamespacedSecureStore()
        adapter = InternalAdapter(
            "default", store.for_instance("default"), exchange, config={}
        )
        exchange.register_instance("default", adapter)
        exchange.set_circuit_breaker("default", failure_threshold=2)
        adapter.fail_next_send = True

        outbound = Message(
            id="cb-1",
            session_id="s-cb",
            from_instance="default",
            sender=Sender(platform_id="bot", name="Bot", is_bot=True),
            ts=datetime.now(UTC),
            to=["default"],
            text="test",
        )
        await exchange.enqueue_outbound("default", outbound)
        await exchange.flush_outbox()
        runtime = exchange.instance_manager.instances["default"]
        self.assertEqual(runtime.circuit_breaker.state, CircuitState.CLOSED)

        adapter.fail_next_send = True
        outbound2 = Message(
            id="cb-2",
            session_id="s-cb-2",
            from_instance="default",
            sender=Sender(platform_id="bot", name="Bot", is_bot=True),
            ts=datetime.now(UTC),
            to=["default"],
            text="test2",
        )
        await exchange.enqueue_outbound("default", outbound2)
        await exchange.flush_outbox()

        runtime = exchange.instance_manager.instances["default"]
        self.assertEqual(runtime.circuit_breaker.state, CircuitState.OPEN)
