"""Tests for FakeChannel and TestKit."""

from __future__ import annotations

import asyncio
import unittest
from datetime import UTC, datetime
from uuid import uuid4

from unigate import Message, Sender
from unigate.testing import FakeChannel, TestKit


class FakeChannelTests(unittest.TestCase):
    def test_fake_channel_to_message(self) -> None:
        channel = FakeChannel(instance_id="test")
        raw = {
            "id": "msg-1",
            "session_id": "session-1",
            "sender_id": "user-1",
            "sender_name": "Test User",
            "text": "Hello",
            "bot_mentioned": True,
        }
        msg = channel.to_message(raw)
        self.assertEqual(msg.id, "msg-1")
        self.assertEqual(msg.session_id, "session-1")
        self.assertEqual(msg.sender.platform_id, "user-1")
        self.assertEqual(msg.text, "Hello")
        self.assertEqual(msg.from_instance, "test")

    def test_fake_channel_send(self) -> None:
        channel = FakeChannel(instance_id="test")
        msg = Message(
            id="out-1",
            session_id="session-1",
            from_instance="handler",
            sender=Sender(platform_id="bot", name="Bot"),
            ts=datetime.now(UTC),
            text="Hello",
        )
        result = asyncio.run(channel.from_message(msg))
        self.assertTrue(result.success)
        self.assertEqual(result.provider_message_id, "sent:out-1")
        self.assertEqual(len(channel.sent), 1)
        self.assertEqual(channel.sent[0].id, "out-1")


class TestKitTests(unittest.TestCase):
    def test_kit_add_instance(self) -> None:
        kit = TestKit()
        channel = kit.add_instance(instance_id="chat1")
        self.assertEqual(channel.instance_id, "chat1")
        self.assertIsNotNone(kit.get_channel("chat1"))

    def test_kit_message_flow(self) -> None:
        kit = TestKit()

        @kit.on_message
        async def handle(msg: Message) -> Message:
            return Message(
                id=str(uuid4()),
                session_id=msg.session_id,
                from_instance="handler",
                sender=Sender(platform_id="bot", name="Bot"),
                ts=datetime.now(UTC),
                text=f"echo: {msg.text}",
            )

        channel = kit.add_instance(instance_id="chat1")
        asyncio.run(kit.start())

        try:
            asyncio.run(channel.inject(text="hello"))
            asyncio.run(kit.flush_outbox())
            self.assertEqual(len(channel.sent), 1)
            self.assertEqual(channel.sent[0].text, "echo: hello")
        finally:
            asyncio.run(kit.stop())

    def test_kit_reset(self) -> None:
        kit = TestKit()
        channel = kit.add_instance(instance_id="chat1")

        @kit.on_message
        async def handle(msg: Message) -> Message:
            return Message(
                id=str(uuid4()),
                session_id=msg.session_id,
                from_instance="handler",
                sender=Sender(platform_id="bot", name="Bot"),
                ts=datetime.now(UTC),
            )

        asyncio.run(kit.start())
        try:
            asyncio.run(channel.inject(text="hello"))
            asyncio.run(kit.flush_outbox())
            self.assertEqual(len(channel.sent), 1)
            self.assertEqual(len(kit.stores.inbox), 1)
            kit.reset()
            self.assertEqual(len(channel.sent), 0)
            self.assertEqual(len(kit.stores.inbox), 0)
        finally:
            asyncio.run(kit.stop())

    def test_kit_fanout(self) -> None:
        kit = TestKit()
        channel1 = kit.add_instance(instance_id="chat1")
        channel2 = kit.add_instance(instance_id="chat2")

        @kit.on_message
        async def handle(msg: Message) -> Message:
            return Message(
                id=str(uuid4()),
                session_id=msg.session_id,
                from_instance="handler",
                sender=Sender(platform_id="bot", name="Bot"),
                ts=datetime.now(UTC),
                to=["chat1", "chat2"],
                text="broadcast",
            )

        asyncio.run(kit.start())
        try:
            asyncio.run(channel1.inject(text="hello"))
            asyncio.run(kit.flush_outbox())
            self.assertEqual(len(channel1.sent), 1)
            self.assertEqual(len(channel2.sent), 1)
        finally:
            asyncio.run(kit.stop())

    def test_kit_ignore_unless_mentioned(self) -> None:
        kit = TestKit()
        channel = kit.add_instance(instance_id="group")

        @kit.on_message
        async def handle(msg: Message) -> Message | None:
            if msg.group_id and not msg.bot_mentioned:
                return None
            return Message(
                id=str(uuid4()),
                session_id=msg.session_id,
                from_instance="handler",
                sender=Sender(platform_id="bot", name="Bot"),
                ts=datetime.now(UTC),
                text="pong",
            )

        asyncio.run(kit.start())
        try:
            asyncio.run(channel.inject(text="just chatting", group_id="g1", bot_mentioned=False))
            asyncio.run(kit.flush_outbox())
            self.assertEqual(len(channel.sent), 0)

            asyncio.run(channel.inject(text="@bot hello", group_id="g1", bot_mentioned=True))
            asyncio.run(kit.flush_outbox())
            self.assertEqual(len(channel.sent), 1)
            self.assertEqual(channel.sent[-1].text, "pong")
        finally:
            asyncio.run(kit.stop())


if __name__ == "__main__":
    unittest.main()
