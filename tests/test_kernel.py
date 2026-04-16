from __future__ import annotations

from datetime import UTC, datetime
import unittest

from unigate import Exchange, InternalAdapter, Message, NamespacedSecureStore, Sender
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
        self.assertEqual(self.adapter.sent[0].to, ["origin-user"])

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
            to=["u2"],
            text="will retry",
        )
        await self.exchange.enqueue_outbound("default", outbound)
        await self.exchange.flush_outbox()
        all_outbox = await self.memory.list_outbox()
        self.assertEqual(len(all_outbox), 1)
        self.assertEqual(all_outbox[0].status, "retry")
