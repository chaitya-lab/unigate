from __future__ import annotations

import json
import tempfile
import unittest
from uuid import uuid4
from datetime import UTC, datetime

from unigate import (
    Action,
    Exchange,
    FormField,
    Interactive,
    InteractiveResponse,
    InternalAdapter,
    MediaRef,
    MediaType,
    Message,
    NamespacedSecureStore,
    Reaction,
    SQLiteStores,
    Sender,
)
from unigate.runtime import UnigateASGIApp


class StorageRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_sqlite_restart_keeps_dedup_and_outbox(self) -> None:
        path = f"{tempfile.gettempdir()}/unigate-test-{uuid4().hex}.db"
        stores_a = SQLiteStores(path)
        stores_b = SQLiteStores(path)
        exchange_a = Exchange(stores_a, stores_a, stores_a, stores_a)
        exchange_b = Exchange(stores_b, stores_b, stores_b, stores_b)
        secure = NamespacedSecureStore()
        adapter_a = InternalAdapter("one", secure.for_instance("one"), exchange_a)
        adapter_b = InternalAdapter("one", secure.for_instance("one"), exchange_b)
        exchange_a.register_instance("one", adapter_a)
        exchange_b.register_instance("one", adapter_b)
        await exchange_a.ingest("one", {"id": "dup-1", "session_id": "s", "sender_id": "u"})
        duplicate = await exchange_b.ingest("one", {"id": "dup-1", "session_id": "s", "sender_id": "u"})
        self.assertEqual(duplicate, "duplicate")
        outbound = Message(
            id="send-1",
            session_id="s",
            from_instance="one",
            sender=Sender(platform_id="bot", name="Bot", is_bot=True),
            ts=datetime.now(UTC),
            to=["u"],
            text="hello",
        )
        await exchange_a.enqueue_outbound("one", outbound)
        pending = await stores_b.due(datetime.now(UTC))
        self.assertEqual(len(pending), 1)

    async def test_asgi_routes_status_health_and_webhook(self) -> None:
        secure = NamespacedSecureStore()
        path = f"{tempfile.gettempdir()}/unigate-test-{uuid4().hex}.db"
        stores = SQLiteStores(path)
        exchange = Exchange(stores, stores, stores, stores)
        adapter = InternalAdapter("inst", secure.for_instance("inst"), exchange)
        exchange.register_instance("inst", adapter)
        app = UnigateASGIApp(exchange, mount_prefix="/api")

        async def call(path: str, method: str, payload: dict[str, object] | None = None) -> tuple[int, dict[str, object]]:
            sent: list[dict[str, object]] = []
            scope = {"type": "http", "path": path, "method": method}
            body = json.dumps(payload or {}).encode("utf-8")
            queue = [{"type": "http.request", "body": body, "more_body": False}]

            async def receive() -> dict[str, object]:
                return queue.pop(0)

            async def send(message: dict[str, object]) -> None:
                sent.append(message)

            await app(scope, receive, send)
            status = int(sent[0]["status"])
            body_bytes = bytes(sent[1]["body"])
            return status, json.loads(body_bytes.decode("utf-8"))

        status_code, status_payload = await call("/api/status", "GET")
        self.assertEqual(status_code, 200)
        self.assertIn("inst", status_payload["instances"])

        health_code, health_payload = await call("/api/health", "GET")
        self.assertEqual(health_code, 200)
        self.assertTrue(bool(health_payload["ok"]))

        webhook_code, webhook_payload = await call(
            "/api/webhook/inst", "POST", {"id": "w1", "session_id": "s1", "sender_id": "u1"}
        )
        self.assertEqual(webhook_code, 200)
        self.assertEqual(webhook_payload["status"], "ack")

    async def test_dead_letter_after_max_attempts(self) -> None:
        secure = NamespacedSecureStore()
        path = f"{tempfile.gettempdir()}/unigate-test-{uuid4().hex}.db"
        stores = SQLiteStores(path)
        exchange = Exchange(stores, stores, stores, stores)
        adapter = InternalAdapter("inst", secure.for_instance("inst"), exchange)
        exchange.register_instance("inst", adapter)
        exchange.set_retry_policy("inst", max_attempts=1, retry_base_seconds=2, retry_max_seconds=30)

        adapter.fail_next_send = True
        outbound = Message(
            id="dead-1",
            session_id="s-dead",
            from_instance="inst",
            sender=Sender(platform_id="bot", name="Bot", is_bot=True),
            ts=datetime.now(UTC),
            to=["inst"],
            text="must dead letter",
        )
        await exchange.enqueue_outbound("inst", outbound)
        await exchange.flush_outbox()
        dead_letters = await stores.list_dead_letters()
        self.assertEqual(len(dead_letters), 1)
        self.assertEqual(dead_letters[0].outbox_id.startswith("dead-1:inst"), True)

    async def test_sqlite_roundtrip_preserves_rich_message_fields(self) -> None:
        path = f"{tempfile.gettempdir()}/unigate-test-{uuid4().hex}.db"
        stores = SQLiteStores(path)
        message = Message(
            id="rich-1",
            session_id="rich-s",
            from_instance="inst",
            sender=Sender(platform_id="sender", name="Sender", handle="@sender"),
            ts=datetime.now(UTC),
            to=["dst"],
            thread_id="th-1",
            group_id="gr-1",
            receiver_id="recv-1",
            text="hello rich",
            media=[MediaRef(media_id="m-1", type=MediaType.IMAGE, filename="photo.png")],
            interactive=Interactive(
                interaction_id="i-1",
                type="confirm",
                prompt="Proceed?",
                fields=[FormField(name="a", label="A", type="text")],
                response=InteractiveResponse(interaction_id="i-1", type="confirm", value="yes"),
            ),
            actions=[Action(type="typing_on", payload={"seconds": 2})],
            reactions=[Reaction(emoji=":thumbs_up:", sender_id="sender", ts=datetime.now(UTC))],
            reply_to_id="prev-1",
            edit_of_id="edit-1",
            deleted_id="del-1",
            stream_id="stream-1",
            is_final=False,
            metadata={"k": "v"},
            raw={"source": "test"},
        )
        from unigate.stores import OutboxRecord

        await stores.put_many(
            [
                OutboxRecord(
                    outbox_id="ob-1",
                    instance_id="inst",
                    destination="dst",
                    message=message,
                    status="pending",
                    attempts=0,
                )
            ]
        )
        due = await stores.due(datetime.now(UTC))
        self.assertEqual(len(due), 1)
        reloaded = due[0].message
        self.assertEqual(reloaded.thread_id, "th-1")
        self.assertEqual(reloaded.media[0].type, MediaType.IMAGE)
        self.assertIsNotNone(reloaded.interactive)
        self.assertEqual(reloaded.actions[0].type, "typing_on")
        self.assertEqual(reloaded.reactions[0].emoji, ":thumbs_up:")
        self.assertFalse(reloaded.is_final)
