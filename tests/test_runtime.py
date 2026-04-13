import unittest

from unigate import OutboundMessage
from unigate.gate import Unigate
from unigate.testing.fake_channel import FakeChannel


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_fake_channel_round_trip(self) -> None:
        gate = Unigate()
        channel = FakeChannel()
        gate.register_instance("internal_app", channel)

        @gate.on_message
        def handle(message):
            return gate.reply(message, text=f"echo: {message.text}")

        await channel.receive_text(
            channel_message_id="in-1",
            channel_session_key="chat-1",
            sender_id="user-1",
            sender_name="User One",
            text="hello",
        )

        self.assertEqual(len(gate.inbox.records), 1)
        self.assertEqual(gate.inbox.records[0].status, "processed")
        self.assertEqual(len(gate.outbox.records), 1)
        self.assertEqual(gate.outbox.records[0].status, "delivered")
        self.assertEqual(channel.acknowledged_message_ids, ["in-1"])
        self.assertEqual(len(channel.sent_messages), 1)
        self.assertEqual(channel.sent_messages[0].text, "echo: hello")
        self.assertEqual(len(gate.event_payloads("session.created")), 1)

    async def test_duplicate_message_is_not_processed_twice(self) -> None:
        gate = Unigate()
        channel = FakeChannel()
        gate.register_instance("internal_app", channel)
        seen_messages: list[str] = []

        @gate.on_message
        def handle(message):
            seen_messages.append(message.channel_message_id)
            return gate.reply(message, text="ok")

        await channel.receive_text(
            channel_message_id="dup-1",
            channel_session_key="chat-1",
            sender_id="user-1",
            sender_name="User One",
            text="hello",
        )
        await channel.receive_text(
            channel_message_id="dup-1",
            channel_session_key="chat-1",
            sender_id="user-1",
            sender_name="User One",
            text="hello again",
        )

        self.assertEqual(seen_messages, ["dup-1"])
        self.assertEqual(len(gate.inbox.records), 1)
        self.assertEqual(len(gate.outbox.records), 1)
        self.assertEqual(len(gate.event_payloads("message.duplicate")), 1)

    async def test_explicit_send_targets_one_instance(self) -> None:
        gate = Unigate()
        channel = FakeChannel()
        gate.register_instance("internal_app", channel)
        session = gate.sessions.get_or_create("internal_app", "chat-1")[0]

        outbound = OutboundMessage(
            destination_instance_id="internal_app",
            session_id=session.session_id,
            outbound_id="out-1",
            text="ping",
        )

        channel_message_id = await gate.send(outbound)

        self.assertTrue(channel_message_id.startswith("out-"))
        self.assertEqual(len(channel.sent_messages), 1)
        self.assertEqual(channel.sent_messages[0].text, "ping")


if __name__ == "__main__":
    unittest.main()
