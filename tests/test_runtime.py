import unittest

from unigate import ApiChannel, OutboundMessage, WebChannel, WebSocketServerChannel
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

    async def test_api_channel_round_trip(self) -> None:
        gate = Unigate()
        channel = ApiChannel()
        gate.register_instance("public_api", channel)

        @gate.on_message
        def handle(message):
            return gate.reply(message, text=f"api:{message.text}")

        await channel.receive_request(
            request_id="req-1",
            client_id="client-1",
            sender_name="Client One",
            text="status",
            conversation_id="conv-1",
        )

        self.assertEqual(len(channel.sent_messages), 1)
        self.assertEqual(channel.sent_messages[0].text, "api:status")
        self.assertEqual(channel.sent_messages[0].instance_id, "public_api")

    async def test_web_channel_round_trip(self) -> None:
        gate = Unigate()
        channel = WebChannel()
        gate.register_instance("site_chat", channel)

        @gate.on_message
        def handle(message):
            return gate.reply(message, text=f"web:{message.text}")

        await channel.receive_browser_message(
            message_id="web-1",
            browser_session_id="browser-1",
            visitor_id="visitor-1",
            visitor_name="Visitor One",
            text="help",
        )

        self.assertEqual(len(channel.sent_messages), 1)
        self.assertEqual(channel.sent_messages[0].text, "web:help")

    async def test_websocket_channel_round_trip(self) -> None:
        gate = Unigate()
        channel = WebSocketServerChannel()
        gate.register_instance("socket_gateway", channel)

        @gate.on_message
        def handle(message):
            return gate.reply(message, text=f"ws:{message.text}")

        await channel.receive_frame(
            frame_id="frame-1",
            connection_id="conn-1",
            sender_id="peer-1",
            sender_name="Peer One",
            text="ping",
        )

        self.assertEqual(len(channel.sent_messages), 1)
        self.assertEqual(channel.sent_messages[0].text, "ws:ping")


if __name__ == "__main__":
    unittest.main()
