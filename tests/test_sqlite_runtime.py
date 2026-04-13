import tempfile
import unittest
from pathlib import Path

from unigate import ApiChannel, Unigate
from unigate.outbox import OutboxRecord


class SqliteRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_sqlite_state_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "unigate.db"

            gate_one = Unigate(storage="sqlite", sqlite_path=str(db_path))
            channel_one = ApiChannel()
            gate_one.register_instance("public_api", channel_one)

            seen: list[str] = []

            @gate_one.on_message
            def handle_one(message):
                seen.append(message.session_id)
                return gate_one.reply(message, text=f"first:{message.text}")

            first_message = await channel_one.receive_request(
                request_id="req-1",
                client_id="client-1",
                sender_name="Client One",
                text="hello",
                conversation_id="conv-1",
            )

            self.assertEqual(len(gate_one.inbox.records), 1)
            self.assertEqual(len(gate_one.outbox.records), 1)
            first_session_id = first_message.session_id

            gate_two = Unigate(storage="sqlite", sqlite_path=str(db_path))
            channel_two = ApiChannel()
            gate_two.register_instance("public_api", channel_two)

            second_seen: list[str] = []

            @gate_two.on_message
            def handle_two(message):
                second_seen.append(message.session_id)
                return gate_two.reply(message, text=f"second:{message.text}")

            second_message = await channel_two.receive_request(
                request_id="req-2",
                client_id="client-1",
                sender_name="Client One",
                text="again",
                conversation_id="conv-1",
            )

            duplicate_message = await channel_two.receive_request(
                request_id="req-2",
                client_id="client-1",
                sender_name="Client One",
                text="again duplicate",
                conversation_id="conv-1",
            )

            self.assertEqual(second_message.session_id, first_session_id)
            self.assertEqual(duplicate_message.is_duplicate, True)
            self.assertEqual(len(second_seen), 1)
            self.assertEqual(len(gate_two.inbox.records), 2)
            self.assertEqual(len(gate_two.outbox.records), 2)
            self.assertEqual(gate_two.inbox.records[1].status, "processed")
            self.assertEqual(gate_two.outbox.records[1].status, "delivered")

    async def test_recover_replays_pending_outbox_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "unigate.db"

            gate_one = Unigate(storage="sqlite", sqlite_path=str(db_path))
            session = gate_one.sessions.get_or_create("public_api", "conv-1")[0]
            gate_one.outbox.add(
                OutboxRecord(
                    outbound_id="out-1",
                    destination_instance_id="public_api",
                    session_id=session.session_id,
                    status="pending",
                    text="recover me",
                )
            )

            gate_two = Unigate(storage="sqlite", sqlite_path=str(db_path))
            channel = ApiChannel()
            gate_two.register_instance("public_api", channel)

            await gate_two.recover()

            self.assertEqual(len(channel.sent_messages), 1)
            self.assertEqual(channel.sent_messages[0].text, "recover me")
            self.assertEqual(gate_two.outbox.records[0].status, "delivered")


if __name__ == "__main__":
    unittest.main()
