"""Web/Webhook channel adapter for HTTP-based integrations."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from typing import Any
from uuid import uuid4

from ..capabilities import ChannelCapabilities
from ..channel import BaseChannel, RawRequest, SendResult
from ..events import KernelEvent
from ..lifecycle import HealthStatus, SetupResult, SetupStatus
from ..message import Message, Sender
from ..stores import SecureStore


class WebChannelPlugin:
    """Generic HTTP webhook channel (simple plugin version)."""
    
    name = "web"
    type = "channel"
    
    async def receive(self, raw: dict[str, Any]) -> Message | None:
        sender_data = raw.get("sender", {})
        sender = Sender(
            platform_id=str(sender_data.get("id", "anonymous")),
            name=str(sender_data.get("name", "Anonymous")),
            handle=sender_data.get("handle"),
        )
        return Message(
            id=raw.get("id", str(uuid4())),
            session_id=raw.get("session_id", sender.platform_id),
            from_instance=self.name,
            sender=sender,
            ts=raw.get("ts"),
            text=raw.get("text"),
            raw=raw,
        )
    
    async def send(self, msg: Message) -> dict[str, Any] | None:
        return {"text": msg.text}


class WebChannel:
    """Generic HTTP webhook channel with per-instance auth."""

    name = "web"
    transport = "http"
    auth_method = "api_key"

    def __init__(
        self,
        instance_id: str,
        store: SecureStore,
        kernel: Any,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.instance_id = instance_id
        self.store = store
        self.kernel = kernel
        self.config = config or {}
        self._sent: list[Message] = []
        self._started = False

    async def setup(self) -> SetupResult:
        return SetupResult(status=SetupStatus.READY)

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    def to_message(self, raw: dict[str, Any]) -> Message:
        sender_data = raw.get("sender", {})
        if isinstance(sender_data, dict):
            sender = Sender(
                platform_id=str(sender_data.get("id", raw.get("from", "unknown"))),
                name=str(sender_data.get("name", sender_data.get("username", "Unknown"))),
                handle=sender_data.get("username"),
                is_bot=sender_data.get("is_bot", False),
                raw=sender_data,
            )
        else:
            sender = Sender(
                platform_id=str(sender_data),
                name=str(sender_data),
            )
        # Instance-scoped session
        explicit_session = raw.get("session_id")
        if explicit_session:
            session_id = explicit_session
        else:
            session_id = f"{self.instance_id}:{sender.platform_id}"
        
        return Message(
            id=raw.get("id", str(uuid4())),
            session_id=session_id,
            from_instance=self.instance_id,
            sender=sender,
            ts=raw.get("ts"),
            platform_id=raw.get("platform_id", raw.get("message_id")),
            to=[],
            thread_id=raw.get("thread_id"),
            group_id=raw.get("group_id"),
            receiver_id=raw.get("to", self.instance_id),
            bot_mentioned=raw.get("bot_mentioned", True),
            text=raw.get("text", raw.get("message", raw.get("content", ""))),
            raw=raw,
            metadata=raw.get("metadata", {}),
        )

    async def from_message(self, msg: Message) -> SendResult:
        self._sent.append(msg)
        return SendResult(success=True, provider_message_id=f"web:{msg.id}")

    async def verify_signature(self, request: RawRequest) -> bool:
        signature_header = self.config.get("signature_header", "X-Signature")
        secret = self.config.get("webhook_secret")
        if not secret:
            return True
        signature = request.headers.get(signature_header.lower(), request.headers.get(signature_header, ""))
        if not signature:
            return False
        expected = self._compute_signature(request.body, secret)
        return hmac.compare_digest(signature, expected)

    def _compute_signature(self, body: bytes, secret: str) -> str:
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            direction="bidirectional",
            supports_groups=self.config.get("supports_groups", True),
            supports_threads=self.config.get("supports_threads", False),
            supports_reply_to=self.config.get("supports_reply_to", True),
            max_message_length=self.config.get("max_message_length", 4096),
        )

    async def reset_setup(self) -> None:
        pass

    async def health_check(self) -> HealthStatus:
        return HealthStatus.HEALTHY if self._started else HealthStatus.UNKNOWN

    async def background_tasks(self) -> list[object]:
        return []

    async def emit_event(self, event: KernelEvent) -> None:
        if self.kernel:
            await self.kernel.emit_event(event)


class BearerTokenWebChannel(WebChannel):
    """WebChannel with Bearer token authentication."""

    auth_method = "bearer"

    async def verify_signature(self, request: RawRequest) -> bool:
        auth_header = request.headers.get("authorization", "")
        expected_prefix = "Bearer "
        if not auth_header.startswith(expected_prefix):
            return False
        token = auth_header[len(expected_prefix):]
        stored_token = await self.store.get("bearer_token")
        if not stored_token:
            stored_token = self.config.get("bearer_token", "")
        return hmac.compare_digest(token, stored_token)


class APIKeyWebChannel(WebChannel):
    """WebChannel with API key in header."""

    auth_method = "api_key"

    async def verify_signature(self, request: RawRequest) -> bool:
        header_name = self.config.get("api_key_header", "X-API-Key").lower()
        provided_key = request.headers.get(header_name, "")
        stored_key = await self.store.get("api_key")
        if not stored_key:
            stored_key = self.config.get("api_key", "")
        return hmac.compare_digest(provided_key, stored_key)
