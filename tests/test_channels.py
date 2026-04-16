"""Tests for channel adapters."""

from __future__ import annotations

import hashlib
import unittest
from datetime import UTC, datetime
from uuid import uuid4

from unigate import Message, Sender
from unigate.channels import APIKeyWebChannel, BearerTokenWebChannel, TelegramChannel, WebChannel
from unigate.channel import RawRequest, SendResult
from unigate.stores import NamespacedSecureStore


class WebChannelTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = NamespacedSecureStore().for_instance("web-test")
        self.channel = WebChannel(
            instance_id="web-test",
            store=self.store,
            kernel=None,
            config={"webhook_secret": "test-secret"},
        )

    def test_web_channel_to_message(self) -> None:
        raw = {
            "id": "msg-1",
            "session_id": "session-1",
            "sender": {"id": "user-1", "name": "Test User"},
            "text": "Hello from web",
        }
        msg = self.channel.to_message(raw)
        self.assertEqual(msg.id, "msg-1")
        self.assertEqual(msg.text, "Hello from web")
        self.assertEqual(msg.sender.platform_id, "user-1")

    async def test_web_channel_from_message(self) -> None:
        msg = Message(
            id="out-1",
            session_id="session-1",
            from_instance="handler",
            sender=Sender(platform_id="bot", name="Bot"),
            ts=datetime.now(UTC),
            text="Hello",
        )
        result = await self.channel.from_message(msg)
        self.assertTrue(result.success)
        self.assertEqual(len(self.channel._sent), 1)

    async def test_web_channel_verify_signature_valid(self) -> None:
        import hmac
        body = b'{"text":"hello"}'
        secret = self.channel.config["webhook_secret"]
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        request = RawRequest(
            headers={"x-signature": signature},
            body=body,
        )
        result = await self.channel.verify_signature(request)
        self.assertTrue(result)

    async def test_web_channel_verify_signature_invalid(self) -> None:
        request = RawRequest(
            headers={"x-signature": "wrong-signature"},
            body=b'{"text":"hello"}',
        )
        result = await self.channel.verify_signature(request)
        self.assertFalse(result)

    def test_web_channel_capabilities(self) -> None:
        caps = self.channel.capabilities
        self.assertEqual(caps.direction, "bidirectional")
        self.assertTrue(caps.supports_groups)


class BearerTokenWebChannelTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = NamespacedSecureStore().for_instance("bearer-test")
        self.channel = BearerTokenWebChannel(
            instance_id="bearer-test",
            store=self.store,
            kernel=None,
            config={"bearer_token": "my-secret-token"},
        )

    async def test_bearer_verify_valid(self) -> None:
        request = RawRequest(
            headers={"authorization": "Bearer my-secret-token"},
            body=b'{}',
        )
        result = await self.channel.verify_signature(request)
        self.assertTrue(result)

    async def test_bearer_verify_invalid(self) -> None:
        request = RawRequest(
            headers={"authorization": "Bearer wrong-token"},
            body=b'{}',
        )
        result = await self.channel.verify_signature(request)
        self.assertFalse(result)


class APIKeyWebChannelTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = NamespacedSecureStore().for_instance("apikey-test")
        self.channel = APIKeyWebChannel(
            instance_id="apikey-test",
            store=self.store,
            kernel=None,
            config={"api_key": "abc123"},
        )

    async def test_apikey_verify_valid(self) -> None:
        request = RawRequest(
            headers={"x-api-key": "abc123"},
            body=b'{}',
        )
        result = await self.channel.verify_signature(request)
        self.assertTrue(result)

    async def test_apikey_verify_invalid(self) -> None:
        request = RawRequest(
            headers={"x-api-key": "wrong-key"},
            body=b'{}',
        )
        result = await self.channel.verify_signature(request)
        self.assertFalse(result)


class TelegramChannelTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = NamespacedSecureStore().for_instance("telegram-test")
        self.channel = TelegramChannel(
            instance_id="telegram-test",
            store=self.store,
            kernel=None,
            config={"token": "test-token"},
        )

    def test_telegram_to_message(self) -> None:
        raw = {
            "id": "123",
            "session_id": "456",
            "sender": {"id": "789", "name": "John Doe", "username": "johndoe"},
            "text": "Hello from Telegram",
            "group_id": "111",
            "raw": {"message_id": 123},
        }
        msg = self.channel.to_message(raw)
        self.assertEqual(msg.id, "123")
        self.assertEqual(msg.text, "Hello from Telegram")
        self.assertEqual(msg.sender.platform_id, "789")
        self.assertEqual(msg.sender.name, "John Doe")
        self.assertEqual(msg.group_id, "111")

    async def test_telegram_setup_with_config_token(self) -> None:
        result = await self.channel.setup()
        self.assertEqual(result.status.value, "ready")

    async def test_telegram_setup_without_token(self) -> None:
        channel = TelegramChannel(
            instance_id="telegram-no-token",
            store=self.store,
            kernel=None,
            config={},
        )
        result = await channel.setup()
        self.assertEqual(result.status.value, "needs_interaction")

    def test_telegram_capabilities(self) -> None:
        caps = self.channel.capabilities
        self.assertEqual(caps.direction, "bidirectional")
        self.assertTrue(caps.supports_groups)
        self.assertTrue(caps.supports_reactions)
        self.assertTrue(caps.supports_reply_to)


if __name__ == "__main__":
    unittest.main()
