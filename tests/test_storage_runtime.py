from __future__ import annotations

import json
import tempfile
import unittest
from uuid import uuid4
from datetime import UTC, datetime

from unigate import Exchange, InternalAdapter, Message, NamespacedSecureStore, SQLiteStores, Sender
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
